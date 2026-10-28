#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""teacher.skill v4.0 - 本地课件与答题提交服务。

做两件事：

1. 把 ``讲义/{课程}/`` 作为静态网站提供，浏览器打开课件链接即可学习
2. 接收课件答题卡的 POST ``/api/answers``，把答案写入
   ``讲义/{课程}/answers/latest.json``，供 AI 读取、批改、记录掌握度

用法（在工作区根目录）：

    python scripts/course_server.py --course "计算机组成原理"
    # 浏览器打开 http://127.0.0.1:8765/

    # 换端口 / 换目录
    python scripts/course_server.py --course "计算机组成原理" --port 9000

只使用 Python 标准库，绑定 127.0.0.1，不对外网开放。
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from urllib.parse import urlparse

from lesson_html import DEFAULT_OUTPUT_DIR, VERSION, safe_component

MAX_BODY = 1_000_000


def _json_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _clean_unit(value: Any) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", str(value or "unit"))
    return text.strip("-_.")[:80] or "unit"


class CourseHandler(SimpleHTTPRequestHandler):
    """静态课件 + /api/answers 提交端点。"""

    answer_dir: Path
    course: str
    server_version = "TeacherCourse/" + VERSION
    sys_version = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("directory", str(self.answer_dir.parent))
        super().__init__(*args, **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/answers":
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._send_json(400, {"ok": False, "error": "invalid content length"})
            return
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        if not isinstance(data, dict) or not isinstance(data.get("answers"), list):
            self._send_json(400, {"ok": False, "error": "answers must be a list"})
            return
        answers = []
        for item in data.get("answers", [])[:50]:
            if not isinstance(item, dict):
                continue
            answers.append(
                {
                    "id": str(item.get("id") or "")[:40],
                    "value": str(item.get("value") or "")[:5000],
                }
            )
        unit = str(data.get("unit") or data.get("title") or "unit")
        now = datetime.now()
        record = {
            "schema": "teacher.skill/answers/v1",
            "course": str(data.get("course") or self.course),
            "unit": unit,
            "title": str(data.get("title") or ""),
            "answers": answers,
            "submitted_at": str(data.get("submitted_at") or now.isoformat(timespec="seconds")),
            "received_at": now.isoformat(timespec="seconds"),
        }
        self.answer_dir.mkdir(parents=True, exist_ok=True)
        latest = self.answer_dir / "latest.json"
        stamped = self.answer_dir / ("%s-%s.json" % (_clean_unit(unit), now.strftime("%Y%m%d-%H%M%S")))
        _json_write(latest, record)
        _json_write(stamped, record)
        self._send_json(
            200,
            {
                "ok": True,
                "path": str(latest),
                "count": len(answers),
            },
        )

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(200, {"ok": True, "service": "teacher.skill", "version": VERSION})
            return
        if path == "/api/answers/latest":
            latest = self.answer_dir / "latest.json"
            if not latest.exists():
                self._send_json(404, {"ok": False, "error": "no answers yet"})
                return
            try:
                payload = json.loads(latest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._send_json(500, {"ok": False, "error": "answer file unreadable"})
                return
            self._send_json(200, {"ok": True, "data": payload})
            return
        super().do_GET()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[course] " + (fmt % args) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="teacher.skill v%s - 提供 HTML 课件并接收答题卡提交" % VERSION
    )
    parser.add_argument("--course", required=True, help="课程名称，例如 计算机组成原理")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="讲义根目录（默认：讲义）")
    parser.add_argument("--course-dir", default=None, help="课程子目录名（默认取课程名）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=8765, help="端口（默认 8765；0 = 自动找空闲端口）")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    course_dir = Path(args.output_dir) / safe_component(args.course_dir or args.course)
    if not course_dir.exists():
        print(
            "[error] 课程目录不存在：%s\n先生成至少一个单元课件再启动服务。" % course_dir,
            file=sys.stderr,
        )
        return 2
    answer_dir = course_dir / "answers"
    handler = functools.partial(CourseHandler, directory=str(course_dir))
    CourseHandler.answer_dir = answer_dir
    CourseHandler.course = args.course
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        print("[error] 无法监听 %s:%s：%s" % (args.host, args.port, exc), file=sys.stderr)
        return 2
    actual_port = server.server_address[1]
    print("teacher.skill v%s 课件服务已启动" % VERSION)
    print("地址：http://%s:%d/" % (args.host, actual_port))
    print("答案文件：%s" % (answer_dir / "latest.json"))
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
