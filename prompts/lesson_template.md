# 单元课件模板（v4.0，HTML-first）

> 用法：复制本模板，替换 `[占位符]`，保存到 `讲义/{课程}/unit-XX-{标题}.md`，
> 然后运行 `lesson_html.py build`。
>
> 只写本单元**实际要讲**的内容；每个 `##` 是一个步骤。

```markdown
---
course: [课程名称]
unit: [单元序号，如 4]
title: [单元标题]
date: [YYYY-MM-DD]
status: [进行中 / 已完成]
kind: lesson
layout: deck
tags: [标签1, 标签2]
objectives:
  - [学完能做什么 1]
  - [学完能做什么 2]
state_id: [learning-state 里的 id，如 U4]
sources:
  - [教材/章节/链接]
description: [一句话摘要]
---

# [单元标题]（脚本会去掉这一行，页面标题已显示）

## 先看一眼

[一句话说明这个单元解决什么问题；可以放一张总览图。]

::: flow [总览标题]
[起点] → [中间] → [终点]
:::

## [概念 1]

[2-4 段大白话。先讲“是什么/为什么”，再给定义。]

::: definition [概念名]
[一句话定义 + 边界/反例]
:::

::: example [例子名]
[具体例子；最好用用户熟悉的领域]
:::

::: hint 提示
[给学有余力的人一个进阶提示]
:::

## [概念 2 / 推导]

[讲解 + 图示/表格/代码。]

::: compare [对比标题]
| 维度 | A | B |
|------|------|------|
| ... | ... | ... |
:::

::: flip [易混概念]
[正面问题]
---
[背面解释]
:::

## 易错点

::: warning [易错点标题]
[常见错法 + 正确做法]
:::

## 练习

先自己做，再点“查看参考答案”。做完点“提交答案”，回聊天告诉 AI“答好了”。

```quiz
{
  "questions": [
    {
      "id": "Q1",
      "type": "choice",
      "prompt": "[概念辨析题]",
      "options": ["[A]", "[B]", "[C]"],
      "answer": "B",
      "explanation": "[为什么 B 对，其他错在哪]"
    },
    {
      "id": "Q2",
      "type": "text",
      "prompt": "[应用题]",
      "answer": "[答案]",
      "explanation": "[步骤]"
    },
    {
      "id": "Q3",
      "type": "text",
      "prompt": "[换场景迁移题]",
      "answer": "[答案]",
      "explanation": "[思路]"
    }
  ]
}
```

## 小结

::: summary 本单元小结
- [要点 1]
- [要点 2]
- [要点 3]
:::

> [下一单元预告 / 一句鼓励]
```

## 生成命令

```bash
python scripts/course_server.py --course "[课程]" --port 8765
python scripts/lesson_html.py build --course "[课程]" \
  --file "讲义/[课程]/unit-XX-[标题].md" \
  --state "teachers/[课程]/learning-state.json" \
  --server-url "http://127.0.0.1:8765"
```

## 内容检查清单

- [ ] 4-8 个 `##` 步骤
- [ ] 至少一个图示，并有一句“看图说话”
- [ ] 每个概念配一个正例 + 一个反例
- [ ] 3 道题：概念 / 应用 / 迁移
- [ ] quiz JSON 合法，答案/解析完整
- [ ] 动画不抢注意力
- [ ] 手机可读
- [ ] 没有密钥、隐私、聊天原文
- [ ] 生成后浏览器打开检查
