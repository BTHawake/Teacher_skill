#!/usr/bin/env python3
"""Detect where a course deck should be hosted.

Priority:
  1. DSH host plugin (same-origin /teacher on the DSH web server)
  2. An already-running teacher.skill course server
  3. A free local port for a new course server

The script only inspects/starts nothing; it prints the decision and the exact
commands/URL the caller should use. This keeps the decision in the skill and
the actual plugin code in the separate dsh-Teacher-skill repository.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

PLUGIN_NAME = "dsh-teacher-skill"
DEFAULT_DSH_URLS = ("http://127.0.0.1:3080",)
DEFAULT_SERVER_URLS = ("http://127.0.0.1:8765",)
INSTALL_REPO = "git@github.com:BTHawake/dsh-Teacher-skill.git"


def _json_get(url: str, timeout: float = 1.0) -> Dict[str, Any] | None:
    try:
        request = Request(url, headers={"accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, dict) else None
    except (URLError, OSError, ValueError, UnicodeError):
        return None


def _candidate_dsh_urls(explicit: str = "") -> List[str]:
    urls: List[str] = []
    if explicit:
        urls.append(explicit)
    for key in ("DSH_WEB_PUBLIC_URL", "DSH_WEB_URL", "DSH_WEB_GUI_URL", "DSH_URL"):
        value = os.environ.get(key)
        if value:
            urls.append(value)
    urls.extend(DEFAULT_DSH_URLS)
    seen = set()
    result = []
    for url in urls:
        normalized = url.rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _candidate_server_urls(explicit: str = "") -> List[str]:
    urls: List[str] = []
    if explicit:
        urls.append(explicit)
    env = os.environ.get("DSH_TEACHER_SERVER_URL")
    if env:
        urls.append(env)
    urls.extend(DEFAULT_SERVER_URLS)
    seen = set()
    result = []
    for url in urls:
        normalized = url.rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_ok(url: str, timeout: float = 1.0) -> bool:
    try:
        request = Request(url, headers={"accept": "text/html"})
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except HTTPError as error:
        return error.code in (401, 403)
    except (URLError, OSError, ValueError):
        return False


def _safe_name(value: str) -> str:
    return value.strip().replace("/", "-").replace("\\", "-") or "workspace"


def _public_base(value: str) -> str:
    text = str(value or "").strip().rstrip("/")
    if text.startswith(("http://", "https://")):
        return text
    return ""


def _install_info() -> Dict[str, Any]:
    return {
        "repo": INSTALL_REPO,
        "hint": "On DSH, install the host plugin once if you want /teacher on the existing port.",
        "command": "git clone %s && dsh plugin --profile web add link:<plugin-dir>" % INSTALL_REPO,
        "restart": True,
    }


def _server_result(course: str, workspace: str, server_url: str, encoded_course: str, public_base: str) -> Dict[str, Any]:
    link = "/%s/index.html" % encoded_course
    for base in _candidate_server_urls(server_url):
        health = _json_get(urljoin(base + "/", "api/health"))
        if health and health.get("ok"):
            result = {
                "mode": "course-server",
                "reason": "A teacher.skill course server is already running.",
                "server_url": base,
                "workspace": workspace,
                "course": course,
                "api_path": "/api/answers",
                "link": link,
                "local_url": base + link,
                "plugin": None,
                "install_required": False,
                "temporary": False,
                "recommended": "course-server",
            }
            if public_base:
                result["public_url"] = public_base + link
            return result

    port = _free_port()
    base = "http://127.0.0.1:%d" % port
    result = {
        "mode": "course-server",
        "reason": "No running course server found; start a local server on a free port.",
        "server_url": base,
        "workspace": workspace,
        "course": course,
        "api_path": "/api/answers",
        "link": link,
        "local_url": base + link,
        "suggested_port": port,
        "start_command": (
            'python scripts/course_server.py --course "%s" --port %d'
            % (course, port)
        ),
        "plugin": None,
        "install_required": True,
        "temporary": False,
        "recommended": "course-server",
        "install": _install_info(),
    }
    if public_base:
        result["public_url"] = public_base + link
    return result


def detect(course: str, workspace: str, dsh_url: str = "", server_url: str = "", public_base: str = "") -> Dict[str, Any]:
    workspace = _safe_name(workspace)
    course = _safe_name(course)
    public_base = _public_base(public_base)
    encoded_workspace = quote(workspace, safe="")
    encoded_course = quote(course, safe="")
    relative_link = "/teacher/%s/%s/index.html" % (encoded_workspace, encoded_course)

    dsh_bases = _candidate_dsh_urls(dsh_url)
    for base in dsh_bases:
        health = _json_get(urljoin(base + "/", "teacher/api/health"))
        if health and health.get("plugin") == PLUGIN_NAME and health.get("ok"):
            workspaces = health.get("workspaces")
            needs_register = False
            if isinstance(workspaces, list) and workspace not in workspaces:
                # Legacy installs may still use a single workspaceRoot and list no workspaces.
                if not (health.get("configured") and not workspaces):
                    needs_register = True
            if needs_register:
                result = {
                    "mode": "dsh-plugin-register-required",
                    "reason": "DSH plugin is mounted, but this workspace is not registered.",
                    "dsh_url": base,
                    "workspace": workspace,
                    "course": course,
                    "api_path": health.get("prefix", "/teacher") + "/api/answers",
                    "link": relative_link,
                    "local_url": base + relative_link,
                    "plugin": health,
                    "install_required": False,
                    "register_required": True,
                    "temporary": False,
                    "recommended": "register-workspace",
                    "register_command": (
                        'python scripts/dsh_register.py --workspace-root "$PWD" --workspace "%s"'
                        % workspace
                    ),
                    "chat_hint": "插件已安装，但当前 workspace 还没注册；先运行 dsh_register.py，再生成链接。",
                }
                if public_base:
                    result["public_url"] = public_base + relative_link
                return result
            result = {
                "mode": "dsh-plugin",
                "reason": "DSH teacher plugin is already mounted; use the same DSH origin.",
                "dsh_url": base,
                "workspace": workspace,
                "course": course,
                "api_path": health.get("prefix", "/teacher") + "/api/answers",
                "link": relative_link,
                "local_url": base + relative_link,
                "plugin": health,
                "install_required": False,
                "register_required": False,
                "temporary": False,
                "recommended": "dsh-plugin",
            }
            if public_base:
                result["public_url"] = public_base + relative_link
            return result

    server = _server_result(course, workspace, server_url, encoded_course, public_base)
    dsh_base = next((base for base in dsh_bases if _http_ok(base + "/")), "")
    if dsh_base:
        result = {
            "mode": "dsh-plugin-missing",
            "reason": "DSH web is reachable, but the /teacher plugin is not mounted.",
            "dsh_url": dsh_base,
            "workspace": workspace,
            "course": course,
            "api_path": "/teacher/api/answers",
            "link": relative_link,
            "local_url": dsh_base + relative_link,
            "plugin": None,
            "install_required": True,
            "temporary": True,
            "recommended": "install-plugin",
            "chat_hint": "检测到你在 DSH 上，但 /teacher 插件还没装。8765 只是临时回退，需要额外端口转发；装插件后链接直接跟着 DSH 域名走。要现在装吗？（安装需要重启一次 DSH）",
            "install": _install_info(),
            "fallback": {**server, "temporary": True},
        }
        if public_base:
            result["public_url"] = public_base + relative_link
        return result
    return server


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect the best host for a teacher.skill course deck.")
    parser.add_argument("--course", required=True, help="课程名")
    parser.add_argument("--workspace", default="", help="工作区目录名（默认取 workspace-root 的目录名）")
    parser.add_argument("--workspace-root", default="", help="课程工作区根目录（默认 pwd）；AI 自己判断")
    parser.add_argument("--dsh-url", default="", help="DSH Web 地址（默认探测 127.0.0.1:3080）")
    parser.add_argument("--server-url", default="", help="已有 course_server 地址")
    parser.add_argument("--public-base", default="", help="远程 DSH 的公网根地址，如 https://dsh.example.com；不填只输出根相对链接")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    workspace_root = Path(args.workspace_root or Path.cwd()).expanduser()
    if not workspace_root.exists() or not workspace_root.is_dir():
        result = {"ok": False, "mode": "invalid-workspace", "error": "workspace root 不存在：%s" % workspace_root}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "ERROR: %s" % result["error"])
        return 2
    workspace = args.workspace or workspace_root.name
    public_base = args.public_base or os.environ.get("DSH_WEB_PUBLIC_URL") or os.environ.get("DSH_PUBLIC_URL") or ""
    result = detect(args.course, workspace, args.dsh_url, args.server_url, public_base)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("mode: %s" % result["mode"])
        print("reason: %s" % result["reason"])
        print("link: %s" % result.get("link", ""))
        if result.get("chat_hint"):
            print("hint: %s" % result["chat_hint"])
        if result.get("public_url"):
            print("public: %s" % result["public_url"])
        if result.get("local_url"):
            print("local (only this machine): %s" % result["local_url"])
        if result.get("start_command"):
            print("start: %s" % result["start_command"])
        if result.get("install_required") and result.get("install"):
            print("plugin: %s" % result["install"]["repo"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
