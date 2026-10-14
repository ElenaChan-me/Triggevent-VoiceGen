"""コマンドライン。

    python -m voicegen speakers              VOICEVOX の話者とスタイル ID を表示
    python -m voicegen list                  生成対象のセリフ数を表示
    python -m voicegen generate              TTS → RVC → 仕上げ → manifest.json
    python -m voicegen generate --stage tts  指定した段階だけ実行（tts / rvc / post）
    python -m voicegen generate --only L_1a2b3c4d S_...   一部のセリフだけ作る（試聴用）
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

from . import applio, audio, config, script, voicevox
from .pipeline import Pipeline


def _items(cfg: config.Config, only: list[str] | None, limit: int | None) -> list[script.Item]:
    items = script.select(script.load(cfg.script), cfg.select)
    if only:
        wanted = set(only)
        unknown = wanted - {i.id for i in items}
        if unknown:
            raise config.ConfigError(f"選択中の台本に無い ID です: {', '.join(sorted(unknown))}")
        items = [i for i in items if i.id in wanted]
    if limit is not None:
        items = items[:limit]
    return items


def cmd_speakers(cfg: config.Config, args) -> None:
    with voicevox.Engine(cfg.voicevox) as client:
        for sp in client.speakers():
            styles = "、".join(f"{st['name']}={st['id']}" for st in sp["styles"])
            print(f"{sp['name']}: {styles}")


def cmd_list(cfg: config.Config, args) -> None:
    items = _items(cfg, None, None)
    counts = collections.Counter(i.kind for i in items)
    print(f"{len(items)} 件: " + "、".join(f"{k} {v}" for k, v in counts.most_common()))


def cmd_generate(cfg: config.Config, args) -> None:
    items = _items(cfg, args.only, args.limit)
    pipe = Pipeline(cfg)
    stages = [args.stage] if args.stage else ["tts", "rvc", "post"]
    if "tts" in stages:
        pipe.run_tts(items)
    if "rvc" in stages:
        pipe.run_rvc(items)
    if "post" in stages:
        pipe.run_post(items)
        path = pipe.write_manifest(items)
        print(f"ボイスパック: {path.parent}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="voicegen", description="Triggevent JP のボイスパックを作る")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="設定ファイル（既定: config.toml）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("speakers", help="VOICEVOX の話者とスタイル ID を表示")
    sub.add_parser("list", help="生成対象のセリフ数を表示")
    gen = sub.add_parser("generate", help="音声を生成する")
    gen.add_argument("--stage", choices=["tts", "rvc", "post"], help="指定した段階だけ実行する")
    gen.add_argument("--only", nargs="+", metavar="ID", help="指定した ID のセリフだけ作る")
    gen.add_argument("--limit", type=int, help="先頭から指定した件数だけ作る")
    args = parser.parse_args(argv)

    try:
        cfg = config.load(args.config)
        {"speakers": cmd_speakers, "list": cmd_list, "generate": cmd_generate}[args.command](cfg, args)
    except (config.ConfigError, voicevox.VoicevoxError, applio.RvcError, audio.AudioError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
