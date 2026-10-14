"""VOICEVOX ENGINE（HTTP API）での音声合成。"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import ConfigError, Voicevox

REQUEST_TIMEOUT = 60
STARTUP_TIMEOUT = 120
POLL_INTERVAL = 1.0


class VoicevoxError(Exception):
    pass


class Client:
    def __init__(self, url: str):
        parsed = urllib.parse.urlparse(url)
        # 台本の文をよそのサーバーに送らないよう、手元のエンジンだけを相手にする
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
            raise ConfigError(f"VOICEVOX の url はこの PC（http://127.0.0.1:ポート）を指定してください: {url}")
        self.url = url

    def _request(self, method: str, path: str, params: dict | None = None, body: bytes | None = None) -> bytes:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        req = urllib.request.Request(self.url + path + query, data=body, method=method,
                                     headers={"Content-Type": "application/json"} if body is not None else {})
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as res:
                return res.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise VoicevoxError(f"VOICEVOX がエラーを返しました（{e.code}）: {detail}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise VoicevoxError(f"VOICEVOX に接続できません（{self.url}）: {e}") from None

    def version(self) -> str:
        return json.loads(self._request("GET", "/version"))

    def is_running(self) -> bool:
        try:
            self.version()
            return True
        except VoicevoxError:
            return False

    def speakers(self) -> list[dict]:
        return json.loads(self._request("GET", "/speakers"))

    def synthesize(self, text: str, cfg: Voicevox) -> bytes:
        query = json.loads(self._request("POST", "/audio_query", {"text": text, "speaker": cfg.speaker}))
        query.update({
            "speedScale": cfg.speed,
            "pitchScale": cfg.pitch,
            "intonationScale": cfg.intonation,
            "volumeScale": cfg.volume,
            "prePhonemeLength": cfg.pre_phoneme,
            "postPhonemeLength": cfg.post_phoneme,
            "outputSamplingRate": cfg.sample_rate,
            "outputStereo": False,
        })
        if cfg.end_rise > 0:
            raise_ending(query, cfg.end_rise, cfg.end_moras)
        wav = self._request("POST", "/synthesis", {"speaker": cfg.speaker},
                            json.dumps(query, ensure_ascii=False).encode("utf-8"))
        if wav[:4] != b"RIFF":
            raise VoicevoxError("VOICEVOX から WAV 以外のデータが返されました。")
        return wav


def raise_ending(query: dict, rise: float, count: int) -> None:
    """文末の音を少しずつ高くする。無声の音（高さ 0）は高さを持たないので飛ばす。"""
    moras = [m for phrase in query.get("accent_phrases", []) for m in phrase.get("moras", []) if m.get("pitch", 0) > 0]
    tail = moras[-count:]
    for n, mora in enumerate(tail, 1):
        mora["pitch"] += rise * n / len(tail)


class Engine:
    """エンジンが起動していなければ起動し、終わったら止める。すでに起動していれば何もしない。"""

    def __init__(self, cfg: Voicevox):
        self.cfg = cfg
        self.client = Client(cfg.url)
        self._process: subprocess.Popen | None = None

    def __enter__(self) -> Client:
        if self.client.is_running():
            return self.client
        exe = self.cfg.engine
        if exe is None or not Path(exe).is_file():
            raise VoicevoxError(f"VOICEVOX が起動しておらず、engine のパスも見つかりません: {exe}")
        port = urllib.parse.urlparse(self.cfg.url).port or 50021
        self._process = subprocess.Popen(
            [str(exe), "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(Path(exe).parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise VoicevoxError(f"VOICEVOX ENGINE が起動直後に終了しました（終了コード {self._process.returncode}）。")
            if self.client.is_running():
                return self.client
            time.sleep(POLL_INTERVAL)
        self._stop()
        raise VoicevoxError("VOICEVOX ENGINE の起動を待ちましたが、応答がありませんでした。")

    def __exit__(self, *exc) -> None:
        self._stop()

    def _stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
