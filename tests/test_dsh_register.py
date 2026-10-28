# -*- coding: utf-8 -*-
"""dsh_register.py 的注册表测试。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dsh_register  # noqa: E402


class DshRegisterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "操作系统"
        self.root.mkdir()
        self.registry = Path(self.tmp.name) / "teacher-workspaces.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_creates_registry(self):
        result = dsh_register.register(self.registry, "操作系统", self.root)
        self.assertTrue(result["ok"])
        data = json.loads(self.registry.read_text(encoding="utf-8"))
        self.assertEqual(data["workspaces"]["操作系统"], str(self.root.resolve()))

    def test_register_updates_existing_workspace(self):
        dsh_register.register(self.registry, "操作系统", self.root)
        other = Path(self.tmp.name) / "计算机组成原理"
        other.mkdir()
        dsh_register.register(self.registry, "计算机组成原理", other)
        data = json.loads(self.registry.read_text(encoding="utf-8"))
        self.assertIn("操作系统", data["workspaces"])
        self.assertIn("计算机组成原理", data["workspaces"])

    def test_rejects_unsafe_workspace_name(self):
        with self.assertRaises(ValueError):
            dsh_register.register(self.registry, "../evil", self.root)


if __name__ == "__main__":
    unittest.main()
