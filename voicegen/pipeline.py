"""台本のセリフを TTS → RVC → 仕上げの順に処理し、ボイスパックにまとめる。

各段階の結果は work/ に保存し、文や設定が変わったものだけを作り直す。
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import __version__, applio, audio, voicevox
from .config import Config
from .script import Item, apply_readings

MANIFEST_FORMAT = 1


def _key(*parts) -> str:
    data = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def _read_key(meta: Path) -> str | None:
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("key")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_key(meta: Path, key: str, **extra) -> None:
    meta.write_text(json.dumps({"key": key, **extra}, ensure_ascii=False), encoding="utf-8")


def _model_stamp(path: Path | None) -> list:
    # モデルを差し替えたら作り直したいので、サイズと更新日時も鍵に含める
    if path is None or not path.is_file():
        return [None]
    st = path.stat()
    return [path.name, st.st_size, int(st.st_mtime)]


class Pipeline:
    def __init__(self, cfg: Config, log: Callable[[str], None] = print):
        self.cfg = cfg
        self.log = log
        self.tts_dir = cfg.work / "tts"
        self.rvc_dir = cfg.work / "rvc"
        self.post_dir = cfg.work / "post"
        self.pack_dir = cfg.output / cfg.pack.name

    # 各段階の鍵。前の段階の鍵を含めるので、上流が変わると下流も作り直される
    def tts_key(self, item: Item) -> str:
        return _key("tts", apply_readings(item.text, self.cfg.readings), asdict(self.cfg.voicevox) | {"engine": None})

    def rvc_key(self, item: Item) -> str:
        rvc = asdict(self.cfg.rvc) | {"applio": None, "model": _model_stamp(self.cfg.rvc.model), "index": _model_stamp(self.cfg.rvc.index)}
        return _key("rvc", self.tts_key(item), rvc)

    def post_key(self, item: Item) -> str:
        upstream = self.rvc_key(item) if self.cfg.rvc.enabled else self.tts_key(item)
        return _key("post", upstream, asdict(self.cfg.post) | {"ffmpeg": None})

    def run_tts(self, items: list[Item]) -> int:
        self.tts_dir.mkdir(parents=True, exist_ok=True)
        todo = [i for i in items if _read_key(self.tts_dir / f"{i.id}.json") != self.tts_key(i) or not (self.tts_dir / f"{i.id}.wav").is_file()]
        self.log(f"TTS: {len(todo)} / {len(items)} 件を合成します")
        if not todo:
            return 0
        with voicevox.Engine(self.cfg.voicevox) as client:
            for n, item in enumerate(todo, 1):
                text = apply_readings(item.text, self.cfg.readings)
                wav = client.synthesize(text, self.cfg.voicevox)
                tmp = self.tts_dir / f"{item.id}.wav.tmp"
                tmp.write_bytes(wav)
                tmp.replace(self.tts_dir / f"{item.id}.wav")
                _write_key(self.tts_dir / f"{item.id}.json", self.tts_key(item), text=text)
                if n % 50 == 0 or n == len(todo):
                    self.log(f"  {n} / {len(todo)}")
        return len(todo)

    def run_rvc(self, items: list[Item]) -> int:
        if not self.cfg.rvc.enabled:
            self.log("RVC: 無効のためスキップします（[rvc] enabled = false）")
            return 0
        self.rvc_dir.mkdir(parents=True, exist_ok=True)
        todo = [i for i in items if _read_key(self.rvc_dir / f"{i.id}.json") != self.rvc_key(i) or not (self.rvc_dir / f"{i.id}.wav").is_file()]
        self.log(f"RVC: {len(todo)} / {len(items)} 件を変換します")
        if not todo:
            return 0
        applio.check(self.cfg.rvc)
        batch_in = self.cfg.work / "rvc_batch_in"
        batch_out = self.cfg.work / "rvc_batch_out"
        for d in (batch_in, batch_out):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
        for item in todo:
            src = self.tts_dir / f"{item.id}.wav"
            if not src.is_file():
                raise applio.RvcError(f"TTS の音声がありません。先に tts を実行してください: {item.id}")
            shutil.copyfile(src, batch_in / src.name)
        applio.convert(self.cfg.rvc, batch_in, batch_out, self.cfg.work / "rvc.log")
        missing = []
        for item in todo:
            out = batch_out / applio.output_name(f"{item.id}.wav")
            if not out.is_file():
                missing.append(item.id)
                continue
            out.replace(self.rvc_dir / f"{item.id}.wav")
            _write_key(self.rvc_dir / f"{item.id}.json", self.rvc_key(item))
        if missing:
            # Applio は1件の失敗では止まらないので、出力がそろっているかをここで確かめる
            raise applio.RvcError(f"{len(missing)} 件が変換されませんでした（例: {', '.join(missing[:5])}）。ログ: {self.cfg.work / 'rvc.log'}")
        return len(todo)

    def run_post(self, items: list[Item]) -> int:
        self.post_dir.mkdir(parents=True, exist_ok=True)
        src_dir = self.rvc_dir if self.cfg.rvc.enabled else self.tts_dir
        todo = [i for i in items if _read_key(self.post_dir / f"{i.id}.json") != self.post_key(i) or not (self.pack_dir / f"{i.id}.wav").is_file()]
        self.log(f"仕上げ: {len(todo)} / {len(items)} 件を処理します")
        for n, item in enumerate(todo, 1):
            src = src_dir / f"{item.id}.wav"
            if not src.is_file():
                raise audio.AudioError(f"前の段階の音声がありません: {src}")
            audio.finish(self.cfg.post, src, self.pack_dir / f"{item.id}.wav")
            _write_key(self.post_dir / f"{item.id}.json", self.post_key(item))
            if n % 100 == 0 or n == len(todo):
                self.log(f"  {n} / {len(todo)}")
        return len(todo)

    def write_manifest(self, items: list[Item]) -> Path:
        entries = {i.id: {"file": f"{i.id}.wav", "text": i.text, "kind": i.kind}
                   for i in items if (self.pack_dir / f"{i.id}.wav").is_file()}
        rvc = None
        if self.cfg.rvc.enabled:
            rvc = {k: v for k, v in asdict(self.cfg.rvc).items() if k not in ("applio", "enabled", "extra_args")}
            rvc["model"] = self.cfg.rvc.model.name if self.cfg.rvc.model else None
            rvc["index"] = self.cfg.rvc.index.name if self.cfg.rvc.index else None
        manifest = {
            "format": MANIFEST_FORMAT,
            "name": self.cfg.pack.name,
            "credit": self.cfg.pack.credit,
            "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "generator": {
                "voicegen": __version__,
                "voicevox": {k: v for k, v in asdict(self.cfg.voicevox).items() if k not in ("url", "engine")},
                "rvc": rvc,
            },
            "entries": entries,
        }
        self.pack_dir.mkdir(parents=True, exist_ok=True)
        path = self.pack_dir / "manifest.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        return path
