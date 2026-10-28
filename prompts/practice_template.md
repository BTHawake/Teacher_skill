# 练习卷模板（v3.0）

> 用法：根据 `python scripts/mastery.py practice --state ...` 给出的薄弱点，
> 复制本模板生成 3 题练习卷，保存到 `讲义/{课程}/practice-XX-{标题}.md`。
>
> 练习卷与讲义同目录；`kind: practice` 会让它出现在 index 的练习卷列表中。

```markdown
---
course: [课程名称]
unit: [单元序号]
title: [单元标题]·[练习主题]
kind: practice
parent_unit: [单元序号]
date: [YYYY-MM-DD]
status: 待复习
review_at: [YYYY-MM-DD]
state_id: [learning-state 里的 id，如 U4]
tags: [变式, 错题, 薄弱点]
objectives:
  - [本练习要验证的能力]
description: [针对哪个薄弱点、什么题型]
---

## 练习说明

先自己做，再展开答案。做完把对错告诉 AI 老师，它会更新掌握度并决定下一步。

### 练习 1（概念辨析 / 正例反例）

[题目：针对 Lv0/Lv1 的概念边界]

::: answer 参考答案
[答案 + 为什么其他选项错]
:::

### 练习 2（应用 / 计算）

[题目：换数字/换条件，但同一考点]

::: answer 参考答案
[答案 + 步骤 + 验算]
:::

### 练习 3（迁移）

[题目：换场景，确认不是背例题]

::: answer 参考答案
[答案 + 思路]
:::
```

## 出题检查清单

- [ ] 3 题覆盖：概念 / 应用 / 迁移
- [ ] 有错题时，优先同型变式，不原题重做
- [ ] 难度不超过当前等级太多；Lv0 先出辨析，不直接上综合题
- [ ] 答案解释"为什么"，不只给结果
- [ ] 同一概念连续 3 次未通过 → 停止加题，改讲法
- [ ] 生成后运行 `lesson_html.py index` 刷新目录

## 做完之后

```bash
python scripts/mastery.py record --state "teachers/{课程}/learning-state.json" \
  --concept "[概念]" --unit [U4] --kind variant --result [pass|partial|fail] \
  --error "[错误标签]"

python scripts/mastery.py advise --state "teachers/{课程}/learning-state.json"
```
