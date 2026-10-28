# 复习页模板（v4.0）

> 到期复习用，2-3 分钟。不是重新教学；先唤醒，再用 1 道检测确认。

```markdown
---
course: [课程]
unit: [单元序号]
title: [主题] · 复习
kind: review
layout: article
parent_unit: [单元序号]
date: [YYYY-MM-DD]
status: 待复习
review_at: [YYYY-MM-DD]
state_id: [U4]
tags: [复习, 间隔重复]
description: [N] 个知识点的快速回顾 + 1 道检测。
---

# [主题] · 复习

## 30 秒唤醒

[用 2-3 个问题/关键词，让用户先回忆，不直接给答案。]

::: hint 提示
[想不起来时再展开]
:::

## 关键点速览

| 知识点 | 一句话 |
|--------|--------|
| [A] | [一句话] |
| [B] | [一句话] |

## 检测

```quiz
{
  "questions": [
    {
      "id": "Q1",
      "type": "choice",
      "prompt": "[概念辨别，降低压力]",
      "options": ["[A]", "[B]", "[C]"],
      "answer": "[B]",
      "explanation": "[为什么]"
    }
  ]
}
```
```

## 复习规则

- 单个复习项 2-3 分钟
- 先复习，再学新的；到期 >5 个时本次只做 3 个，其余顺延
- 复习通过 → 按 1/3/7/14/30 天更新下次复习
- 复习不通过 → 回到补讲/练习，不要直接背答案
- 记录 `--kind review`
