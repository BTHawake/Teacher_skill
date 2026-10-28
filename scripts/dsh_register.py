#!/usr/bin/env python3
"""Register the current workspace for the dsh-Teacher-skill plugin.

The AI decides the workspace root (usually `pwd`); this script persists that
decision into ~/.dsh/teacher-workspaces.json. The plugin only serves roots
listed there, so the AI never needs to hardcode a machine path.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def dsh_home() -> Path:
    return Path(os.environ.get("DSH_HOME") or (Path.home() / ".dsh"))


def registry_path(explicit: str = "") -> Path:
    return Path(explicit).expanduser() if explicit else dsh_home() / "teacher-workspaces.json"


def load(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def safe_name(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and text not in (".", "..") and "/" not in text and "\\" not in text


def register(registry: Path, workspace: str, root: Path) -> Dict[str, Any]:
    if not safe_name(workspace):
        raise ValueError("workspace name must be a single path segment")
    if not root.exists() or not root.is_dir():
        raise ValueError("workspace root does not exist: %s" % root)
    data = load(registry)
    workspaces = data.get("workspaces")
    if not isinstance(workspaces, dict):
        workspaces = {}
    workspaces[workspace] = str(root.resolve())
    data["workspaces"] = workspaces
    registry.parent.mkdir(parents=True, exist_ok=True)
    temp = registry.with_name(registry.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(registry)
    return {"ok": True, "registry": str(registry), "workspace": workspace, "root": str(root.resolve())}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Register a workspace for dsh-Teacher-skill.")
    parser.add_argument("--workspace-root", default=str(Path.cwd()), help="课程工作区根目录（默认 pwd）")
    parser.add_argument("--workspace", default="", help="URL 里的 workspace 名（默认目录名）")
    parser.add_argument("--registry", default="", help="注册表路径（默认 $DSH_HOME/teacher-workspaces.json）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.workspace_root).expanduser()
    workspace = args.workspace or root.name
    path = registry_path(args.registry)
    try:
        result = register(path, workspace, root)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) if args.json else "ERROR: %s" % exc)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("registered: %s -> %s" % (result["workspace"], result["root"]))
        print("registry:   %s" % result["registry"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
