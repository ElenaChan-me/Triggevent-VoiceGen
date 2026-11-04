"""台本に無い読み上げの音声を作る。

戦闘中に文が決まる読み上げや、台本を作った後に増えたトリガーの読み上げは、Triggevent Plus が日本語にした文を頼んでくる。
パックの lines フォルダに置き、ファイル名は文のハッシュで、Triggevent Plus の VoicePack.lineId と同じ規則にする。
"""
from __future__ import annotations

import hashlib
import unicodedata

from .script import Item

MAX_LINES = 24
# 戦闘中の読み上げとして十分に長く、誤って長文を頼まれたときは断れる長さ
MAX_CHARS = 120


def line_id(text: str) -> str:
    return "line_" + hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:10]


def items(lines: list[str]) -> list[Item]:
    """文の一覧を検証して、生成する項目にする。不正な文があれば ValueError。"""
    if len(lines) > MAX_LINES:
        raise ValueError(f"一度に作れる読み上げは {MAX_LINES} 件までです。")
    out = {}
    for text in lines:
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"読み上げる文が正しくありません: {text!r}")
        text = text.strip()
        if len(text) > MAX_CHARS:
            raise ValueError(f"読み上げる文が長すぎます（{MAX_CHARS} 文字まで）: {text[:20]}…")
        # 改行などの制御文字は TTS に渡さない
        if any(unicodedata.category(c) == "Cc" for c in text):
            raise ValueError(f"読み上げる文に使えない文字が含まれています: {text!r}")
        out.setdefault(line_id(text), Item(line_id(text), text, "line"))
    return list(out.values())
