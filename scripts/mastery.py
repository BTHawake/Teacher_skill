#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""teacher.skill v3.0 - 自适应掌握度引擎。

读取/更新 ``teachers/{name}/learning-state.json``，根据课后练习与检测结果：

- 记录每个知识点的掌握等级（0 未掌握 / 1 模糊 / 2 基本掌握 / 3 掌握）
- 按艾宾浩斯间隔安排下一次复习
- 给出下一步建议：重讲 / 继续练习 / 到期复习 / 进入下一单元
- 输出薄弱知识点与建议练习题类型，供 AI 生成针对性练习

用法：

    python scripts/mastery.py init --state teachers/demo/learning-state.json
    python scripts/mastery.py record --state ... --concept "位权" --unit U4 \
        --result pass --error "读题不完整" --note "第二次变式通过"
    python scripts/mastery.py advise --state ...
    python scripts/mastery.py due --state ...
    python scripts/mastery.py practice --state ... --count 3

只使用标准库，兼容 Python 3.9+。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

VERSION = "4.3.1"
LEVEL_LABELS = {0: "未掌握", 1: "模糊", 2: "基本掌握", 3: "掌握"}
REVIEW_INTERVALS = [1, 3, 7, 14, 30]

RESULT_ALIASES = {
    "pass": "pass",
    "passed": "pass",
    "correct": "pass",
    "通过": "pass",
    "对": "pass",
    "partial": "partial",
    "partially": "partial",
    "部分": "partial",
    "部分正确": "partial",
    "fail": "fail",
    "failed": "fail",
    "wrong": "fail",
    "未通过": "fail",
    "错": "fail",
}

KIND_ALIASES = {
    "first": "first",
    "首轮": "first",
    "初讲": "first",
    "variant": "variant",
    "变式": "variant",
    "复习": "review",
    "review": "review",
    "practice": "practice",
    "练习": "practice",
}

ERROR_SUGGESTIONS = {
    "概念混淆": ["概念辨析题", "正例/反例判断"],
    "步骤遗漏": ["过程排序题", "补全步骤题"],
    "计算错误": ["计算题", "估算/验算题"],
    "读题不完整": ["双分句选项拆解题", "找错题"],
    "表达不清": ["用自己的话复述", "给外行解释"],
    "迁移失败": ["换场景变式题", "应用题"],
    "记忆混淆": ["对比表填空", "易混概念配对"],
}


# ---------------------------------------------------------------------------
# 状态结构
# ---------------------------------------------------------------------------


def default_state(name: str = "default") -> Dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "meta": {
            "name": name,
            "created_at": now,
            "updated_at": now,
            "version": VERSION,
        },
        "user": {
            "level": None,
            "familiar_fields": [],
            "learning_goal": "",
            "time_expectation": "",
            "preference": "",
        },
        "route": {"subject": name, "material_type": "", "total_units": 0, "units": []},
        "progress": {
            "status": "new",
            "current_unit_index": 0,
            "completed_units": [],
            "overall_percent": 0,
        },
        "verification": {"checkpoints": [], "final_result": None},
        "review": {"last_check_at": None, "due_count": 0, "overdue": []},
        "mastery": {
            "version": VERSION,
            "concepts": {},
            "next_action": None,
            "updated_at": now,
        },
    }


def normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """补齐旧版 state 缺失的字段；不删除任何已有数据。"""
    if not isinstance(state, dict):
        raise ValueError("state 根节点必须是对象")
    state.setdefault("meta", {})
    state["meta"].setdefault("name", "default")
    state["meta"].setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    state["meta"]["version"] = VERSION
    state.setdefault("user", {})
    state.setdefault("route", {})
    state["route"].setdefault("subject", state["meta"].get("name", ""))
    state["route"].setdefault("total_units", 0)
    state["route"].setdefault("units", [])
    state.setdefault("progress", {})
    state["progress"].setdefault("status", "new")
    state["progress"].setdefault("current_unit_index", 0)
    state["progress"].setdefault("completed_units", [])
    state["progress"].setdefault("overall_percent", 0)
    state.setdefault("verification", {"checkpoints": [], "final_result": None})
    state.setdefault("review", {"last_check_at": None, "due_count": 0, "overdue": []})
    state.setdefault(
        "mastery",
        {
            "version": VERSION,
            "concepts": {},
            "next_action": None,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    state["mastery"].setdefault("version", VERSION)
    state["mastery"].setdefault("concepts", {})
    state["mastery"].setdefault("next_action", None)
    return state


def load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError("学习状态文件不存在：%s" % path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return normalize_state(data)


def save_state(path: Path, state: Dict[str, Any]) -> None:
    state = normalize_state(state)
    state["meta"]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state["mastery"]["updated_at"] = state["meta"]["updated_at"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 掌握度计算
# ---------------------------------------------------------------------------


def normalize_result(value: str) -> str:
    key = str(value or "").strip().lower()
    if key in RESULT_ALIASES:
        return RESULT_ALIASES[key]
    raise ValueError("未知结果：%s（可用 pass / partial / fail）" % value)


def normalize_kind(value: str) -> str:
    key = str(value or "practice").strip().lower()
    if key in KIND_ALIASES:
        return KIND_ALIASES[key]
    raise ValueError("未知检测类型：%s（可用 first / variant / review / practice）" % value)


def _today() -> date:
    return date.today()


def _date_str(value: date) -> str:
    return value.isoformat()


def _parse_date(value: Any) -> Optional[date]:
    text = str(value or "").strip().replace("/", "-")
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _apply_pass(concept: Dict[str, Any], errors: List[str], kind: str) -> None:
    before = int(concept.get("level", 0) or 0)
    now = datetime.now().isoformat(timespec="seconds")
    concept["last_result"] = "pass"
    concept["correct_streak"] = int(concept.get("correct_streak", 0) or 0) + 1
    concept["review_count"] = int(concept.get("review_count", 0) or 0) + 1
    interval = REVIEW_INTERVALS[min(concept["review_count"] - 1, len(REVIEW_INTERVALS) - 1)]
    concept["next_review_at"] = _date_str(_today() + timedelta(days=interval))

    if kind == "first":
        concept["first_pass_at"] = concept.get("first_pass_at") or now
        concept["level"] = max(before, 2)
    elif kind == "variant":
        if concept.get("first_pass_at"):
            concept["level"] = 3
            concept["variant_passed"] = True
            concept["variant_pass_at"] = now
        else:
            concept["first_pass_at"] = now
            concept["level"] = max(before, 2)
    elif kind == "review":
        if before < 2:
            concept["level"] = 2
        elif before >= 3:
            concept["level"] = 3
    else:  # practice
        if before <= 1:
            concept["level"] = 2
            if not concept.get("first_pass_at"):
                concept["first_pass_at"] = now
        elif before == 2:
            concept["level"] = 3
            concept["variant_passed"] = True
            concept["variant_pass_at"] = now
        else:
            concept["level"] = 3

    concept["advance_ready"] = bool(concept.get("variant_passed")) and int(
        concept.get("level", 0)
    ) >= 3


def _apply_partial(concept: Dict[str, Any]) -> None:
    level = int(concept.get("level", 0) or 0)
    concept["level"] = max(1, min(level, 1))
    concept["correct_streak"] = 0
    concept["review_count"] = 0
    concept["variant_passed"] = False
    concept["advance_ready"] = False
    concept["next_review_at"] = _date_str(_today() + timedelta(days=1))
    concept["last_result"] = "partial"


def _apply_fail(concept: Dict[str, Any]) -> None:
    level = int(concept.get("level", 0) or 0)
    concept["level"] = max(0, level - 1)
    concept["correct_streak"] = 0
    concept["review_count"] = 0
    concept["variant_passed"] = False
    concept["advance_ready"] = False
    concept["next_review_at"] = _date_str(_today() + timedelta(days=1))
    concept["last_result"] = "fail"


def record_result(
    state: Dict[str, Any],
    concept_name: str,
    result: str,
    unit: str = "",
    errors: Optional[Sequence[str]] = None,
    note: str = "",
    unit_title: str = "",
    complete_unit: bool = False,
    kind: str = "practice",
) -> Dict[str, Any]:
    """记录一次练习/检测结果，更新掌握度并重算下一步建议。

    ``kind`` 用于区分首轮检测（first）、换场景变式（variant）、
    到期复习（review）和普通练习（practice）。推进下一单元需要
    first + variant 都通过（Lv3 / advance_ready）。
    """
    state = normalize_state(state)
    name = str(concept_name or "").strip()
    if not name:
        raise ValueError("concept 不能为空")
    result = normalize_result(result)
    kind = normalize_kind(kind)
    errors = [str(e).strip() for e in (errors or []) if str(e).strip()]

    concepts = state["mastery"]["concepts"]
    concept = concepts.get(name)
    if not isinstance(concept, dict):
        concept = {
            "name": name,
            "unit": str(unit or ""),
            "level": 0,
            "status": LEVEL_LABELS[0],
            "attempts": 0,
            "correct_streak": 0,
            "review_count": 0,
            "last_result": "",
            "last_error": "",
            "error_tags": [],
            "next_review_at": "",
            "first_pass_at": "",
            "variant_passed": False,
            "variant_pass_at": "",
            "advance_ready": False,
            "history": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": "",
        }
    if unit:
        concept["unit"] = str(unit)
    concept["attempts"] = int(concept.get("attempts", 0) or 0) + 1

    if result == "pass":
        _apply_pass(concept, errors, kind)
    elif result == "partial":
        _apply_partial(concept)
    else:
        _apply_fail(concept)

    if errors:
        existing = list(concept.get("error_tags", []) or [])
        for err in errors:
            if err not in existing:
                existing.append(err)
        concept["error_tags"] = existing[-12:]
        concept["last_error"] = errors[-1]
    concept["status"] = LEVEL_LABELS[int(concept.get("level", 0))]
    concept["updated_at"] = datetime.now().isoformat(timespec="seconds")
    history = list(concept.get("history", []) or [])
    history.append(
        {
            "at": concept["updated_at"],
            "result": result,
            "kind": kind,
            "note": str(note or ""),
            "errors": errors,
            "level": concept["level"],
        }
    )
    concept["history"] = history[-20:]
    concepts[name] = concept

    if complete_unit and result == "pass" and concept.get("advance_ready"):
        _mark_unit_complete(state, unit or name, unit_title or name, concept, errors)

    action = recommend(state)
    return {"concept": concept, "action": action}


def _mark_unit_complete(
    state: Dict[str, Any],
    unit: str,
    unit_title: str,
    concept: Dict[str, Any],
    errors: Sequence[str],
) -> None:
    progress = state["progress"]
    completed = list(progress.get("completed_units", []) or [])
    now = datetime.now().isoformat(timespec="seconds")
    entry = None
    for item in completed:
        if not isinstance(item, dict):
            continue
        if str(item.get("id", "")) == str(unit) or str(item.get("name", "")) == str(unit_title):
            entry = item
            break
    if entry is None:
        entry = {"id": str(unit), "name": str(unit_title)}
        completed.append(entry)
    entry.update(
        {
            "result": "pass",
            "completed_at": now,
            "next_review_at": concept.get("next_review_at", ""),
            "review_count": concept.get("review_count", 0),
            "wrong_answers": list(errors),
        }
    )
    progress["completed_units"] = completed
    progress["status"] = "in_progress"
    total = int(state["route"].get("total_units", 0) or 0)
    if total > 0:
        progress["overall_percent"] = min(100, int(round(len(completed) * 100.0 / total)))


# ---------------------------------------------------------------------------
# 建议 / 复习 / 练习
# ---------------------------------------------------------------------------


def _concept_list(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    concepts = state.get("mastery", {}).get("concepts", {})
    if not isinstance(concepts, dict):
        return []
    result = []
    for name, info in concepts.items():
        if not isinstance(info, dict):
            continue
        item = dict(info)
        item["name"] = str(item.get("name") or name)
        item["level"] = int(item.get("level", 0) or 0)
        result.append(item)
    return result


def due_concepts(state: Dict[str, Any], today: Optional[date] = None) -> List[Dict[str, Any]]:
    today = today or _today()
    due = []
    for concept in _concept_list(state):
        review = _parse_date(concept.get("next_review_at"))
        if review and review <= today:
            concept["days_overdue"] = (today - review).days
            due.append(concept)
    due.sort(key=lambda c: (c["level"], c.get("days_overdue", 0) * -1, c["name"]))
    return due


def _fail_concepts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [c for c in _concept_list(state) if c.get("last_result") == "fail"]
    items.sort(key=lambda c: (c["level"], c["name"]))
    return items


def _partial_concepts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [c for c in _concept_list(state) if c.get("last_result") == "partial"]
    items.sort(key=lambda c: (c["level"], c["name"]))
    return items


def _weak_concepts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [c for c in _concept_list(state) if c["level"] <= 1]
    items.sort(key=lambda c: (c["level"], c["name"]))
    return items


def _shaky_concepts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [c for c in _concept_list(state) if c["level"] == 2]
    items.sort(key=lambda c: (c["level"], c["name"]))
    return items


def recommend(state: Dict[str, Any]) -> Dict[str, Any]:
    """根据当前掌握度给出下一步建议，并写入 state['mastery']['next_action']。"""
    state = normalize_state(state)
    due = due_concepts(state)
    failed = _fail_concepts(state)
    partial = _partial_concepts(state)
    weak = _weak_concepts(state)
    shaky = _shaky_concepts(state)

    action: Dict[str, Any]
    if failed:
        target = failed[0]
        action = {
            "type": "reteach",
            "target": target["name"],
            "unit": target.get("unit", ""),
            "reason": "最近一次未通过，先换一种讲法重讲，不要直接刷题。",
            "suggested_count": 2,
        }
    elif partial:
        target = partial[0]
        action = {
            "type": "practice",
            "target": target["name"],
            "unit": target.get("unit", ""),
            "reason": "部分正确，先做 2 道针对性变式题再判断是否推进。",
            "suggested_count": 2,
        }
    elif due:
        target = due[0]
        threshold = 5
        shown = 3 if len(due) > threshold else len(due)
        deferred = max(0, len(due) - shown)
        action = {
            "type": "review",
            "target": target["name"],
            "unit": target.get("unit", ""),
            "reason": "有 %d 个知识点到了复习时间，先快速回顾 %d 个%s。"
            % (
                len(due),
                shown,
                "，其余 %d 个顺延到下次" % deferred if deferred else "",
            ),
            "suggested_count": shown,
            "deferred_count": deferred,
        }
    elif weak:
        target = weak[0]
        action = {
            "type": "reteach",
            "target": target["name"],
            "unit": target.get("unit", ""),
            "reason": "掌握度仍在『%s』，换一个更具体的例子/图示重讲。" % LEVEL_LABELS[target["level"]],
            "suggested_count": 2,
        }
    elif shaky:
        target = shaky[0]
        needs_variant = not bool(target.get("variant_passed"))
        action = {
            "type": "practice",
            "target": target["name"],
            "unit": target.get("unit", ""),
            "mode": "variant" if needs_variant else "practice",
            "reason": (
                "首轮检测已通过，但还没换场景验证；先做 1 道变式题，通过后再推进。"
                if needs_variant
                else "基本掌握但还不稳，做 2 道换场景的变式题巩固。"
            ),
            "suggested_count": 1 if needs_variant else 2,
        }
    elif _concept_list(state):
        concepts = _concept_list(state)
        not_ready = [c for c in concepts if not c.get("advance_ready")]
        if not_ready:
            target = not_ready[0]
            action = {
                "type": "practice",
                "target": target["name"],
                "unit": target.get("unit", ""),
                "mode": "variant",
                "reason": "还没有完成『首轮 + 变式』验证，先补一道变式题。",
                "suggested_count": 1,
            }
        else:
            action = {
                "type": "advance",
                "target": "",
                "unit": "",
                "reason": "当前知识点都已完成首轮 + 变式验证，可以进入下一单元；记得按复习计划回来。",
                "suggested_count": 0,
            }
    else:
        action = {
            "type": "start",
            "target": "",
            "unit": "",
            "reason": "还没有掌握度记录，先完成一个单元的教学与检测。",
            "suggested_count": 0,
        }

    action["created_at"] = datetime.now().isoformat(timespec="seconds")
    state["mastery"]["next_action"] = action
    return action


def practice_targets(state: Dict[str, Any], count: int = 3) -> List[Dict[str, Any]]:
    """返回建议练习的知识点（薄弱优先，兼顾到期复习）。"""
    state = normalize_state(state)
    concepts = _concept_list(state)
    today = _today()
    priority: Dict[str, int] = {}
    for concept in concepts:
        level = concept["level"]
        if concept.get("last_result") == "fail":
            priority[concept["name"]] = 0
        elif concept.get("last_result") == "partial":
            priority[concept["name"]] = 1
        elif level <= 1:
            priority[concept["name"]] = 2
        elif _parse_date(concept.get("next_review_at")) and _parse_date(
            concept.get("next_review_at")
        ) <= today:
            priority[concept["name"]] = 3
        elif level == 2:
            priority[concept["name"]] = 4
        else:
            priority[concept["name"]] = 5
    concepts.sort(key=lambda c: (priority.get(c["name"], 9), c["level"], c["name"]))
    targets: List[Dict[str, Any]] = []
    for concept in concepts:
        if len(targets) >= max(1, count):
            break
        errors = concept.get("error_tags", []) or []
        needs_variant = not bool(concept.get("variant_passed"))
        suggestions: List[str] = []
        for err in errors:
            for item in ERROR_SUGGESTIONS.get(err, []):
                if item not in suggestions:
                    suggestions.append(item)
        if concept["level"] <= 1:
            suggestions.extend(["概念辨析题", "正例/反例判断"])
        elif concept["level"] == 2 and needs_variant:
            suggestions.extend(["换场景变式题", "应用题"])
        elif concept["level"] == 2:
            suggestions.extend(["应用题", "迁移题"])
        else:
            suggestions.extend(["迁移题", "综合题"])
        targets.append(
            {
                "concept": concept["name"],
                "unit": concept.get("unit", ""),
                "level": concept["level"],
                "status": LEVEL_LABELS[concept["level"]],
                "last_result": concept.get("last_result", ""),
                "needs_variant": needs_variant,
                "advance_ready": bool(concept.get("advance_ready")),
                "error_tags": errors,
                "question_types": list(dict.fromkeys(suggestions))[:4],
                "next_review_at": concept.get("next_review_at", ""),
            }
        )
    return targets


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _summary_line(concept: Dict[str, Any]) -> str:
    return "  - %s: %s (Lv%d, %d 次, 复习 %s)" % (
        concept["name"],
        LEVEL_LABELS.get(int(concept.get("level", 0)), "?"),
        int(concept.get("level", 0)),
        int(concept.get("attempts", 0)),
        concept.get("next_review_at") or "未安排",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="teacher.skill v%s - 自适应掌握度引擎" % VERSION
    )
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="创建新的学习状态文件")
    init.add_argument("--state", required=True)
    init.add_argument("--name", default="default")

    for name in ("record", "advise", "due", "practice", "show"):
        p = sub.add_parser(name)
        p.add_argument("--state", required=True)
        p.add_argument("--json", action="store_true", help="输出 JSON")

    record = sub.choices["record"]
    record.add_argument("--concept", required=True)
    record.add_argument("--unit", default="")
    record.add_argument("--result", required=True, help="pass / partial / fail")
    record.add_argument(
        "--kind",
        default="practice",
        choices=["first", "variant", "review", "practice"],
        help="first=首轮检测 / variant=换场景变式 / review=到期复习 / practice=普通练习",
    )
    record.add_argument("--error", action="append", default=[], help="错误标签，可重复")
    record.add_argument("--note", default="")
    record.add_argument("--unit-title", default="")
    record.add_argument("--complete-unit", action="store_true")

    practice = sub.choices["practice"]
    practice.add_argument("--count", type=int, default=3)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    path = Path(args.state)
    try:
        if args.command == "init":
            if path.exists():
                print("状态文件已存在：%s" % path, file=sys.stderr)
                return 1
            state = default_state(args.name)
            save_state(path, state)
            print("已创建：%s" % path)
            return 0

        state = load_state(path)
        if args.command == "record":
            result = record_result(
                state,
                args.concept,
                args.result,
                args.unit,
                args.error,
                args.note,
                args.unit_title,
                args.complete_unit,
                args.kind,
            )
            save_state(path, state)
            if args.json:
                _print_json(result)
            else:
                concept = result["concept"]
                print("已记录：%s → %s" % (concept["name"], concept["status"]))
                print(_summary_line(concept))
                print("下一步：%s - %s" % (result["action"]["type"], result["action"]["reason"]))
            return 0

        if args.command == "advise":
            action = recommend(state)
            save_state(path, state)
            if args.json:
                _print_json(action)
            else:
                print("建议下一步：%s" % action["type"])
                if action.get("target"):
                    print("目标：%s" % action["target"])
                print("理由：%s" % action["reason"])
                print("建议题量：%d" % int(action.get("suggested_count", 0)))
            return 0

        if args.command == "due":
            due = due_concepts(state)
            if args.json:
                _print_json(due)
            else:
                if not due:
                    print("没有到期复习项。")
                else:
                    print("到期复习 %d 项：" % len(due))
                    for concept in due:
                        print(_summary_line(concept))
            return 0

        if args.command == "practice":
            targets = practice_targets(state, args.count)
            if args.json:
                _print_json(targets)
            else:
                if not targets:
                    print("还没有掌握度记录，先完成一个单元的检测。")
                else:
                    print("建议练习 %d 个知识点：" % len(targets))
                    for target in targets:
                        print(
                            "  - %s（%s）建议题型：%s"
                            % (
                                target["concept"],
                                target["status"],
                                "、".join(target["question_types"]),
                            )
                        )
            return 0

        if args.command == "show":
            concepts = sorted(_concept_list(state), key=lambda c: (c["level"], c["name"]))
            if args.json:
                _print_json(concepts)
            else:
                if not concepts:
                    print("还没有掌握度记录。")
                else:
                    print("掌握度总览：")
                    for concept in concepts:
                        print(_summary_line(concept))
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("[error] %s" % exc, file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
