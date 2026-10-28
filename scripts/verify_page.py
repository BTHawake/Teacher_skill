#!/usr/bin/env python3
"""Verify that a generated course page exists and can actually be opened.

Two layers:
  1. local file integrity: exists, non-trivial size, complete HTML, title
  2. HTTP reachability: 200 + HTML + expected title (optional)

Boundary: this is not a browser. It does not execute JS, detect a blank
render, test remote DNS/auth, POST answers, or inspect the plugin registry.
Those need a browser, a real submission, or dsh_host.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MAX_FILE_BYTES = 8 * 1024 * 1024


def _title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()


def verify_file(path: Path) -> Dict[str, Any]:
    errors = []
    warnings = []
    if not path.exists():
        return {"ok": False, "errors": ["文件不存在"], "warnings": warnings, "title": "", "size": 0}
    if not path.is_file():
        return {"ok": False, "errors": ["不是普通文件"], "warnings": warnings, "title": "", "size": 0}
    size = path.stat().st_size
    if size == 0:
        errors.append("文件为空")
    if size > MAX_FILE_BYTES:
        warnings.append("文件超过 8MB，可能不是单页课件")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "errors": ["读取失败：%s" % exc], "warnings": warnings, "title": "", "size": size}

    lowered = text.lower()
    if "<!doctype html" not in lowered and "<html" not in lowered:
        errors.append("缺少 HTML 根结构")
    if "</html>" not in lowered:
        errors.append("HTML 未闭合（缺少 </html>）")
    if "</body>" not in lowered:
        errors.append("HTML 未闭合（缺少 </body>）")
    if 'class="deck"' not in text and 'class="lesson' not in text and 'class="quiz-card"' not in text:
        warnings.append("没有检测到课件/答题卡结构，可能不是 teacher.skill 页面")
    title = _title(text)
    if not title:
        warnings.append("没有 <title>")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "title": title,
        "size": size,
    }


def _request(url: str, timeout: float):
    encoded = quote(url, safe=":/?#[]@!$&'()*+,;=%")
    request = Request(encoded, headers={"accept": "text/html"})
    return urlopen(request, timeout=timeout)


def verify_url(url: str, expected_title: str = "", timeout: float = 5.0) -> Dict[str, Any]:
    errors = []
    warnings = []
    status = 0
    content_type = ""
    title = ""
    try:
        with _request(url, timeout) as response:
            status = response.status
            content_type = response.headers.get("content-type", "")
            body = response.read(MAX_FILE_BYTES).decode("utf-8", errors="replace")
    except HTTPError as exc:
        status = exc.code
        errors.append("HTTP %s" % exc.code)
    except (URLError, OSError, ValueError) as exc:
        errors.append("请求失败：%s" % exc)
    else:
        if status != 200:
            errors.append("HTTP %s（不是 200）" % status)
        if "text/html" not in content_type.lower():
            errors.append("content-type 不是 HTML：%s" % (content_type or "空"))
        if "<html" not in body.lower():
            errors.append("响应不是完整 HTML")
        title = _title(body)
        if expected_title and expected_title not in title:
            errors.append("标题不匹配：页面为 %r，期望包含 %r" % (title, expected_title))
        if not title:
            warnings.append("页面没有 <title>")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "status": status,
        "content_type": content_type,
        "title": title,
        "url": url,
    }


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a generated teacher.skill page can be opened.")
    parser.add_argument("--file", required=True, help="生成的 HTML 路径")
    parser.add_argument("--url", default="", help="要验证的 HTTP 地址（可选）")
    parser.add_argument("--title", default="", help="期望页面标题包含的文字（可选）")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    file_result = verify_file(path)
    url_result = None
    if args.url:
        url_result = verify_url(args.url, args.title or file_result.get("title", ""), args.timeout)

    result = {
        "ok": bool(file_result["ok"] and (url_result is None or url_result["ok"])),
        "file": file_result,
        "url": url_result,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("file: %s" % ("OK" if file_result["ok"] else "FAIL"))
        print("path: %s" % path)
        print("title: %s" % (file_result.get("title") or "(none)"))
        for error in file_result["errors"]:
            print("  ! %s" % error)
        if url_result is not None:
            print("url: %s" % ("OK" if url_result["ok"] else "FAIL"))
            print("  %s" % args.url)
            for error in url_result["errors"]:
                print("  ! %s" % error)
        print("RESULT: %s" % ("PASS" if result["ok"] else "FAIL"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
