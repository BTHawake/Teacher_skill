#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""teacher.skill v4.3 - HTML 讲义 / 练习导出器。

把 AI 老师写好的 Markdown 讲义渲染成不依赖网络的单文件 HTML，并维护一个
课程总目录 index.html，方便课后复习。

用法（在工作区根目录执行）：

    python scripts/lesson_html.py build --course "计算机组成原理" \
        --file "讲义/计算机组成原理/unit-04.md" \
        --state "teachers/计算机组成原理/learning-state.json"

    python scripts/lesson_html.py rebuild --course "计算机组成原理" \
        --state "teachers/计算机组成原理/learning-state.json"

    python scripts/lesson_html.py index --course "计算机组成原理"

输出目录默认是工作区顶层的 ``讲义/<课程>/``。主课件用稳定编号：

    unit-04.md     # 源文件（可再次编辑 / rebuild）
    unit-04.html   # 自包含页面（讲义 + 练习 + 折叠答案）
    index.html     # 课程目录 / 复习入口

源文件不在课程目录时默认只警告、不复制；需要复制时显式传 --copy-source。
只使用 Python 标准库，兼容 Python 3.9+。
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

VERSION = "4.3.2"
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
    "hint": {"label": "提示", "icon": "?", "class": "hint"},
    "think": {"label": "先想一想", "icon": "★", "class": "think"},
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
    """Stable lesson identity: unit number, not the mutable title."""
    unit_text = str(unit if unit not in (None, "") else "").strip()
    if re.fullmatch(r"\d+", unit_text):
        return "unit-%02d" % int(unit_text)
    if unit_text:
        return "unit-" + slugify(unit_text, "x")
    return "lesson-" + slugify(title)


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
        self.quiz: Optional[Dict[str, Any]] = None
        self.quiz_error = ""
        self._diagram_seq = 0

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
                diagram_kinds = {"flow", "layers", "timeline", "cycle", "compare", "bars"}
                if kind == "flip":
                    out.append(self._render_flip(title, inner))
                elif kind in diagram_kinds:
                    out.append(self._render_diagram(kind, title, inner))
                else:
                    if kind in ("formula", "definition", "hint", "think"):
                        inner_lines = [_inline(line) for line in inner if line.strip()]
                        inner_html = '<div class="callout-lines">%s</div>' % "\n".join(inner_lines)
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
                if lang.lower() == "quiz":
                    try:
                        data = json.loads(code)
                        if isinstance(data, list):
                            data = {"questions": data}
                        if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
                            raise ValueError('quiz 需要 {"questions": [...]} 结构')
                        if self.quiz is None:
                            self.quiz = data
                        else:
                            self.quiz["questions"].extend(data["questions"])
                        out.append("<!--QUIZ-->")
                    except (ValueError, TypeError) as exc:
                        self.quiz_error = str(exc)
                        out.append(
                            '<div class="quiz-error">练习数据解析失败：%s</div>'
                            % html.escape(str(exc))
                        )
                    i = j + 1
                    continue
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
        if kind in ("answer", "hint", "think"):
            return (
                '<details class="%s">'
                '<summary><span class="answer-icon">%s</span>%s</summary>'
                '<div class="answer-body">%s</div></details>'
                % (
                    "answer" if kind == "answer" else ("hint" if kind == "hint" else "hint think"),
                    info["icon"],
                    _inline(label),
                    inner_html,
                )
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

    def _render_diagram(self, kind: str, title: str, inner: Sequence[str]) -> str:
        labels = {
            "flow": "流程",
            "layers": "层次",
            "timeline": "时间线",
            "cycle": "循环",
            "compare": "对比",
            "bars": "数据",
        }
        title = title.strip() or labels.get(kind, kind)
        if kind == "flow":
            body = self._render_flow(inner)
        elif kind == "layers":
            body = self._render_layers(inner)
        elif kind == "timeline":
            body = self._render_timeline(inner)
        elif kind == "cycle":
            body = self._render_cycle(inner)
        elif kind == "compare":
            body = self._render_compare(inner)
        elif kind == "bars":
            body = self._render_bars(inner)
        else:
            return ""
        if not body:
            return ""
        return (
            '<figure class="diagram diagram-%s"><figcaption>%s</figcaption>%s</figure>'
            % (kind, _inline(title), body)
        )

    def _render_flow(self, inner: Sequence[str]) -> str:
        raw = " ".join(line.strip() for line in inner if line.strip())
        if not raw:
            return ""
        nodes = [n.strip() for n in re.split(r"\s*(?:→|->|⇒|➜)\s*", raw) if n.strip()]
        if len(nodes) < 2:
            return ""
        parts: List[str] = []
        for idx, node in enumerate(nodes):
            parts.append(
                '<span class="flow-node" style="--i:%d">%s</span>' % (idx, _inline(node))
            )
            if idx < len(nodes) - 1:
                parts.append('<span class="flow-arrow" aria-hidden="true">→</span>')
        return '<div class="flow-track">%s</div>' % "".join(parts)

    def _render_layers(self, inner: Sequence[str]) -> str:
        lines = [line.strip() for line in inner if line.strip()]
        if not lines:
            return ""
        parts: List[str] = []
        total = len(lines)
        for idx, line in enumerate(lines):
            name, note = line, ""
            if "|" in line:
                name, note = [part.strip() for part in line.split("|", 1)]
            width = 100 if total == 1 else 55 + 45.0 * idx / (total - 1)
            parts.append(
                '<div class="layer" style="--w:%.0f%%;--i:%d">'
                '<span class="layer-name">%s</span>%s</div>'
                % (
                    width,
                    idx,
                    _inline(name),
                    ('<span class="layer-note">%s</span>' % _inline(note)) if note else "",
                )
            )
        return '<div class="layers">%s</div>' % "".join(parts)

    def _render_timeline(self, inner: Sequence[str]) -> str:
        items: List[str] = []
        for idx, line in enumerate([line.strip() for line in inner if line.strip()]):
            date, text = "", line
            if "|" in line:
                date, text = [part.strip() for part in line.split("|", 1)]
            else:
                match = re.match(r"^((?:19|20)\d{2}(?:-\d{1,2})?)\s+(.+)$", line)
                if match:
                    date, text = match.group(1), match.group(2)
            items.append(
                '<li style="--i:%d"><span class="timeline-dot"></span>'
                '<div class="timeline-card">%s<div class="timeline-text">%s</div></div></li>'
                % (
                    idx,
                    ('<div class="timeline-date">%s</div>' % _inline(date)) if date else "",
                    _inline(text),
                )
            )
        if not items:
            return ""
        return '<ol class="timeline">%s</ol>' % "".join(items)

    def _render_cycle(self, inner: Sequence[str]) -> str:
        raw = " ".join(line.strip() for line in inner if line.strip())
        nodes = [n.strip() for n in re.split(r"\s*(?:→|->|⇒|➜)\s*", raw) if n.strip()]
        if len(nodes) < 3 or len(nodes) > 8:
            return self._render_flow(inner)
        self._diagram_seq += 1
        uid = "cycle-%d" % self._diagram_seq
        width, height = 460, 340
        cx, cy, radius, node_r = 230, 170, 118, 40
        angles = [math.radians(-90 + i * 360.0 / len(nodes)) for i in range(len(nodes))]
        points = [
            (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            for angle in angles
        ]
        edges: List[str] = []
        delta = min(0.38, (2 * math.pi / len(nodes)) * 0.32)
        for idx in range(len(nodes)):
            a1 = angles[idx] + delta
            a2 = angles[(idx + 1) % len(nodes)] - delta
            x1, y1 = cx + radius * math.cos(a1), cy + radius * math.sin(a1)
            x2, y2 = cx + radius * math.cos(a2), cy + radius * math.sin(a2)
            edges.append(
                '<path class="cycle-edge" d="M %.1f %.1f A %d %d 0 0 1 %.1f %.1f" '
                'marker-end="url(#%s-arrow)"/>'
                % (x1, y1, radius, radius, x2, y2, uid)
            )
        node_svg: List[str] = []
        for idx, node in enumerate(nodes):
            x, y = points[idx]
            chunks = [node[i : i + 6] for i in range(0, len(node), 6)][:2]
            if len(chunks) == 1:
                text_y = y + 4
                spans = '<tspan x="%.1f" y="%.1f">%s</tspan>' % (
                    x,
                    text_y,
                    html.escape(chunks[0]),
                )
            else:
                spans = (
                    '<tspan x="%.1f" y="%.1f">%s</tspan>'
                    '<tspan x="%.1f" y="%.1f">%s</tspan>'
                    % (
                        x,
                        y - 4,
                        html.escape(chunks[0]),
                        x,
                        y + 12,
                        html.escape(chunks[1]),
                    )
                )
            node_svg.append(
                '<g class="cycle-node" style="--i:%d">'
                '<circle cx="%.1f" cy="%.1f" r="%d"/>'
                '<text x="%.1f" y="%.1f" text-anchor="middle">%s</text></g>'
                % (idx, x, y, node_r, x, y, spans)
            )
        svg = (
            '<svg viewBox="0 0 %d %d" role="img" aria-label="%s">'
            '<defs><marker id="%s-arrow" viewBox="0 0 10 10" refX="8" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M0,0 L10,5 L0,10 z" fill="var(--accent)"/></marker></defs>'
            "%s%s</svg>"
            % (
                width,
                height,
                _escape("循环图"),
                uid,
                "".join(edges),
                "".join(node_svg),
            )
        )
        return svg

    def _render_compare(self, inner: Sequence[str]) -> str:
        inner_html, _ = self._blocks(inner, 0)
        if not inner_html.strip():
            return ""
        return '<div class="compare-body">%s</div>' % inner_html

    def _render_bars(self, inner: Sequence[str]) -> str:
        items: List[Tuple[str, float, str]] = []
        for line in [line.strip() for line in inner if line.strip()]:
            match = re.match(r"^(.+?)\s*[:|]\s*(-?\d+(?:\.\d+)?)\s*(%?)$", line)
            if not match:
                continue
            items.append((match.group(1).strip(), float(match.group(2)), match.group(3)))
        if not items:
            return ""
        max_value = max(abs(value) for _, value, _ in items) or 1.0
        parts: List[str] = []
        for idx, (label, value, suffix) in enumerate(items):
            width = max(2.0, abs(value) / max_value * 100.0)
            parts.append(
                '<div class="bar-row" style="--i:%d">'
                '<span class="bar-label">%s</span>'
                '<span class="bar-track"><span class="bar-fill" style="--w:%.1f%%"></span></span>'
                '<span class="bar-value">%s%s</span></div>'
                % (idx, _inline(label), width, ("%g" % value), suffix)
            )
        return '<div class="bars">%s</div>' % "".join(parts)

    def _render_flip(self, title: str, inner: Sequence[str]) -> str:
        """交互翻转卡：正面一句话/问题，背面解释。用单独一行 --- 分隔。"""
        front: List[str] = []
        back: List[str] = []
        target = front
        for line in inner:
            if line.strip() == "---":
                target = back
                continue
            target.append(line)
        front_html, _ = self._blocks(front, 0)
        back_html, _ = self._blocks(back, 0)
        if not back_html.strip():
            back_html = "<p>（背面内容待补充）</p>"
        label = _inline(title or "概念卡")
        return (
            '<div class="flip-card" tabindex="0" role="button" aria-label="翻转卡片：%s">'
            '<div class="flip-inner">'
            '<div class="flip-face flip-front"><div class="flip-label">%s</div>%s'
            '<span class="flip-tip">点击翻面</span></div>'
            '<div class="flip-face flip-back"><div class="flip-label">背面</div>%s</div>'
            "</div></div>" % (_escape(_strip_tags(label)), label, front_html, back_html)
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
a.btn{display:inline-flex;align-items:center;gap:6px;text-decoration:none}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn-primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn-primary:hover{color:#fff;opacity:.92}
.back-to-chat{border-color:var(--accent);color:var(--accent)}
@media (max-width:640px){
  .topbar-inner{padding:8px 10px;gap:8px}
  .topbar-actions{gap:4px;flex-wrap:nowrap;overflow-x:auto;max-width:calc(100vw - 68px);scrollbar-width:none}
  .topbar-actions::-webkit-scrollbar{display:none}
  .topbar-actions .btn{padding:5px 8px;font-size:11.5px;white-space:nowrap;flex:0 0 auto}
  .brand{flex:0 0 auto}
  .brand a{max-width:68px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
}
[hidden]{display:none!important}
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
.callout-lines{white-space:pre-wrap;overflow-wrap:anywhere}
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
      var all=Array.prototype.slice.call(document.querySelectorAll('details.answer,details.quiz-answer'));
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
    document.querySelectorAll('details.answer,details.quiz-answer').forEach(function(d){
      opened.push([d,d.open]);d.open=true;
    });
  });
  window.addEventListener('afterprint',function(){
    opened.forEach(function(pair){pair[0].open=pair[1];});opened=[];
  });
})();
"""

QUIZ_CSS = r"""
.quiz-card{
  margin:24px 0;padding:18px 20px;border:1px solid var(--border);border-radius:var(--radius);
  background:var(--card);box-shadow:var(--shadow);
}
.quiz-card-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.quiz-card-head strong{font-size:16px}
.quiz-card-head span{color:var(--muted);font-size:12.5px}
.quiz-question{padding:12px 0;border-top:1px dashed var(--border)}
.quiz-question:first-of-type{border-top:0;padding-top:0}
.quiz-q-title{font-size:12.5px;color:var(--muted);letter-spacing:.04em;margin-bottom:4px}
.quiz-prompt{font-weight:600;margin-bottom:8px}
.quiz-options{display:flex;flex-direction:column;gap:6px}
.quiz-option{display:flex;gap:8px;align-items:flex-start;padding:7px 10px;border:1px solid var(--border);border-radius:8px;cursor:pointer}
.quiz-option:hover{border-color:var(--accent);background:var(--accent-soft)}
.quiz-option input{margin-top:4px}
.quiz-option .opt-letter{font-weight:700;color:var(--accent);min-width:18px}
.quiz-text{width:100%;min-height:76px;padding:10px 12px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font:inherit;resize:vertical}
.quiz-text:focus{outline:2px solid var(--accent-soft);border-color:var(--accent)}
.quiz-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.quiz-status{margin:8px 0 0;font-size:13px;color:var(--muted);min-height:18px}
.quiz-status.ok{color:var(--green)}
.quiz-status.err{color:var(--red)}
.quiz-submission{width:100%;margin-top:8px;min-height:90px;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text);font:12px/1.5 monospace;resize:vertical}
.quiz-answer{margin-top:8px;border:1px solid var(--border);border-radius:8px;padding:0 12px;background:var(--bg)}
.quiz-answer summary{cursor:pointer;color:var(--accent);font-weight:600;padding:8px 0;font-size:13px}
.quiz-answer .quiz-explanation{padding:0 0 10px;font-size:14px}
.quiz-explanation p{margin:4px 0}
.quiz-error{border:1px solid var(--red);background:var(--red-soft);color:var(--red);padding:10px 12px;border-radius:8px;margin:12px 0;font-size:13.5px}
.deck{margin-top:8px}
.deck-top{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.deck-progress{flex:1;height:7px;background:var(--bg);border:1px solid var(--border);border-radius:999px;overflow:hidden}
.deck-progress > i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),#22c55e);transition:width .2s ease}
.deck-counter{font-size:12.5px;color:var(--muted);white-space:nowrap}
.deck-step{display:none;animation:deck-in .18s ease}
.deck-step.active{display:block}
@keyframes deck-in{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.step-kicker{font-size:12px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin-bottom:6px}
.deck-controls{display:flex;justify-content:space-between;gap:10px;margin-top:26px;padding-top:16px;border-top:1px solid var(--border)}
.deck-controls button{min-width:110px}
.deck-controls button:disabled{opacity:.4;cursor:not-allowed}
.deck-toc a{cursor:pointer}
.deck-toc a.active{color:var(--accent);border-left-color:var(--accent);font-weight:600}
@media (max-width:900px){
  .deck-top{position:static}
  .deck-controls button{min-width:0;flex:1}
}
@media print{
  .deck-step{display:block!important;animation:none}
  .deck-top,.deck-controls,.deck-toc{display:none!important}
  .step-kicker{display:none}
}
"""

VIVID_CSS = r"""
/* 主题切换 */
html[data-theme="light"]{
  --bg:#f5f6f8;--card:#ffffff;--text:#1f2328;--muted:#667085;
  --border:#e4e7ec;--accent:#2563eb;--accent-soft:#eff6ff;
  --green:#15803d;--green-soft:#ecfdf3;--amber:#b45309;--amber-soft:#fffbeb;
  --red:#b91c1c;--red-soft:#fef2f2;--purple:#6d28d9;--purple-soft:#f5f3ff;
  --code-bg:#f1f5f9;--shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.1);
}
html[data-theme="dark"]{
  --bg:#0f1115;--card:#161a20;--text:#e6e8eb;--muted:#98a2b3;
  --border:#2a3038;--accent:#60a5fa;--accent-soft:#17233a;
  --green:#4ade80;--green-soft:#12251a;--amber:#fbbf24;--amber-soft:#2a2110;
  --red:#f87171;--red-soft:#2a1515;--purple:#c4b5fd;--purple-soft:#211a35;
  --code-bg:#1c222b;--shadow:0 1px 3px rgba(0,0,0,.4);
}
/* 提示 / 先想一想 */
details.hint{
  border:1px solid var(--border);border-left:4px solid var(--amber);border-radius:0 10px 10px 0;
  background:var(--amber-soft);margin:14px 0;padding:0 14px;
}
details.hint.think{border-left-color:var(--purple);background:var(--purple-soft)}
details.hint summary{
  cursor:pointer;font-weight:700;color:var(--amber);padding:9px 0;list-style:none;
  display:flex;gap:7px;align-items:center;
}
details.hint.think summary{color:var(--purple)}
details.hint summary::-webkit-details-marker{display:none}
details.hint summary::after{content:"▸";margin-left:auto;color:var(--muted);transition:transform .15s}
details.hint[open] summary::after{transform:rotate(90deg)}
details.hint .answer-body{padding:0 0 10px;border-top:1px dashed var(--border);padding-top:8px}
/* 翻转卡 */
.flip-card{display:block;width:100%;min-height:180px;perspective:1200px;margin:18px 0;cursor:pointer}
.flip-inner{position:relative;width:100%;min-height:180px;transition:transform .55s cubic-bezier(.2,.7,.2,1);transform-style:preserve-3d}
.flip-card.flipped .flip-inner{transform:rotateY(180deg)}
.flip-face{
  position:absolute;inset:0;backface-visibility:hidden;border:1px solid var(--border);
  border-radius:14px;background:var(--card);box-shadow:var(--shadow);padding:18px 20px;
  overflow:auto;
}
.flip-front{border-left:4px solid var(--accent)}
.flip-back{transform:rotateY(180deg);border-left:4px solid var(--green);background:var(--green-soft)}
.flip-label{font-weight:800;font-size:17px;margin-bottom:8px}
.flip-tip{display:block;color:var(--muted);font-size:12px;margin-top:10px}
/* 图形通用 */
.diagram figcaption{font-size:13px;color:var(--muted);text-align:left;margin-bottom:10px;font-weight:600}
.flow-track{display:flex;align-items:center;justify-content:center;gap:4px;flex-wrap:wrap}
.flow-node{
  display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:8px 13px;
  border:1px solid var(--border);border-radius:10px;background:var(--card);color:var(--text);
  font-size:14px;line-height:1.35;text-align:center;animation:diagram-pop .35s both;
  animation-delay:calc(var(--i) * .09s);box-shadow:var(--shadow);
}
.flow-arrow{color:var(--accent);font-size:20px;line-height:1;padding:0 2px;animation:arrow-pulse 1.6s infinite}
.layers{display:flex;flex-direction:column;align-items:center;gap:8px}
.layer{
  width:var(--w);min-width:55%;display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:10px 14px;border:1px solid var(--border);border-radius:10px;background:var(--card);
  box-shadow:var(--shadow);animation:diagram-pop .4s both;animation-delay:calc(var(--i) * .1s);
}
.layer-name{font-weight:700}
.layer-note{color:var(--muted);font-size:12.5px;text-align:right}
.timeline{list-style:none;margin:6px 0;padding:0 0 0 22px;position:relative}
.timeline::before{content:"";position:absolute;left:7px;top:4px;bottom:4px;width:2px;background:var(--border)}
.timeline li{position:relative;margin:0 0 14px;padding-left:6px;animation:diagram-pop .4s both;animation-delay:calc(var(--i) * .1s)}
.timeline-dot{position:absolute;left:-20px;top:7px;width:11px;height:11px;border-radius:50%;background:var(--accent);border:2px solid var(--card);box-shadow:0 0 0 2px var(--accent-soft)}
.timeline-card{border:1px solid var(--border);border-radius:10px;background:var(--card);padding:9px 12px}
.timeline-date{color:var(--accent);font-weight:700;font-size:12.5px;margin-bottom:2px}
.timeline-text{font-size:14px}
.cycle-edge{fill:none;stroke:var(--accent);stroke-width:2;stroke-dasharray:7 6;animation:cycle-flow 1.2s linear infinite}
.cycle-node circle{fill:var(--card);stroke:var(--accent);stroke-width:2}
.cycle-node text{fill:var(--text);font-size:12.5px;font-weight:600}
.cycle-node{animation:diagram-pop .4s both;animation-delay:calc(var(--i) * .08s)}
.compare-body .table-wrap{margin:0}
.bars{display:flex;flex-direction:column;gap:9px}
.bar-row{display:grid;grid-template-columns:minmax(76px,1fr) 3fr auto;gap:10px;align-items:center;animation:diagram-pop .35s both;animation-delay:calc(var(--i) * .08s)}
.bar-label{font-size:13.5px;color:var(--text);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bar-track{height:14px;border-radius:999px;background:var(--bg);border:1px solid var(--border);overflow:hidden}
.bar-fill{display:block;height:100%;width:var(--w);border-radius:999px;background:linear-gradient(90deg,var(--accent),#22c55e);animation:bar-grow .7s both}
.bar-value{font-size:12.5px;color:var(--muted);min-width:42px;text-align:right}
.diagram svg .pulse{animation:svg-pulse 2s ease-in-out infinite}
.diagram svg .flow{stroke-dasharray:8 6;animation:cycle-flow 1.2s linear infinite}
.diagram svg .float{animation:svg-float 3s ease-in-out infinite}
/* 代码复制 */
.content pre.code{position:relative}
.code-copy{
  position:absolute;top:8px;right:8px;z-index:2;border:1px solid #334155;background:#1e293b;
  color:#cbd5e1;border-radius:6px;padding:3px 8px;font-size:11.5px;cursor:pointer;
}
.code-copy:hover{background:#334155;color:#fff}
/* 已读步骤 */
.deck-toc a.visited::after{content:"✓";float:right;color:var(--green);font-size:12px;margin-left:6px}
.deck-read{font-size:12.5px;color:var(--muted);white-space:nowrap}
/* 答题卡计数 */
.quiz-count{font-size:12px;color:var(--muted);margin-left:auto;white-space:nowrap}
/* 动画 */
@keyframes diagram-pop{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes arrow-pulse{0%,100%{opacity:.55;transform:translateX(0)}50%{opacity:1;transform:translateX(2px)}}
@keyframes cycle-flow{to{stroke-dashoffset:-26}}
@keyframes bar-grow{from{width:0}to{width:var(--w)}}
@keyframes svg-pulse{0%,100%{opacity:1}50%{opacity:.45}}
@keyframes svg-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}
}
@media print{
  html[data-theme="light"],html[data-theme="dark"]{
    --bg:#fff;--card:#fff;--text:#000;--muted:#444;--border:#ddd;--code-bg:#f5f5f5;
  }
  .flip-card{min-height:0}
  .flip-inner{transform:none!important}
  .flip-face{position:static;transform:none!important;box-shadow:none;margin-bottom:8px;backface-visibility:visible}
  .flip-back{display:block!important}
}
"""

QUIZ_JS = r"""
(function(){
  var card=document.querySelector('.quiz-card');
  if(!card){return;}
  var status=card.querySelector('.quiz-status');
  var submissionBox=card.querySelector('.quiz-submission');
  var submitBtn=card.querySelector('.quiz-submit');
  var copyBtn=card.querySelector('.quiz-copy');
  var revealBtn=card.querySelector('.quiz-reveal');
  var storageKey='teacher-quiz:'+(card.dataset.course||'')+':'+(card.dataset.unit||'');

  function questions(){
    return Array.prototype.slice.call(card.querySelectorAll('.quiz-question'));
  }
  function collect(){
    var answers=[];
    questions().forEach(function(q){
      var qid=q.getAttribute('data-qid')||'';
      var checked=q.querySelector('input[type=radio]:checked');
      if(checked){
        answers.push({id:qid,value:checked.value});
      }else{
        var ta=q.querySelector('textarea');
        answers.push({id:qid,value:ta?ta.value:''});
      }
    });
    return answers;
  }
  function payload(){
    return {
      workspace:card.dataset.workspace||'',
      course:card.dataset.course||'',
      unit:card.dataset.unit||'',
      title:card.dataset.title||'',
      answers:collect(),
      submitted_at:new Date().toISOString()
    };
  }
  function submissionText(){
    var lines=[];
    if(card.dataset.course){lines.push('课程：'+card.dataset.course);}
    if(card.dataset.unit){lines.push('单元：'+card.dataset.unit);}
    if(card.dataset.title){lines.push('标题：'+card.dataset.title);}
    collect().forEach(function(a){
      lines.push(a.id+': '+(a.value||'（未作答）'));
    });
    return lines.join('\n');
  }
  var countEl=card.querySelector('.quiz-count');
  function updateCount(){
    if(!countEl){return;}
    var total=questions().length;
    var done=collect().filter(function(a){return a.value && a.value.trim();}).length;
    countEl.textContent='已答 '+done+'/'+total;
  }
  function setStatus(msg,cls){
    if(!status){return;}
    status.textContent=msg||'';
    status.className='quiz-status'+(cls?' '+cls:'');
  }
  function saveDraft(){
    try{localStorage.setItem(storageKey,JSON.stringify(collect()));}catch(e){}
  }
  function restoreDraft(){
    var raw=null;
    try{raw=localStorage.getItem(storageKey);}catch(e){}
    if(!raw){return;}
    var draft;
    try{draft=JSON.parse(raw);}catch(e){return;}
    if(!Array.isArray(draft)){return;}
    draft.forEach(function(item){
      var q=card.querySelector('.quiz-question[data-qid="'+item.id+'"]');
      if(!q){return;}
      var radio=q.querySelector('input[type=radio][value="'+item.value+'"]');
      if(radio){radio.checked=true;return;}
      var ta=q.querySelector('textarea');
      if(ta){ta.value=item.value||'';}
    });
  }
  function saveAndCount(){
    saveDraft();
    updateCount();
  }
  card.addEventListener('change',saveAndCount);
  card.addEventListener('input',saveAndCount);
  restoreDraft();
  updateCount();

  function fallbackCopy(text){
    if(!submissionBox){return;}
    submissionBox.hidden=false;
    submissionBox.value=text;
    submissionBox.focus();
    submissionBox.select();
    try{document.execCommand('copy');setStatus('已复制提交文本，粘贴到聊天发给 AI。','ok');}
    catch(e){setStatus('请手动复制下面的提交文本。','err');}
  }
  if(copyBtn){
    copyBtn.addEventListener('click',function(){
      var text=submissionText();
      if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(text).then(function(){
          setStatus('已复制提交文本，粘贴到聊天发给 AI。','ok');
        }).catch(function(){fallbackCopy(text);});
      }else{
        fallbackCopy(text);
      }
    });
  }
  if(revealBtn){
    revealBtn.addEventListener('click',function(){
      var all=Array.prototype.slice.call(card.querySelectorAll('details.quiz-answer'));
      var anyClosed=all.some(function(d){return !d.open;});
      all.forEach(function(d){d.open=anyClosed;});
      revealBtn.textContent=anyClosed?'收起参考答案':'查看参考答案';
    });
  }
  if(submitBtn){
    submitBtn.addEventListener('click',function(){
      var url='';
      var apiPath=card.dataset.apiPath||'';
      try{
        if(apiPath && location.protocol!=='file:'){
          var current=location.pathname;
          var marker=current.indexOf('/teacher/');
          if(marker>=0){
            url=current.slice(0,marker)+'/teacher/api/answers';
          }else{
            url=new URL(apiPath,location.href).href;
          }
        }else if(location.protocol==='file:'){
          var base=card.dataset.serverUrl||'';
          if(base){url=base.replace(/\/$/,'')+'/api/answers';}
        }else{
          url=new URL('api/answers',location.href).href;
        }
      }catch(e){url='';}
      if(!url){
        setStatus('没有检测到本地服务，请点“复制提交文本”发到聊天。','err');
        fallbackCopy(submissionText());
        return;
      }
      var headers={'Content-Type':'application/json'};
      if(card.dataset.apiToken){headers['x-teacher-token']=card.dataset.apiToken;}
      setStatus('正在提交…');
      fetch(url,{
        method:'POST',
        headers:headers,
        body:JSON.stringify(payload())
      }).then(function(r){
        if(!r.ok){throw new Error('HTTP '+r.status);}
        return r.json();
      }).then(function(){
        setStatus('已提交！去聊天告诉 AI：答好了。','ok');
      }).catch(function(){
        setStatus('提交失败（本地服务未启动？）。已生成提交文本，请复制到聊天。','err');
        fallbackCopy(submissionText());
      });
    });
  }
})();
"""

DECK_JS = r"""
(function(){
  var deck=document.querySelector('.deck');
  if(!deck){return;}
  var steps=Array.prototype.slice.call(deck.querySelectorAll('.deck-step'));
  if(!steps.length){return;}
  var links=Array.prototype.slice.call(document.querySelectorAll('.deck-toc a[data-step]'));
  var bar=deck.querySelector('.deck-progress > i');
  var counter=deck.querySelector('.deck-counter');
  var readEl=deck.querySelector('.deck-read');
  var prev=deck.querySelector('.deck-prev');
  var next=deck.querySelector('.deck-next');
  var current=0;
  var total=parseInt(deck.getAttribute('data-total'),10);
  if(!total){total=Math.max(0,steps.length-1);}
  var visited={};
  var visitKey='teacher-deck:'+location.pathname;
  try{visited=JSON.parse(localStorage.getItem(visitKey)||'{}')||{};}catch(e){visited={};}
  function saveVisited(){
    try{localStorage.setItem(visitKey,JSON.stringify(visited));}catch(e){}
  }
  function renderVisited(){
    var count=0;
    links.forEach(function(a,i){
      var seen=!!visited[i];
      a.classList.toggle('visited',seen);
      if(seen && i>0){count++;}
    });
    if(readEl){readEl.textContent='已读 '+count+'/'+total;}
  }
  function markVisited(index){
    if(!visited[index]){visited[index]=true;saveVisited();}
    renderVisited();
  }
  function show(index,scroll){
    current=Math.max(0,Math.min(steps.length-1,index));
    steps.forEach(function(step,i){
      var active=i===current;
      step.classList.toggle('active',active);
      step.setAttribute('aria-hidden',active?'false':'true');
    });
    links.forEach(function(a,i){
      a.classList.toggle('active',i===current);
      if(i===current){a.setAttribute('aria-current','step');}else{a.removeAttribute('aria-current');}
    });
    if(bar){bar.style.width=(total?current/total*100:0)+'%';}
    if(counter){counter.textContent=current===0?'开始':current+' / '+total;}
    markVisited(current);
    if(prev){prev.disabled=current===0;}
    if(next){next.disabled=current===steps.length-1;}
    try{history.replaceState(null,'','#step-'+(current+1));}catch(e){}
    if(scroll){window.scrollTo({top:0,behavior:'smooth'});}
  }
  if(prev){prev.addEventListener('click',function(){show(current-1,true);});}
  if(next){next.addEventListener('click',function(){show(current+1,true);});}
  links.forEach(function(a,i){
    a.addEventListener('click',function(ev){ev.preventDefault();show(i,true);});
  });
  document.addEventListener('keydown',function(ev){
    if(ev.target && /INPUT|TEXTAREA|SELECT/.test(ev.target.tagName)){return;}
    if(ev.key==='ArrowLeft'){show(current-1,true);}
    if(ev.key==='ArrowRight'){show(current+1,true);}
  });
  var match=/^#step-(\d+)$/.exec(location.hash||'');
  renderVisited();
  show(match?parseInt(match[1],10)-1:0,false);
})();
"""

VIVID_JS = r"""
(function(){
  var root=document.documentElement;
  var themeBtn=document.getElementById('theme-btn');
  var themeKey='teacher-theme';
  var modes=['auto','light','dark'];
  var themeLabels={auto:'主题：自动',light:'主题：浅色',dark:'主题：深色'};
  function applyTheme(mode){
    if(mode==='auto'){root.removeAttribute('data-theme');}
    else{root.setAttribute('data-theme',mode);}
    if(themeBtn){themeBtn.textContent=themeLabels[mode]||themeLabels.auto;}
    try{localStorage.setItem(themeKey,mode);}catch(e){}
  }
  var saved='auto';
  try{saved=localStorage.getItem(themeKey)||'auto';}catch(e){}
  applyTheme(saved);
  if(themeBtn){
    themeBtn.addEventListener('click',function(){
      var idx=modes.indexOf(saved);
      saved=modes[(idx+1)%modes.length];
      applyTheme(saved);
    });
  }

  Array.prototype.slice.call(document.querySelectorAll('.flip-card')).forEach(function(card){
    function toggle(){card.classList.toggle('flipped');}
    card.addEventListener('click',function(ev){
      if(ev.target && ev.target.closest && ev.target.closest('a')){return;}
      toggle();
    });
    card.addEventListener('keydown',function(ev){
      if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggle();}
    });
  });

  Array.prototype.slice.call(document.querySelectorAll('pre.code')).forEach(function(pre){
    var btn=document.createElement('button');
    btn.type='button';
    btn.className='code-copy';
    btn.textContent='复制';
    btn.addEventListener('click',function(){
      var code=pre.querySelector('code');
      var text=code?code.textContent:'';
      function done(){btn.textContent='已复制';setTimeout(function(){btn.textContent='复制';},1400);}
      if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(text).then(done).catch(function(){});
      }else{
        var ta=document.createElement('textarea');
        ta.value=text;document.body.appendChild(ta);ta.select();
        try{document.execCommand('copy');done();}catch(e){}
        document.body.removeChild(ta);
      }
    });
    pre.appendChild(btn);
  });

  var back=document.getElementById('back-to-chat');
  if(back){
    var marker=location.pathname.indexOf('/teacher/');
    if(marker<0){return;}
    var dshRoot=(location.pathname.slice(0,marker)||'')+'/';
    var origin=location.origin;
    function sameOrigin(url){
      try{return new URL(url,location.href).origin===origin;}catch(e){return false;}
    }
    var openerUrl='';
    try{
      if(window.opener && !window.opener.closed){openerUrl=window.opener.location.href||'';}
    }catch(e){}
    var ref=document.referrer||'';
    var target='';
    if(openerUrl && sameOrigin(openerUrl)){target=openerUrl;}
    else if(ref && sameOrigin(ref)){target=ref;}
    else{target=dshRoot;}
    back.href=target;
    back.hidden=false;
    back.addEventListener('click',function(ev){
      if(openerUrl && window.opener && !window.opener.closed && sameOrigin(openerUrl)){
        ev.preventDefault();
        try{window.opener.focus();}catch(e){}
      }
    });
  }
})();
"""


DEFAULT_SERVER_URL = "http://127.0.0.1:8765"


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _strip_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def normalize_api_path(value: Any) -> str:
    """Keep a URL path stable even when Git Bash rewrites a leading slash to C:/..."""
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    posix = text.replace("\\", "/")
    marker = posix.find("/teacher/")
    if marker >= 0:
        return posix[marker:]
    if posix.startswith("/"):
        return posix
    return "/" + posix


def _quiz_data_attrs(api_path: str, workspace: str, api_token: str, meta: Dict[str, Any]) -> str:
    attrs: List[str] = []
    path = normalize_api_path(api_path or str(meta.get("api_path") or ""))
    ws = workspace or str(meta.get("workspace") or "")
    token = api_token or str(meta.get("api_token") or "")
    if path:
        attrs.append(' data-api-path="%s"' % _escape(path))
    if ws:
        attrs.append(' data-workspace="%s"' % _escape(ws))
    if token:
        attrs.append(' data-api-token="%s"' % _escape(token))
    return "".join(attrs)


def render_quiz_card(
    quiz: Optional[Dict[str, Any]],
    meta: Dict[str, Any],
    server_url: str = DEFAULT_SERVER_URL,
    api_path: str = "",
    workspace: str = "",
    api_token: str = "",
) -> str:
    """把 ```quiz JSON 渲染成答题卡；答案默认折叠。"""
    if not isinstance(quiz, dict):
        return ""
    questions = quiz.get("questions")
    if not isinstance(questions, list) or not questions:
        return ""

    blocks: List[str] = []
    for idx, question in enumerate(questions, 1):
        if not isinstance(question, dict):
            continue
        qid = str(question.get("id") or "Q%d" % idx)
        qtype = str(question.get("type") or "text").lower()
        prompt = _inline(str(question.get("prompt") or ""))
        options = question.get("options")
        if qtype == "choice" and isinstance(options, list) and options:
            opts: List[str] = []
            for opt_idx, option in enumerate(options):
                label = chr(ord("A") + opt_idx) if opt_idx < 26 else str(opt_idx + 1)
                if isinstance(option, dict):
                    value = str(option.get("value") or label)
                    text = str(option.get("text") or option.get("label") or value)
                else:
                    value = label
                    text = str(option)
                opts.append(
                    '<label class="quiz-option">'
                    '<input type="radio" name="%s" value="%s" data-qid="%s">'
                    '<span class="opt-letter">%s</span><span>%s</span></label>'
                    % (
                        _escape(qid),
                        _escape(value),
                        _escape(qid),
                        _escape(label),
                        _inline(text),
                    )
                )
            body = '<div class="quiz-options">%s</div>' % "".join(opts)
        else:
            body = (
                '<textarea class="quiz-text" data-qid="%s" '
                'placeholder="在这里写答案或关键步骤；也可以只写你的思路"></textarea>'
                % _escape(qid)
            )
        answer = question.get("answer")
        explanation = str(question.get("explanation") or "").strip()
        answer_parts: List[str] = []
        if answer not in (None, ""):
            answer_parts.append("<p><strong>答案：</strong>%s</p>" % _inline(str(answer)))
        if explanation:
            answer_parts.append("<p>%s</p>" % _inline(explanation))
        answer_html = ""
        if answer_parts:
            answer_html = (
                '<details class="quiz-answer"><summary>参考答案</summary>'
                '<div class="quiz-explanation">%s</div></details>'
                % "".join(answer_parts)
            )
        blocks.append(
            '<div class="quiz-question" data-qid="%s" data-qtype="%s">'
            '<div class="quiz-q-title">第 %d 题</div>'
            '<div class="quiz-prompt">%s</div>%s%s</div>'
            % (_escape(qid), _escape(qtype), idx, prompt, body, answer_html)
        )

    if not blocks:
        return ""
    course = _escape(meta.get("course"))
    unit = _escape(meta.get("unit") or meta.get("order") or "")
    title = _escape(meta.get("title"))
    return (
        '<section class="quiz-card" data-course="%s" data-unit="%s" data-title="%s" '
        'data-server-url="%s"%s>'
        '<div class="quiz-card-head"><strong>答题卡</strong>'
        "<span>做完点“提交答案”；若本地服务未启动，点“复制提交文本”发到聊天。</span>"
        '<span class="quiz-count" data-total="%d">已答 0/%d</span></div>'
        "<form class=\"quiz-form\" onsubmit=\"return false\">%s</form>"
        '<div class="quiz-actions">'
        '<button class="btn btn-primary quiz-submit" type="button">提交答案</button>'
        '<button class="btn quiz-copy" type="button">复制提交文本</button>'
        '<button class="btn quiz-reveal" type="button">查看参考答案</button>'
        "</div>"
        '<p class="quiz-status" role="status"></p>'
        '<textarea class="quiz-submission" readonly hidden aria-label="提交文本"></textarea>'
        "</section>"
        % (
            course,
            unit,
            title,
            _escape(server_url),
            _quiz_data_attrs(api_path, workspace, api_token, meta),
            len(blocks),
            len(blocks),
            "".join(blocks),
        )
    )


def _render_deck(content_html: str) -> Tuple[str, List[str]]:
    """把一个单元的正文拆成步骤；每个 h2 是一步，前面加一个开始页。"""
    parts = [p for p in re.split(r"(?=<h2\b)", content_html) if p.strip()]
    preamble = ""
    sections: List[str] = []
    if parts and not re.match(r"^\s*<h2\b", parts[0]):
        preamble = parts[0].strip()
        parts = parts[1:]
    sections = parts
    content_total = len(sections)
    labels = ["开始"]
    for section in sections:
        match = re.search(r"<h2[^>]*>(.*?)</h2>", section, re.S)
        labels.append(_strip_tags(match.group(1)) if match else "步骤")

    steps: List[str] = []
    intro = [
        '<section class="deck-step active" id="step-1" data-step="0" aria-hidden="false">',
        '<div class="step-kicker">开始</div>',
        "<p>本单元共 %d 个步骤。建议按顺序阅读；有疑问随时在聊天里问，做完练习再提交答案。</p>"
        % content_total,
    ]
    if preamble:
        intro.append(preamble)
    intro.append("</section>")
    steps.append("".join(intro))

    for idx, section in enumerate(sections, 1):
        steps.append(
            '<section class="deck-step" id="step-%d" data-step="%d" aria-hidden="true">'
            '<div class="step-kicker">步骤 %d / %d</div>%s</section>'
            % (idx + 1, idx, idx, content_total, section)
        )

    deck = (
        '<div class="deck" data-total="%d">'
        '<div class="deck-top"><div class="deck-progress"><i></i></div>'
        '<span class="deck-counter">开始</span>'
        '<span class="deck-read">已读 0/%d</span></div>'
        '<div class="deck-steps">%s</div>'
        '<div class="deck-controls">'
        '<button class="btn deck-prev" type="button" disabled>← 上一步</button>'
        '<button class="btn btn-primary deck-next" type="button">下一步 →</button>'
        "</div></div>"
        % (content_total, content_total, "".join(steps))
    )
    return deck, labels


def _render_deck_nav(labels: List[str]) -> str:
    if not labels:
        return ""
    items = []
    for idx, label in enumerate(labels):
        items.append(
            '<li><a href="#step-%d" data-step="%d">%s</a></li>'
            % (idx + 1, idx, html.escape(label))
        )
    return (
        '<nav class="toc deck-toc" aria-label="课件步骤">'
        '<p class="toc-title">课件步骤</p><ol>%s</ol></nav>' % "".join(items)
    )


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
    quiz: Optional[Dict[str, Any]] = None,
    server_url: str = DEFAULT_SERVER_URL,
    layout: Optional[str] = None,
    api_path: str = "",
    workspace: str = "",
    api_token: str = "",
) -> str:
    title = str(meta.get("title") or "未命名单元")
    kind = str(meta.get("kind") or "lesson").strip().lower()
    unit = meta.get("unit") or meta.get("order") or ""
    if kind == "practice":
        unit_label = "练习卷"
    elif kind == "reteach":
        unit_label = "补讲"
    elif kind == "review":
        unit_label = "复习"
    elif re.fullmatch(r"\d+", str(unit)):
        unit_label = "第 %s 单元" % unit
    elif str(unit):
        unit_label = "单元 %s" % unit
    else:
        unit_label = "讲义"
    layout = str(layout or meta.get("layout") or ("deck" if kind == "lesson" else "article")).lower()
    if layout not in ("deck", "article"):
        layout = "article"
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
    kind_chip = ""
    if kind in ("practice", "reteach", "review"):
        kind_chip = '<span class="chip kind">%s</span>' % {
            "practice": "练习卷",
            "reteach": "补讲",
            "review": "复习",
        }[kind]
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

    quiz_card = render_quiz_card(quiz, meta, server_url, api_path, workspace, api_token)
    if quiz_card:
        if "<!--QUIZ-->" in content_html:
            content_html = content_html.replace("<!--QUIZ-->", quiz_card)
        else:
            content_html += quiz_card
    else:
        content_html = content_html.replace("<!--QUIZ-->", "")

    if layout == "deck":
        deck_html, step_labels = _render_deck(content_html)
        content_html = deck_html
        toc_html = _render_deck_nav(step_labels)
        body_class = "layout-deck"
    else:
        toc_html = _render_toc(headings)
        body_class = "layout-article"
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
<body class="__BODY_CLASS__">
<a class="skip" href="#main">跳到正文</a>
<header class="topbar">
  <div class="topbar-inner">
    <div class="brand"><span class="logo">T</span><a href="index.html">__COURSE__</a></div>
    <div class="topbar-actions">
      <a class="btn back-to-chat" id="back-to-chat" href="#" hidden>← 返回对话</a>
      <button class="btn" id="theme-btn" type="button">主题：自动</button>
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
        "__CSS__": COMMON_CSS + QUIZ_CSS + VIVID_CSS,
        "__BODY_CLASS__": body_class,
        "__TOC__": toc_html,
        "__UNIT_LABEL__": html.escape(unit_label),
        "__META__": "".join(meta_bits),
        "__OBJECTIVES__": objectives_html,
        "__CONTENT__": content_html,
        "__SOURCES__": sources_html,
        "__PREV__": prev_html,
        "__NEXT__": next_html,
        "__GENERATED__": date.today().isoformat(),
        "__JS__": LESSON_JS + QUIZ_JS + DECK_JS + VIVID_JS,
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page


INDEX_CSS = COMMON_CSS + VIVID_CSS + r"""
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
    <div class="topbar-actions"><a class="btn back-to-chat" id="back-to-chat" href="#" hidden>← 返回对话</a><button class="btn" id="theme-btn" type="button">主题：自动</button><button class="btn" id="print-btn" type="button" onclick="window.print()">打印 / PDF</button></div>
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
        "__JS__": INDEX_JS + VIVID_JS,
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
        html_path = path.with_suffix(".html")
        if not html_path.exists():
            # 旧版/重命名前的源文件没有对应 HTML，不属于当前课程目录。
            continue
        try:
            meta, _ = parse_frontmatter(_read_text(path))
        except (OSError, UnicodeError) as exc:
            _warn("读取 %s 失败：%s" % (path, exc))
            continue
        if not meta.get("title") and not re.search(r"unit", path.stem, re.I):
            continue
        entry = _entry_from_markdown(path, meta)
        entry["_html_mtime"] = html_path.stat().st_mtime
        entry["_canonical"] = entry["stem"] == unit_file_stem(entry.get("unit"), entry.get("title"))
        entries.append(entry)
    entries.sort(
        key=lambda entry: (
            _sort_key(entry),
            0 if entry.get("_canonical") else 1,
            -entry.get("_html_mtime", 0),
        )
    )
    # 同一单元只保留最新生成的 lesson；旧的重命名稿不再重复出现在目录里。
    unique: List[Dict[str, Any]] = []
    seen_lessons = set()
    for entry in entries:
        key = None
        if entry.get("kind") == "lesson" and entry.get("unit") not in ("", None):
            key = ("lesson", str(entry["unit"]))
        if key is not None:
            if key in seen_lessons:
                continue
            seen_lessons.add(key)
        entry.pop("_html_mtime", None)
        entry.pop("_canonical", None)
        unique.append(entry)
    return unique


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
    server_url: str = DEFAULT_SERVER_URL,
    layout: Optional[str] = None,
    api_path: str = "",
    workspace: str = "",
    api_token: str = "",
    copy_source: bool = False,
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
    workspace = workspace or str(meta.get("workspace") or Path.cwd().name)
    api_path = api_path or str(meta.get("api_path") or "")
    api_token = api_token or str(meta.get("api_token") or "")

    folder = safe_component(course_dir_name or course)
    course_dir = output_root / folder
    course_dir.mkdir(parents=True, exist_ok=True)

    kind = str(meta.get("kind") or "lesson").strip().lower()
    if kind in ("practice", "reteach", "review"):
        unit_part = meta.get("parent_unit") or meta.get("unit")
        if re.fullmatch(r"\d+", str(unit_part or "")):
            stem = "%s-%02d-%s" % (kind, int(str(unit_part)), slugify(meta.get("title")))
        else:
            stem = "%s-%s" % (kind, slugify(meta.get("title")))
    else:
        stem = unit_file_stem(meta.get("unit"), meta.get("title"))
    md_path = course_dir / (stem + ".md")
    html_path = course_dir / (stem + ".html")
    if source.resolve() != md_path.resolve():
        if copy_source:
            md_path.write_text(raw, encoding="utf-8")
        else:
            _warn(
                "源文件不在课程目录：%s\n"
                "未复制到 %s；rebuild 不会包含它。"
                "建议把源文件直接写到课程目录，或显式传 --copy-source。"
                % (source, md_path)
            )

    entries = scan_entries(course_dir)
    current_entry = _entry_from_markdown(md_path, meta)
    entries = [entry for entry in entries if entry["path"].resolve() != md_path.resolve()]
    if current_entry.get("kind") == "lesson" and current_entry.get("unit") not in ("", None):
        entries = [
            entry for entry in entries
            if not (entry.get("kind") == "lesson" and str(entry.get("unit")) == str(current_entry["unit"]))
        ]
    entries.append(current_entry)
    entries.sort(key=_sort_key)
    state = load_state(state_path)
    apply_state(entries, state)
    current_index = next(
        (idx for idx, entry in enumerate(entries) if entry["stem"] == stem), -1
    )
    prev_entry = entries[current_index - 1] if current_index > 0 else None
    next_entry = entries[current_index + 1] if 0 <= current_index < len(entries) - 1 else None

    renderer = MarkdownRenderer()
    content, headings = renderer.render(strip_leading_h1(body))
    if renderer.quiz_error:
        _warn("练习数据解析失败：%s" % renderer.quiz_error)
    mastery_info = _find_mastery_concept(state, meta)
    page = render_lesson_page(
        meta,
        content,
        headings,
        course,
        prev_entry,
        next_entry,
        mastery_info,
        quiz=renderer.quiz,
        server_url=server_url,
        layout=layout,
        api_path=api_path,
        workspace=workspace,
        api_token=api_token,
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
    server_url: str = DEFAULT_SERVER_URL,
    layout: Optional[str] = None,
    api_path: str = "",
    workspace: str = "",
    api_token: str = "",
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
        if renderer.quiz_error:
            _warn("%s：练习数据解析失败：%s" % (entry["path"], renderer.quiz_error))
        prev_entry = entries[idx - 1] if idx > 0 else None
        next_entry = entries[idx + 1] if idx < len(entries) - 1 else None
        mastery_info = _find_mastery_concept(state, meta)
        entry_workspace = workspace or str(meta.get("workspace") or Path.cwd().name)
        entry_api_path = api_path or str(meta.get("api_path") or "")
        entry_api_token = api_token or str(meta.get("api_token") or "")
        page = render_lesson_page(
            meta,
            content,
            headings,
            course,
            prev_entry,
            next_entry,
            mastery_info,
            quiz=renderer.quiz,
            server_url=server_url,
            layout=layout,
            api_path=entry_api_path,
            workspace=entry_workspace,
            api_token=entry_api_token,
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
        p.add_argument(
            "--server-url",
            default=DEFAULT_SERVER_URL,
            help="答题提交服务地址（默认 http://127.0.0.1:8765）",
        )
        p.add_argument(
            "--api-path",
            default="",
            help="同源答题 API 路径，例如 /teacher/api/answers（DSH 插件模式）",
        )
        p.add_argument(
            "--workspace",
            default="",
            help="工作区目录名（DSH 插件 URL 需要，默认当前目录名）",
        )
        p.add_argument(
            "--api-token",
            default="",
            help="DSH 插件 token（可选，写入页面 data-api-token）",
        )
        p.add_argument(
            "--layout",
            choices=["deck", "article"],
            default=None,
            help="页面布局：deck 分步课件（讲义默认）/ article 长文",
        )
        p.add_argument("--quiet", action="store_true", help="不打印生成日志")

    build = sub.add_parser("build", help="渲染单个讲义并更新目录")
    common(build)
    build.add_argument("--file", required=True, help="Markdown 源文件路径")
    build.add_argument(
        "--copy-source",
        action="store_true",
        help="源文件不在课程目录时复制进去（默认只警告，不复制）",
    )

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
                server_url=args.server_url,
                layout=args.layout,
                api_path=args.api_path,
                workspace=args.workspace,
                api_token=args.api_token,
                copy_source=args.copy_source,
            )
            return 0 if result else 1
        if args.command == "rebuild":
            rebuild_course(
                args.course,
                output_root,
                state_path,
                args.course_dir,
                args.quiet,
                server_url=args.server_url,
                layout=args.layout,
                api_path=args.api_path,
                workspace=args.workspace,
                api_token=args.api_token,
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
