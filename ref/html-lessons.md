---
name: html-lessons
description: >
  teacher.skill v3.0 HTML 讲义与练习导出指南：Markdown 格式、
  callout、折叠答案、课程目录、学习状态映射与排错。
version: 3.0.0
---

# HTML 讲义与练习导出

> 每教完一个单元，AI 老师把讲义、练习与答案写成 Markdown，再用一个脚本生成**不依赖网络**的单文件 HTML。
> 课后复习、打印、做 PDF 都用这一份，不用翻聊天记录。

## 1. 目录结构

默认输出到工作区顶层的 `讲义/`：

```
讲义/
└── 计算机组成原理/
    ├── index.html                       # 课程目录 / 复习入口
    ├── unit-04-进位计数制.md             # 源文件（可编辑）
    ├── unit-04-进位计数制.html           # 自包含讲义
    ├── practice-04-错题变式.md           # 练习卷（kind: practice）
    └── practice-04-错题变式.html
```

- 一个单元一个 HTML，上半部分是讲义，下半部分是练习
- `index.html` 自动生成/更新，列出所有讲义与练习卷
- 默认路径可用 `--output-dir` 修改；课程子目录可用 `--course-dir` 修改

## 2. Frontmatter

每个 Markdown 开头必须有 `---` 包围的元数据：

### 讲义（kind 省略或 lesson）

```yaml
---
course: 计算机组成原理
unit: 4
title: 进位计数制
date: 2026-10-28
status: 已完成            # 已完成 / 进行中 / 待复习 / 待学
kind: lesson
tags: [进制, 位权, 转换]
objectives:
  - 理解基数与位权的关系
  - 掌握二 / 八 / 十六进制互转
review_at: 2026-11-04      # 下次复习日期，可选
state_id: U4               # 对应 learning-state 的 id，可选但推荐
sources:
  - 王道《计算机组成原理》第 1 章
description: 从位权展开出发理解进制转换。  # 目录卡片摘要
---
```

### 练习卷

```yaml
---
course: 计算机组成原理
unit: 4
title: 进位计数制·错题变式
kind: practice
parent_unit: 4             # 练习卷归到哪个单元（用于排序/链接）
date: 2026-10-28
status: 待复习
review_at: 2026-10-29
state_id: U4
tags: [变式, 错题]
description: 针对「分组转换」概念混淆生成的 3 道题。
---
```

必填：`course`、`unit`、`title`。其余可省略，脚本会从文件名推断 unit。

## 3. Markdown 语法

支持常用 Markdown 子集，**不依赖任何外部库/网络**：

| 语法 | 效果 |
|------|------|
| `## 标题` / `### 标题` | 正文标题，自动生成右侧目录 |
| `**粗体**`、`*斜体*`、`~~删除~~`、`==高亮==` | 行内格式 |
| `` `代码` `` | 行内代码 |
| 围栏代码块 | 代码块（带语言标签） |
| `| 表 | 表 |` | 表格 |
| `- 列表` / `1. 列表` | 无序/有序列表（支持嵌套） |
| `> 引用` | 引用块 |
| `![alt](path)` | 图片（本地相对路径/URL） |
| `[文字](url)` | 链接 |
| `$r$` | 行内公式（衬线斜体） |
| `---` | 分隔线 |

### 代码块

````text
```python
for i in range(3):
    print(i)
```
````

### SVG 示意图

````text
```svg
<svg ...>...</svg>
```
````

只允许以 `<svg` 开头的内容原样嵌入；其他 HTML 会转义，防止意外脚本。

## 4. Callout（重点框）

用三冒号包裹：

```text
::: definition 基数
一个进制允许使用的数字个数。
:::
```

支持的类型：

| 类型 | 用途 | 默认标题 |
|------|------|---------|
| `definition` | 定义/术语 | 定义 |
| `example` | 例子 | 例子 |
| `warning` | 易错点/警告 | 注意 |
| `tip` | 技巧/捷径 | 技巧 |
| `note` | 补充说明 | 补充 |
| `summary` | 单元小结 | 小结 |
| `keypoint` | 关键要点 | 要点 |
| `formula` | 公式 | 公式 |
| `practice` | 练习提示 | 练习 |
| `exam` | 考点 | 考点 |
| `source` | 来源 | 来源 |
| `answer` | 参考答案（默认折叠） | 参考答案 |

### 折叠答案

```text
::: answer 参考答案
整数部分每 4 位一组：`1101 0110` → `D6`。
:::
```

渲染为 `<details>`，默认折叠；页面顶部有「展开全部答案」按钮，打印时自动展开。

## 5. 生成命令

在工作区根目录执行：

```bash
# 生成单个单元 + 更新 index
python scripts/lesson_html.py build \
  --course "计算机组成原理" \
  --file "讲义/计算机组成原理/unit-04-进位计数制.md" \
  --state "teachers/计算机组成原理/learning-state.json"

# 重建该课程全部 HTML（改了多个 md 后）
python scripts/lesson_html.py rebuild --course "计算机组成原理" \
  --state "teachers/计算机组成原理/learning-state.json"

# 只刷新 index（新增/删除单元、掌握度变化后）
python scripts/lesson_html.py index --course "计算机组成原理" \
  --state "teachers/计算机组成原理/learning-state.json"
```

参数：

| 参数 | 说明 |
|------|------|
| `--course` | 课程名，必填；决定 `讲义/{课程}/` 目录 |
| `--file` | 源 Markdown，`build` 必填 |
| `--output-dir` | 输出根目录，默认 `讲义` |
| `--course-dir` | 课程子目录名，默认同 `--course` |
| `--state` | `learning-state.json` 路径；不传会自动找 `teachers/{课程}/learning-state.json` |
| `--quiet` | 不打印生成日志 |

## 6. index.html

自动生成，包含：

- **统计**：单元总数、已完成、待复习、薄弱知识点
- **进度条**：来自 `learning-state.json` 的 `progress.overall_percent`（缺失时按已完成单元计算）
- **该复习了**：到期复习项（最多展示 8 个）
- **薄弱知识点**：Lv0/Lv1，带掌握度标签
- **AI 建议下一步**：来自 `mastery.next_action`（重讲/练习/复习/推进）
- **搜索**：按标题、单元、标签、练习/讲义过滤
- **状态筛选**：全部 / 已完成 / 进行中 / 待复习 / 待学
- **打印**：打印按钮 + 打印样式

## 7. 与 learning-state.json 的映射

脚本会读取（存在时）：

- `route.units[]`：单元 id/title/status
- `progress.completed_units[]`：完成状态、`next_review_at`
- `progress.overall_percent`：进度条
- `mastery.concepts`：掌握度、薄弱项、到期复习
- `mastery.next_action`：建议下一步

匹配顺序：frontmatter `state_id` → `unit` → `title` 包含关系。匹配不上不影响页面生成，只是不显示对应掌握度/状态。

## 8. 练习卷工作流

1. 用户做完课后练习/检测，AI 记录结果：

```bash
python scripts/mastery.py record --state ... --concept "分组转换" --unit U4 \
  --kind first --result fail --error "概念混淆"
```

2. 取建议练习目标：

```bash
python scripts/mastery.py practice --state ... --count 3
```

3. 按 `prompts/practice_template.md` 写练习卷 Markdown，保存为
   `讲义/{课程}/practice-XX-{标题}.md`，frontmatter 加 `kind: practice` 与 `parent_unit`
4. 运行 `lesson_html.py build` 生成 HTML；index 会自动把它列为「练习卷」
5. 用户做完后，用 `mastery.py record` 记录，再运行 `lesson_html.py index` 刷新

## 9. 打印 / PDF

- 页面顶部「打印 / PDF」按钮
- `@media print` 隐藏目录/按钮/导航，自动展开答案
- 建议用 Chrome/Edge 的「另存为 PDF」，A4 页边距默认即可

## 10. 离线与安全

- CSS/JS 全部内联，不加载 CDN、字体、统计脚本
- 图片可用相对路径；跨设备分享时把图片一起带走
- 所有 Markdown 文本默认转义；只允许 `svg` 代码块原样嵌入
- 链接只允许 `http/https/mailto/#` 和相对路径，`javascript:` 会被替换为 `#`
- 不要把 API key、聊天原文、个人隐私写进讲义

## 11. 排错

| 现象 | 原因/处理 |
|------|----------|
| `找不到源文件` | `--file` 路径不对；用引号包住含空格/中文的路径 |
| 生成的 index 没更新 | 用了 `build` 但源文件在别处；`build` 会复制 md 到输出目录，再 `rebuild/index` |
| 状态没显示 | `--state` 路径不对，或 JSON 损坏；脚本会警告并使用 frontmatter 状态 |
| 中文文件名乱码 | Windows 终端编码问题，文件本身是 UTF-8；用浏览器/编辑器打开确认 |
| 浏览器打不开 `file://` | 某些工具限制；直接双击 HTML，或起一个本地静态服务器 |
| 答案没折叠 | 用了普通 Markdown 而不是 `::: answer` |
| 表格错位 | 表头分隔行必须是 `|---|---|` 形式 |

## 12. 示例

参见 `prompts/lesson_template.md` 与 `prompts/practice_template.md`；仓库里的 `examples/lesson-demo.md` 是一个可构建的完整示例。
