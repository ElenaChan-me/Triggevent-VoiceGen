# Triggevent-VoiceGen

Triggevent Plus の読み上げ（コールアウト）を、VOICEVOX で読ませた音声を RVC（Applio）で好きな声に変換して、ボイスパックとして書き出すツールです。

A tool that reads Triggevent Plus callouts with VOICEVOX, converts the voice with RVC (Applio), and writes the result as a voice pack.

## 流れ / How it works

```
台本 (data/script.json) → VOICEVOX で読み上げ → Applio (RVC) で声質変換 → ffmpeg で仕上げ → output/<名前>/
```

- **台本の中身:** 台本は Triggevent Plus の読み上げ文を日本語にしたものです。
  - 名前や方角が入る文は、固定の部分と部品（方角・数字・「自分」）に分かれています。
  - DoT 名とリキャスト名はジョブ別に分かれています。
- **作り直す範囲:** 各段階の結果は `work/` に保存されます。文や設定が変わったセリフだけを作り直します。
- **仕上げ:** 前後の無音を詰め、音量をそろえて、48kHz・16bit・モノラルの WAV にします。
- **manifest.json:** ボイスパックには `manifest.json` が付きます。セリフの ID・ファイル・文・クレジット・生成に使った設定が入っています。

The script is the Japanese version of Triggevent Plus's callouts. Each stage is cached under `work/`, and only lines whose text or settings changed are regenerated. Output files are 48 kHz, 16-bit, mono WAV with a `manifest.json`.

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

配布用の zip（`voicepack-<名前>.zip`、XIVToolHub でインストールできる形）は `python -m voicegen package dist` で作ります。プレイヤー名の音声（`names`）は入れません。

`python -m voicegen package dist` builds the distributable zip (`voicepack-<name>.zip`) that XIVToolHub can install. Player name clips are not included.

### プレイヤー名 / Player names

`python -m voicegen names "Lily Tayler"` で、パックの `names` フォルダに名前の音声を作ります（読むのは名だけです）。`python -m voicegen ui` を起動している間は、Triggevent Plus の設定で有効にすると、パーティが変わったときに自動で頼まれます（`/api/names`、127.0.0.1 のみ）。

`python -m voicegen names "Lily Tayler"` creates name clips in the pack's `names` folder (first name only). While `ui` is running, Triggevent Plus can request them automatically via `/api/names` (127.0.0.1 only).

## 自分の声で直す / Fixing lines with your own voice

TTS の読み方がおかしいセリフは、自分で読んだ声を RVC に通して差し替えられます。録音があるセリフは、VOICEVOX の代わりに録音が使われます。

1. 録音スタジオの画面を開きます（ブラウザで `http://127.0.0.1:8765` が開きます）。
   ```powershell
   python -m voicegen ui
   ```
2. セリフを検索し、「● 録音」で読み上げて「■ 停止」で止めます（Esc でも止まります）。
   - 「録音後に作り直す」がオンなら、そのまま RVC にかけて仕上がりを再生します。
   - 「▶ TTS」「▶ 録音」「▶ 仕上がり」で聞き比べられます。
   - 「録音を消す」で VOICEVOX に戻せます。
3. 声の高さが VOICEVOX の話者と違う場合は、`[recordings] pitch` で録音だけ RVC の pitch を変えられます。

録音は `recordings/<セリフID>.wav` に保存されます（Git には入りません）。ほかのソフトで録音したファイルは、コマンドでも取り込めます。

```powershell
python -m voicegen find 全体攻撃                  # ID を調べる
python -m voicegen record L_402ac15b 録音.wav      # 取り込む
python -m voicegen generate --only L_402ac15b      # 作り直す
python -m voicegen record L_402ac15b --delete      # 録音を消して TTS に戻す
```

Lines that TTS reads badly can be replaced with your own recording, which is then converted with RVC. Run `python -m voicegen ui` to open a local recording studio in the browser (only reachable from this PC), or import files with `record`. Recordings are stored in `recordings/` and are not committed.

Copy `config.example.toml` to `config.toml`, pick a VOICEVOX style with `speakers`, check the selection with `list`, try a few lines with `generate --limit 10`, then enable RVC and run `generate`.

## 話し方を変えたパック / Packs with a different speaking style

同じ台本から、雰囲気の違うパックを作れます（例: 本気用の `mia` と、かわいい話し方の `mia-cute`）。設定ファイルをパックごとに分け、`--config` で選んで生成します。

- `[style] file` で語尾の書き換え規則を指定します。`data/styles/cute.toml` は「全体攻撃くるよー」「散開してね」「塔を避けてね」のように語尾を変えます。
  - 語尾を付けるのは読み上げの最後になる部分だけで、方角などの部品はそのまま使います。
  - 最後が方角などで終わる読み上げには、語尾だけの音声（「だよー」）を後ろにつなげます。
- `[voicevox] end_rise` で文末を少し上げ、`[post] extra_filter` で声の質感（柔らかさ・響き）を変えられます。
- パックごとに `[paths] work` と `[recordings] dir` を分けてください。分けないと、作業ファイルや録音が混ざります。

```powershell
python -m voicegen --config config.cute.toml generate
```

できたパックを同じフォルダ（`output/`）に並べておくと、Triggevent Plus の「ボイスパック」タブで切り替えられます。

You can build several packs with different speaking styles from the same script by keeping one config file per pack and choosing it with `--config`. `[style] file` points to sentence-ending rules (see `data/styles/cute.toml`). Endings are added only to the part that ends a callout, and callouts that end with a direction get a short ending clip appended. `[voicevox] end_rise` raises the pitch at the end of sentences, and `[post] extra_filter` adds an ffmpeg filter to change the voice texture. Use a separate `work` and `recordings` folder for each pack. Packs placed side by side in `output/` can be switched from Triggevent Plus's Voice Pack tab.

## 台本の作り直し / Rebuilding the script

台本は `tools/script_builder/` のスクリプトで作ります（`data/source` で実行します）。

- **`extract.py`:** Triggevent Plus のソースから読み上げ文を抜き出します。
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
