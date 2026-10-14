# Triggevent-VoiceGen

Triggevent JP の読み上げ（コールアウト）を、VOICEVOX で読ませた音声を RVC（Applio）で好きな声に変換して、ボイスパックとして書き出すツールです。

A tool that reads Triggevent JP callouts with VOICEVOX, converts the voice with RVC (Applio), and writes the result as a voice pack.

## 流れ / How it works

```
台本 (data/script.json) → VOICEVOX で読み上げ → Applio (RVC) で声質変換 → ffmpeg で仕上げ → output/<名前>/
```

- **台本の中身:** 台本は Triggevent JP の読み上げ文を日本語にしたものです。
  - 名前や方角が入る文は、固定の部分と部品（方角・数字・「自分」）に分かれています。
  - DoT 名とリキャスト名はジョブ別に分かれています。
- **作り直す範囲:** 各段階の結果は `work/` に保存されます。文や設定が変わったセリフだけを作り直します。
- **仕上げ:** 前後の無音を詰め、音量をそろえて、48kHz・16bit・モノラルの WAV にします。
- **manifest.json:** ボイスパックには `manifest.json` が付きます。セリフの ID・ファイル・文・クレジット・生成に使った設定が入っています。

The script is the Japanese version of Triggevent JP's callouts. Each stage is cached under `work/`, and only lines whose text or settings changed are regenerated. Output files are 48 kHz, 16-bit, mono WAV with a `manifest.json`.

## 必要なもの / Requirements

- Python 3.11 以降（ツール本体は標準ライブラリだけで動きます）
- ffmpeg
- [VOICEVOX ENGINE](https://github.com/VOICEVOX/voicevox_engine)（`config.toml` の `engine` にパスを書くと、自動で起動・終了します）
- [Applio](https://github.com/IAHispano/Applio)（RVC を使う場合）と、RVC モデル（`.pth`、あれば `.index`）

この PC では、ツールを `D:\VoiceGenTools` に置いています。

| ツール | 場所 | 補足 |
| --- | --- | --- |
| Applio 3.6.5 | `D:\VoiceGenTools\Applio` | Python 3.12 と PyTorch 2.11（CUDA 12.8）の仮想環境 `.venv`。RTX 50 シリーズに対応 |
| VOICEVOX ENGINE 0.25.2（CPU 版） | `D:\VoiceGenTools\voicevox_engine\windows-cpu` | |

## 使い方 / Usage

1. 設定ファイルを用意します。
   ```powershell
   Copy-Item config.example.toml config.toml
   ```
2. 話者を選びます。表示されたスタイル ID を `[voicevox] speaker` に書きます。
   ```powershell
   python -m voicegen speakers
   ```
3. 生成対象を確認します（`[select]` でコンテンツ・ジョブを絞り込めます）。
   ```powershell
   python -m voicegen list
   ```
4. 数件だけ作って試聴します。
   ```powershell
   python -m voicegen generate --limit 10
   ```
5. RVC モデルを `models/` に置き、`[rvc] enabled = true` にしてパラメーターを設定します。そのうえで全件を生成します。
   ```powershell
   python -m voicegen generate
   ```

段階を指定して実行することもできます（`--stage tts` / `rvc` / `post`）。特定のセリフだけ作るときは `--only <ID>` を使います。

Copy `config.example.toml` to `config.toml`, pick a VOICEVOX style with `speakers`, check the selection with `list`, try a few lines with `generate --limit 10`, then enable RVC and run `generate`.

## 台本の作り直し / Rebuilding the script

台本は `tools/script_builder/` のスクリプトで作ります（`data/source` で実行します）。

- **`extract.py`:** Triggevent JP のソースから読み上げ文を抜き出します。
- **`names.py` / `jobs.py`:** DoT・リキャストの日本語名と、使うジョブをゲームデータ（XIVAPI）から取得します。
- **`build.py`:** 翻訳（`translated*.json`）と組み合わせて `data/script.json` を作ります。
- **`render_page.py`:** 収録・確認用の HTML ページを作ります。

## テスト / Tests

```powershell
python -m unittest discover -s tests
```

VOICEVOX は偽のサーバーで代用するので、エンジンが無くても実行できます。仕上げのテストには ffmpeg が必要です。

## 権利について / Licensing

- **VOICEVOX:** 話者（キャラクター）ごとに利用規約があります。多くは「VOICEVOX:話者名」のクレジット表記が必要です。生成した音声を使う前に、各話者の規約を確認してください。
- **RVC モデル:** 声の持ち主とモデル作者から利用の許可を得たモデルだけを使ってください。実在の人物の声を本人の許可なく使わないでください。
- **クレジット表記:** `[pack] credit` に書いた内容は `manifest.json` に入ります。

Each VOICEVOX speaker has its own terms (most require a "VOICEVOX:speaker" credit). Only use RVC models you have permission to use, and never imitate a real person's voice without their consent.
