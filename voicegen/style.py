"""話し方のスタイル。セリフの語尾を書き換えて、同じ台本から雰囲気の違うボイスパックを作る。

語尾を付けるのは「そこで読み上げが終わる」ものだけにする。
テンプレートの途中に入る部品（方角・選択肢・途中の文字）は変えない。
最後が固定の文字のテンプレートは、その文字に語尾を付けた別のファイル（ID の末尾に _e）を作る。
最後が可変部分（方角など）のテンプレートは、後ろに語尾だけのファイル（tail）をつなげる。
"""
from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

# 語尾を付けた部品の ID に付ける印
ENDING_SUFFIX = "_e"
TAIL_ID = "E_tail"
# 語尾を付けられる種類。セリフの最後になる部品は line として扱う
KINDS = {"line", "dot", "cd", "system"}


class StyleError(Exception):
    pass


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern
    replace: tuple[str, ...]
    kinds: frozenset[str]


@dataclass(frozen=True)
class Style:
    name: str
    rules: tuple[Rule, ...]
    # 最後が可変部分のテンプレートの後ろに足す言葉
    tail: str
    # すでに語尾が付いているものは書き換えない
    skip: re.Pattern | None

    def ending(self, text: str, kind: str) -> str:
        if kind not in KINDS or (self.skip and self.skip.search(text)):
            return text
        for rule in self.rules:
            if kind not in rule.kinds:
                continue
            m = rule.pattern.search(text)
            if not m:
                continue
            # 同じ語尾ばかりにならないよう、候補が複数あるときは文ごとに決まった1つを選ぶ
            replace = rule.replace[int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % len(rule.replace)]
            return text[:m.start()] + m.expand(replace) + text[m.end():]
        return text

    def terminal(self, part_id: str, text: str) -> tuple[str, str]:
        """セリフの最後に来る部品の ID と文。語尾が変わらなければ元の部品をそのまま使う。"""
        ended = self.ending(text, "line")
        return (part_id, text) if ended == text else (part_id + ENDING_SUFFIX, ended)


def load(path: Path) -> Style:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise StyleError(f"スタイルのファイルが見つかりません: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise StyleError(f"スタイルのファイルの書式が正しくありません（{path.name}）: {e}") from None

    rules = []
    for n, r in enumerate(raw.get("rules", []), 1):
        if not isinstance(r, dict) or not isinstance(r.get("match"), str):
            raise StyleError(f"rules の {n} 番目に match（正規表現）がありません。")
        replace = r.get("replace", "")
        replace = [replace] if isinstance(replace, str) else replace
        if not replace or not all(isinstance(x, str) for x in replace):
            raise StyleError(f"rules の {n} 番目の replace は文字列か文字列の配列で指定してください。")
        kinds = r.get("kinds", ["line"])
        if not isinstance(kinds, list) or not kinds or not set(kinds) <= KINDS:
            raise StyleError(f"rules の {n} 番目の kinds は {sorted(KINDS)} から選んでください: {kinds!r}")
        try:
            pattern = re.compile(r["match"])
        except re.error as e:
            raise StyleError(f"rules の {n} 番目の正規表現が正しくありません: {e}") from None
        # 置き換え文の \1 などが正しいかを、生成の途中ではなく読み込むときに確かめておく
        for x in replace:
            _check_groups(x, pattern.groups)
        rules.append(Rule(pattern, tuple(replace), frozenset(kinds)))

    skip = raw.get("skip", "")
    try:
        skip_pattern = re.compile(skip) if skip else None
    except re.error as e:
        raise StyleError(f"skip の正規表現が正しくありません: {e}") from None
    tail = raw.get("tail", "")
    if not isinstance(tail, str):
        raise StyleError("tail は文字列で指定してください。")
    return Style(name=str(raw.get("name", path.stem)), rules=tuple(rules), tail=tail, skip=skip_pattern)


def _check_groups(replace: str, groups: int) -> None:
    for m in re.finditer(r"\\(\d+)|\\g<(\d+)>", replace):
        if int(m.group(1) or m.group(2)) > groups:
            raise StyleError(f"置き換え文の {m.group(0)} に当たるグループが match にありません: {replace!r}")
