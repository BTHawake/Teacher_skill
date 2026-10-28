# -*- coding: utf-8 -*-
"""verify_page.py 的本地/HTTP 验活测试。"""

import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_page  # noqa: E402

PAGE = """<!DOCTYPE html>
<html><head><title>第 4 单元 · 计算机组成原理</title></head>
<body><div class="deck"><div class="quiz-card"></div></div></body></html>
"""


class VerifyPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "unit.html"
        self.path.write_text(PAGE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_file_ok(self):
        result = verify_page.verify_file(self.path)
        self.assertTrue(result["ok"], result)
        self.assertIn("第 4 单元", result["title"])

    def test_file_missing_closing_tag(self):
        self.path.write_text("<html><body>broken", encoding="utf-8")
        result = verify_page.verify_file(self.path)
        self.assertFalse(result["ok"])
        self.assertTrue(any("未闭合" in error for error in result["errors"]))

    def test_file_missing(self):
        result = verify_page.verify_file(Path(self.tmp.name) / "nope.html")
        self.assertFalse(result["ok"])

    def test_http_ok_and_404(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/ok":
                    body = PAGE.encode("utf-8")
                    self.send_response(200)
                    self.send_header("content-type", "text/html; charset=utf-8")
                    self.send_header("content-length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            ok = verify_page.verify_url("http://127.0.0.1:%d/ok" % port, "第 4 单元")
            self.assertTrue(ok["ok"], ok)
            missing = verify_page.verify_url("http://127.0.0.1:%d/missing" % port)
            self.assertFalse(missing["ok"])
            self.assertEqual(missing["status"], 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
