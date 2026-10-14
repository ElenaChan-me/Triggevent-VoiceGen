"""Applio（RVC）での声質変換。フォルダ単位でまとめて変換し、モデルの読み込みを1回で済ませる。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Rvc


class RvcError(Exception):
    pass


def python_path(cfg: Rvc) -> Path:
    return cfg.applio / ".venv" / "Scripts" / "python.exe"


def output_name(input_name: str) -> str:
    """Applio の一括変換が付ける出力ファイル名。"""
    return Path(input_name).stem + "_output.wav"


def build_command(cfg: Rvc, input_dir: Path, output_dir: Path) -> list[str]:
    cmd = [
        str(python_path(cfg)), "core.py", "batch_infer",
        "--input-folder", str(input_dir),
        "--output-folder", str(output_dir),
        "--pth-path", str(cfg.model),
        # index を使わない場合も Applio は引数を必須にしているので空文字を渡す
        "--index-path", str(cfg.index) if cfg.index else "",
        "--pitch", str(cfg.pitch),
        "--index-rate", str(cfg.index_rate if cfg.index else 0.0),
        "--protect", str(cfg.protect),
        "--f0-method", cfg.f0_method,
        "--volume-envelope", str(cfg.volume_envelope),
        "--embedder-model", cfg.embedder,
        "--export-format", "WAV",
    ]
    return cmd + list(cfg.extra_args)


def check(cfg: Rvc) -> None:
    if not python_path(cfg).is_file():
        raise RvcError(f"Applio の Python が見つかりません: {python_path(cfg)}")
    if not (cfg.applio / "core.py").is_file():
        raise RvcError(f"Applio の core.py が見つかりません: {cfg.applio}")
    if cfg.model is None or not cfg.model.is_file():
        raise RvcError(f"RVC のモデル（.pth）が見つかりません: {cfg.model}")
    if cfg.index is not None and not cfg.index.is_file():
        raise RvcError(f"RVC の index ファイルが見つかりません: {cfg.index}")


def convert(cfg: Rvc, input_dir: Path, output_dir: Path, log_path: Path) -> None:
    check(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as log:
        result = subprocess.run(build_command(cfg, input_dir, output_dir), cwd=str(cfg.applio),
                                stdout=log, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        raise RvcError(f"Applio の変換が失敗しました（終了コード {result.returncode}）。ログ: {log_path}")
