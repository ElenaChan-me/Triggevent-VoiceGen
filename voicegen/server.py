"""セリフを選んで自分の声を録音し、RVC で作り直す画面（ローカルの Web サーバー）。

この PC のブラウザからだけ使う前提で 127.0.0.1 で待ち受け、ほかのサイトからのリクエストは受け付けない。
"""
from __future__ import annotations

import json
import tempfile
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import applio, audio, recordings, script, voicevox
from .config import Config, ConfigError
from .pipeline import Pipeline, SharedEngine

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UI_FILE = Path(__file__).with_name("ui.html")


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.items = script.select(script.load(cfg.script), cfg.select, cfg.style)
        self.by_id = {i.id: i for i in self.items}
        self.engine = SharedEngine(cfg)
        self.pipeline = Pipeline(cfg, log=lambda _: None, engine=self.engine)
        # RVC は GPU を使い、manifest も書き換えるので、作り直しは1件ずつ順番に行う
        self.lock = threading.Lock()

    def item(self, item_id: str) -> script.Item:
        item = self.by_id.get(item_id)
        if item is None:
            raise KeyError(item_id)
        return item

    def status(self, item: script.Item) -> dict:
        p = self.pipeline
        return {
            "id": item.id, "text": item.text, "kind": item.kind, "tags": list(item.tags),
            "recorded": p.uses_recording(item),
            "hasTts": (p.tts_dir / f"{item.id}.wav").is_file(),
            "hasResult": (p.pack_dir / f"{item.id}.wav").is_file(),
            "current": p.is_current(item),
        }

    def info(self) -> dict:
        rvc = self.cfg.rvc
        return {
            "pack": self.cfg.pack.name,
            "rvcEnabled": rvc.enabled,
            "model": rvc.model.name if rvc.model else None,
            "pitch": rvc.pitch,
            "recordingPitch": self.cfg.recordings.pitch,
            "maxSeconds": self.cfg.recordings.max_seconds,
            "count": len(self.items),
        }

    def regenerate(self, item: script.Item) -> dict:
        with self.lock:
            self.pipeline.run_all([item])
            self.pipeline.write_manifest(self.items)
        return self.status(item)

    def audio_path(self, kind: str, item: script.Item) -> Path:
        p = self.pipeline
        return {
            "tts": p.tts_dir / f"{item.id}.wav",
            "recording": recordings.path_for(self.cfg, item.id),
            "result": p.pack_dir / f"{item.id}.wav",
        }[kind]


def make_handler(app: App, origin: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, data, status=HTTPStatus.OK):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status, message):
            self._json({"error": message}, status)

        def _foreign(self) -> bool:
            # 別のサイトのページから、この PC のサーバーを操作されないようにする
            sent = self.headers.get("Origin")
            if sent is not None and sent != origin:
                self._error(HTTPStatus.FORBIDDEN, "このページ以外からの操作は受け付けません。")
                return True
            return False

        def _route(self):
            parts = [p for p in urlparse(self.path).path.split("/") if p]
            return parts

        def do_GET(self):
            parts = self._route()
            if not parts:
                body = UI_FILE.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parts == ["api", "info"]:
                self._json(app.info())
            elif parts == ["api", "items"]:
                self._json([app.status(i) for i in app.items])
            elif len(parts) == 3 and parts[0] == "audio" and parts[1] in ("tts", "recording", "result"):
                self._audio(parts[1], parts[2].removesuffix(".wav"))
            else:
                self._error(HTTPStatus.NOT_FOUND, "見つかりません。")

        def _audio(self, kind, item_id):
            try:
                path = app.audio_path(kind, app.item(item_id))
            except (KeyError, ValueError):
                return self._error(HTTPStatus.NOT_FOUND, "セリフが見つかりません。")
            if not path.is_file():
                return self._error(HTTPStatus.NOT_FOUND, "まだ音声がありません。")
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self._foreign():
                return
            parts = self._route()
            if len(parts) != 3 or parts[0] != "api" or parts[1] not in ("recording", "generate"):
                return self._error(HTTPStatus.NOT_FOUND, "見つかりません。")
            try:
                item = app.item(parts[2])
            except KeyError:
                return self._error(HTTPStatus.NOT_FOUND, "セリフが見つかりません。")
            try:
                if parts[1] == "recording":
                    self._upload(item)
                else:
                    self._json(app.regenerate(item))
            except (ConfigError, voicevox.VoicevoxError, applio.RvcError, audio.AudioError, ValueError) as e:
                self._error(HTTPStatus.BAD_REQUEST, str(e))
            except Exception:
                traceback.print_exc()
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "予期しないエラーが発生しました。コンソールを確認してください。")

        def _upload(self, item):
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_UPLOAD_BYTES:
                return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "録音が空か、大きすぎます。")
            data = self.rfile.read(length)
            app.cfg.work.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=app.cfg.work, suffix=".upload", delete=False) as tmp:
                tmp.write(data)
            try:
                recordings.save(app.cfg, item.id, Path(tmp.name))
            finally:
                Path(tmp.name).unlink(missing_ok=True)
            self._json(app.status(item))

        def do_DELETE(self):
            if self._foreign():
                return
            parts = self._route()
            if len(parts) != 3 or parts[:2] != ["api", "recording"]:
                return self._error(HTTPStatus.NOT_FOUND, "見つかりません。")
            try:
                item = app.item(parts[2])
            except KeyError:
                return self._error(HTTPStatus.NOT_FOUND, "セリフが見つかりません。")
            recordings.delete(app.cfg, item.id)
            self._json(app.status(item))

    return Handler


def serve(cfg: Config, port: int, open_browser: bool = True) -> None:
    app = App(cfg)
    server = ThreadingHTTPServer(("127.0.0.1", port), None)
    origin = f"http://127.0.0.1:{server.server_address[1]}"
    server.RequestHandlerClass = make_handler(app, origin)
    print(f"録音・修正の画面: {origin}  （終了するには Ctrl+C）")
    if open_browser:
        webbrowser.open(origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.engine.close()
