"""コマンドライン。

    python -m voicegen speakers              VOICEVOX の話者とスタイル ID を表示
    python -m voicegen list                  生成対象のセリフ数を表示
    python -m voicegen generate              TTS → RVC → 仕上げ → manifest.json
    python -m voicegen generate --stage tts  指定した段階だけ実行（tts / rvc / post）
    python -m voicegen generate --only L_1a2b3c4d S_...   一部のセリフだけ作る（試聴用）
    python -m voicegen find 散開              セリフを検索して ID を表示
    python -m voicegen ui                    セリフを選んで自分の声を録音・作り直す画面を開く
    python -m voicegen record L_1a2b3c4d 録音.wav   録音ファイルを取り込む（TTS の代わりに使う）
    python -m voicegen record L_1a2b3c4d --delete  録音を消して TTS に戻す
    python -m voicegen names "Lily Tayler" ...    プレイヤー名の音声を作る（Triggevent Plus は ui のサーバーに自動で頼む）
    python -m voicegen export-mapping callouts-ja.json  画面表示の日本語化に使う対応表を書き出す（Triggevent Plus に同梱する）
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

from . import applio, audio, config, mapping, names, recordings, script, server, voicevox
from .pipeline import Pipeline


def _items(cfg: config.Config, only: list[str] | None, limit: int | None) -> list[script.Item]:
    items = script.select(script.load(cfg.script), cfg.select, cfg.style)
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


def cmd_find(cfg: config.Config, args) -> None:
    pipe = Pipeline(cfg)
    words = args.text.lower()
    hits = [i for i in _items(cfg, None, None) if words in i.text.lower() or words in i.id.lower()]
    for item in hits[:args.max]:
        source = "録音" if pipe.uses_recording(item) else "TTS"
        print(f"{item.id}	{source}	{item.text}")
    if len(hits) > args.max:
        print(f"…ほか {len(hits) - args.max} 件（--max で表示件数を増やせます）")


def cmd_record(cfg: config.Config, args) -> None:
    item = next((i for i in _items(cfg, None, None) if i.id == args.id), None)
    if item is None:
        raise config.ConfigError(f"選択中の台本に無い ID です: {args.id}")
    if args.delete:
        print("録音を消しました。" if recordings.delete(cfg, item.id) else "録音はありませんでした。")
        return
    if args.file is None:
        raise config.ConfigError("取り込む録音ファイルを指定してください（または --delete）。")
    path = recordings.save(cfg, item.id, args.file)
    print(f"「{item.text}」の録音を取り込みました: {path}")
    print(f"作り直すには: python -m voicegen generate --only {item.id}")


def cmd_names(cfg: config.Config, args) -> None:
    items = names.items(args.names)
    pipe = Pipeline(cfg, subdir="names")
    pipe.run_all(items)
    for n, item in zip(args.names, items):
        print(f"{n}	{item.id}	{item.text}")


def cmd_export_mapping(cfg: config.Config, args) -> None:
    # 語尾のスタイルは付けない。画面表示とパックが無いときの読み上げに使う、素の日本語の対応表
    data = mapping.build(script.load(cfg.script))
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{args.out}（{len(data['static']) + len(data['names']) + len(data['templates'])} 件）")


def cmd_ui(cfg: config.Config, args) -> None:
    server.serve(cfg, args.port, open_browser=not args.no_browser)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="voicegen", description="Triggevent Plus のボイスパックを作る")
    parser.add_argument("--config", type=Path, default=Path("config.toml"), help="設定ファイル（既定: config.toml）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("speakers", help="VOICEVOX の話者とスタイル ID を表示")
    sub.add_parser("list", help="生成対象のセリフ数を表示")
    gen = sub.add_parser("generate", help="音声を生成する")
    gen.add_argument("--stage", choices=["tts", "rvc", "post"], help="指定した段階だけ実行する")
    gen.add_argument("--only", nargs="+", metavar="ID", help="指定した ID のセリフだけ作る")
    gen.add_argument("--limit", type=int, help="先頭から指定した件数だけ作る")
    find = sub.add_parser("find", help="セリフを検索して ID を表示")
    find.add_argument("text", help="セリフや ID の一部")
    find.add_argument("--max", type=int, default=50, help="表示する件数（既定: 50）")
    rec = sub.add_parser("record", help="自分の録音を取り込む（TTS の代わりに RVC に通す）")
    rec.add_argument("id", help="セリフ ID")
    rec.add_argument("file", nargs="?", type=Path, help="録音ファイル（WAV・MP3・WebM など）")
    rec.add_argument("--delete", action="store_true", help="録音を消して TTS に戻す")
    nm = sub.add_parser("names", help="プレイヤー名の音声を作る")
    nm.add_argument("names", nargs="+", help="キャラクター名（例: \"Lily Tayler\"）")
    exp = sub.add_parser("export-mapping", help="画面表示の日本語化に使う対応表を書き出す")
    exp.add_argument("out", type=Path, help="書き出すファイル")
    ui = sub.add_parser("ui", help="セリフを選んで録音・作り直しをする画面を開く")
    ui.add_argument("--port", type=int, default=8765, help="待ち受けるポート（既定: 8765。0 なら空いているポート）")
    ui.add_argument("--no-browser", action="store_true", help="ブラウザを自動で開かない")
    args = parser.parse_args(argv)

    try:
        cfg = config.load(args.config)
        commands = {"speakers": cmd_speakers, "list": cmd_list, "generate": cmd_generate,
                    "find": cmd_find, "record": cmd_record, "ui": cmd_ui,
                    "export-mapping": cmd_export_mapping, "names": cmd_names}
        commands[args.command](cfg, args)
    except (config.ConfigError, voicevox.VoicevoxError, applio.RvcError, audio.AudioError, ValueError, OSError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
