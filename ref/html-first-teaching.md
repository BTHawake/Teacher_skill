---
name: html-first-teaching
description: >
  teacher.skill v4.1 HTML-first 教学法：HTML 是主课堂，
  聊天只做学情诊断、答疑、批改与下一步决策。
version: 4.3.0
---

# HTML-first 教学法（v4.0）

> **HTML 是课堂，聊天是交互。**
>
> AI 把讲解、图示、动画、例题、练习全部放进 HTML 课件；
> 用户看 HTML、做题，在聊天里提问和提交答案；AI 批改后决定下一步。

---

## 1. 为什么这样改

- 聊天适合**即时追问**，不适合承载长讲解、图示和复杂排版
- HTML 适合**结构化、可视化、可复习**的内容
- 把两者分开：HTML 负责“讲清楚”，聊天负责“确认懂了、下一步做什么”

**不要两边讲同一遍。** 用户在 HTML 里看过的内容，聊天里不重复。

---

## 2. 角色分工

| 环节 | 谁来做 | 在哪里 |
|------|--------|--------|
| 学情诊断 | AI | 聊天（1-2 轮） |
| 学习路线 | AI | 聊天确认 + `learning-state.json` |
| 讲解正文 | AI 写 Markdown → 生成 HTML | HTML 课件 |
| 图示/动画/交互 | HTML 组件 | HTML 课件 |
| 做题 | 用户 | HTML 答题卡 / 思考 |
| 提交答案 | 用户点提交 | 写入 `answers/latest.json` |
| 批改 | AI | 聊天 + `mastery.py` |
| 下一步决策 | AI | 聊天告知 + 生成下一页 |
| 复习 | 用户看 HTML，AI 抽检 | HTML + 聊天 |

---

## 3. 标准流程

### Step 1：诊断（聊天）

收到“教我 X”后，先做 1-2 轮诊断：

- 目标：为什么学、学到什么程度
- 基础：学过什么、哪些概念模糊
- 偏好：先看图还是先看例子、要不要公式

不要一上来生成整门课。

### Step 2：路线（聊天确认）

给出 3-8 个单元的学习路线，说明每个单元的目标；用户确认后写入 `learning-state.json`。

### Step 3：生成第 1 单元课件（HTML）

按 `prompts/lesson_template.md` 写 Markdown，必须包含：

- `layout: deck`
- 每个 `##` 是一个步骤
- 至少一个图示（flow/layers/timeline/cycle/compare/bars/SVG）
- 一个 ` ```quiz ` JSON 块（3 题：概念/应用/迁移）
- 一句“看图说话”，告诉用户这张图在解释什么

然后先探测宿主：

```bash
python scripts/dsh_host.py --course "计算机组成原理" \
  --workspace "TeacherSkillEditor" --json
```

- `dsh-plugin`：加 `--api-path "/teacher/api/answers" --workspace "TeacherSkillEditor"`，走同源 `/teacher/`
- `course-server`：加 `--server-url "http://127.0.0.1:<port>"`
- 插件缺失：按 `ref/dsh-hosting.md` 判断是否安装；不装就回退

```bash
python scripts/lesson_html.py build \
  --course "计算机组成原理" \
  --file "讲义/计算机组成原理/unit-04-进位计数制.md" \
  --state "teachers/计算机组成原理/learning-state.json" \
  --api-path "/teacher/api/answers" \
  --workspace "TeacherSkillEditor"
```

### Step 4：聊天只发“导览”

生成后，聊天回复控制在 3-5 行，且给**可直接打开的链接**：

```
第 4 单元课件已生成（共 7 步）：
[打开第 4 单元](/teacher/TeacherSkillEditor/计算机组成原理/unit-04-进位计数制.html)
先看第 2-4 步；做完练习点“提交答案”，然后回我一句“答好了”。
```

不要发文件路径，不要贴课件正文，不要重复解释。

### Step 5：用户学习 + 提问

- 用户问概念：先 2-3 句答疑；如果暴露概念缺口，生成补讲页
- 用户问“下一步”：引导看下一步/下一个 h2
- 用户说“没懂”：不要重复原话；换图示/例子，写进 HTML

### Step 6：用户提交 + AI 读取

用户说“答好了”时：

```bash
cat "讲义/计算机组成原理/answers/latest.json"
```

读取顺序：

1. `answers/latest.json`（最近一次提交）
2. 如果不存在，再看聊天里用户贴的答案
3. 如果都没有，提醒用户提交或粘贴

### Step 7：批改 + 记录

```bash
python scripts/mastery.py record \
  --state "teachers/计算机组成原理/learning-state.json" \
  --concept "位权展开" --unit U4 \
  --kind first --result pass --note "Q1/Q2 正确"
```

逐题批改，指出对在哪里、错在哪里；不要只说“不错”。

### Step 8：决策 + 生成下一页

```bash
python scripts/mastery.py advise --state "..."
```

| 建议 | 生成的 HTML |
|------|-------------|
| `reteach` | `reteach-XX-{薄弱点}.html`：换表征 + 2 道变式 |
| `practice` | `practice-XX-{主题}.html`：3 道针对性题 |
| `review` | `review-XX-{主题}.html`：快速回顾 + 1 道检测 |
| `advance` | 下一单元 `unit-XX-{标题}.html` |

生成后聊天只发链接 + 一句“先看哪里、做完回我”。

---

## 4. 课件类型

| kind | 文件前缀 | 用途 | 布局 |
|------|---------|------|------|
| `lesson` | `unit-` | 单元主课件 | deck |
| `practice` | `practice-` | 针对性练习 | article（可 deck） |
| `reteach` | `reteach-` | 单个薄弱点补讲 | article |
| `review` | `review-` | 到期复习 | article |

所有类型都放在同一个 `讲义/{课程}/`，index 统一列出。

---

## 5. 图示原则

**图要解释，不要装饰。**

- 每个单元通常 0-2 张图；只有图能降低理解成本时才画
- 每张图配一句“看图说话”
- 流程用 `flow`，层次用 `layers`，时间用 `timeline`，循环用 `cycle`，对比用 `compare`，数据用 `bars`
- 复杂数据通路/电路/几何图用 `svg` 代码块
- 动画只做“引导视线”：淡入、流动、脉冲；不要全屏乱动
- 尊重 `prefers-reduced-motion`

### 图示语法

```text
::: flow 指令周期
取指 → 译码 → 执行 → 访存 → 写回
:::

::: layers 存储层次
CPU 寄存器 | 最快、最小
Cache | 介于 CPU 与内存
内存 | 主存
磁盘 | 最慢、最大
:::

::: timeline 发展
1946 | ENIAC
1952 | EDVAC
1964 | IBM System/360
:::

::: cycle 指令周期
取指 → 译码 → 执行 → 写回
:::

::: compare 冯·诺依曼 vs 哈佛
| 维度 | 冯·诺依曼 | 哈佛 |
|------|-----------|------|
| 存储 | 指令数据同存 | 分开存储 |
:::

::: bars 性能对比
方案A: 40
方案B: 75
方案C: 60
:::
```

### 交互组件

```text
::: hint 提示
先想想：为什么取指阶段要先算 PC+1？
:::

::: flip 位权
位权是什么？
---
基数的幂，随位置变化。
:::
```

- `hint`：折叠提示，默认关闭
- `flip`：点击翻面，适合术语/易混概念
- 所有组件可打印；`flip` 打印时正反面都显示

---

## 6. 答题卡与提交

### Markdown 中的 quiz 块

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
      "explanation": "为什么 B 对"
    },
    {
      "id": "Q2",
      "type": "text",
      "prompt": "把十进制 200 转成二进制。",
      "answer": "11001000",
      "explanation": "除基取余，逆序排列"
    }
  ]
}
```
````

- 选择题 `type: choice`，选项值默认 A/B/C
- 简答题 `type: text`
- `answer`/`explanation` 只用于“查看参考答案”，默认折叠
- 页面会自动加答题卡、计数、提交、复制文本

### 提交服务

```bash
python scripts/course_server.py --course "计算机组成原理" --port 8765
```

- 服务只绑定 `127.0.0.1`
- 用户点“提交答案”，写入 `answers/latest.json`
- 没有服务时，用“复制提交文本”发到聊天
- AI 读取文件后，不要把它当成“用户说懂了”；仍要看具体答案

### latest.json 结构

```json
{
  "schema": "teacher.skill/answers/v1",
  "course": "计算机组成原理",
  "unit": "4",
  "title": "进位计数制",
  "answers": [
    {"id": "Q1", "value": "B"},
    {"id": "Q2", "value": "11001000"}
  ],
  "submitted_at": "2026-10-28T11:42:10"
}
```

---

## 7. 聊天发言规范

### 应该

- “第 4 单元课件已生成（7 步）：链接。先看第 2-4 步，做完点提交，回我‘答好了’。”
- “Q1 对；Q2 思路对，但漏了最后一步验算。我在补讲页第 3 步加了一个例子。”
- “这个概念你卡在‘为什么除基取余’，我生成了一张补讲卡：链接。看完做 2 道变式。”

### 不应该

- 把 HTML 里的讲解再贴一遍
- 一次发 20 行推导
- 用户说“没懂”时重复原话
- 用户说“答好了”却不去读 `answers/latest.json`
- 用“你真棒”代替具体批改

### 长度

默认 3-5 行；需要更长时，写进 HTML 再给链接。

---

## 8. 补讲页规则

- 原课件不改，单独生成 `reteach-XX-*.html`
- 只针对一个薄弱点：换一种表征 + 1 个例子 + 2 道变式
- 补讲页要回答“我原来哪里想错了”，而不只是再讲一遍
- 补讲后让用户重做原题的同型变式，再记录 `kind: variant`
- 同一概念 3 次补讲仍不过 → 降级/拆更小/换学科路径

---

## 9. 质量检查

生成 HTML 后快速检查：

- [ ] 每个 `##` 是一个步骤，步骤数 4-8
- [ ] 至少一个图示；图有“看图说话”
- [ ] quiz 3 题，答案/解析完整
- [ ] 动画不抢注意力；`prefers-reduced-motion` 生效
- [ ] 手机宽度可读，按钮不挤
- [ ] 打印/PDF 正常，答案展开
- [ ] 没有密钥、隐私、聊天原文
- [ ] 链接指向正确的课程目录

## 10. 边界

- HTML 是静态页面，不能替用户“实时讲课”；它承载的是**预设的讲解 + 交互**
- 用户的问题仍需 AI 在聊天里回答；HTML 只负责可沉淀的内容
- 不要为了动画牺牲可读性
- 不要把整门课一次性生成；按单元/掌握度逐步生成
- 答题卡文件只存学习数据，不上传网络
