import io
import json
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from voicegen import applio, audio, config, script
from voicegen.config import ConfigError
from voicegen.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE = 48000


def make_wav(seconds: float = 0.5, silence: float = 0.2) -> bytes:
    """前後に無音がある 440Hz の音。"""
    import math
    frames = []
    total = int(SAMPLE_RATE * (seconds + silence * 2))
    for n in range(total):
        t = n / SAMPLE_RATE
        value = 0 if t < silence or t > silence + seconds else int(8000 * math.sin(2 * math.pi * 440 * t))
        frames.append(struct.pack("<h", value))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"".join(frames))
    return buf.getvalue()


class FakeVoicevox(BaseHTTPRequestHandler):
    texts: list = []

    def log_message(self, *args):
        pass

    def _send(self, body: bytes, kind: str):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/version":
            self._send(b'"0.25.2"', "application/json")
        else:
            self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if url.path == "/audio_query":
            FakeVoicevox.texts.append(parse_qs(url.query)["text"][0])
            self._send(json.dumps({"accent_phrases": []}).encode(), "application/json")
        elif url.path == "/synthesis":
            query = json.loads(body)
            assert query["outputSamplingRate"] == SAMPLE_RATE
            self._send(make_wav(), "audio/wav")
        else:
            self.send_error(404)


def write_config(base: Path, port: int, **overrides) -> Path:
    text = f"""
[paths]
script = "{(ROOT / 'data' / 'script.json').as_posix()}"
work = "work"
output = "output"
[select]
contents = ["M9S"]
jobs = ["WHM"]
[voicevox]
url = "http://127.0.0.1:{port}"
speaker = 2
[readings]
"DPS" = "ディーピーエス"
[pack]
name = "test"
credit = "VOICEVOX:テスト"
"""
    for line in overrides.get("extra", []):
        text += line + "\n"
    path = base / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.data = script.load(ROOT / "data" / "script.json")

    def test_select_content_and_job_without_duplicates(self):
        sel = config.Select(contents=["M9S"], jobs=["WHM"], parts=True, system=True, jobless_dots=False)
        items = script.select(self.data, sel)
        ids = [i.id for i in items]
        self.assertEqual(len(ids), len(set(ids)))
        kinds = {i.kind for i in items}
        self.assertTrue({"line", "part", "dot", "cd", "system"} <= kinds)
        # 白魔道士の DoT（ディア）は入り、ナイトだけのアクションは入らない
        self.assertIn("ディア", [i.text for i in items if i.kind == "dot"])
        pld_only = [c["id"] for c in self.data["cooldowns"] if c["jobs"] == ["PLD"]]
        self.assertFalse(set(pld_only) & set(ids))

    def test_unknown_names_are_rejected(self):
        with self.assertRaises(ConfigError):
            script.select(self.data, config.Select(["XYZ"], [], True, True, False))
        with self.assertRaises(ConfigError):
            script.select(self.data, config.Select([], ["ABC"], True, True, False))

    def test_readings_replace_longest_first(self):
        self.assertEqual(script.apply_readings("DPSとD", {"D": "ディー", "DPS": "ディーピーエス"}), "ディーピーエスとディー")


class ConfigTests(unittest.TestCase):
    def test_example_config_loads(self):
        cfg = config.load(ROOT / "config.example.toml")
        self.assertFalse(cfg.rvc.enabled)
        self.assertEqual(cfg.voicevox.sample_rate, 48000)

    def test_out_of_range_and_remote_url_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_config(Path(tmp), 1, extra=["[rvc]", 'enabled = true'])
            with self.assertRaises(ConfigError):
                config.load(path)  # model が無い
            path.write_text('[voicevox]\nspeaker = 1\nspeed = 5.0\n', encoding="utf-8")
            with self.assertRaises(ConfigError):
                config.load(path)
        with self.assertRaises(ConfigError):
            from voicegen.voicevox import Client
            Client("http://example.com:50021")


class ApplioTests(unittest.TestCase):
    def test_command_and_output_name(self):
        rvc = config.Rvc(True, Path("C:/Applio"), Path("C:/m/a.pth"), None, 2, 0.5, 0.3, "rmvpe", 1.0, "contentvec", ["--split-audio"])
        cmd = applio.build_command(rvc, Path("in"), Path("out"))
        self.assertEqual(cmd[1:3], ["core.py", "batch-infer"])
        # index が無いときは index_rate を 0 にする
        self.assertEqual(cmd[cmd.index("--index-rate") + 1], "0.0")
        self.assertEqual(cmd[cmd.index("--index-path") + 1], "")
        self.assertEqual(cmd[-1], "--split-audio")
        self.assertEqual(applio.output_name("L_1234.wav"), "L_1234_output.wav")


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg が必要")
class PipelineTests(unittest.TestCase):
    def setUp(self):
        FakeVoicevox.texts = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeVoicevox)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def test_generate_trims_and_caches(self):
        cfg = config.load(write_config(self.base, self.server.server_address[1]))
        items = script.select(script.load(cfg.script), cfg.select)[:5]
        pipe = Pipeline(cfg, log=lambda _: None)
        self.assertEqual(pipe.run_tts(items), 5)
        self.assertEqual(pipe.run_rvc(items), 0)
        self.assertEqual(pipe.run_post(items), 5)
        manifest = json.loads(pipe.write_manifest(items).read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["entries"]), 5)
        self.assertEqual(manifest["credit"], "VOICEVOX:テスト")

        out = cfg.output / "test" / f"{items[0].id}.wav"
        with wave.open(str(out)) as w:
            self.assertEqual((w.getnchannels(), w.getframerate(), w.getsampwidth()), (1, 48000, 2))
            duration = w.getnframes() / w.getframerate()
        # 0.5 秒の音の前後 0.2 秒ずつの無音が詰められ、前後 20ms ずつ足されている
        self.assertAlmostEqual(duration, 0.54, delta=0.03)

        # 2 回目は何も作り直さない
        self.assertEqual(pipe.run_tts(items), 0)
        self.assertEqual(pipe.run_post(items), 0)

        # 話速を変えると TTS から作り直し、仕上げもやり直す
        path = write_config(self.base, self.server.server_address[1])
        path.write_text(path.read_text(encoding="utf-8").replace("speaker = 2", "speaker = 2\nspeed = 1.3"), encoding="utf-8")
        pipe2 = Pipeline(config.load(path), log=lambda _: None)
        self.assertEqual(pipe2.run_tts(items), 5)
        self.assertEqual(pipe2.run_post(items), 5)



@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg が必要")
class RecordingTests(unittest.TestCase):
    def setUp(self):
        FakeVoicevox.texts = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeVoicevox)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.wav = self.base / "my_voice.wav"
        self.wav.write_bytes(make_wav(0.8, 0.1))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def load(self, *extra):
        return config.load(write_config(self.base, self.server.server_address[1], extra=list(extra)))

    def test_recording_replaces_tts(self):
        from voicegen import recordings
        cfg = self.load()
        items = script.select(script.load(cfg.script), cfg.select)[:3]
        recordings.save(cfg, items[0].id, self.wav)
        pipe = Pipeline(cfg, log=lambda _: None)
        self.assertEqual(pipe.run_tts(items), 2)  # 録音のあるセリフは合成しない
        self.assertEqual(len(FakeVoicevox.texts), 2)
        self.assertEqual(pipe.run_post(items), 3)
        manifest = json.loads(pipe.write_manifest(items).read_text(encoding="utf-8"))
        self.assertEqual(manifest["entries"][items[0].id]["source"], "recording")
        self.assertEqual(manifest["entries"][items[1].id]["source"], "tts")

        # 録音を差し替えると、そのセリフだけ仕上げをやり直す
        self.wav.write_bytes(make_wav(0.3, 0.1))
        recordings.save(cfg, items[0].id, self.wav)
        self.assertEqual(pipe.run_post(items), 1)
        # 録音を消すと TTS に戻り、合成し直す
        recordings.delete(cfg, items[0].id)
        self.assertEqual(pipe.run_tts(items), 1)

    def test_bad_ids_are_rejected(self):
        from voicegen import recordings
        cfg = self.load()
        for bad in ("../x", "a/b", "", "x" * 65):
            with self.assertRaises(ValueError):
                recordings.path_for(cfg, bad)

    def test_rvc_splits_batches_by_pitch(self):
        from unittest import mock
        from voicegen import recordings
        applio_dir = self.base / "Applio"
        (applio_dir / ".venv" / "Scripts").mkdir(parents=True)
        (applio_dir / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
        (applio_dir / "core.py").write_text("", encoding="utf-8")
        (self.base / "voice.pth").write_bytes(b"model")
        cfg = self.load("[rvc]", "enabled = true", f'applio = "{applio_dir.as_posix()}"', 'model = "voice.pth"', "pitch = 3",
                        "[recordings]", "pitch = -5")
        items = script.select(script.load(cfg.script), cfg.select)[:3]
        recordings.save(cfg, items[0].id, self.wav)
        pipe = Pipeline(cfg, log=lambda _: None)
        pipe.run_tts(items)
        calls = []

        def fake_convert(rvc_cfg, src, dst, log):
            calls.append((rvc_cfg.pitch, sorted(p.name for p in src.iterdir())))
            for p in src.iterdir():
                shutil.copyfile(p, dst / applio.output_name(p.name))

        with mock.patch.object(applio, "convert", side_effect=fake_convert):
            self.assertEqual(pipe.run_rvc(items), 3)
        self.assertEqual(sorted(c[0] for c in calls), [-5, 3])
        self.assertEqual(dict(calls)[-5], [f"{items[0].id}.wav"])
        with mock.patch.object(applio, "convert", side_effect=fake_convert):
            self.assertEqual(pipe.run_rvc(items), 0)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg が必要")
class ServerTests(unittest.TestCase):
    def setUp(self):
        import urllib.request
        from voicegen import server
        FakeVoicevox.texts = []
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.vv = ThreadingHTTPServer(("127.0.0.1", 0), FakeVoicevox)
        threading.Thread(target=self.vv.serve_forever, daemon=True).start()
        cfg = config.load(write_config(self.base, self.vv.server_address[1]))
        self.app = server.App(cfg)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), None)
        self.origin = f"http://127.0.0.1:{self.http.server_address[1]}"
        self.http.RequestHandlerClass = server.make_handler(self.app, self.origin)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.urllib = urllib.request

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.app.engine.close()
        self.vv.shutdown()
        self.vv.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None, origin=None):
        import urllib.error
        headers = {"Origin": origin or self.origin}
        req = self.urllib.Request(self.origin + path, data=body, method=method, headers=headers)
        try:
            with self.urllib.urlopen(req) as res:
                return res.status, res.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_record_generate_and_delete(self):
        status, body = self.call("GET", "/api/items")
        self.assertEqual(status, 200)
        item_id = json.loads(body)[0]["id"]
        status, body = self.call("POST", f"/api/recording/{item_id}", make_wav())
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["recorded"])
        status, body = self.call("POST", f"/api/generate/{item_id}")
        self.assertEqual(status, 200, body)
        result = json.loads(body)
        self.assertTrue(result["hasResult"] and result["current"])
        self.assertEqual(FakeVoicevox.texts, [])  # 録音を使うので TTS は呼ばない
        status, body = self.call("GET", f"/audio/result/{item_id}.wav")
        self.assertEqual((status, body[:4]), (200, b"RIFF"))
        status, body = self.call("DELETE", f"/api/recording/{item_id}")
        self.assertFalse(json.loads(body)["recorded"])

    def test_rejects_other_sites_and_unknown_ids(self):
        status, _ = self.call("POST", "/api/generate/L_00000000", origin="https://evil.example")
        self.assertEqual(status, 403)
        status, _ = self.call("POST", "/api/recording/..%2F..%2Fx", b"x")
        self.assertEqual(status, 404)
        status, _ = self.call("GET", "/audio/result/..%2Fconfig.toml")
        self.assertEqual(status, 404)

    def test_names_are_generated_into_pack(self):
        from voicegen import names
        pack = self.app.cfg.pack.name
        body = json.dumps({"pack": pack, "names": ["Lily Tayler", "Lily Tayler"]}).encode()
        status, res = self.call("POST", "/api/names", body)
        self.assertEqual(status, 200, res)
        result = json.loads(res)
        self.assertEqual(result["ready"], ["name_08234852e9"])
        self.assertEqual(FakeVoicevox.texts[-1:], ["Lily"])  # 名だけを読む
        self.assertTrue((self.app.cfg.output / pack / "names" / "name_08234852e9.wav").is_file())
        # 2回目は作り直さない
        status, res = self.call("POST", "/api/names", body)
        self.assertEqual(json.loads(res)["generated"], 0)

    def test_names_reject_other_packs_and_bad_names(self):
        status, _ = self.call("POST", "/api/names", json.dumps({"pack": "other", "names": ["Lily Tayler"]}).encode())
        self.assertEqual(status, 409)
        status, _ = self.call("POST", "/api/names", json.dumps({"pack": self.app.cfg.pack.name, "names": ["../x"]}).encode())
        self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/names", json.dumps({"pack": "x", "names": ["Lily Tayler"]}).encode(),
                              origin="https://evil.example")
        self.assertEqual(status, 403)


class MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from voicegen import mapping
        cls.mapping = mapping
        cls.m = mapping.build(script.load(ROOT / "data" / "script.json"))

    def test_resolves_static_names_and_templates(self):
        r = self.mapping.resolve
        self.assertEqual(r(self.m, "Raidwide"), (["L_402ac15b"], "全体攻撃"))
        self.assertEqual(r(self.m, "Test"), (["sys_test"], "テスト"))
        ids, ja = r(self.m, "Buster on YOU")
        self.assertEqual((ids[0], ja), ("part_you", "自分にタンク強攻撃"))
        ids, ja = r(self.m, "Buster on Lily Tayler")
        self.assertIsNone(ids[0])  # プレイヤー名は収録できない
        self.assertEqual(ja, "Lily Taylerにタンク強攻撃")
        # 何にでも一致する {xxx} だけのテンプレートは入れない
        self.assertIsNone(r(self.m, "completely unknown text"))

    def test_every_template_round_trips(self):
        for t in self.m["templates"]:
            values = [s["choices"][-1]["en"] if s["kind"] == "choice" else
                      {"direction": "Southwest", "number": "3", "player": "YOU"}.get(s["kind"], "Foo") for s in t["slots"]]
            text = "".join(p["lit"] if "lit" in p else values[p["slot"]] for p in t["enPieces"])
            self.assertIsNotNone(self.mapping.resolve(self.m, text), text)


class StyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from voicegen import mapping, style
        cls.mapping = mapping
        cls.style = style
        cls.cute = style.load(ROOT / "data" / "styles" / "cute.toml")
        cls.data = script.load(ROOT / "data" / "script.json")

    def test_endings(self):
        e = self.cute.ending
        self.assertIn(e("全体攻撃", "line"), ("全体攻撃くるよー", "全体攻撃くるよっ"))
        self.assertEqual(e("塔を避ける", "line"), "塔を避けてね")
        self.assertEqual(e("塔を踏む", "line"), "塔を踏んでね")
        self.assertEqual(e("動く", "line"), "動いてね")
        self.assertEqual(e("その場に残る", "line"), "その場に残ってね")
        self.assertIn(e("動かない", "line"), ("動かないよー", "動かないよ"))
        self.assertTrue(e("ディア", "dot").startswith("ディア、かけなおして"))
        # 途中に入る部品や、記号だけのものは変えない
        self.assertEqual(e("北", "part"), "北")
        self.assertEqual(e("}", "line"), "}")
        # 同じ文はいつも同じ語尾になる
        self.assertEqual(e("散開", "line"), e("散開", "line"))
        self.assertEqual(self.cute.terminal("S_1", "}"), ("S_1", "}"))
        self.assertEqual(self.cute.terminal("S_1", "でペア"), ("S_1_e", "でペアになってね"))

    def test_mapping_matches_selected_items(self):
        sel = config.Select(contents=[], jobs=[], parts=True, system=True, jobless_dots=True)
        items = {i.id: i.text for i in script.select(self.data, sel, self.cute)}
        m = self.mapping.build(self.data, self.cute)
        # 対応表が指すファイルは、すべて同じ文で生成対象に入っている
        for t in m["templates"]:
            for p in t["jaPieces"]:
                if "lit" in p:
                    self.assertEqual(items.get(p["id"]), p["lit"], p["id"])
        for table in ("static", "names"):
            for hit in m[table].values():
                if hit["id"] in items:
                    self.assertEqual(items[hit["id"]], hit["ja"], hit["id"])
        ids, ja = self.mapping.resolve(m, "Buster on YOU")
        self.assertEqual(ids, ["part_you", "S_9c9f3a36_e"])
        self.assertTrue(ja.startswith("自分にタンク強攻撃くるよ"), ja)

    def test_tail_follows_slot_at_end(self):
        line = {"en": "Then {safe}", "ja": "そのあと{safe}",
                "parts": [{"type": "segment", "id": "S_then", "ja": "そのあと"}, {"type": "slot", "kind": "direction", "expr": "safe"}]}
        t = self.mapping._template(line, self.cute)
        self.assertEqual(t["jaPieces"][-1], {"lit": self.cute.tail, "id": self.style.TAIL_ID})
        self.assertEqual(t["jaPieces"][0]["id"], "S_then")

    def test_bad_style_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.toml"
            for text in ('[[rules]]\nmatch = "("\nreplace = "x"\n',
                         '[[rules]]\nmatch = "a$"\nreplace = "\\\\2"\n',
                         '[[rules]]\nmatch = "a$"\nreplace = "x"\nkinds = ["part"]\n'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(self.style.StyleError):
                    self.style.load(path)
            cfg = write_config(Path(tmp), 1, extra=["[post]", 'extra_filter = "anull;[a]anull"'])
            with self.assertRaises(ConfigError):
                config.load(cfg)

    def test_raise_ending_skips_unvoiced(self):
        from voicegen.voicevox import raise_ending
        query = {"accent_phrases": [{"moras": [{"pitch": 5.0}, {"pitch": 5.0}, {"pitch": 0.0}]}]}
        raise_ending(query, 0.2, 2)
        pitches = [m["pitch"] for m in query["accent_phrases"][0]["moras"]]
        self.assertAlmostEqual(pitches[0], 5.1)
        self.assertAlmostEqual(pitches[1], 5.2)
        self.assertEqual(pitches[2], 0.0)


if __name__ == "__main__":
    unittest.main()
