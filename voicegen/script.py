"""台本データ（data/script.json）から、生成するセリフを選ぶ。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import ConfigError, Select


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    kind: str
    # このセリフを使うコンテンツやジョブ（画面での絞り込み用）
    tags: tuple[str, ...] = ()


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"台本データが見つかりません: {path}") from None


def select(script: dict, sel: Select) -> list[Item]:
    """選んだコンテンツ・ジョブで必要なセリフを、重複なしで返す。空のリストは「すべて」を意味する。"""
    content_keys = [c["key"] for c in script["contents"]]
    job_keys = [j["abbr"] for j in script["jobs"]]
    for key in sel.contents:
        if key not in content_keys:
            raise ConfigError(f"コンテンツ「{key}」は台本にありません。使えるもの: {', '.join(content_keys)}")
    for key in sel.jobs:
        if key not in job_keys:
            raise ConfigError(f"ジョブ「{key}」は台本にありません。使えるもの: {', '.join(job_keys)}")
    contents = set(sel.contents or content_keys)
    jobs = set(sel.jobs or job_keys)

    items: dict[str, Item] = {}
    tags: dict[str, list[str]] = {}

    def add(item_id: str, text: str, kind: str, tag: str = "") -> None:
        items.setdefault(item_id, Item(item_id, text, kind))
        if tag and tag not in tags.setdefault(item_id, []):
            tags[item_id].append(tag)

    for content in script["contents"]:
        if content["key"] not in contents:
            continue
        for line in content["lines"]:
            if line.get("id"):
                add(line["id"], line["ja"], "line", content["key"])
                continue
            for part in line.get("parts", []):
                if part["type"] == "segment":
                    add(part["id"], part["ja"], "segment", content["key"])
                for choice in part.get("choices", []):
                    add(choice["id"], choice["ja"], "choice", content["key"])
    if sel.parts:
        for entries in script["parts"].values():
            for item_id, text in entries:
                add(item_id, text, "part")
    for kind, key in (("dot", "dots"), ("cd", "cooldowns")):
        for entry in script[key]:
            if entry["jobs"] and jobs.intersection(entry["jobs"]):
                for job in sorted(jobs.intersection(entry["jobs"])):
                    add(entry["id"], entry["ja"], kind, job)
            elif not entry["jobs"] and sel.jobless_dots:
                add(entry["id"], entry["ja"], kind)
    if sel.system:
        for entry in script["system"]:
            add(entry["id"], entry["ja"], "system")
    return [Item(i.id, i.text, i.kind, tuple(tags.get(i.id, ()))) for i in items.values()]


def apply_readings(text: str, readings: dict[str, str]) -> str:
    """合成するときだけ読みを置き換える。長い語を先に置き換えて、短い語が一部に当たらないようにする。"""
    for word in sorted(readings, key=len, reverse=True):
        text = text.replace(word, readings[word])
    return text
