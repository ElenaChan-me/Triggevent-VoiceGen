"""ボイスパックを配布用の zip にする。

XIVToolHub は zip を展開したフォルダの manifest.json を目印にするので、manifest.json を zip の一番上に置く。
プレイヤー名の音声（names）は使う人ごとに違うので入れない。
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .config import Config, ConfigError

# zip に入れるもの。これ以外（作業中の一時ファイルなど）は入れない
INCLUDE_SUFFIXES = {".wav", ".json"}
CREDITS_FILE = "CREDITS.txt"


def asset_name(pack: str) -> str:
    return f"voicepack-{pack}.zip"


def build(cfg: Config, out_dir: Path) -> Path:
    pack_dir = cfg.output / cfg.pack.name
    manifest = pack_dir / "manifest.json"
    if not manifest.is_file():
        raise ConfigError(f"{manifest} がありません。先に generate でパックを作ってください。")
    entries = json.loads(manifest.read_text(encoding="utf-8")).get("entries", {})
    missing = [i for i, e in entries.items() if not (pack_dir / e.get("file", "")).is_file()]
    if missing:
        raise ConfigError(f"manifest.json にあるのに音声が無いものがあります（{len(missing)} 件、例: {missing[0]}）。generate をやり直してください。")

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / asset_name(cfg.pack.name)
    tmp = out.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        for path in sorted(pack_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in INCLUDE_SUFFIXES:
                continue
            # wav はほとんど縮まないので圧縮しない（展開が速くなる）
            compress = zipfile.ZIP_STORED if path.suffix.lower() == ".wav" else zipfile.ZIP_DEFLATED
            z.write(path, path.name, compress_type=compress)
        credits = f"{cfg.pack.name}\n{cfg.pack.credit}\n" if cfg.pack.credit else f"{cfg.pack.name}\n"
        z.writestr(CREDITS_FILE, credits, compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(out)
    return out
