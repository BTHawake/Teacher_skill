---
name: html-lessons
description: >
  teacher.skill v4.1 HTML 课件指南：分步 deck、图示 DSL、
  答题卡、本地提交服务、课程目录与排错。
version: 4.3.1
---

# HTML 课件指南（v4.0）

> HTML 是主课堂。每单元一个分步课件，用户看 HTML 学习；
> 聊天只做答疑、批改和下一步决策。

## 1. 目录结构

```
讲义/
└── 计算机组成原理/
    ├── index.html                     # 课程地图 + 复习入口
    ├── unit-04.md           # 源文件
    ├── unit-04.html         # 分步 deck
    ├── practice-04-错题变式.html       # 练习页
    ├── reteach-04-位权.html            # 补讲页
    ├── review-04-进制转换.html         # 复习页
    └── answers/
        ├── latest.json                # 最近一次答题卡提交
        └── 4-20261028-114210.json     # 历史快照
```

所有页面自包含（CSS/JS 内联），离线可打开。

## 2. Frontmatter

### 单元主课件

```yaml
---
course: 计算机组成原理
unit: 4
title: 进位计数制
date: 2026-10-28
status: 进行中
kind: lesson
layout: deck
tags: [进制, 位权]
objectives:
  - 理解基数与位权
  - 掌握二/八/十六进制互转
state_id: U4
sources:
  - 王道《计算机组成原理》第 1 章
description: 从位权展开出发理解进制转换。
---
```

### 练习 / 补讲 / 复习页

```yaml
---
course: 计算机组成原理
unit: 4
title: 进位计数制·错题变式
kind: practice      # practice | reteach | review
layout: article     # 可选，默认 article
parent_unit: 4
date: 2026-10-28
status: 待复习
state_id: U4
tags: [变式, 错题]
description: 针对「分组转换」概念混淆生成的 3 道题。
---
```

必填：`course`、`unit`、`title`；`kind` 决定文件前缀与 index 标签。

## 3. 分步 deck

`layout: deck` 时：

- 每个 `## 二级标题` = 一个步骤
- 自动生成「开始」页
- 顶部进度条、步骤计数、已读计数
- 侧边栏步骤导航；已读步骤打勾
- 上一步/下一步、键盘 ← →、`#step-N` 深链
- 打印时所有步骤展开

建议每单元 4-8 步：目标 → 概念 → 例子/推导 → 易错点 → 对比/图示 → 练习 → 小结。

## 4. 交互组件

### 提示 / 先想一想

```text
::: hint 提示
先想想：为什么取指阶段要先算 PC+1？
:::

::: think 先想一想
如果 Cache 命中率变成 100%，平均访问时间怎么变？
:::
```

默认折叠，点击展开。

### 翻转卡

```text
::: flip 位权
位权是什么？
---
基数的幂，随位置变化。
:::
```

点击/回车翻面；打印时正反面都显示。

### 答案折叠

```text
::: answer 参考答案
整数部分每 4 位一组：`1101 0110` → `D6`。
:::
```

## 5. 图示 DSL

所有图都是 HTML/CSS/SVG，离线、响应式、可打印。

### flow（流程）

```text
::: flow 指令周期
取指 → 译码 → 执行 → 访存 → 写回
:::
```

### layers（层次）

```text
::: layers 存储层次
CPU 寄存器 | 最快、最小
Cache | 介于 CPU 与内存
内存 | 主存
磁盘 | 最慢、最大
:::
```

### timeline（时间线）

```text
::: timeline 发展
1946 | ENIAC
1952 | EDVAC
1964 | IBM System/360
:::
```

### cycle（循环）

```text
::: cycle 指令周期
取指 → 译码 → 执行 → 写回
:::
```

3-8 个节点；超过范围自动退化成 flow。

### compare（对比）

```text
::: compare 冯·诺依曼 vs 哈佛
| 维度 | 冯·诺依曼 | 哈佛 |
|------|-----------|------|
| 存储 | 指令数据同存 | 分开存储 |
:::
```

### bars（数据图表）

```text
::: bars 性能对比
方案A: 40
方案B: 75
方案C: 60
:::
```

目前支持柱状/条形图；折线/坐标图用 `svg` 代码块。

### 原始 SVG

````text
```svg
<svg ...>...</svg>
```
````

SVG 元素可加动画类：

- `class="pulse"`：脉冲
- `class="flow"`：虚线流动
- `class="float"`：上下浮动

## 6. 答题卡

在 Markdown 中放一个 ` ```quiz ` JSON 块：

````text
```quiz
{
  "questions": [
    {
      "id": "Q1",
      "type": "choice",
      "prompt": "以下哪句话正确？",
      "options": ["A 选项", "B 选项", "C 选项"],
      "answer": "B",
      "explanation": "位权是基数的幂。"
    },
    {
      "id": "Q2",
      "type": "text",
      "prompt": "把十进制 200 转成二进制。",
      "answer": "11001000",
      "explanation": "除基取余，逆序排列。"
    }
  ]
}
```
````

自动生成：

- 选题/简答输入
- 已答计数
- 提交答案（本地服务）
- 复制提交文本（无服务兜底）
- 查看参考答案（默认折叠）
- 本地保存草稿

## 7. 提交服务

```bash
python scripts/course_server.py --course "计算机组成原理" --port 8765
```

- 只绑定 `127.0.0.1`
- 静态提供 `讲义/{课程}/`
- `POST /api/answers` 写入 `answers/latest.json`
- `GET /api/health`、`GET /api/answers/latest`
- 用户点提交后，AI 读取 `latest.json` 批改

如果没有启动服务，答题卡会提示“复制提交文本”，用户粘贴到聊天即可。

## 8. 生成命令

```bash
# 生成单个课件 + 更新 index
python scripts/lesson_html.py build \
  --course "计算机组成原理" \
  --file "讲义/计算机组成原理/unit-04.md" \
  --state "teachers/计算机组成原理/learning-state.json" \
  --server-url "http://127.0.0.1:8765"

# 重建全部
python scripts/lesson_html.py rebuild --course "计算机组成原理" --state "..."

# 只刷新目录
python scripts/lesson_html.py index --course "计算机组成原理" --state "..."
```

参数：

| 参数 | 说明 |
|------|------|
| `--course` | 课程名，决定目录 |
| `--file` | Markdown 源文件（build 必填） |
| `--copy-source` | 源文件不在课程目录时才复制进去；默认只警告 |
| `--output-dir` | 输出根目录，默认 `讲义` |
| `--course-dir` | 课程子目录名 |
| `--state` | learning-state.json 路径 |
| `--server-url` | 答题提交服务地址，默认 `http://127.0.0.1:8765` |
| `--api-path` | 同源答题 API，例如 `/teacher/api/answers`（DSH 插件模式） |
| `--workspace` | DSH 插件 URL 的工作区名，默认当前目录名 |
| `--api-token` | DSH 插件 token；写入页面 `data-api-token` |
| `--layout` | `deck` / `article`，覆盖 frontmatter |
| `--quiet` | 不打印生成日志 |

## 9. index.html

- 统计：单元总数、已完成、待复习、薄弱知识点
- 进度条、完成度
- 到期复习清单
- 薄弱知识点 + AI 建议下一步
- 搜索 / 状态筛选
- 练习/补讲/复习页统一列出
- 打印/PDF

## 10. 状态映射

读取：

- `route.units[]`：单元状态
- `progress.completed_units[]`：完成状态、`next_review_at`
- `progress.overall_percent`：进度条
- `mastery.concepts`：掌握度、薄弱项、到期复习
- `mastery.next_action`：建议下一步

匹配顺序：`state_id` → `unit` → `title` 包含关系。

## 11. 主题与动画

- 顶部「主题」按钮：自动 / 浅色 / 深色，保存在 localStorage
- 步骤切换、图示入场、流程箭头、柱状图增长
- 答题卡提交状态、翻卡、提示展开
- 尊重 `prefers-reduced-motion`
- 打印时隐藏控件、展开答案

## 12. 排错

| 现象 | 处理 |
|------|------|
| 找不到源文件 | 检查 `--file` 路径；中文/空格用引号 |
| 答案没写入 | 服务是否启动、端口是否一致、页面是否从服务地址打开 |
| `answers/latest.json` 不存在 | 用户未提交；让用户点提交或复制文本 |
| quiz 解析失败 | 检查 ` ```quiz ` 块是否是合法 JSON |
| 图示不显示 | 检查 `::: flow` 等是否闭合；节点是否用 `→` 分隔 |
| 中文文件名乱码 | 文件是 UTF-8；终端显示问题不影响浏览器 |
| 打印是深色 | 打印样式会覆盖主题；如仍异常，切浅色再打印 |
| 动画太多 | 系统设置“减少动态效果”即可关闭 |

## 13. 安全与隐私

- 所有内容本地生成，不上传网络
- 只允许 `svg` 代码块原样嵌入；其他 HTML 转义
- 链接只允许 http/https/mailto/# 和相对路径
- 答题文件只存学习数据，不存聊天原文/密钥
- `teachers/`、`讲义/`、`.dsh-meow/` 已在 `.gitignore` 排除

## 14. 示例

- `examples/lesson-demo.md`：完整 deck + 图示 + 折叠答案
- `examples/practice-demo.md`：练习页
- `prompts/lesson_template.md`、`practice_template.md`、`reteach_template.md`、`review_template.md`
