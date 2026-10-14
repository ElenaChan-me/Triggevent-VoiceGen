"""ffmpeg での仕上げ。前後の無音を詰め、音量をそろえて、48kHz・16bit・モノラルの WAV にする。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Post


class AudioError(Exception):
    pass


def filter_chain(cfg: Post) -> str:
    trim = f"silenceremove=start_periods=1:start_threshold={cfg.trim_db}dB:start_silence=0.01"
    pad = cfg.pad_ms / 1000
    return ",".join([
        # 先頭の無音を詰め、反転してもう一度詰めることで末尾の無音も詰める
        trim, "areverse", trim, "areverse",
        f"loudnorm=I={cfg.loudness}:TP={cfg.true_peak}:LRA=11",
        f"adelay={cfg.pad_ms}:all=1",
        f"apad=pad_dur={pad}",
        f"aresample={cfg.sample_rate}",
    ])


def build_command(cfg: Post, src: Path, dst: Path) -> list[str]:
    return [cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
            "-af", filter_chain(cfg), "-ac", "1", "-ar", str(cfg.sample_rate), "-c:a", "pcm_s16le", str(dst)]


def finish(cfg: Post, src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(build_command(cfg, src, dst), capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise AudioError(f"ffmpeg が見つかりません: {cfg.ffmpeg}") from None
    if result.returncode != 0:
        raise AudioError(f"ffmpeg の処理に失敗しました（{src.name}）: {result.stderr.strip()[:300]}")
