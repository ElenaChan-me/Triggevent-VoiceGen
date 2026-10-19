"""Triggevent が読み上げ文（英語）から収録音声を探すための対応表（callouts.json）を作る。

Triggevent の読み上げは、名前や方角を埋め込んだあとの英語の文として届く。
台本の英語のテンプレートを「固定の文字」と「可変部分」に分けておき、
Triggevent 側で正規表現にして照合する。可変部分は方角・数字・「自分」・選択肢なら収録音声に、
それ以外（プレイヤー名など）は TTS で読む。
"""
from __future__ import annotations

import re

from .style import TAIL_ID, Style

MAPPING_FORMAT = 1
QUOTED = re.compile(r"'([^']*)'|\"([^\"]*)\"")

# Triggevent の ArenaSector の表示名と略称
DIRECTIONS = {
    "part_dir_n": ("北", ["North", "N"]),
    "part_dir_ne": ("北東", ["Northeast", "NE"]),
    "part_dir_e": ("東", ["East", "E"]),
    "part_dir_se": ("南東", ["Southeast", "SE"]),
    "part_dir_s": ("南", ["South", "S"]),
    "part_dir_sw": ("南西", ["Southwest", "SW"]),
    "part_dir_w": ("西", ["West", "W"]),
    "part_dir_nw": ("北西", ["Northwest", "NW"]),
    "part_dir_c": ("中央", ["Center", "Mid", "Middle"]),
}
# Triggevent が自分を指すときに入れる文字（設定の既定値）
YOU = "YOU"


def split_placeholders(text: str) -> list[tuple[str, str]]:
    """文を ("lit", 文字) と ("slot", 式) の並びに分ける。{{ }} の入れ子も1つの式として扱う。"""
    pieces = []
    buf = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            depth, j = 1, i + 1
            while j < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            if depth:
                raise ValueError(f"括弧が閉じていません: {text}")
            if buf:
                pieces.append(("lit", "".join(buf)))
                buf = []
            pieces.append(("slot", text[i + 1:j - 1].strip()))
            i = j
        else:
            buf.append(text[i])
            i += 1
    if buf:
        pieces.append(("lit", "".join(buf)))
    return pieces


def normalize(expr: str) -> str:
    """訳で中の文字列だけが変わった式を同じものとして扱うため、文字列と空白を除く。"""
    return re.sub(r"\s+", "", QUOTED.sub("''", expr))


def literals(expr: str) -> list[str]:
    return [(m.group(1) if m.group(1) is not None else m.group(2)).strip() for m in QUOTED.finditer(expr)]


def build(script: dict, style: Style | None = None) -> dict:
    static = {}
    templates = []
    skipped = 0
    for content in script["contents"]:
        for line in content["lines"]:
            en = line["en"]
            if line.get("id"):
                static.setdefault(en, {"id": line["id"], "ja": _styled(style, line["ja"], "line")})
                continue
            template = _template(line, style)
            if template is None:
                skipped += 1
            elif all(t["en"] != en for t in templates):
                templates.append(template)
    # 「全体攻撃」のような固定の文字が多いものから照合し、{安置} だけのような何にでも一致するものは最後にする
    templates.sort(key=lambda t: -sum(len(p["lit"].strip()) for p in t["enPieces"] if "lit" in p))
    names = {}
    for key, kind in (("dots", "dot"), ("cooldowns", "cd"), ("system", "system")):
        for entry in script[key]:
            names.setdefault(entry["ja"], {"id": entry["id"], "ja": _styled(style, entry["ja"], kind)})
    # ゲームや Triggevent が英語で読み上げるもの
    names.setdefault("Dots", {"id": "dot_brd", "ja": _styled(style, "DoT", "dot")})
    test = _styled(style, "テスト", "system")
    names.setdefault("Test", {"id": "sys_test", "ja": test})
    names.setdefault("test", {"id": "sys_test", "ja": test})
    return {
        "format": MAPPING_FORMAT,
        "static": static,
        "templates": templates,
        "names": names,
        "directions": {pid: {"ja": ja, "en": en} for pid, (ja, en) in DIRECTIONS.items()},
        "numbers": {str(n): f"part_num_{n}" for n in range(1, 9)},
        "you": {"en": YOU, "ja": "自分", "id": "part_you"},
        "skipped": skipped,
    }


def _styled(style: Style | None, text: str, kind: str) -> str:
    return style.ending(text, kind) if style else text


def _template(line: dict, style: Style | None = None) -> dict | None:
    en_pieces = split_placeholders(line["en"])
    ja_slots = [p for p in line["parts"] if p["type"] == "slot"]
    en_slots = [expr for kind, expr in en_pieces if kind == "slot"]
    # Groovy のクロージャ（{{ ... }}）のように、値を照合できない式を含むものは扱わない
    if any("{" in e for e in en_slots) or len(en_slots) != len(ja_slots):
        return None
    # 固定の文字が無いもの（{次のギミック} だけなど）は何にでも一致してしまうので扱わない
    if not any(kind == "lit" and value.strip(" ,.-:") for kind, value in en_pieces):
        return None
    slots = []
    used = set()
    for ja_slot in ja_slots:
        match = next((i for i, e in enumerate(en_slots) if i not in used and normalize(e) == normalize(ja_slot["expr"])), None)
        if match is None:
            return None
        used.add(match)
        slot = {"kind": ja_slot["kind"], "en": match}
        if ja_slot["kind"] == "choice":
            en_words = literals(en_slots[match])
            choices = ja_slot.get("choices", [])
            if len(en_words) != len(choices) or not en_words:
                return None
            slot["choices"] = [{"en": w, "ja": c["ja"], "id": c["id"]} for w, c in zip(en_words, choices)]
        slots.append(slot)
    # 英語の並び順で可変部分の番号を引けるようにする
    order = {s["en"]: n for n, s in enumerate(slots)}
    ja_pieces = [{"lit": p["ja"], "id": p["id"]} if p["type"] == "segment" else {"slot": n}
                 for n, p in _slot_numbers(line["parts"])]
    # 台本の select と同じ規則で、最後の部品を語尾付きのものに差し替える
    if style is not None and ja_pieces:
        last = ja_pieces[-1]
        if "lit" in last:
            last["id"], last["lit"] = style.terminal(last["id"], last["lit"])
        elif style.tail:
            ja_pieces.append({"lit": style.tail, "id": TAIL_ID})
    return {
        "en": line["en"],
        "ja": line["ja"],
        "enPieces": [{"lit": v} if k == "lit" else {"slot": order[i]} for i, (k, v) in _numbered(en_pieces)],
        "jaPieces": ja_pieces,
        "slots": [{k: v for k, v in s.items() if k != "en"} for s in slots],
    }


def _numbered(pieces):
    n = 0
    for kind, value in pieces:
        if kind == "slot":
            yield n, (kind, value)
            n += 1
        else:
            yield None, (kind, value)


def _slot_numbers(parts):
    n = 0
    for p in parts:
        if p["type"] == "slot":
            yield n, p
            n += 1
        else:
            yield None, p


def resolve(mapping: dict, text: str) -> tuple[list[str], str] | None:
    """読み上げ文から、つなげて鳴らすファイル ID の並びと、日本語の文を求める（Triggevent 側と同じ処理の参考実装）。

    プレイヤー名のように収録できない部分がある場合、ID の並びには None が入る。
    """
    for table in ("static", "names"):
        if text in mapping[table]:
            hit = mapping[table][text]
            return [hit["id"]], hit["ja"]
    for t in mapping["templates"]:
        regex = "".join(re.escape(p["lit"]) if "lit" in p else f"(?P<s{p['slot']}>{_slot_regex(t['slots'][p['slot']])})"
                        for p in t["enPieces"])
        m = re.fullmatch(regex, text)
        if not m:
            continue
        ids, words = [], []
        for p in t["jaPieces"]:
            if "lit" in p:
                ids.append(p["id"])
                words.append(p["lit"])
                continue
            pid, word = _slot_value(mapping, t["slots"][p["slot"]], m.group(f"s{p['slot']}"))
            ids.append(pid)
            words.append(word)
        return ids, "".join(words)
    return None


def _slot_regex(slot: dict) -> str:
    if slot["kind"] == "choice":
        return "|".join(re.escape(c["en"]) for c in sorted(slot["choices"], key=lambda c: -len(c["en"])))
    return ".+?"


def _slot_value(mapping: dict, slot: dict, value: str) -> tuple[str | None, str]:
    if slot["kind"] == "choice":
        c = next(c for c in slot["choices"] if c["en"] == value)
        return c["id"], c["ja"]
    if value == mapping["you"]["en"]:
        return mapping["you"]["id"], mapping["you"]["ja"]
    for pid, d in mapping["directions"].items():
        if value in d["en"]:
            return pid, d["ja"]
    if value in mapping["numbers"]:
        return mapping["numbers"][value], value
    return None, value
