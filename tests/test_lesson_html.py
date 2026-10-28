# -*- coding: utf-8 -*-
"""lesson_html.py 的单元测试。"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lesson_html as lh  # noqa: E402


SAMPLE = """---
course: 计算机组成原理
unit: 4
title: 进位计数制
date: 2026-10-28
status: 已完成
tags: [进制, 位权]
objectives:
  - 理解位权
  - 掌握转换
review_at: 2000-01-01
sources:
  - 王道教材
state_id: U4
description: 从位权展开出发理解进制转换。
---

# 进位计数制

## 为什么需要进制

计算机只认识 0 和 1。**进制只是写法不同**。

::: definition 基数
一个进制允许使用的数字个数。
:::

::: example 345
`345 = 3×10² + 4×10¹ + 5×10⁰`
:::

| 转换 | 方法 |
|------|------|
| 二 → 十 | 位权求和 |
| 十 → 二 | 除基取余 |

::: warning 常见错误
不要混淆基数和位权。
:::

::: answer 参考答案
答案是 **D6.A**。
:::

::: summary 小结
- 位权展开
- 分组转换
:::
"""


class FrontmatterTests(unittest.TestCase):
    def test_scalars_lists_and_block_scalar(self):
        text = """---
title: "测试: 标题"
unit: 04
description: >
  第一行
  第二行
tags: [a, "b c"]
objectives:
  - 目标一
  - "目标二"
---
正文
"""
        meta, body = lh.parse_frontmatter(text)
        self.assertEqual(meta["title"], "测试: 标题")
        self.assertEqual(meta["unit"], 4)
        self.assertEqual(meta["description"], "第一行 第二行")
        self.assertEqual(meta["tags"], ["a", "b c"])
        self.assertEqual(meta["objectives"], ["目标一", "目标二"])
        self.assertEqual(body.strip(), "正文")

    def test_no_frontmatter(self):
        meta, body = lh.parse_frontmatter("just text")
        self.assertEqual(meta, {})
        self.assertEqual(body, "just text")


class MarkdownTests(unittest.TestCase):
    def test_headings_toc_and_leading_h1(self):
        meta, content, headings = lh.render_markdown("# 标题\n\n## 第一节\n\n### 小节")
        self.assertIn('<h2 id="sec-1">第一节</h2>', content)
        self.assertIn('<h3 id="sec-2">小节</h3>', content)
        self.assertEqual([h["text"] for h in headings], ["第一节", "小节"])
        self.assertNotIn(">标题<", content)

    def test_inline_escaping_and_safe_links(self):
        _, content, _ = lh.render_markdown(
            'Hello <script>alert(1)</script> [x](javascript:alert(1)) `a<b`'
        )
        self.assertNotIn("<script>", content)
        self.assertIn("&lt;script&gt;", content)
        self.assertIn('href="#"', content)
        self.assertIn("<code>a&lt;b</code>", content)

    def test_table_and_alignment(self):
        _, content, _ = lh.render_markdown(
            "| 左 | 中 | 右 |\n|:---|:---:|---:|\n| a | b | c |"
        )
        self.assertIn("<table>", content)
        self.assertIn('style="text-align:left"', content)
        self.assertIn('style="text-align:center"', content)
        self.assertIn('style="text-align:right"', content)

    def test_callouts_and_answers(self):
        _, content, _ = lh.render_markdown(
            "::: definition 基数\n定义内容\n:::\n\n::: answer\n答案内容\n:::"
        )
        self.assertIn('class="callout definition"', content)
        self.assertIn('class="callout-title"', content)
        self.assertIn('<details class="answer">', content)
        self.assertIn("答案内容", content)

    def test_nested_callout(self):
        _, content, _ = lh.render_markdown(
            "::: note 外层\n外层\n\n::: warning 内层\n内层\n:::\n:::"
        )
        self.assertIn('class="callout note"', content)
        self.assertIn('class="callout warning"', content)
        self.assertIn("内层", content)

    def test_nested_lists(self):
        _, content, _ = lh.render_markdown(
            "- A\n  - A1\n  - A2\n    - A3\n- B\n1. 一\n2. 二"
        )
        self.assertIn("<ul><li>A<ul><li>A1</li>", content)
        self.assertIn("<li>A3</li>", content)
        self.assertIn("<ol><li>一</li>", content)

    def test_code_and_svg(self):
        _, content, _ = lh.render_markdown(
            "```python\nprint('<x>')\n```\n\n```svg\n<svg></svg>\n```"
        )
        self.assertIn('class="code language-python"', content)
        self.assertIn("print(&#x27;&lt;x&gt;&#x27;)", content.replace("'", "&#x27;"))
        self.assertIn('<figure class="diagram"><svg></svg></figure>', content)

    def test_inline_math(self):
        _, content, _ = lh.render_markdown("任意 $r$ 进制数")
        self.assertIn('<span class="math">r</span>', content)


class UtilityTests(unittest.TestCase):
    def test_safe_component(self):
        self.assertEqual(lh.safe_component('a/b:c*?"<>|'), "a-b-c------")
        self.assertEqual(lh.safe_component("CON"), "_CON")
        self.assertEqual(lh.safe_component("  "), "course")

    def test_unit_file_stem(self):
        self.assertEqual(lh.unit_file_stem(4, "进位计数制"), "unit-04-进位计数制")
        self.assertEqual(lh.unit_file_stem("U1-2", "进程"), "unit-u1-2-进程")


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out = self.root / "讲义"

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_build_creates_html_and_index(self):
        src = self._write("unit-04.md", SAMPLE)
        result = lh.build_lesson("计算机组成原理", src, self.out, quiet=True)
        html_path = result["html"]
        index_path = result["index"]
        self.assertTrue(html_path.exists())
        self.assertTrue(index_path.exists())
        page = html_path.read_text(encoding="utf-8")
        self.assertIn("进位计数制", page)
        self.assertIn('class="callout definition"', page)
        self.assertIn('<details class="answer">', page)
        self.assertIn("<table>", page)
        self.assertNotIn("__TITLE__", page)
        self.assertNotIn("<script>alert", page)
        index = index_path.read_text(encoding="utf-8")
        self.assertIn("进位计数制", index)
        self.assertIn("该复习了", index)  # review_at 是 2000 年，已到期
        self.assertIn("unit-04-进位计数制.html", index)
        # 源文件被复制到输出目录，供 rebuild 使用
        self.assertTrue((html_path.parent / "unit-04-进位计数制.md").exists())

    def test_build_two_units_sorted_and_navigation(self):
        src4 = self._write("unit-04.md", SAMPLE)
        src5 = self._write(
            "unit-05.md",
            "---\ncourse: 计算机组成原理\nunit: 5\ntitle: 定点数编码\n---\n\n## 内容\n",
        )
        lh.build_lesson("计算机组成原理", src5, self.out, quiet=True)
        result4 = lh.build_lesson("计算机组成原理", src4, self.out, quiet=True)
        lh.rebuild_course("计算机组成原理", self.out, quiet=True)
        page4 = result4["html"].read_text(encoding="utf-8")
        self.assertIn("下一单元", page4)
        self.assertIn("定点数编码", page4)
        page5 = (self.out / "计算机组成原理" / "unit-05-定点数编码.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("上一单元", page5)
        index = (self.out / "计算机组成原理" / "index.html").read_text(encoding="utf-8")
        self.assertLess(index.find("进位计数制"), index.find("定点数编码"))

    def test_state_mapping(self):
        src = self._write("unit-04.md", SAMPLE)
        state_path = self._write(
            "state.json",
            json.dumps(
                {
                    "route": {
                        "units": [
                            {"id": "U4", "title": "进位计数制", "status": "in_progress"}
                        ]
                    },
                    "progress": {
                        "overall_percent": 40,
                        "completed_units": [],
                    },
                },
                ensure_ascii=False,
            ),
        )
        result = lh.build_lesson(
            "计算机组成原理", src, self.out, state_path=state_path, quiet=True
        )
        index = result["index"].read_text(encoding="utf-8")
        self.assertIn("进行中", index)
        self.assertIn("完成度 40%", index)

    def test_malformed_state_is_tolerated(self):
        src = self._write("unit-04.md", SAMPLE)
        state_path = self._write("state.json", "{not valid json")
        with redirect_stderr(io.StringIO()) as err:
            result = lh.build_lesson(
                "计算机组成原理", src, self.out, state_path=state_path, quiet=True
            )
        self.assertTrue(result["html"].exists())
        self.assertIn("解析失败", err.getvalue())

    def test_rebuild_and_index(self):
        src = self._write("unit-04.md", SAMPLE)
        lh.build_lesson("计算机组成原理", src, self.out, quiet=True)
        html_path = self.out / "计算机组成原理" / "unit-04-进位计数制.html"
        html_path.write_text("stale", encoding="utf-8")
        built = lh.rebuild_course("计算机组成原理", self.out, quiet=True)
        self.assertEqual(len(built), 1)
        self.assertIn("进位计数制", built[0].read_text(encoding="utf-8"))
        index_path = lh.rebuild_index_only("计算机组成原理", self.out, quiet=True)
        self.assertIn("进位计数制", index_path.read_text(encoding="utf-8"))

    def test_empty_index(self):
        course_dir = self.out / "空课程"
        course_dir.mkdir(parents=True)
        path = lh.rebuild_index_only("空课程", self.out, quiet=True)
        text = path.read_text(encoding="utf-8")
        self.assertIn("还没有讲义", text)

    def test_deck_layout_with_quiz(self):
        src = self._write(
            "unit-06.md",
            """---
course: 计算机组成原理
unit: 6
title: 乘法器
layout: deck
kind: lesson
---
## 第一步
概念一
## 第二步
概念二

```quiz
{"questions":[{"id":"Q1","type":"choice","prompt":"选哪个？","options":["甲","乙"],"answer":"B"}]}
```
""",
        )
        result = lh.build_lesson(
            "计算机组成原理",
            src,
            self.out,
            quiet=True,
            server_url="http://127.0.0.1:9999",
            api_path="/teacher/api/answers",
            workspace="TeacherSkillEditor",
        )
        page = result["html"].read_text(encoding="utf-8")
        self.assertIn('<body class="layout-deck">', page)
        self.assertIn('class="deck"', page)
        self.assertIn('data-total="3"', page)
        self.assertIn('class="deck-step', page)
        self.assertIn('class="quiz-card"', page)
        self.assertIn('data-server-url="http://127.0.0.1:9999"', page)
        self.assertIn('data-api-path="/teacher/api/answers"', page)
        self.assertIn('data-workspace="TeacherSkillEditor"', page)
        self.assertIn('id="back-to-chat"', page)
        self.assertIn("indexOf('/teacher/')", page)
        self.assertIn('data-qid="Q1"', page)
        self.assertNotIn("language-quiz", page)
        self.assertNotIn("<!--QUIZ-->", page)

    def test_normalize_api_path_repairs_msys_rewrite(self):
        self.assertEqual(lh.normalize_api_path("/teacher/api/answers"), "/teacher/api/answers")
        self.assertEqual(
            lh.normalize_api_path(r"C:/Users/wake/.dsh/profiles/web/node_modules/x/teacher/api/answers"),
            "/teacher/api/answers",
        )
        self.assertEqual(lh.normalize_api_path("teacher/api/answers"), "/teacher/api/answers")

    def test_article_layout_keeps_long_page(self):
        src = self._write(
            "unit-07.md",
            """---
course: 计算机组成原理
unit: 7
title: 浮点数
layout: article
kind: lesson
---
## 概念
正文
""",
        )
        result = lh.build_lesson("计算机组成原理", src, self.out, quiet=True)
        page = result["html"].read_text(encoding="utf-8")
        self.assertIn('<body class="layout-article">', page)
        self.assertNotIn('<div class="deck"', page)
        self.assertIn('class="toc"', page)

    def test_vivid_diagrams_and_interactions(self):
        src = self._write(
            "unit-08.md",
            """---
course: 计算机组成原理
unit: 8
title: 图示
layout: deck
kind: lesson
---
## 流程

::: flow 取指到写回
取指 → 译码 → 执行 → 写回
:::

::: layers 存储层次
CPU | 快
内存 | 慢
:::

::: timeline 发展
1946 | ENIAC
1952 | EDVAC
:::

::: cycle 指令周期
取指 → 译码 → 执行 → 写回
:::

::: compare 两种结构
| 维度 | A | B |
|---|---|---|
| 存储 | 同存 | 分开 |
:::

::: bars 性能
A: 10
B: 20
:::

::: hint 想一想
先想一想。
:::

::: flip 位权
位权是什么？
---
基数的幂。
:::
""",
        )
        result = lh.build_lesson("计算机组成原理", src, self.out, quiet=True)
        page = result["html"].read_text(encoding="utf-8")
        for marker in [
            "diagram-flow",
            "flow-node",
            "diagram-layers",
            "layer-name",
            "diagram-timeline",
            "timeline-date",
            "diagram-cycle",
            "cycle-edge",
            "diagram-compare",
            "diagram-bars",
            "bar-fill",
            "details class=\"hint\"",
            "flip-card",
        ]:
            self.assertIn(marker, page)

    def test_mastery_index_and_practice_sheet(self):
        src = self._write("unit-04.md", SAMPLE)
        state_path = self._write(
            "state.json",
            json.dumps(
                {
                    "progress": {"overall_percent": 30},
                    "mastery": {
                        "concepts": {
                            "进位计数制": {
                                "name": "进位计数制",
                                "unit": "U4",
                                "level": 2,
                                "variant_passed": False,
                                "next_review_at": "2000-01-01",
                            },
                            "分组转换": {
                                "name": "分组转换",
                                "unit": "U4",
                                "level": 0,
                                "variant_passed": False,
                                "next_review_at": "2000-01-01",
                            },
                        },
                        "next_action": {
                            "type": "reteach",
                            "target": "分组转换",
                            "unit": "U4",
                            "reason": "最近一次未通过",
                        },
                    },
                },
                ensure_ascii=False,
            ),
        )
        lh.build_lesson(
            "计算机组成原理", src, self.out, state_path=state_path, quiet=True
        )
        practice = self._write(
            "practice.md",
            """---
course: 计算机组成原理
unit: 4
title: 进位计数制练习
kind: practice
parent_unit: 4
status: 待复习
review_at: 2000-01-01
state_id: U4
---
## 练习
::: answer
答案
:::
""",
        )
        result = lh.build_lesson(
            "计算机组成原理", practice, self.out, state_path=state_path, quiet=True
        )
        self.assertTrue(result["html"].name.startswith("practice-04-"))
        index = result["index"].read_text(encoding="utf-8")
        self.assertIn("薄弱知识点", index)
        self.assertIn("AI 建议下一步", index)
        self.assertIn("练习卷 1 份", index)
        self.assertIn('data-kind="practice"', index)
        lesson = (self.out / "计算机组成原理" / "unit-04-进位计数制.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("掌握度：Lv2", lesson)


if __name__ == "__main__":
    unittest.main()
