"""config.toml の読み込みと検証。"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Select:
    contents: list[str]
    jobs: list[str]
    parts: bool
    system: bool
    jobless_dots: bool


@dataclass(frozen=True)
class Voicevox:
    url: str
    engine: Path | None
    speaker: int
    speed: float
    pitch: float
    intonation: float
    volume: float
    pre_phoneme: float
    post_phoneme: float
    sample_rate: int


@dataclass(frozen=True)
class Rvc:
    enabled: bool
    applio: Path
    model: Path | None
    index: Path | None
    pitch: int
    index_rate: float
    protect: float
    f0_method: str
    volume_envelope: float
    embedder: str
    extra_args: list[str]


@dataclass(frozen=True)
class Post:
    ffmpeg: str
    sample_rate: int
    trim_db: float
    pad_ms: int
    loudness: float
    true_peak: float


@dataclass(frozen=True)
class Recordings:
    dir: Path
    # 自分の声と VOICEVOX の話者では高さが違うので、RVC の pitch を別に指定できるようにする。None なら [rvc] と同じ
    pitch: int | None
    max_seconds: int


@dataclass(frozen=True)
class Pack:
    name: str
    credit: str


@dataclass(frozen=True)
class Config:
    base: Path
    script: Path
    work: Path
    output: Path
    select: Select
    voicevox: Voicevox
    readings: dict[str, str]
    rvc: Rvc
    post: Post
    pack: Pack
    recordings: Recordings
    extra: dict = field(default_factory=dict)


F0_METHODS = {"rmvpe", "crepe", "crepe-tiny", "fcpe", "hybrid[rmvpe+fcpe]"}
EMBEDDERS = {"contentvec", "spin", "spin-v2", "chinese-hubert-base", "japanese-hubert-base", "korean-hubert-base"}


def _get(table: dict, key: str, kind: type | tuple, default=None, *, required: bool = False):
    if key not in table:
        if required:
            raise ConfigError(f"「{key}」が設定されていません。")
        return default
    value = table[key]
    # TOML の整数は float の項目にも書けるようにする
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ConfigError(f"「{key}」の値の型が正しくありません: {value!r}")
    return value


def _range(name: str, value: float, low: float, high: float) -> float:
    if not low <= value <= high:
        raise ConfigError(f"「{name}」は {low}〜{high} の範囲で指定してください: {value}")
    return value


def _path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else (base / p).resolve()


def load(path: Path) -> Config:
    path = path.resolve()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"設定ファイルが見つかりません: {path}（config.example.toml をコピーして作成してください）") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"設定ファイルの書式が正しくありません: {e}") from None
    base = path.parent

    paths = raw.get("paths", {})
    sel = raw.get("select", {})
    vv = raw.get("voicevox", {})
    rvc = raw.get("rvc", {})
    post = raw.get("post", {})
    pack = raw.get("pack", {})
    readings = raw.get("readings", {})
    rec = raw.get("recordings", {})
    if not all(isinstance(k, str) and isinstance(v, str) and k for k, v in readings.items()):
        raise ConfigError("[readings] は「置き換える文字 = 読み」の形で、文字列で指定してください。")

    rvc_enabled = _get(rvc, "enabled", bool, False)
    model = _path(base, _get(rvc, "model", str, ""))
    index = _path(base, _get(rvc, "index", str, ""))
    if rvc_enabled and model is None:
        raise ConfigError("[rvc] enabled = true のときは model（.pth）を指定してください。")
    f0 = _get(rvc, "f0_method", str, "rmvpe")
    if f0 not in F0_METHODS:
        raise ConfigError(f"f0_method は {sorted(F0_METHODS)} のいずれかを指定してください: {f0}")
    embedder = _get(rvc, "embedder", str, "contentvec")
    if embedder not in EMBEDDERS:
        raise ConfigError(f"embedder は {sorted(EMBEDDERS)} のいずれかを指定してください: {embedder}")
    extra_args = _get(rvc, "extra_args", list, [])
    if not all(isinstance(a, str) for a in extra_args):
        raise ConfigError("extra_args は文字列の配列で指定してください。")

    name = _get(pack, "name", str, "voice")
    if not name or any(c in name for c in '\\/:*?"<>|'):
        raise ConfigError(f"[pack] name にファイル名に使えない文字が含まれています: {name!r}")

    return Config(
        base=base,
        script=_path(base, _get(paths, "script", str, "data/script.json")),
        work=_path(base, _get(paths, "work", str, "work")),
        output=_path(base, _get(paths, "output", str, "output")),
        select=Select(
            contents=list(_get(sel, "contents", list, [])),
            jobs=list(_get(sel, "jobs", list, [])),
            parts=_get(sel, "parts", bool, True),
            system=_get(sel, "system", bool, True),
            jobless_dots=_get(sel, "jobless_dots", bool, False),
        ),
        voicevox=Voicevox(
            url=_get(vv, "url", str, "http://127.0.0.1:50021").rstrip("/"),
            engine=_path(base, _get(vv, "engine", str, "")),
            speaker=_get(vv, "speaker", int, required=True),
            speed=_range("speed", _get(vv, "speed", float, 1.0), 0.5, 2.0),
            pitch=_range("pitch", _get(vv, "pitch", float, 0.0), -0.15, 0.15),
            intonation=_range("intonation", _get(vv, "intonation", float, 1.0), 0.0, 2.0),
            volume=_range("volume", _get(vv, "volume", float, 1.0), 0.0, 2.0),
            pre_phoneme=_range("pre_phoneme", _get(vv, "pre_phoneme", float, 0.05), 0.0, 1.5),
            post_phoneme=_range("post_phoneme", _get(vv, "post_phoneme", float, 0.05), 0.0, 1.5),
            sample_rate=_get(vv, "sample_rate", int, 48000),
        ),
        readings=dict(readings),
        rvc=Rvc(
            enabled=rvc_enabled,
            applio=_path(base, _get(rvc, "applio", str, "D:/VoiceGenTools/Applio")),
            model=model,
            index=index,
            pitch=int(_range("pitch", _get(rvc, "pitch", int, 0), -24, 24)),
            index_rate=_range("index_rate", _get(rvc, "index_rate", float, 0.3), 0.0, 1.0),
            protect=_range("protect", _get(rvc, "protect", float, 0.33), 0.0, 0.5),
            f0_method=f0,
            volume_envelope=_range("volume_envelope", _get(rvc, "volume_envelope", float, 1.0), 0.0, 1.0),
            embedder=embedder,
            extra_args=list(extra_args),
        ),
        post=Post(
            ffmpeg=_get(post, "ffmpeg", str, "ffmpeg"),
            sample_rate=_get(post, "sample_rate", int, 48000),
            trim_db=_range("trim_db", _get(post, "trim_db", float, -50.0), -90.0, -10.0),
            pad_ms=int(_range("pad_ms", _get(post, "pad_ms", int, 20), 0, 1000)),
            loudness=_range("loudness", _get(post, "loudness", float, -16.0), -40.0, -5.0),
            true_peak=_range("true_peak", _get(post, "true_peak", float, -1.5), -9.0, 0.0),
        ),
        pack=Pack(name=name, credit=_get(pack, "credit", str, "")),
        recordings=Recordings(
            dir=_path(base, _get(rec, "dir", str, "recordings")),
            pitch=None if "pitch" not in rec else int(_range("recordings.pitch", _get(rec, "pitch", int), -24, 24)),
            max_seconds=int(_range("max_seconds", _get(rec, "max_seconds", int, 15), 1, 120)),
        ),
    )
