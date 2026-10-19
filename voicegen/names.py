"""プレイヤー名の音声を作る。

台本に無いプレイヤー名は、Triggevent Plus から頼まれたときに作り、パックの names フォルダに置く。
ファイル名は名前のハッシュで、Triggevent Plus の VoicePack.nameId と同じ規則にする。
"""
from __future__ import annotations

import hashlib
import re

from .script import Item

# FF14 のキャラクター名は英字・アポストロフィ・ハイフンの姓と名
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z'\-]{0,19}(?: [A-Za-z][A-Za-z'\-]{0,19})?$")
MAX_NAMES = 24


def name_id(name: str) -> str:
    return "name_" + hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:10]


def spoken(name: str) -> str:
    """読み上げる部分。日本のプレイヤーは名で呼ぶことが多いので、姓は読まない。"""
    return name.strip().split(" ")[0]


def items(names: list[str]) -> list[Item]:
    """名前の一覧を検証して、生成する項目にする。不正な名前があれば ValueError。"""
    if len(names) > MAX_NAMES:
        raise ValueError(f"一度に作れる名前は {MAX_NAMES} 件までです。")
    out = {}
    for n in names:
        if not isinstance(n, str) or not NAME_PATTERN.match(n.strip()):
            raise ValueError(f"キャラクター名として正しくありません: {n!r}")
        out.setdefault(name_id(n), Item(name_id(n), spoken(n), "name"))
    return list(out.values())
