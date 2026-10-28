# -*- coding: utf-8 -*-
"""course_server.py 的单元测试。"""

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import course_server  # noqa: E402


class CourseServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "index.html").write_text("ok", encoding="utf-8")
        course_server.CourseHandler.answer_dir = self.root / "answers"
        course_server.CourseHandler.course = "测试课程"
        self.server = course_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), course_server.CourseHandler
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def _url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)

    def test_health_and_index(self):
        with urllib.request.urlopen(self._url("/api/health")) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertTrue(data["ok"])
        with urllib.request.urlopen(self._url("/index.html")) as response:
            self.assertEqual(response.read().decode("utf-8"), "ok")

    def test_submit_answers(self):
        payload = {
            "course": "测试课程",
            "unit": "4",
            "title": "进位计数制",
            "answers": [
                {"id": "Q1", "value": "B"},
                {"id": "Q2", "value": "11001000"},
            ],
        }
        request = urllib.request.Request(
            self._url("/api/answers"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
        self.assertTrue(result["ok"])
        latest = json.loads(
            (self.root / "answers" / "latest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(latest["schema"], "teacher.skill/answers/v1")
        self.assertEqual(latest["unit"], "4")
        self.assertEqual(len(latest["answers"]), 2)
        self.assertEqual(latest["answers"][0]["value"], "B")
        with urllib.request.urlopen(self._url("/api/answers/latest")) as response:
            fetched = json.loads(response.read().decode("utf-8"))
        self.assertEqual(fetched["data"]["unit"], "4")

    def test_rejects_bad_payload(self):
        request = urllib.request.Request(
            self._url("/api/answers"),
            data=b"not-json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
        else:
            self.fail("expected HTTP 400")


if __name__ == "__main__":
    unittest.main()
