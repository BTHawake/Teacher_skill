# 练习页模板（v4.0）

> 根据 `mastery.py practice --state ...` 给出的薄弱点，生成 3 道针对性题。
> 保存为 `讲义/{课程}/practice-XX-{标题}.md`，用 `lesson_html.py build` 生成。

```markdown
---
course: [课程]
unit: [单元序号]
title: [单元标题]·[练习主题]
kind: practice
layout: article
parent_unit: [单元序号]
date: [YYYY-MM-DD]
status: 待复习
state_id: [U4]
tags: [变式, 错题, 薄弱点]
description: [针对哪个薄弱点、什么题型]
---

# [练习标题]

先自己做，再点“查看参考答案”。做完点“提交答案”，回聊天告诉 AI“答好了”。

## 练习

```quiz
{
  "questions": [
    {
      "id": "Q1",
      "type": "choice",
      "prompt": "[概念辨析 / 正例反例]",
      "options": ["[A]", "[B]", "[C]"],
      "answer": "[B]",
      "explanation": "[为什么]"
    },
    {
      "id": "Q2",
      "type": "text",
      "prompt": "[同型变式，换数字/条件]",
      "answer": "[答案]",
      "explanation": "[步骤]"
    },
    {
      "id": "Q3",
      "type": "text",
      "prompt": "[换场景迁移]",
      "answer": "[答案]",
      "explanation": "[思路]"
    }
  ]
}
```
```

## 出题检查清单

- [ ] 3 题覆盖：概念 / 应用 / 迁移
- [ ] 有错题时优先同型变式，不原题重做
- [ ] 难度不超过当前等级太多；Lv0 先出辨析
- [ ] 答案解释“为什么”，不只给结果
- [ ] 同一概念连续 3 次未通过 → 停止加题，改讲法
- [ ] 生成后运行 `lesson_html.py index` 刷新目录

## 做完之后

```bash
python scripts/mastery.py record --state "teachers/{课程}/learning-state.json" \
  --concept "[概念]" --unit [U4] --kind variant --result [pass|partial|fail] \
  --error "[错误标签]"

python scripts/mastery.py advise --state "teachers/{课程}/learning-state.json"
```
