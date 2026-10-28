#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""teacher.skill v3.0 - HTML 讲义 / 练习导出器。

把 AI 老师写好的 Markdown 讲义渲染成不依赖网络的单文件 HTML，并维护一个
课程总目录 index.html，方便课后复习。

用法（在工作区根目录执行）：

    python scripts/lesson_html.py build --course "计算机组成原理" \
        --file "讲义/计算机组成原理/unit-04-进位计数制.md" \
        --state "teachers/计算机组成原理/learning-state.json"

    python scripts/lesson_html.py rebuild --course "计算机组成原理" \
        --state "teachers/计算机组成原理/learning-state.json"

    python scripts/lesson_html.py index --course "计算机组成原理"

输出目录默认是工作区顶层的 ``讲义/<课程>/``。每个单元生成：

    unit-04-进位计数制.md     # 源文件（可再次编辑 / rebuild）
    unit-04-进位计数制.html   # 自包含页面（讲义 + 练习 + 折叠答案）
    index.html                # 课程目录 / 复习入口

只使用 Python 标准库，兼容 Python 3.9+。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

VERSION = "3.0.0"
DEFAULT_OUTPUT_DIR = "讲义"
DEFAULT_STATE_GLOB = "teachers/*/learning-state.json"

CALLOUTS: Dict[str, Dict[str, str]] = {
    "definition": {"label": "定义", "icon": "§", "class": "definition"},
    "example": {"label": "例子", "icon": "▸", "class": "example"},
    "warning": {"label": "注意", "icon": "!", "class": "warning"},
    "tip": {"label": "技巧", "icon": "★", "class": "tip"},
    "note": {"label": "补充", "icon": "·", "class": "note"},
    "summary": {"label": "小结", "icon": "✓", "class": "summary"},
    "keypoint": {"label": "要点", "icon": "◆", "class": "keypoint"},
    "source": {"label": "来源", "icon": "↗", "class": "source"},
    "formula": {"label": "公式", "icon": "ƒ", "class": "formula"},
    "practice": {"label": "练习", "icon": "✎", "class": "practice"},
    "answer": {"label": "参考答案", "icon": "?", "class": "answer"},
    "exam": {"label": "考点", "icon": "◆", "class": "exam"},
}

STATUS_LABELS = {
    "completed": "已完成",
    "complete": "已完成",
    "done": "已完成",
    "pass": "已完成",
    "已完成": "已完成",
    "in_progress": "进行中",
    "in-progress": "进行中",
    "进行中": "进行中",
    "pending": "待学",
    "todo": "待学",
    "待学": "待学",
    "待复习": "待复习",
    "review": "待复习",
}

STATUS_CLASSES = {
    "已完成": "status-done",
    "进行中": "status-doing",
    "待学": "status-todo",
    "待复习": "status-due",
}

LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*([A-Za-z0-9_+\-]*)\s*$")
CALLOUT_RE = re.compile(r"^\s*:::\s*([A-Za-z][A-Za-z0-9_\-]*)(?:\s+(.*))?\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
FM_KEY_RE = re.compile(r"^([A-Za-z0-9_\-\u4e00-\u9fff]+)\s*:\s*(.*)$")


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------


def _log(message: str) -> None:
    print(message, flush=True)


def _warn(message: str) -> None:
    print("[warn] " + message, file=sys.stderr, flush=True)


def _parse_scalar(raw: str) -> Any:
    """解析 frontmatter 里的简单标量。"""
    value = raw.strip()
    if value == "":
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
        value = value.replace('\\"', '"').replace("\\'", "'")
        return value
    low = value.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", "~"):
        return None
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(r"-?\d+\.\d+", value):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """解析 ``---`` YAML 子集，返回 (meta, body)。

    支持 key: value、引号字符串、布尔/数字、``[a, b]`` 行内列表、
    ``- item`` 块列表，以及 ``>`` / ``|`` 块标量。复杂 YAML 不在此范围内。
    """
    text = text.lstrip("\ufeff")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text

    fm = lines[1:end]
    body = "\n".join(lines[end + 1 :])
    data: Dict[str, Any] = {}
    key: Optional[str] = None
    i = 0
    while i < len(fm):
        raw = fm[i]
        line = raw.rstrip()
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        item_match = re.match(r"^\s+-\s+(.*)$", line)
        if item_match and key:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(_parse_scalar(item_match.group(1)))
            continue

        match = FM_KEY_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        value = match.group(2).strip()

        if value in (">", "|"):
            block: List[str] = []
            while i < len(fm):
                nxt = fm[i]
                if nxt.strip() and not nxt.startswith((" ", "\t")):
                    break
                block.append(nxt.strip())
                i += 1
            joined = (" " if value == ">" else "\n").join(
                [b for b in block if b]
            )
            data[key] = joined
            continue

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                data[key] = []
            else:
                data[key] = [
                    _parse_scalar(part.strip())
                    for part in inner.split(",")
                    if part.strip()
                ]
        elif value == "":
            data[key] = []
        else:
            data[key] = _parse_scalar(value)

    return data, body


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [text]


def safe_component(name: Any, fallback: str = "course") -> str:
    """生成安全的文件/目录名（保留中文）。"""
    text = unicodedata.normalize("NFKC", str(name or "")).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = fallback
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    if text.upper() in reserved:
        text = "_" + text
    return text[:80]


def slugify(text: Any, fallback: str = "lesson") -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value)
    value = value.strip("-_")
    return (value[:48] or fallback)


def unit_file_stem(unit: Any, title: Any) -> str:
    unit_text = str(unit if unit not in (None, "") else "").strip()
    if re.fullmatch(r"\d+", unit_text):
        unit_part = "unit-%02d" % int(unit_text)
    elif unit_text:
        unit_part = "unit-" + slugify(unit_text, "x")
    else:
        unit_part = "unit"
    return "%s-%s" % (unit_part, slugify(title))


def normalize_status(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return STATUS_LABELS.get(raw, STATUS_LABELS.get(raw.lower(), raw))


def _safe_url(url: str, image: bool = False) -> str:
    value = html.unescape(str(url or "")).strip()
    if not value:
        return "#"
    low = value.lower()
    if low.startswith(("javascript:", "vbscript:", "data:text/html")):
        return "#"
    if image:
        if low.startswith(("http://", "https://", "data:image/", "./", "../", "/")):
            return value
        if ":" not in value:
            return value
        return "#"
    if low.startswith(("http://", "https://", "mailto:", "#", "./", "../", "/")):
        return value
    if ":" not in value:
        return value
    return "#"


def _inline(text: str) -> str:
    """行内 Markdown -> HTML。先保护代码片段，再转义，最后套格式。"""
    codes: List[str] = []

    def _code(match: re.Match) -> str:
        codes.append(match.group(2))
        return "\x00CODE%d\x00" % (len(codes) - 1)

    text = re.sub(r"(`+)(.+?)\1", _code, text, flags=re.S)
    text = html.escape(text, quote=False)

    def _image(match: re.Match) -> str:
        alt = match.group(1)
        src = _safe_url(match.group(2), image=True)
        return '<img src="%s" alt="%s" loading="lazy">' % (
            html.escape(src, quote=True),
            html.escape(alt, quote=True),
        )

    text = re.sub(
        r"!\[([^\]]*)\]\(((?:[^()\s]|\([^()\s]*\))+)(?:\s+\"[^\"]*\")?\)",
        _image,
        text,
    )

    def _link(match: re.Match) -> str:
        label = match.group(1)
        href = _safe_url(match.group(2))
        return '<a href="%s">%s</a>' % (
            html.escape(href, quote=True),
            label,
        )

    text = re.sub(
        r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)(?:\s+\"[^\"]*\")?\)",
        _link,
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text, flags=re.S)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text, flags=re.S)
    text = re.sub(r"==(.+?)==", r"<mark>\1</mark>", text, flags=re.S)
    text = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: '<span class="math">%s</span>' % m.group(1),
        text,
    )

    for idx, code in enumerate(codes):
        text = text.replace(
            "\x00CODE%d\x00" % idx,
            "<code>%s</code>" % html.escape(code, quote=False),
        )
    return text


def _plain_text(markup: str) -> str:
    """去掉行内标记，供 TOC 使用。"""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", markup)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("~~", "").replace("==", "")
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Markdown 渲染
# ---------------------------------------------------------------------------


class MarkdownRenderer:
    def __init__(self) -> None:
        self.headings: List[Dict[str, Any]] = []
        self._heading_seq = 0

    def render(self, markdown: str) -> Tuple[str, List[Dict[str, Any]]]:
        lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        body, _ = self._blocks(lines, 0)
        return body, self.headings

    # -- 块级 ---------------------------------------------------------------

    def _blocks(
        self, lines: Sequence[str], start: int = 0, stop_callout: bool = False
    ) -> Tuple[str, int]:
        out: List[str] = []
        i = start
        while i < len(lines):
            line = lines[i]
            if stop_callout and CALLOUT_RE.match(line) and line.strip() == ":::":
                break
            if not line.strip():
                i += 1
                continue

            # 自定义容器（callout / answer）
            callout = CALLOUT_RE.match(line)
            if callout:
                kind = callout.group(1).lower()
                title = (callout.group(2) or "").strip()
                inner: List[str] = []
                depth = 1
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    if CALLOUT_RE.match(nxt) and not nxt.strip().startswith("::::"):
                        depth += 1
                    if nxt.strip() == ":::":
                        depth -= 1
                        if depth == 0:
                            break
                    inner.append(nxt)
                    j += 1
                inner_html, _ = self._blocks(inner, 0)
                out.append(self._render_callout(kind, title, inner_html))
                i = j + 1
                continue

            # 代码围栏
            fence = FENCE_RE.match(line)
            if fence:
                marker = fence.group(1)[0]
                lang = fence.group(2).strip()
                code_lines: List[str] = []
                j = i + 1
                while j < len(lines):
                    close = re.match(r"^\s*(```+|~~~+)\s*$", lines[j])
                    if close and close.group(1)[0] == marker:
                        break
                    code_lines.append(lines[j])
                    j += 1
                code = "\n".join(code_lines)
                if lang.lower() == "svg":
                    svg = code.strip()
                    if not svg.lower().startswith("<svg"):
                        svg = '<pre class="code"><code>%s</code></pre>' % html.escape(code)
                    out.append('<figure class="diagram">%s</figure>' % svg)
                else:
                    cls = "code" + ((' language-' + html.escape(lang)) if lang else "")
                    out.append(
                        '<pre class="%s"><code>%s</code></pre>'
                        % (cls, html.escape(code, quote=False))
                    )
                i = j + 1
                continue

            # 标题 h1-h4（正文里的 h1 降为 h2，避免和页面标题重复）
            heading = HEADING_RE.match(line)
            if heading:
                level = len(heading.group(1))
                if level == 1:
                    level = 2
                text = heading.group(2).strip()
                self._heading_seq += 1
                heading_id = "sec-%d" % self._heading_seq
                self.headings.append(
                    {"level": level, "text": _plain_text(text), "id": heading_id}
                )
                out.append(
                    '<h%d id="%s">%s</h%d>'
                    % (level, heading_id, _inline(text), level)
                )
                i += 1
                continue

            # 分隔线
            if HR_RE.match(line):
                out.append("<hr>")
                i += 1
                continue

            # 表格
            if "|" in line and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1]):
                table_html, i = self._render_table(lines, i)
                out.append(table_html)
                continue

            # 引用
            if line.lstrip().startswith(">"):
                quote_lines: List[str] = []
                while i < len(lines) and lines[i].lstrip().startswith(">"):
                    quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                    i += 1
                inner_html, _ = self._blocks(quote_lines, 0)
                out.append("<blockquote>%s</blockquote>" % inner_html)
                continue

            # 列表
            if LIST_RE.match(line):
                list_html, i = self._render_list(lines, i)
                out.append(list_html)
                continue

            # 段落
            para: List[str] = []
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    break
                if (
                    CALLOUT_RE.match(nxt)
                    or FENCE_RE.match(nxt)
                    or HEADING_RE.match(nxt)
                    or LIST_RE.match(nxt)
                    or HR_RE.match(nxt)
                    or (nxt.lstrip().startswith(">"))
                ):
                    break
                if "|" in nxt and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1]):
                    break
                para.append(nxt.strip())
                i += 1
            if para:
                out.append("<p>%s</p>" % _inline(" ".join(para)))
            else:
                i += 1

        return "\n".join(out), i

    def _render_callout(self, kind: str, title: str, inner_html: str) -> str:
        info = CALLOUTS.get(kind, {"label": kind, "icon": "📌", "class": "note"})
        label = title or info["label"]
        if kind == "answer":
            return (
                '<details class="answer">'
                '<summary><span class="answer-icon">%s</span>%s</summary>'
                '<div class="answer-body">%s</div></details>'
                % (info["icon"], _inline(label), inner_html)
            )
        return (
            '<aside class="callout %s">'
            '<div class="callout-title"><span class="callout-icon">%s</span>%s</div>'
            '<div class="callout-body">%s</div></aside>'
            % (
                info["class"],
                info["icon"],
                _inline(label),
                inner_html,
            )
        )

    def _render_table(self, lines: Sequence[str], start: int) -> Tuple[str, int]:
        header = _split_table_row(lines[start])
        sep = _split_table_row(lines[start + 1])
        aligns: List[str] = []
        for cell in sep:
            cell = cell.strip()
            if cell.startswith(":") and cell.endswith(":"):
                aligns.append("center")
            elif cell.endswith(":"):
                aligns.append("right")
            elif cell.startswith(":"):
                aligns.append("left")
            else:
                aligns.append("")
        rows: List[List[str]] = []
        i = start + 2
        while i < len(lines) and "|" in lines[i] and lines[i].strip():
            rows.append(_split_table_row(lines[i]))
            i += 1

        def cell_html(tag: str, value: str, index: int) -> str:
            align = aligns[index] if index < len(aligns) else ""
            style = ' style="text-align:%s"' % align if align else ""
            return "<%s%s>%s</%s>" % (tag, style, _inline(value.strip()), tag)

        parts = ['<div class="table-wrap"><table>']
        parts.append("<thead><tr>")
        for idx, cell in enumerate(header):
            parts.append(cell_html("th", cell, idx))
        parts.append("</tr></thead><tbody>")
        for row in rows:
            parts.append("<tr>")
            for idx in range(max(len(header), len(row))):
                value = row[idx] if idx < len(row) else ""
                parts.append(cell_html("td", value, idx))
            parts.append("</tr>")
        parts.append("</tbody></table></div>")
        return "".join(parts), i

    def _render_list(self, lines: Sequence[str], start: int) -> Tuple[str, int]:
        """栈式列表渲染，支持两级以上嵌套，输出合法嵌套结构。"""
        out: List[str] = []
        # 每层记录缩进、列表标签、当前 <li> 是否还开着
        stack: List[Dict[str, Any]] = []
        base_indent = len(LIST_RE.match(lines[start]).group(1))
        i = start

        while i < len(lines):
            match = LIST_RE.match(lines[i])
            if not match:
                break
            indent = len(match.group(1))
            marker = match.group(2)
            tag = "ol" if marker[0].isdigit() else "ul"
            if indent < base_indent:
                break

            # 先关掉所有比当前层级更深的列表
            while stack and indent < stack[-1]["indent"]:
                if stack[-1]["li_open"]:
                    out.append("</li>")
                    stack[-1]["li_open"] = False
                out.append("</%s>" % stack[-1]["tag"])
                stack.pop()

            if not stack or indent > stack[-1]["indent"]:
                out.append("<%s>" % tag)
                stack.append({"indent": indent, "tag": tag, "li_open": False})
            elif indent == stack[-1]["indent"]:
                if stack[-1]["li_open"]:
                    out.append("</li>")
                    stack[-1]["li_open"] = False
                if stack[-1]["tag"] != tag:
                    out.append("</%s>" % stack[-1]["tag"])
                    stack.pop()
                    out.append("<%s>" % tag)
                    stack.append({"indent": indent, "tag": tag, "li_open": False})

            text = match.group(3).strip()
            task = re.match(r"^\[([ xX])\]\s+(.*)$", text)
            if task:
                checked = " checked" if task.group(1).lower() == "x" else ""
                out.append(
                    '<li class="task"><input type="checkbox" disabled%s> %s'
                    % (checked, _inline(task.group(2)))
                )
            else:
                out.append("<li>" + _inline(text))
            stack[-1]["li_open"] = True
            i += 1

            # 列表项的续行（缩进且不是新的列表项）
            while (
                i < len(lines)
                and lines[i].strip()
                and not LIST_RE.match(lines[i])
                and lines[i].startswith(" " * (indent + 2))
            ):
                out.append(" " + _inline(lines[i].strip()))
                i += 1

        while stack:
            if stack[-1]["li_open"]:
                out.append("</li>")
            out.append("</%s>" % stack[-1]["tag"])
            stack.pop()
        return "".join(out), i


def _split_table_row(line: str) -> List[str]:
    value = line.strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [part.strip() for part in value.split("|")]


# ---------------------------------------------------------------------------
# 页面模板（自包含 CSS/JS）
# ---------------------------------------------------------------------------


COMMON_CSS = r"""
:root{
  --bg:#f5f6f8;--card:#ffffff;--text:#1f2328;--muted:#667085;
  --border:#e4e7ec;--accent:#2563eb;--accent-soft:#eff6ff;
  --green:#15803d;--green-soft:#ecfdf3;--amber:#b45309;--amber-soft:#fffbeb;
  --red:#b91c1c;--red-soft:#fef2f2;--purple:#6d28d9;--purple-soft:#f5f3ff;
  --code-bg:#f1f5f9;--shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.1);
  --radius:12px;--maxw:860px;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#0f1115;--card:#161a20;--text:#e6e8eb;--muted:#98a2b3;
    --border:#2a3038;--accent:#60a5fa;--accent-soft:#17233a;
    --green:#4ade80;--green-soft:#12251a;--amber:#fbbf24;--amber-soft:#2a2110;
    --red:#f87171;--red-soft:#2a1515;--purple:#c4b5fd;--purple-soft:#211a35;
    --code-bg:#1c222b;--shadow:0 1px 3px rgba(0,0,0,.4);
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC","Noto Sans CJK SC",sans-serif;
  font-size:16px;line-height:1.85;-webkit-font-smoothing:antialiased;
}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.skip{position:absolute;left:-9999px;top:0;background:var(--card);padding:8px 12px;z-index:99}
.skip:focus{left:8px;top:8px}
.topbar{
  position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--card) 92%,transparent);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--border);
}
.topbar-inner{
  max-width:1180px;margin:0 auto;padding:10px 20px;display:flex;align-items:center;
  gap:12px;justify-content:space-between;
}
.brand{font-weight:700;font-size:15px;display:flex;align-items:center;gap:8px}
.brand a{color:var(--text)}
.logo{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:6px;background:var(--accent);color:#fff;font-size:13px;font-weight:800;line-height:1}
@media (max-width:900px){
  .brand .logo{display:inline-flex}
}
.topbar-actions{display:flex;align-items:center;gap:8px}
.btn{
  appearance:none;border:1px solid var(--border);background:var(--card);color:var(--text);
  padding:6px 12px;border-radius:8px;font-size:13px;cursor:pointer;line-height:1.4;
}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn-primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn-primary:hover{color:#fff;opacity:.92}
.shell{max-width:1180px;margin:0 auto;padding:28px 20px 60px;display:grid;grid-template-columns:240px minmax(0,1fr);gap:36px}
.toc{position:sticky;top:76px;align-self:start;max-height:calc(100vh - 100px);overflow:auto;padding-right:8px}
.toc-title{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
.toc ol{list-style:none;margin:0;padding:0;border-left:2px solid var(--border)}
.toc li{margin:0}
.toc a{display:block;padding:3px 0 3px 12px;color:var(--muted);font-size:13px;line-height:1.5;border-left:2px solid transparent;margin-left:-2px}
.toc a:hover{color:var(--accent);text-decoration:none}
.toc a.active{color:var(--accent);border-left-color:var(--accent);font-weight:600}
.toc .toc-h3 a{padding-left:24px;font-size:12.5px}
.lesson{min-width:0}
.lesson-header{margin-bottom:26px}
.eyebrow{font-size:13px;color:var(--muted);margin-bottom:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.eyebrow a{color:var(--muted)}
h1{font-size:32px;line-height:1.3;margin:0 0 14px;letter-spacing:-.01em}
.meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:18px}
.chip{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--border);background:var(--card);color:var(--muted);border-radius:999px;padding:3px 10px;font-size:12.5px}
.chip.tag{color:var(--accent);background:var(--accent-soft);border-color:transparent}
.chip.status-done{color:var(--green);background:var(--green-soft);border-color:transparent}
.chip.status-doing{color:var(--accent);background:var(--accent-soft);border-color:transparent}
.chip.status-due{color:var(--amber);background:var(--amber-soft);border-color:transparent}
.chip.mastery{color:var(--purple);background:var(--purple-soft);border-color:transparent}
.chip.kind{color:var(--purple);background:var(--purple-soft);border-color:transparent}
.chip.status-todo{color:var(--muted);background:var(--bg)}
.objectives{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin:20px 0 8px;box-shadow:var(--shadow)}
.objectives h2{font-size:14px;margin:0 0 8px;color:var(--muted);letter-spacing:.05em}
.objectives ul{margin:0;padding-left:20px}
.objectives li{margin:3px 0}
.content{font-size:16px}
.content h2{font-size:23px;margin:36px 0 12px;padding-left:12px;border-left:4px solid var(--accent);line-height:1.45}
.content h3{font-size:18.5px;margin:26px 0 8px}
.content h4{font-size:16.5px;margin:20px 0 6px;color:var(--muted)}
.content p{margin:10px 0}
.content ul,.content ol{padding-left:24px;margin:10px 0}
.content li{margin:4px 0}
.content li.task{list-style:none;margin-left:-20px}
.content strong{font-weight:700}
.content hr{border:0;border-top:1px solid var(--border);margin:26px 0}
.content blockquote{
  margin:16px 0;padding:10px 16px;border-left:4px solid var(--border);
  background:var(--card);border-radius:0 8px 8px 0;color:var(--muted);
}
.content blockquote p{margin:4px 0}
.content code{
  font-family:"Cascadia Code","JetBrains Mono",Consolas,"Courier New",monospace;
  font-size:.92em;background:var(--code-bg);padding:2px 5px;border-radius:5px;
}
.math{font-family:"Cambria Math","STIX Two Math",Georgia,serif;font-style:italic;white-space:nowrap}
.content pre.code{
  background:#0f172a;color:#e2e8f0;border-radius:10px;padding:16px 18px;
  overflow:auto;line-height:1.65;font-size:13.5px;margin:14px 0;border:1px solid var(--border);
}
.content pre.code code{background:none;padding:0;color:inherit;font-size:inherit}
.content pre.code::before{
  content:attr(class);display:block;color:#94a3b8;font-size:11px;margin-bottom:6px;
  font-family:inherit;text-transform:uppercase;letter-spacing:.05em;
}
.content pre.language-python::before{content:"python"}
.content pre.language-c::before{content:"c"}
.content pre.language-cpp::before{content:"c++"}
.content pre.language-javascript::before{content:"javascript"}
.content pre.language-js::before{content:"javascript"}
.content pre.language-bash::before{content:"bash"}
.content pre.language-sql::before{content:"sql"}
.content pre.language-html::before{content:"html"}
.content pre.language-json::before{content:"json"}
.content pre.language-text::before{content:"text"}
.content pre.code::before{opacity:.7}
.content pre.code:not([class*="language-"])::before{content:"";display:none}
.diagram{margin:18px 0;padding:14px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:auto;text-align:center}
.diagram svg{max-width:100%;height:auto}
.table-wrap{overflow:auto;margin:16px 0;border:1px solid var(--border);border-radius:10px}
.content table{border-collapse:collapse;width:100%;font-size:14.5px;background:var(--card)}
.content th,.content td{padding:9px 12px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
.content th{background:var(--bg);font-weight:700;white-space:nowrap}
.content tr:last-child td{border-bottom:0}
.content tbody tr:hover{background:color-mix(in srgb,var(--accent-soft) 45%,transparent)}
.callout{
  border:1px solid var(--border);border-left:4px solid var(--accent);
  background:var(--card);border-radius:0 10px 10px 0;padding:12px 16px;margin:16px 0;
}
.callout-title{font-weight:700;font-size:14px;margin-bottom:4px;display:flex;gap:7px;align-items:center}
.callout-body>*:first-child{margin-top:0}
.callout-body>*:last-child{margin-bottom:0}
.callout-body p{margin:5px 0}
.callout.definition{border-left-color:var(--purple);background:var(--purple-soft)}
.callout.definition .callout-title{color:var(--purple)}
.callout.example{border-left-color:var(--accent);background:var(--accent-soft)}
.callout.example .callout-title{color:var(--accent)}
.callout.warning{border-left-color:var(--red);background:var(--red-soft)}
.callout.warning .callout-title{color:var(--red)}
.callout.tip{border-left-color:var(--green);background:var(--green-soft)}
.callout.tip .callout-title{color:var(--green)}
.callout.summary{border-left-color:var(--green);background:var(--green-soft)}
.callout.summary .callout-title{color:var(--green)}
.callout.keypoint{border-left-color:var(--amber);background:var(--amber-soft)}
.callout.keypoint .callout-title{color:var(--amber)}
.callout.formula{border-left-color:var(--purple);background:var(--purple-soft)}
.callout.formula .callout-title{color:var(--purple)}
.callout.practice{border-left-color:var(--accent);background:var(--accent-soft)}
.callout.exam{border-left-color:var(--amber);background:var(--amber-soft)}
.callout.exam .callout-title{color:var(--amber)}
.callout.source{border-left-color:var(--muted);background:var(--bg)}
.callout.source .callout-title{color:var(--muted)}
details.answer{
  border:1px solid var(--border);border-radius:10px;background:var(--card);
  margin:12px 0;padding:0 14px;
}
details.answer summary{
  cursor:pointer;font-weight:700;color:var(--accent);padding:10px 0;
  list-style:none;display:flex;gap:7px;align-items:center;
}
details.answer summary::-webkit-details-marker{display:none}
details.answer summary::after{content:"▸";margin-left:auto;color:var(--muted);transition:transform .15s}
details.answer[open] summary::after{transform:rotate(90deg)}
details.answer .answer-body{padding:0 0 12px;border-top:1px dashed var(--border);margin-top:0;padding-top:10px}
details.answer .answer-body>*:first-child{margin-top:0}
details.answer .answer-body>*:last-child{margin-bottom:0}
.lesson-footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--border);color:var(--muted);font-size:13px}
.lesson-footer .sources{margin:8px 0}
.lesson-footer .sources ul{margin:4px 0 0;padding-left:20px}
.prevnext{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:24px}
.prevnext a{
  display:block;border:1px solid var(--border);background:var(--card);border-radius:10px;
  padding:10px 14px;color:var(--text);text-decoration:none;
}
.prevnext a:hover{border-color:var(--accent);text-decoration:none}
.prevnext .dir{display:block;font-size:11.5px;color:var(--muted);margin-bottom:2px}
.prevnext .next{text-align:right}
.prevnext .empty{visibility:hidden}
.footer-note{margin-top:26px;color:var(--muted);font-size:12px;text-align:center}
@media (max-width:900px){
  .shell{grid-template-columns:1fr;gap:18px;padding-top:18px}
  .toc{position:static;max-height:none;border:1px solid var(--border);background:var(--card);border-radius:10px;padding:12px 14px}
  .toc ol{border-left:0;columns:2;column-gap:18px}
  .toc a{padding-left:0;border-left:0}
  .toc .toc-h3 a{padding-left:10px}
  h1{font-size:26px}
  .topbar-inner{padding:8px 14px}
  .brand span:not(.logo){display:none}
}
@media print{
  :root{--bg:#fff;--card:#fff;--text:#000;--muted:#444;--border:#ddd}
  .topbar,.toc,.btn,.prevnext,.footer-note{display:none!important}
  .shell{display:block;max-width:none;padding:0}
  body{font-size:12pt;line-height:1.6}
  .content h2{page-break-after:avoid}
  .callout,details.answer,table,pre.code,.diagram{page-break-inside:avoid}
  details.answer .answer-body{display:block!important}
  details.answer summary::after{display:none}
  a{color:#000;text-decoration:none}
}
"""

LESSON_JS = r"""
(function(){
  var toggle=document.getElementById('toggle-answers');
  if(toggle){
    toggle.addEventListener('click',function(){
      var all=Array.prototype.slice.call(document.querySelectorAll('details.answer'));
      if(!all.length){return;}
      var anyClosed=all.some(function(d){return !d.open;});
      all.forEach(function(d){d.open=anyClosed;});
      toggle.textContent=anyClosed?'收起全部答案':'展开全部答案';
    });
  }
  var printBtn=document.getElementById('print-btn');
  if(printBtn){printBtn.addEventListener('click',function(){window.print();});}
  var links=Array.prototype.slice.call(document.querySelectorAll('.toc a[href^="#"]'));
  if(links.length && 'IntersectionObserver' in window){
    var map={};
    links.forEach(function(a){map[decodeURIComponent(a.getAttribute('href').slice(1))]=a;});
    var obs=new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if(en.isIntersecting){
          links.forEach(function(a){a.classList.remove('active');});
          var a=map[en.target.id];
          if(a){a.classList.add('active');}
        }
      });
    },{rootMargin:'-20% 0px -70% 0px'});
    document.querySelectorAll('.content h2[id],.content h3[id]').forEach(function(h){obs.observe(h);});
  }
  var opened=[];
  window.addEventListener('beforeprint',function(){
    opened=[];
    document.querySelectorAll('details.answer').forEach(function(d){
      opened.push([d,d.open]);d.open=true;
    });
  });
  window.addEventListener('afterprint',function(){
    opened.forEach(function(pair){pair[0].open=pair[1];});opened=[];
  });
})();
"""


def _render_toc(headings: List[Dict[str, Any]]) -> str:
    if not headings:
        return ""
    items: List[str] = ['<nav class="toc" aria-label="本页目录">', '<p class="toc-title">本页目录</p>', "<ol>"]
    for heading in headings:
        if heading["level"] > 3:
            continue
        cls = "toc-h3" if heading["level"] == 3 else "toc-h2"
        items.append(
            '<li class="%s"><a href="#%s">%s</a></li>'
            % (cls, heading["id"], html.escape(heading["text"]))
        )
    items.extend(["</ol>", "</nav>"])
    return "".join(items)


def render_lesson_page(
    meta: Dict[str, Any],
    content_html: str,
    headings: List[Dict[str, Any]],
    course: str,
    prev_entry: Optional[Dict[str, Any]] = None,
    next_entry: Optional[Dict[str, Any]] = None,
    mastery: Optional[Dict[str, Any]] = None,
) -> str:
    title = str(meta.get("title") or "未命名单元")
    kind = str(meta.get("kind") or "lesson").strip().lower()
    unit = meta.get("unit") or meta.get("order") or ""
    if kind == "practice":
        unit_label = "练习卷"
    elif re.fullmatch(r"\d+", str(unit)):
        unit_label = "第 %s 单元" % unit
    elif str(unit):
        unit_label = "单元 %s" % unit
    else:
        unit_label = "讲义"
    status = normalize_status(meta.get("status"))
    status_html = ""
    if status:
        status_html = '<span class="chip %s">%s</span>' % (
            STATUS_CLASSES.get(status, "status-todo"),
            html.escape(status),
        )
    tags = as_list(meta.get("tags"))
    tags_html = "".join('<span class="chip tag">%s</span>' % html.escape(t) for t in tags)
    date_text = html.escape(str(meta.get("date") or ""))
    review_text = html.escape(str(meta.get("review_at") or meta.get("review") or ""))
    review_chip = (
        '<span class="chip status-due">复习：%s</span>' % review_text
        if review_text
        else ""
    )
    mastery_chip = ""
    if isinstance(mastery, dict):
        level = int(mastery.get("level", 0) or 0)
        status_label = LEVEL_LABELS.get(level, "未掌握")
        mastery_chip = '<span class="chip mastery">掌握度：Lv%d %s</span>' % (
            level,
            html.escape(status_label),
        )
    kind_chip = '<span class="chip kind">练习卷</span>' if kind == "practice" else ""
    objectives = as_list(meta.get("objectives"))
    objectives_html = ""
    if objectives:
        objectives_html = (
            '<section class="objectives"><h2>学完本单元，你应该能</h2><ul>%s</ul></section>'
            % "".join("<li>%s</li>" % _inline(o) for o in objectives)
        )
    sources = as_list(meta.get("sources"))
    sources_html = ""
    if sources:
        sources_html = '<div class="sources"><strong>参考来源</strong><ul>%s</ul></div>' % "".join(
            "<li>%s</li>" % _inline(s) for s in sources
        )

    prev_html = '<span class="empty">没有上一单元</span>'
    if prev_entry:
        prev_html = (
            '<a href="%s"><span class="dir">← 上一单元</span>%s</a>'
            % (
                html.escape(prev_entry["html_name"], quote=True),
                html.escape(prev_entry["title"]),
            )
        )
    next_html = '<span class="empty">没有下一单元</span>'
    if next_entry:
        next_html = (
            '<a class="next" href="%s"><span class="dir">下一单元 →</span>%s</a>'
            % (
                html.escape(next_entry["html_name"], quote=True),
                html.escape(next_entry["title"]),
            )
        )

    toc_html = _render_toc(headings)
    meta_bits = []
    if date_text:
        meta_bits.append('<span class="chip">%s</span>' % date_text)
    if unit_label:
        meta_bits.append('<span class="chip">%s</span>' % html.escape(unit_label))
    if review_chip:
        meta_bits.append(review_chip)
    if status_html:
        meta_bits.append(status_html)
    if mastery_chip:
        meta_bits.append(mastery_chip)
    if kind_chip:
        meta_bits.append(kind_chip)
    if tags_html:
        meta_bits.append(tags_html)

    page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="teacher.skill v__VERSION__">
<title>__TITLE__ · __COURSE__</title>
<style>__CSS__</style>
</head>
<body>
<a class="skip" href="#main">跳到正文</a>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand"><span class="logo">T</span><a href="index.html">__COURSE__</a></div>
    <div class="topbar-actions">
      <button class="btn" id="toggle-answers" type="button">展开全部答案</button>
      <button class="btn" id="print-btn" type="button">打印 / PDF</button>
    </div>
  </div>
</header>
<div class="shell">
  __TOC__
  <main class="lesson" id="main">
    <header class="lesson-header">
      <div class="eyebrow"><a href="index.html">课程讲义</a><span>/</span><span>__UNIT_LABEL__</span></div>
      <h1>__TITLE__</h1>
      <div class="meta">__META__</div>
      __OBJECTIVES__
    </header>
    <article class="content">
      __CONTENT__
    </article>
    <footer class="lesson-footer">
      __SOURCES__
      <div class="prevnext">__PREV____NEXT__</div>
      <p class="footer-note">由 teacher.skill v__VERSION__ 生成 · __GENERATED__<br>本页面为本地学习讲义，不依赖网络。</p>
    </footer>
  </main>
</div>
<script>__JS__</script>
</body>
</html>
"""
    replacements = {
        "__VERSION__": VERSION,
        "__TITLE__": html.escape(title),
        "__COURSE__": html.escape(course),
        "__CSS__": COMMON_CSS,
        "__TOC__": toc_html,
        "__UNIT_LABEL__": html.escape(unit_label),
        "__META__": "".join(meta_bits),
        "__OBJECTIVES__": objectives_html,
        "__CONTENT__": content_html,
        "__SOURCES__": sources_html,
        "__PREV__": prev_html,
        "__NEXT__": next_html,
        "__GENERATED__": date.today().isoformat(),
        "__JS__": LESSON_JS,
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page


INDEX_CSS = COMMON_CSS + r"""
.index-shell{max-width:980px;margin:0 auto;padding:34px 20px 70px}
.index-hero{margin-bottom:24px}
.index-hero h1{font-size:34px;margin-bottom:8px}
.index-desc{color:var(--muted);margin:0}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}
.stat{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow)}
.stat strong{display:block;font-size:24px;line-height:1.2}
.stat span{color:var(--muted);font-size:12.5px}
.progress{height:8px;background:var(--bg);border-radius:999px;overflow:hidden;margin:6px 0 2px;border:1px solid var(--border)}
.progress > i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),#22c55e);border-radius:999px}
.due-box{background:var(--amber-soft);border:1px solid color-mix(in srgb,var(--amber) 30%,var(--border));border-radius:var(--radius);padding:14px 18px;margin:18px 0}
.due-box h2{font-size:15px;margin:0 0 6px;color:var(--amber)}
.due-box ul{margin:0;padding-left:20px}
.due-box li{margin:3px 0}
.weak-box{background:var(--red-soft);border-color:color-mix(in srgb,var(--red) 28%,var(--border))}
.weak-box h2{color:var(--red)}
.next-box{background:var(--accent-soft);border:1px solid color-mix(in srgb,var(--accent) 25%,var(--border));border-radius:var(--radius);padding:14px 18px;margin:18px 0}
.next-box h2{font-size:15px;margin:0 0 6px;color:var(--accent)}
.next-box p{margin:4px 0;color:var(--text)}
.level{color:var(--muted);font-size:12.5px}
.chip.kind{color:var(--purple);background:var(--purple-soft);border-color:transparent}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:22px 0 14px}
.toolbar input{
  flex:1 1 220px;min-width:180px;padding:9px 12px;border:1px solid var(--border);
  border-radius:9px;background:var(--card);color:var(--text);font-size:14px;
}
.toolbar input:focus{outline:2px solid var(--accent-soft);border-color:var(--accent)}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.filter{border:1px solid var(--border);background:var(--card);color:var(--muted);border-radius:999px;padding:5px 12px;font-size:12.5px;cursor:pointer}
.filter.active{background:var(--accent);border-color:var(--accent);color:#fff}
.lesson-list{display:flex;flex-direction:column;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:var(--card);box-shadow:var(--shadow)}
.lesson-row{display:flex;gap:14px;align-items:flex-start;padding:14px 16px;border-bottom:1px solid var(--border);color:var(--text);text-decoration:none}
.lesson-row:last-child{border-bottom:0}
.lesson-row:hover{background:var(--accent-soft);text-decoration:none}
.unit-badge{
  flex:0 0 auto;min-width:40px;height:40px;border-radius:10px;background:var(--bg);
  border:1px solid var(--border);display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:14px;color:var(--muted);
}
.lesson-row.done .unit-badge{background:var(--green-soft);border-color:transparent;color:var(--green)}
.lesson-row.doing .unit-badge{background:var(--accent-soft);border-color:transparent;color:var(--accent)}
.lesson-row.due .unit-badge{background:var(--amber-soft);border-color:transparent;color:var(--amber)}
.row-main{flex:1;min-width:0}
.row-title{display:block;font-weight:700;font-size:15.5px;line-height:1.5}
.row-desc{display:block;color:var(--muted);font-size:13px;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.row-side{flex:0 0 auto;text-align:right;display:flex;flex-direction:column;gap:5px;align-items:flex-end}
.row-date{color:var(--muted);font-size:12px}
.empty-state{border:1px dashed var(--border);border-radius:var(--radius);padding:42px 20px;text-align:center;color:var(--muted);background:var(--card)}
.index-footer{margin-top:26px;color:var(--muted);font-size:12px;text-align:center}
@media (max-width:640px){
  .index-hero h1{font-size:26px}
  .stats{grid-template-columns:1fr 1fr;gap:8px}
  .stat{padding:10px 12px}
  .stat strong{font-size:20px}
  .lesson-row{padding:12px}
  .row-side{display:none}
}
@media print{.toolbar,.filters,.due-box{display:none!important}}
"""

INDEX_JS = r"""
(function(){
  var input=document.getElementById('search');
  var rows=Array.prototype.slice.call(document.querySelectorAll('.lesson-row'));
  var filters=Array.prototype.slice.call(document.querySelectorAll('.filter'));
  var active='all';
  function apply(){
    var q=(input&&input.value||'').trim().toLowerCase();
    rows.forEach(function(row){
      var text=(row.getAttribute('data-search')||'').toLowerCase();
      var status=row.getAttribute('data-status')||'';
      var okQ=!q||text.indexOf(q)>=0;
      var okF=active==='all'||status===active;
      row.hidden=!(okQ&&okF);
    });
  }
  if(input){input.addEventListener('input',apply);}
  filters.forEach(function(btn){
    btn.addEventListener('click',function(){
      filters.forEach(function(b){b.classList.remove('active');});
      btn.classList.add('active');active=btn.getAttribute('data-filter')||'all';apply();
    });
  });
})();
"""


LEVEL_LABELS = {0: "未掌握", 1: "模糊", 2: "基本掌握", 3: "掌握"}


def _mastery_view(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """从 learning-state.json 提取 index 需要的掌握度信息。"""
    result: Dict[str, Any] = {
        "concepts": [],
        "weak": [],
        "due": [],
        "action": None,
    }
    if not isinstance(state, dict):
        return result
    mastery = state.get("mastery")
    if not isinstance(mastery, dict):
        return result
    concepts = mastery.get("concepts")
    if not isinstance(concepts, dict):
        return result
    today = date.today()
    items: List[Dict[str, Any]] = []
    for name, info in concepts.items():
        if not isinstance(info, dict):
            continue
        level = int(info.get("level", 0) or 0)
        item = {
            "name": str(info.get("name") or name),
            "unit": str(info.get("unit") or ""),
            "level": level,
            "status": LEVEL_LABELS.get(level, "未掌握"),
            "variant_passed": bool(info.get("variant_passed")),
            "next_review_at": str(info.get("next_review_at") or ""),
        }
        review = _parse_date(item["next_review_at"])
        item["is_due"] = bool(review and review <= today)
        items.append(item)
    items.sort(key=lambda c: (c["level"], c["name"]))
    result["concepts"] = items
    result["weak"] = [c for c in items if c["level"] <= 1]
    result["due"] = [c for c in items if c["is_due"]]
    action = mastery.get("next_action")
    if isinstance(action, dict):
        result["action"] = action
    return result


def _find_mastery_concept(
    state: Optional[Dict[str, Any]], meta: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not isinstance(state, dict):
        return None
    mastery = state.get("mastery")
    if not isinstance(mastery, dict):
        return None
    concepts = mastery.get("concepts")
    if not isinstance(concepts, dict):
        return None
    keys = [
        str(meta.get("state_id") or ""),
        str(meta.get("unit") or ""),
        str(meta.get("title") or ""),
    ]
    for key in keys:
        if key and isinstance(concepts.get(key), dict):
            info = dict(concepts[key])
            info.setdefault("name", key)
            return info
    title = str(meta.get("title") or "")
    for name, info in concepts.items():
        if not isinstance(info, dict) or not name:
            continue
        if title and (name in title or title in name) and len(name) >= 2:
            result = dict(info)
            result.setdefault("name", name)
            return result
    return None


def _concept_link(concept: Dict[str, Any], entries: List[Dict[str, Any]]) -> str:
    unit = str(concept.get("unit") or "")
    name = str(concept.get("name") or "")
    for entry in entries:
        meta = entry.get("meta", {})
        if unit and (
            str(entry.get("unit") or "") == unit
            or str(meta.get("state_id") or "") == unit
        ):
            return entry["html_name"]
    for entry in entries:
        title = str(entry.get("title") or "")
        if name and title and (name in title or title in name):
            return entry["html_name"]
    return ""


def render_index_page(
    course: str,
    entries: List[Dict[str, Any]],
    state: Optional[Dict[str, Any]] = None,
    course_dir_name: str = "",
) -> str:
    lessons = [e for e in entries if e.get("kind") != "practice"]
    practice_count = len(entries) - len(lessons)
    total = len(lessons)
    done = sum(1 for e in lessons if e.get("final_status") == "已完成")
    mastery = _mastery_view(state)
    weak = mastery["weak"]
    due_count = sum(1 for e in lessons if e.get("is_due"))
    if mastery["due"]:
        due_count = max(due_count, len(mastery["due"]))
    percent = 0
    state_percent = None
    if isinstance(state, dict):
        progress = state.get("progress")
        if isinstance(progress, dict):
            state_percent = progress.get("overall_percent")
    if isinstance(state_percent, (int, float)) and not (
        int(state_percent) == 0 and done > 0
    ):
        percent = max(0, min(100, int(state_percent)))
    elif total:
        percent = int(round(done * 100.0 / total))

    # 到期复习：优先用掌握度数据（含概念级复习），再补讲义 frontmatter 里的
    due_items: List[str] = []
    seen_titles = set()
    for concept in mastery["due"]:
        href = _concept_link(concept, lessons)
        title = html.escape(concept["name"])
        label = '<a href="%s">%s</a>' % (html.escape(href, quote=True), title) if href else title
        due_items.append(
            "<li>%s · <span class=\"level\">Lv%d %s</span></li>"
            % (label, concept["level"], html.escape(concept["status"]))
        )
        seen_titles.add(concept["name"])
    for entry in lessons:
        if entry.get("is_due") and entry["title"] not in seen_titles:
            due_items.append(
                '<li><a href="%s">%s</a> · %s</li>'
                % (
                    html.escape(entry["html_name"], quote=True),
                    html.escape(entry["title"]),
                    html.escape(str(entry.get("review_at") or "待复习")),
                )
            )
            seen_titles.add(entry["title"])
    due_html = ""
    if due_items:
        due_html = (
            '<section class="due-box"><h2>该复习了（%d）</h2><ul>%s</ul></section>'
            % (len(due_items), "".join(due_items[:8]))
        )

    weak_html = ""
    if weak:
        items = []
        for concept in weak[:8]:
            href = _concept_link(concept, lessons)
            label = (
                '<a href="%s">%s</a>' % (html.escape(href, quote=True), html.escape(concept["name"]))
                if href
                else html.escape(concept["name"])
            )
            items.append(
                "<li>%s · <span class=\"level\">Lv%d %s</span>%s</li>"
                % (
                    label,
                    concept["level"],
                    html.escape(concept["status"]),
                    " · 待变式验证"
                    if concept["level"] == 2 and not concept["variant_passed"]
                    else "",
                )
            )
        weak_html = (
            '<section class="due-box weak-box"><h2>薄弱知识点（%d）</h2>'
            "<ul>%s</ul></section>" % (len(weak), "".join(items))
        )

    action_html = ""
    action = mastery["action"]
    action_labels = {
        "reteach": "重讲",
        "practice": "继续练习",
        "review": "到期复习",
        "advance": "推进下一单元",
        "start": "开始新单元",
    }
    if action:
        label = action_labels.get(str(action.get("type")), str(action.get("type")))
        target = str(action.get("target") or "")
        if action.get("mode") == "variant":
            label += "（变式验证）"
        target_html = ""
        if target:
            concept = {"name": target, "unit": str(action.get("unit") or "")}
            href = _concept_link(concept, lessons)
            target_html = (
                '<a href="%s">%s</a>' % (html.escape(href, quote=True), html.escape(target))
                if href
                else html.escape(target)
            )
        action_html = (
            '<section class="next-box"><h2>AI 建议下一步</h2>'
            "<p><strong>%s</strong>%s</p><p>%s</p></section>"
            % (
                html.escape(label),
                (" · " + target_html) if target_html else "",
                html.escape(str(action.get("reason") or "")),
            )
        )

    rows: List[str] = []
    for entry in entries:
        status = entry.get("final_status") or ""
        css_status = {
            "已完成": "done",
            "进行中": "doing",
            "待复习": "due",
            "待学": "todo",
        }.get(status, "")
        if entry.get("is_due") and status != "已完成":
            css_status = "due"
        status_pill = (
            '<span class="chip %s">%s</span>'
            % (STATUS_CLASSES.get(status, "status-todo"), html.escape(status))
            if status
            else ""
        )
        review_pill = (
            '<span class="chip status-due">复习 %s</span>' % html.escape(str(entry["review_at"]))
            if entry.get("is_due")
            else ""
        )
        date_text = html.escape(str(entry.get("date") or ""))
        kind = str(entry.get("kind") or "lesson")
        kind_tag = '<span class="chip kind">练习</span>' if kind == "practice" else ""
        tags = kind_tag + "".join(
            '<span class="chip tag">%s</span>' % html.escape(t)
            for t in entry.get("tags", [])
        )
        search_blob = " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("unit", "")),
                "练习" if kind == "practice" else "讲义",
                " ".join(entry.get("tags", [])),
            ]
        )
        unit_text = "练" if kind == "practice" else str(entry.get("unit") or "·")
        rows.append(
            '<a class="lesson-row %s" href="%s" data-status="%s" data-kind="%s" data-search="%s">'
            '<span class="unit-badge">%s</span>'
            '<span class="row-main"><span class="row-title">%s</span>'
            '<span class="row-desc">%s</span>'
            '<span class="row-tags">%s</span></span>'
            '<span class="row-side">%s%s<span class="row-date">%s</span></span>'
            "</a>"
            % (
                css_status,
                html.escape(entry["html_name"], quote=True),
                html.escape(status, quote=True),
                html.escape(kind, quote=True),
                html.escape(search_blob, quote=True),
                html.escape(unit_text),
                html.escape(entry["title"]),
                html.escape(str(entry.get("description") or "")),
                tags,
                status_pill,
                review_pill,
                date_text,
            )
        )

    if rows:
        list_html = '<div class="lesson-list">%s</div>' % "".join(rows)
    else:
        list_html = (
            '<div class="empty-state">这个课程还没有讲义。对 AI 老师说“教我……”并学完一个单元后，'
            "讲义会自动生成到这里。</div>"
        )

    page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="teacher.skill v__VERSION__">
<title>__COURSE__ · 课程讲义</title>
<style>__CSS__</style>
</head>
<body>
<a class="skip" href="#main">跳到正文</a>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand"><span class="logo">T</span><span>__COURSE__</span></div>
    <div class="topbar-actions"><button class="btn" id="print-btn" type="button" onclick="window.print()">打印 / PDF</button></div>
  </div>
</header>
<main class="index-shell" id="main">
  <header class="index-hero">
    <div class="eyebrow">teacher.skill · 课程讲义</div>
    <h1>__COURSE__</h1>
    <p class="index-desc">所有单元的讲义与练习都保存在这里。答案默认折叠，先自己做一遍，再点开核对。</p>
  </header>
  <section class="stats" aria-label="学习统计">
    <div class="stat"><strong>__TOTAL__</strong><span>单元总数</span></div>
    <div class="stat"><strong>__DONE__</strong><span>已完成</span></div>
    <div class="stat"><strong>__DUE__</strong><span>待复习</span></div>
    <div class="stat"><strong>__WEAK__</strong><span>薄弱知识点</span></div>
  </section>
  <div class="progress" aria-label="完成进度"><i style="width:__PERCENT__%"></i></div>
  <p class="index-desc">完成度 __PERCENT__% · 更新于 __GENERATED__ · 练习卷 __PRACTICE__ 份</p>
  __DUE__HTML__
  __WEAK__HTML__
  __ACTION__HTML__
  <div class="toolbar">
    <input id="search" type="search" placeholder="搜索单元 / 标题 / 标签…" aria-label="搜索讲义">
    <div class="filters">
      <button class="filter active" data-filter="all" type="button">全部</button>
      <button class="filter" data-filter="已完成" type="button">已完成</button>
      <button class="filter" data-filter="进行中" type="button">进行中</button>
      <button class="filter" data-filter="待复习" type="button">待复习</button>
      <button class="filter" data-filter="待学" type="button">待学</button>
    </div>
  </div>
  __LIST__
  <p class="index-footer">由 teacher.skill v__VERSION__ 生成 · 本地文件，可离线打开<br>课程目录：__DIR__</p>
</main>
<script>__JS__</script>
</body>
</html>
"""
    replacements = {
        "__VERSION__": VERSION,
        "__COURSE__": html.escape(course),
        "__CSS__": INDEX_CSS,
        "__TOTAL__": str(total),
        "__DONE__": str(done),
        "__DUE__": str(due_count),
        "__WEAK__": str(len(weak)),
        "__PRACTICE__": str(practice_count),
        "__PERCENT__": str(percent),
        "__GENERATED__": date.today().isoformat(),
        "__DUE__HTML__": due_html,
        "__WEAK__HTML__": weak_html,
        "__ACTION__HTML__": action_html,
        "__LIST__": list_html,
        "__DIR__": html.escape(course_dir_name or course),
        "__JS__": INDEX_JS,
    }
    page = page.replace("__DUE__HTML__", due_html)
    page = page.replace("__WEAK__HTML__", weak_html)
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page


# ---------------------------------------------------------------------------
# 数据 / 学习状态
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _entry_from_markdown(path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    title = str(meta.get("title") or path.stem)
    unit = meta.get("unit") if meta.get("unit") not in (None, "") else ""
    if not unit:
        match = re.search(r"unit[-_ ]?(\d+)", path.stem, re.I)
        if match:
            unit = int(match.group(1))
    status = normalize_status(meta.get("status"))
    review_raw = meta.get("review_at") or meta.get("review") or ""
    review_at = str(review_raw).strip()
    tags = as_list(meta.get("tags"))
    description = str(meta.get("description") or "").strip()
    kind = str(meta.get("kind") or "lesson").strip().lower()
    parent_unit = meta.get("parent_unit") if meta.get("parent_unit") not in (None, "") else ""
    return {
        "path": path,
        "stem": path.stem,
        "html_name": path.stem + ".html",
        "title": title,
        "unit": unit,
        "kind": kind,
        "parent_unit": parent_unit,
        "status": status,
        "final_status": status,
        "review_at": review_at,
        "is_due": False,
        "date": str(meta.get("date") or ""),
        "tags": tags,
        "description": description,
        "meta": meta,
    }


def _sort_key(entry: Dict[str, Any]) -> Tuple[int, int, Any, str]:
    kind_rank = 1 if entry.get("kind") == "practice" else 0
    unit = entry.get("parent_unit") if kind_rank and entry.get("parent_unit") else entry.get("unit")
    order = entry.get("meta", {}).get("order")
    if isinstance(unit, int) or re.fullmatch(r"\d+", str(unit)):
        return (kind_rank, 0, int(str(unit)), entry.get("title", ""))
    if isinstance(order, int) or re.fullmatch(r"\d+", str(order or "")):
        return (kind_rank, 1, int(str(order)), entry.get("title", ""))
    return (kind_rank, 2, str(unit or ""), entry.get("title", ""))


def scan_entries(course_dir: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for path in sorted(course_dir.glob("*.md")):
        if path.name.startswith("."):
            continue
        try:
            meta, _ = parse_frontmatter(_read_text(path))
        except (OSError, UnicodeError) as exc:
            _warn("读取 %s 失败：%s" % (path, exc))
            continue
        if not meta.get("title") and not re.search(r"unit", path.stem, re.I):
            continue
        entries.append(_entry_from_markdown(path, meta))
    entries.sort(key=_sort_key)
    return entries


def _coerce_state_map(state: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """把 learning-state.json 压成 {key: info}，key 包括 id 和标题。"""
    result: Dict[str, Dict[str, Any]] = {}
    if not isinstance(state, dict):
        return result

    route = state.get("route") if isinstance(state.get("route"), dict) else {}
    for unit in route.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        info = {
            "status": normalize_status(unit.get("status")),
            "review_at": "",
            "name": str(unit.get("title") or ""),
        }
        for key in (str(unit.get("id") or ""), info["name"]):
            if key:
                result[key] = info

    progress = state.get("progress") if isinstance(state.get("progress"), dict) else {}
    for done in progress.get("completed_units", []) or []:
        if not isinstance(done, dict):
            continue
        info = {
            "status": "已完成",
            "review_at": str(done.get("next_review_at") or ""),
            "name": str(done.get("name") or ""),
        }
        for key in (str(done.get("id") or ""), info["name"]):
            if key:
                result[key] = info
    return result


def _match_state(entry: Dict[str, Any], state_map: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not state_map:
        return None
    meta = entry.get("meta", {})
    explicit = str(meta.get("state_id") or "").strip()
    candidates = []
    if explicit:
        candidates.append(explicit)
    if entry.get("unit") not in (None, ""):
        candidates.append(str(entry["unit"]))
    candidates.append(entry.get("title", ""))
    for key in candidates:
        if key and key in state_map:
            return state_map[key]
    # 标题包含匹配（避免“第2章 2.1”这类长标题对不上）
    title = str(entry.get("title") or "")
    for key, info in state_map.items():
        if key and title and (key in title or title in key) and len(key) >= 2:
            return info
    return None


def apply_state(entries: List[Dict[str, Any]], state: Optional[Dict[str, Any]]) -> None:
    state_map = _coerce_state_map(state)
    today = date.today()
    for entry in entries:
        info = _match_state(entry, state_map)
        if info:
            if info.get("status"):
                entry["final_status"] = info["status"]
            if info.get("review_at"):
                entry["review_at"] = info["review_at"]
        review = _parse_date(entry.get("review_at"))
        if review and review <= today and entry.get("final_status") != "已完成":
            entry["is_due"] = True
        elif review and review <= today:
            entry["is_due"] = True


def _parse_date(value: Any) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("/", "-")
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def load_state(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    if not path.exists():
        _warn("学习状态文件不存在：%s" % path)
        return None
    try:
        data = json.loads(_read_text(path))
        if not isinstance(data, dict):
            raise ValueError("根节点不是对象")
        return data
    except (OSError, UnicodeError, ValueError) as exc:
        _warn("学习状态 JSON 解析失败（%s）：%s；将只使用讲义 frontmatter 的状态。" % (path, exc))
        return None


def discover_state(course: str, explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        path = Path(explicit)
        return path if path.exists() else path
    candidate = Path("teachers") / safe_component(course) / "learning-state.json"
    if candidate.exists():
        return candidate
    for path in sorted(Path(".").glob(DEFAULT_STATE_GLOB)):
        try:
            data = json.loads(_read_text(path))
        except (OSError, UnicodeError, ValueError):
            continue
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        names = {
            str(meta.get("name", "")),
            str(data.get("route", {}).get("subject", "")),
        } if isinstance(data, dict) else set()
        if course in names or safe_component(course) in names:
            return path
    return None


# ---------------------------------------------------------------------------
# 构建
# ---------------------------------------------------------------------------


def render_markdown(markdown: str) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
    meta, body = parse_frontmatter(markdown)
    body = strip_leading_h1(body)
    renderer = MarkdownRenderer()
    content, headings = renderer.render(body)
    return meta, content, headings


def strip_leading_h1(body: str) -> str:
    """正文开头通常重复写了一次单元标题，页面头部已有 h1，这里去掉。"""
    lines = body.replace("\r\n", "\n").split("\n")
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        if re.match(r"^#\s+", line):
            del lines[idx]
        break
    return "\n".join(lines)


def build_lesson(
    course: str,
    source: Path,
    output_root: Path,
    state_path: Optional[Path] = None,
    course_dir_name: Optional[str] = None,
    quiet: bool = False,
) -> Dict[str, Path]:
    if not source.exists():
        raise FileNotFoundError("找不到源文件：%s" % source)
    raw = _read_text(source)
    meta, body = parse_frontmatter(raw)
    if not meta.get("title"):
        match = re.search(r"unit[-_ ]?(\d+)", source.stem, re.I)
        meta["title"] = source.stem
        if match:
            meta["unit"] = int(match.group(1))
    if not meta.get("unit") and meta.get("order"):
        meta["unit"] = meta["order"]
    if not meta.get("course"):
        meta["course"] = course

    folder = safe_component(course_dir_name or course)
    course_dir = output_root / folder
    course_dir.mkdir(parents=True, exist_ok=True)

    kind = str(meta.get("kind") or "lesson").strip().lower()
    if kind == "practice":
        unit_part = meta.get("parent_unit") or meta.get("unit")
        if re.fullmatch(r"\d+", str(unit_part or "")):
            stem = "practice-%02d-%s" % (int(str(unit_part)), slugify(meta.get("title")))
        else:
            stem = "practice-%s" % slugify(meta.get("title"))
    else:
        stem = unit_file_stem(meta.get("unit"), meta.get("title"))
    md_path = course_dir / (stem + ".md")
    html_path = course_dir / (stem + ".html")
    if source.resolve() != md_path.resolve():
        md_path.write_text(raw, encoding="utf-8")

    entries = scan_entries(course_dir)
    state = load_state(state_path)
    apply_state(entries, state)
    current_index = next(
        (idx for idx, entry in enumerate(entries) if entry["stem"] == stem), -1
    )
    prev_entry = entries[current_index - 1] if current_index > 0 else None
    next_entry = entries[current_index + 1] if 0 <= current_index < len(entries) - 1 else None

    renderer = MarkdownRenderer()
    content, headings = renderer.render(strip_leading_h1(body))
    mastery_info = _find_mastery_concept(state, meta)
    page = render_lesson_page(
        meta, content, headings, course, prev_entry, next_entry, mastery_info
    )
    html_path.write_text(page, encoding="utf-8")

    index_html = render_index_page(course, entries, state, folder)
    (course_dir / "index.html").write_text(index_html, encoding="utf-8")
    if not quiet:
        _log("已生成：%s" % html_path)
        _log("已更新：%s" % (course_dir / "index.html"))
    return {"markdown": md_path, "html": html_path, "index": course_dir / "index.html"}


def rebuild_course(
    course: str,
    output_root: Path,
    state_path: Optional[Path] = None,
    course_dir_name: Optional[str] = None,
    quiet: bool = False,
) -> List[Path]:
    folder = safe_component(course_dir_name or course)
    course_dir = output_root / folder
    if not course_dir.exists():
        raise FileNotFoundError("课程目录不存在：%s" % course_dir)
    entries = scan_entries(course_dir)
    state = load_state(state_path)
    apply_state(entries, state)
    built: List[Path] = []
    for idx, entry in enumerate(entries):
        meta, body = parse_frontmatter(_read_text(entry["path"]))
        renderer = MarkdownRenderer()
        content, headings = renderer.render(strip_leading_h1(body))
        prev_entry = entries[idx - 1] if idx > 0 else None
        next_entry = entries[idx + 1] if idx < len(entries) - 1 else None
        mastery_info = _find_mastery_concept(state, meta)
        page = render_lesson_page(
            meta, content, headings, course, prev_entry, next_entry, mastery_info
        )
        html_path = course_dir / entry["html_name"]
        html_path.write_text(page, encoding="utf-8")
        built.append(html_path)
        if not quiet:
            _log("已重建：%s" % html_path)
    index_html = render_index_page(course, entries, state, folder)
    (course_dir / "index.html").write_text(index_html, encoding="utf-8")
    if not quiet:
        _log("已更新：%s" % (course_dir / "index.html"))
    return built


def rebuild_index_only(
    course: str,
    output_root: Path,
    state_path: Optional[Path] = None,
    course_dir_name: Optional[str] = None,
    quiet: bool = False,
) -> Path:
    folder = safe_component(course_dir_name or course)
    course_dir = output_root / folder
    if not course_dir.exists():
        raise FileNotFoundError("课程目录不存在：%s" % course_dir)
    entries = scan_entries(course_dir)
    state = load_state(state_path)
    apply_state(entries, state)
    index_html = render_index_page(course, entries, state, folder)
    (course_dir / "index.html").write_text(index_html, encoding="utf-8")
    if not quiet:
        _log("已更新：%s（%d 个单元）" % ((course_dir / "index.html"), len(entries)))
    return course_dir / "index.html"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="teacher.skill v%s - 把 Markdown 讲义渲染成自包含 HTML，并维护课程目录。" % VERSION
    )
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--course", required=True, help="课程名称，例如 计算机组成原理")
        p.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="输出根目录（默认：讲义）")
        p.add_argument("--course-dir", default=None, help="课程子目录名（默认取课程名）")
        p.add_argument("--state", default=None, help="learning-state.json 路径（可自动发现）")
        p.add_argument("--quiet", action="store_true", help="不打印生成日志")

    build = sub.add_parser("build", help="渲染单个讲义并更新目录")
    common(build)
    build.add_argument("--file", required=True, help="Markdown 源文件路径")

    rebuild = sub.add_parser("rebuild", help="重建课程目录下所有 HTML")
    common(rebuild)

    index = sub.add_parser("index", help="只重建课程目录 index.html")
    common(index)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    output_root = Path(args.output_dir)
    state_path = discover_state(args.course, args.state)
    try:
        if args.command == "build":
            result = build_lesson(
                args.course,
                Path(args.file),
                output_root,
                state_path,
                args.course_dir,
                args.quiet,
            )
            return 0 if result else 1
        if args.command == "rebuild":
            rebuild_course(
                args.course, output_root, state_path, args.course_dir, args.quiet
            )
            return 0
        if args.command == "index":
            rebuild_index_only(
                args.course, output_root, state_path, args.course_dir, args.quiet
            )
            return 0
    except (FileNotFoundError, OSError, UnicodeError) as exc:
        _warn(str(exc))
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
