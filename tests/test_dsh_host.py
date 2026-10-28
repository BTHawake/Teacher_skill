# -*- coding: utf-8 -*-
"""dsh_host.py 的宿主决策测试（不启动真实服务）。"""

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dsh_host  # noqa: E402


class DshHostTests(unittest.TestCase):
    def test_prefers_dsh_plugin(self):
        def fake_get(url, timeout=1.0):
            if url.endswith("/teacher/api/health"):
                return {"ok": True, "plugin": "dsh-teacher-skill", "prefix": "/teacher"}
            return None

        with mock.patch.object(dsh_host, "_json_get", fake_get):
            result = dsh_host.detect("计算机组成原理", "TeacherSkillEditor", "http://127.0.0.1:3080")
        self.assertEqual(result["mode"], "dsh-plugin")
        self.assertEqual(result["api_path"], "/teacher/api/answers")
        self.assertTrue(result["link"].startswith("/teacher/TeacherSkillEditor/"))
        self.assertFalse(result["install_required"])

    def test_uses_running_course_server(self):
        def fake_get(url, timeout=1.0):
            if url.endswith("/api/health"):
                return {"ok": True, "service": "teacher.skill"}
            return None

        with mock.patch.object(dsh_host, "_json_get", fake_get):
            with mock.patch.object(dsh_host, "_http_ok", return_value=False):
                result = dsh_host.detect("计算机组成原理", "TeacherSkillEditor", "http://127.0.0.1:3080")
        self.assertEqual(result["mode"], "course-server")
        self.assertIn("/api/answers", result["api_path"])

    def test_falls_back_to_free_port_and_reports_install(self):
        with mock.patch.object(dsh_host, "_json_get", return_value=None):
            with mock.patch.object(dsh_host, "_http_ok", return_value=False):
                with mock.patch.object(dsh_host, "_free_port", return_value=18765):
                    result = dsh_host.detect("计算机组成原理", "TeacherSkillEditor", "http://127.0.0.1:3080")
        self.assertEqual(result["mode"], "course-server")
        self.assertEqual(result["suggested_port"], 18765)
        self.assertIn("--port 18765", result["start_command"])
        self.assertTrue(result["install_required"])
        self.assertIn("dsh-Teacher-skill", result["install"]["repo"])

    def test_reports_missing_plugin_when_dsh_is_reachable(self):
        with mock.patch.object(dsh_host, "_json_get", return_value=None):
            with mock.patch.object(dsh_host, "_http_ok", return_value=True):
                with mock.patch.object(dsh_host, "_free_port", return_value=18765):
                    result = dsh_host.detect("计算机组成原理", "TeacherSkillEditor", "http://127.0.0.1:3080")
        self.assertEqual(result["mode"], "dsh-plugin-missing")
        self.assertEqual(result["api_path"], "/teacher/api/answers")
        self.assertTrue(result["install_required"])
        self.assertEqual(result["fallback"]["mode"], "course-server")


if __name__ == "__main__":
    unittest.main()
