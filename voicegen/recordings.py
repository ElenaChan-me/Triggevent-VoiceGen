"""自分で録音した声。TTS の代わりに RVC の入力として使う。

録音は recordings/<セリフID>.wav に、48kHz・16bit・モノラルにそろえて保存する。
このファイルがあるセリフは、VOICEVOX ではなく録音を元に作られる。
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from .audio import AudioError
from .config import Config

ID_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,64}$")
SAMPLE_RATE = 48000


def path_for(cfg: Config, item_id: str) -> Path:
    # ID は URL やコマンドから来るので、フォルダの外を指せない形かを確かめる
    if not ID_PATTERN.fullmatch(item_id):
        raise ValueError(f"セリフ ID の形式が正しくありません: {item_id!r}")
    return cfg.recordings.dir / f"{item_id}.wav"


def exists(cfg: Config, item_id: str) -> bool:
    return path_for(cfg, item_id).is_file()


def digest(cfg: Config, item_id: str) -> str:
    return hashlib.sha256(path_for(cfg, item_id).read_bytes()).hexdigest()[:16]


def save(cfg: Config, item_id: str, source: Path) -> Path:
    """録音ファイル（WAV・WebM・MP3 など ffmpeg が読める形式）を取り込む。"""
    dst = path_for(cfg, item_id)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".tmp.wav")
    cmd = [cfg.post.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
           "-t", str(cfg.recordings.max_seconds), "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(tmp)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise AudioError(f"ffmpeg が見つかりません: {cfg.post.ffmpeg}") from None
    if result.returncode != 0 or not tmp.is_file() or tmp.stat().st_size <= 44:
        tmp.unlink(missing_ok=True)
        raise AudioError(f"録音を読み込めませんでした: {result.stderr.strip()[:300]}")
    tmp.replace(dst)
    return dst


def delete(cfg: Config, item_id: str) -> bool:
    path = path_for(cfg, item_id)
    if path.is_file():
        path.unlink()
        return True
    return False
