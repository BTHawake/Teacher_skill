# 老师.skill

> 好老师不是告诉你答案的人，是帮你找到答案的人。

[安装](#安装) · [使用](#使用) · [效果示例](#效果示例) · [常见问题](#常见问题) · [English](README_EN.md) · [GitHub 仓库](https://github.com/BTHawake/Teacher_skill)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![AgentSkills](https://img.shields.io/badge/AgentSkills-Standard-green)](https://agentskills.io)
[![Version](https://img.shields.io/badge/version-4.3.0-blue)]()
[![Subjects](https://img.shields.io/badge/subjects-10-orange)]()
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)
[![Multi-Platform](https://img.shields.io/badge/Multi--Platform-6%20Platforms-orange)]()
[![Readme EN](https://img.shields.io/badge/Readme-English-blue)](README_EN.md)

---

把一份文档、一本书、一门课程丢给 AI，它会像一位耐心的老师一样，先了解你的基础，再用你能听懂的方式，一步步教会你。

不假设你"应该知道"什么，不急于给答案，不跳过任何一步。每个知识点讲完都会确认你真的懂了，然后再往下走。

**v4.3 核心能力**：**HTML 是主课堂**。每单元生成一个分步 HTML 课件（讲解 + 图示 + 动画 + 答题卡），用户看 HTML、在聊天里答题；AI 读取答题卡提交，按掌握度生成补讲/练习/复习页或下一单元。新增 **DSH 宿主探测**：优先挂到 DSH 自己的 `/teacher/` 插件，远程访问不用转发 8765；没有插件时回退独立课程服务；workspace 由 AI 判断并注册，端口由 AI 自选。10 个学科自带执行微流程，按知识型 / 方法论型分流；支持 5 分钟轻量微课。

现在支持 **10 个学科** 的专业教学策略：数学、编程、语文、英语、物理、化学、历史、生物、AI、费曼思维。说"我想学会巴菲特的思维方式"会自动搜索匹配 skill 并生成课程。

---

## 安装
注意！命令行下不了，clash要开虚拟网卡模式

### Claude Code

```bash
# 项目级（仅当前项目可用）
mkdir -p .claude/skills
git clone https://github.com/BTHawake/Teacher_skill .claude/skills/teacher-skills

# 全局（所有项目可用）
git clone https://github.com/BTHawake/Teacher_skill ~/.claude/skills/teacher-skills
```

> **重要**：Claude Code 从 git 仓库根目录扫描 `.claude/skills/`，请确保目录结构正确。

### OpenAI Codex CLI

```bash
# 启用 skills 功能
codex --enable skills

# 项目级
mkdir -p .codex/skills
git clone https://github.com/BTHawake/Teacher_skill .codex/skills/teacher-skills

# 全局
git clone https://github.com/BTHawake/Teacher_skill ~/.codex/skills/teacher-skills
```

### OpenCode

```bash
# 项目级
mkdir -p .opencode/skills
git clone https://github.com/BTHawake/Teacher_skill .opencode/skills/teacher-skills

# 个人级
git clone https://github.com/BTHawake/Teacher_skill ~/.config/opencode/skills/teacher-skills
```

### OpenClaw

```bash
git clone https://github.com/BTHawake/Teacher_skill ~/.openclaw/workspace/skills/teacher-skills
# 重启 Gateway 生效
```

### DeepSeek Harness（DSH）

DSH 会实时发现 `.dsh/skills/` 下的 `SKILL.md`，装完无需重启。先确认已安装 Git，并且 `git` 在 PATH 中：

```bat
git --version
```

#### 项目级（仅当前工作区，在 DSH 工作区根目录执行）

**CMD**

```bat
if not exist ".dsh\skills" mkdir ".dsh\skills"
git clone https://github.com/BTHawake/Teacher_skill ".dsh\skills\teacher"
```

**PowerShell**

```powershell
New-Item -ItemType Directory -Force ".dsh\skills" | Out-Null
git clone https://github.com/BTHawake/Teacher_skill ".dsh\skills\teacher"
```

#### 全局（所有工作区生效）

**CMD**

```bat
if not exist "%USERPROFILE%\.dsh\skills" mkdir "%USERPROFILE%\.dsh\skills"
git clone https://github.com/BTHawake/Teacher_skill "%USERPROFILE%\.dsh\skills\teacher"
```

**PowerShell**

```powershell
New-Item -ItemType Directory -Force "$HOME\.dsh\skills" | Out-Null
git clone https://github.com/BTHawake/Teacher_skill "$HOME\.dsh\skills\teacher"
```

#### 更新

只执行你实际安装位置对应的一条：

**CMD**

```bat
:: 项目级
git -C ".dsh\skills\teacher" pull --ff-only

:: 全局
git -C "%USERPROFILE%\.dsh\skills\teacher" pull --ff-only
```

**PowerShell**

```powershell
# 项目级
git -C ".dsh\skills\teacher" pull --ff-only

# 全局
git -C "$HOME\.dsh\skills\teacher" pull --ff-only
```

> `pull --ff-only` 要求本地没有冲突修改；失败时先 `git -C "<安装目录>" status` 查看，或备份后重装。
> 如果当初是 zip/复制安装（目录里没有 `.git`），不能 `pull`，需要删除目录后重新 clone。

注意：

- DSH 忽略 `allowed-tools` / `triggers` 等额外 frontmatter，但会读取 `name` / `description`
- 联网工具是 `web_search` / `web_fetch`；课前搜索规则已改为平台无关
- HTML 课件用浏览器直接打开即可；部分工具限制 `file://`，可双击文件或用本地服务

#### 远程连接 DSH 时

**优先方案：挂到 DSH 自己的端口。** 安装独立插件 [dsh-Teacher-skill](https://github.com/BTHawake/dsh-Teacher-skill)：

```bash
git clone git@github.com:BTHawake/dsh-Teacher-skill.git
cd dsh-Teacher-skill
dsh plugin --profile web add "link:$PWD"
# 重启 dsh web
```

安装后课件挂在 DSH 的 `/teacher/` 路径下。本机调试地址是 `http://127.0.0.1:3080/teacher/...`，但**远程要发根相对链接**（如 `/teacher/...`），让浏览器按当前 DSH 域名解析；不要发 `127.0.0.1` 绝对地址。

skill 会先探测：

```bash
python scripts/dsh_host.py --course "计算机组成原理" --workspace "TeacherSkillEditor" --json
```

返回 `mode: "dsh-plugin"` 时，生成课件加：

```bash
--api-path "/teacher/api/answers" --workspace "TeacherSkillEditor"
```

聊天里发根相对链接即可：

```markdown
[打开第 4 单元课件](/teacher/TeacherSkillEditor/计算机组成原理/unit-04-进位计数制.html)
```

**如果没有插件、或不想安装**，再回退到独立课程服务（临时/兼容模式，需要端口转发）：

课程服务默认只监听 `127.0.0.1`。如果你远程连 DSH，浏览器在本地，`127.0.0.1:8765` 指向的是**你自己的电脑**，不是 DSH 主机。把 8765 和 3080 一起转发即可：

```bash
# SSH 隧道（把 3080 和 8765 都转发到本地）
ssh -L 3080:127.0.0.1:3080 -L 8765:127.0.0.1:8765 user@host
```

然后：

- 在 DSH 主机上启动 `python scripts/course_server.py --course "课程" --port 8765`
- 本地浏览器打开 `http://127.0.0.1:8765/`
- 课件生成时 `--server-url` 用你浏览器实际访问的地址；同一来源下脚本会自动推导 API

其他远程方式：

| 方式 | 做法 |
|------|------|
| VS Code Remote / JetBrains | 在 Ports 面板转发 `8765` |
| 远程桌面 | 在远程桌面里打开浏览器，直接访问 `127.0.0.1:8765` |
| Tailscale / ZeroTier | 服务绑定 Tailscale IP 或用 `--host 0.0.0.0`，访问 `http://<tailscale-ip>:8765`（私有网络） |
| 公网隧道 / 反向代理 | 增加 `/api/answers` 路由并加鉴权；不要把 8765 直接裸奔到公网 |

> 答题卡会自动按 `location.href` 推导 `/api/answers`，所以通过子路径反代也能提交；用 `file://` 打开时才会用 `data-server-url`。

### TRAE

TRAE 使用 Rules 系统而非 Skills 目录。将 `SKILL.md` 复制为规则文件：

```bash
mkdir -p .trae/rules
cp teacher-skills/SKILL.md .trae/rules/teacher.md
```

在规则文件顶部添加 TRAE 元数据：

```yaml
---
description: "AI老师：给定资料后像老师一样教会用户理解内容，支持学情诊断和分级教学"
alwaysApply: false
priority: 2
---
```

在聊天中用 `#teacher` 引用。

---

## 环境要求

- Node.js 18+（Claude Code / Codex CLI 依赖）
- Git 2.0+（用 `git clone` / `git pull` 安装或更新时需要）
- Claude Pro/Max 订阅或 Anthropic API Key（Claude Code）
- OpenAI API Key（Codex CLI）
- Python 3.9+（HTML 课件、答题服务、掌握度引擎与进度脚本需要；只聊天可不用）

---

## 使用

安装完成后，对 AI 说：

```
教我这份文档的内容
```

然后粘贴或上传你的资料。AI 会自动进入教学流程。

你也可以直接指定主题：

```
/teacher 机器学习
```

### v4.0 课堂形态：HTML 讲课，聊天答题

```
聊天诊断 → 生成第 1 单元 HTML 课件 → 用户看 HTML 学习
                                      ↓
                          HTML 答题卡 → 提交到 answers/latest.json
                                      ↓
                          聊天里说“答好了” → AI 读取并批改
                                      ↓
                    按掌握度生成：补讲页 / 练习页 / 复习页 / 下一单元
```

聊天只负责四件事：**诊断、答疑、批改、决策**。讲解正文、图示、动画、例题、练习都在 HTML 里，AI 不会在聊天里再讲一遍。

启动本地课件服务：

```bash
python scripts/course_server.py --course "计算机组成原理" --port 8765
# 浏览器打开 http://127.0.0.1:8765/
```

生成第 4 单元课件：

```bash
python scripts/lesson_html.py build --course "计算机组成原理" \
  --file "讲义/计算机组成原理/unit-04-进位计数制.md" \
  --state "teachers/计算机组成原理/learning-state.json" \
  --server-url "http://127.0.0.1:8765"
```

一次典型对话：

```
❯ 第 4 单元课件已生成（共 7 步）：
   http://127.0.0.1:8765/unit-04-进位计数制.html
   先看第 2-4 步；做完练习点“提交答案”，回我“答好了”。

❯ 答好了

   Q1 ✅
   Q2 ❌ 漏了最后一步验算（步骤遗漏）。
   补讲页第 3 步有一个同型例子：[链接]
   看完做 2 道变式，再回我。
```

首轮 + 换场景变式都通过才推进；没过就生成补讲/练习页，不重写原课件。

### 网页能有多生动

- 分步切换、进度条、已读步骤勾选、键盘 ← →
- 翻卡、折叠提示、代码一键复制、浅色/深色主题
- 流程图箭头流动、层次图逐层点亮、时间线入场、循环图旋转箭头
- 答题卡提交状态、已答计数、打印/PDF
- 图示语法：`flow` / `layers` / `timeline` / `cycle` / `compare` / `bars`，复杂图用 SVG

### 模仿名师风格

如果你想 AI 用某位老师的教学风格来教你：

```
用这个风格教我线性代数
```

然后上传课程字幕文件（SRT/VTT/TXT），或提供视频链接（YouTube/Bilibili）。

AI 会自动分析该教师的教学风格（句式、词汇、节奏、互动方式等），然后用这种风格教你。

```
❯ 用这个风格教我（上传某名师的课程字幕）

   我正在分析这份教学素材...

   风格分析完成。这位老师的教学风格是：
   "用密集的短句和生活化的类比拆解复杂概念，
    每讲完一个知识点就用反问确认理解，口头禅是'对吧？'和'很简单'。"

   接下来我会用这种风格教你。如果觉得模仿得不像，
   可以提供更多素材让我调整。
```

### 管理命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/teacher status` | 查看当前学习进度 | `/teacher status` |
| `/teacher reset` | 重置学习会话 | `/teacher reset` |
| `/teacher level` | 手动调整能力等级 | `/teacher level advanced` |
| `/teacher skip` | 跳过当前单元 | `/teacher skip` |
| `/teacher review` | 打开讲义目录，回顾到期复习项（v4.0） | `/teacher review` |
| `/teacher quick` | 轻量模式：一个概念 + 一个例子 + 一道检测 | `/teacher quick 什么是位权` |
| `/teacher practice` | 按薄弱点生成 3 道练习并导出练习页 | `/teacher practice` |
| `/teacher mastery` | 查看 Lv0-Lv3 掌握度与下次复习 | `/teacher mastery` |
| `/teacher export` | 把当前单元导出为 HTML 课件 | `/teacher export` |
| `/teacher rebuild` | 重建当前课程全部 HTML | `/teacher rebuild` |
| `/teacher html on/off` | 开关每单元自动生成 HTML | `/teacher html off` |
| `/teacher quit` | 结束当前学习 | `/teacher quit` |
| `/teacher style` | 查看当前教学风格档案 | `/teacher style` |
| `/teacher style off` | 关闭风格模仿 | `/teacher style off` |
| `/teacher style more` | 增强风格模仿强度 | `/teacher style more` |
| `/update-teacher {slug}` | 追加新材料进化教学档案 | `/update-teacher wang-laoshi` |
| `/list-teachers` | 列出所有已创建的教学档案 | `/list-teachers` |
| `/teacher rollback {v}` | 回滚到指定版本 | `/teacher rollback v3` |

---

## 效果示例

> 输入：教我这份 PDF 的内容（上传《线性代数应该这样学》第三章）

```
❯ 我已经收到了你的资料，让我先看看内容。

   这份资料是《线性代数应该这样学》第三章，主要讲的是"线性映射"。
   大约包含 5 个核心知识点。学完之后你将能够理解什么是线性映射、
   如何判断一个映射是否线性、以及矩阵如何表示线性映射。

   在开始之前，我想先了解一下你的情况——
   你之前学过线性代数吗？了解多少？
```

```
❯ 学过一点点，但矩阵那些东西已经记不清了...

   明白。根据我们的交流，我判断你在"线性代数"领域属于中等基础。
   我会用脚手架式教学法来教你：先帮你梳理框架，再逐步深入。
   如果觉得太快或太慢，随时告诉我。

   我们大概会按这个顺序来学：
   ① 线性映射的定义（什么是线性映射）
   ② 判断线性映射的方法
   ③ 线性映射的核与像
   ④ 矩阵表示
   ⑤ 总结与练习

   准备好了吗？我们从①开始。
```

```
❯ 好的

   来看第一个概念：线性映射。

   你可以把它想象成一个"规则"——它接受一个输入向量，
   然后按照某种固定的方式，输出另一个向量。

   但这个"规则"有两个硬性要求：
   1. 加法保持：f(u + v) = f(u) + f(v)
   2. 数乘保持：f(cu) = c · f(u)

   用大白话说就是：先加再变 = 变完再加，先乘再变 = 变完再乘。

   到目前为止能跟上吗？
```

### v4.3 更新日志

| 能力 | 说明 |
|------|------|
| **返回对话** | 顶部栏 `← 返回对话`：优先聚焦聊天标签，其次 referrer，最后 DSH 根路径 |
| **DSH 安装提醒** | 检测到 DSH 但缺插件时先提醒安装；8765 明确标注“临时回退” |
| **临时端口** | `course-server` 降级为兼容模式，不再默认静默启动 |
| **生成后验活** | `verify_page.py` 验文件完整性 + HTTP 200 + 标题；PASS 才发链接 |
| **workspace 注册** | AI 用 `pwd` 判断，写 `~/.dsh/teacher-workspaces.json`；插件只服务注册根 |
| **端口** | 插件无独立端口；fallback 才由 AI 找空闲端口（`--port 0`） |
| **目录去重** | 忽略没有对应 HTML 的旧 `.md`；同一单元只保留最新课件 |
| **远程链接** | 默认发根相对链接 `/teacher/...`，不再把 `127.0.0.1` 绝对地址发给远程用户 |
| **绝对 URL** | `dsh_host.py --public-base https://host/...` 生成 `public_url`；`local_url` 只用于本机调试 |
| **DSH 宿主探测** | `dsh_host.py` 优先探测 `/teacher` 插件，再决定插件/独立服务/静态导出 |
| **DSH 插件（独立仓库）** | [dsh-Teacher-skill](https://github.com/BTHawake/dsh-Teacher-skill)：课件挂到 DSH 3080 的 `/teacher/`，远程访问不用转发 8765 |
| **HTML-first** | HTML 是主课堂；聊天只做诊断/答疑/批改/决策 |
| **分步 deck** | 每单元一个分步课件，进度条、已读勾选、键盘导航 |
| **答题卡 + 本地服务** | 用户提交，AI 读取 `answers/latest.json` 批改 |
| **补讲/练习/复习页** | 决策落成独立 HTML，不重写原课件 |
| **图示 DSL** | flow / layers / timeline / cycle / compare / bars + 原始 SVG |
| **动效与交互** | 主题切换、翻转卡、提示折叠、代码复制、SVG 动画 |
| **自适应掌握度** | Lv0-Lv3；首轮 + 变式都通过才推进 |
| **复习调度** | 1/3/7/14/30 天；到期 >5 个时本次只做 3 个 |
| **测试 / CI** | 52 个 unittest；GitHub Actions 跑 Python 3.9-3.12 |

---

## 功能特性

### 学情诊断

通过自然对话评估用户的学习能力，不让人感觉在"考试"。

| 能力等级 | 判断依据 | 教学策略 |
|---------|---------|---------|
| 🔴 弱基础 | 完全零基础，领域术语陌生 | 讲授式 + 大量类比 + 小步快跑 |
| 🟡 中等基础 | 有模糊印象，概念不清晰 | 脚手架式 + 渐进练习 |
| 🟢 强基础 | 能准确描述核心概念 | 探究式 + 挑战性练习 |

诊断不是一次性的。教学过程中会根据用户表现持续修正判断，支持动态升级或降级。

### 三级教学策略

| | 🔴 弱基础 | 🟡 中等基础 | 🟢 强基础 |
|---|----------|-----------|----------|
| **方法** | 讲授式 + 大量类比 | 脚手架式 | 探究式 |
| **讲解/练习** | 70% / 30% | 50% / 50% | 30% / 70% |
| **检查方式** | 选择题/判断题 | 复述题/应用题 | 分析题/设计题 |
| **节奏** | 慢，每步都检查 | 中等，每概念检查 | 快，每2-3概念检查 |

### 通俗化讲解

内置万能类比库，将抽象概念翻译成日常语言：

| 抽象概念 | 类比 |
|---------|------|
| 算法 | 菜谱 |
| 缓存 | 冰箱 |
| 递归 | 俄罗斯套娃 |
| API | 餐厅服务员 |
| 容器(Docker) | 集装箱 |
| 版本控制(Git) | 游戏存档 |

### 进化机制

教学档案创建后支持三种进化方式：

- **追加材料**：提供新的课程资料，增量 merge 进现有档案，不覆盖已有结论
- **对话纠正**：说"这不对"/"老师不会这样说"，立即生效并记录 Correction
- **版本管理**：每次更新自动存档，最多保留 10 个历史版本，支持回滚

### 风格模仿

上传课程字幕或提供视频链接，AI 自动提取教师的教学风格并模仿：

| 输入方式 | 说明 |
|---------|------|
| 课程字幕（SRT/VTT/TXT） | 最佳，直接上传文件 |
| 视频链接（YouTube/Bilibili） | 自动提取字幕（需安装 yt-dlp） |
| 文字稿/文章 | 直接粘贴教学文本 |

风格分析覆盖六个维度：句式结构、词汇特征、教学节奏、互动模式、内容组织、情感态度。

> **依赖**：视频字幕提取需要 `yt-dlp`（`pip install yt-dlp`）。如果视频没有字幕，请上传课程字幕文件。

### 跨学科思维（v2.0）

不再孤立地教单个学科——在教学全流程中嵌入网状知识连接，帮助学生建立跨学科联想习惯。

| 能力 | 说明 | 教学时机 |
|------|------|---------|
| **知识联网** | 12组核心概念跨6+学科映射（如"反馈"在生物=稳态、在电子=电路、在编程=递归） | 概念讲解时自然穿插 |
| **举一反三** | 结构化类比三步法：从熟悉领域提取模式 → 应用到新概念 → 验证理解 | 引入新概念时 |
| **联想激发** | 三句话联想练习 + 跨界五问 + 10张跨界碰撞卡（如"如果把这个概念做成产品..."） | 课后巩固/阶段性回顾 |

跨学科连接不是额外负担——好的跨学科教学让每个概念都"多了一个维度"。当你学数学时看到物理的影子，学物理时闻到化学的味道，知识就活了。

详见 `ref/cross-disciplinary-thinking.md`。

### 技能教学（v2.2）

说"我想学会XXX的思维方式"自动完成搜索、生成、教学全流程：

1. 搜索开源 skill 仓库（awesome-persona-skills 等）查找匹配 skill
2. 搜索不到时自动网络搜索补充公开信息
3. 统一提取管道：用户资料 + skill + 网络信息 → 四维提取（核心观点/实际应用/多视角/案例库）→ 三重验证 → 课程组装
4. 每条核心观点标注来源链接

说"我想学会巴菲特的思维方式" → 搜索巴菲特.skill → 分析提取 6 个心智模型 → 生成课程 → 直接开课。

> 用户提供自己的资料时，以资料为主，skill 为辅助。

### HTML 主课堂（v4.3）

每单元生成一个**分步 HTML 课件**，讲解、图示、动画、例题和练习都在里面；聊天只发导览和批改结果。

生成前先探测宿主（插件 / 已有服务 / 空闲端口），再决定链接：

```bash
python scripts/dsh_host.py --course "计算机组成原理" --workspace "TeacherSkillEditor" --json
```

- 返回 `dsh-plugin` → 用同源 `/teacher/`，远程 DSH 不用转发 8765
- 返回 `dsh-plugin-register-required` → AI 先运行 `dsh_register.py --workspace-root "$PWD"` 注册当前工作区
- 返回 `dsh-plugin-missing` → 先提醒安装插件；8765 只是临时方案，等用户确认
- 返回 `course-server` → 临时/兼容模式，启动或复用独立服务

注册当前工作区（AI 用 `pwd` 判断）：

```bash
python scripts/dsh_register.py --workspace-root "$PWD" --json
```

```
讲义/
└── 计算机组成原理/
    ├── index.html                     # 进度、到期复习、薄弱点、AI 建议、搜索
    ├── unit-04-进位计数制.html         # 分步 deck：讲义 + 图示 + 答题卡
    ├── practice-04-错题变式.html       # 练习页
    ├── reteach-04-位权.html            # 补讲页
    └── answers/latest.json             # 答题卡提交（AI 读取）
```

- 分步导航、进度条、已读勾选、键盘 ← →
- 翻卡、提示折叠、代码复制、浅色/深色主题
- 流程图箭头流动、层次图逐层点亮、时间线入场、循环图箭头
- 答题卡：提交到 DSH `/teacher` 或本地服务，或复制提交文本发到聊天
- 顶部栏 `← 返回对话`：优先聚焦聊天标签，其次回 referrer，最后回 DSH 根路径
- 离线单文件、不加载 CDN；可打印 / 另存 PDF

![HTML 课件：图示与交互](docs/html-first-cycle.png)

![HTML 课件：答题卡](docs/html-first-quiz.png)

```bash
# A. DSH 插件模式（推荐，远程 DSH 不用转发 8765）
python scripts/lesson_html.py build --course "计算机组成原理" \
  --file "讲义/计算机组成原理/unit-04-进位计数制.md" \
  --state "teachers/计算机组成原理/learning-state.json" \
  --api-path "/teacher/api/answers" \
  --workspace "TeacherSkillEditor"

# B. 没有插件：独立课程服务（临时/兼容模式）
python scripts/course_server.py --course "计算机组成原理" --port 8765
python scripts/lesson_html.py build --course "计算机组成原理" \
  --file "讲义/计算机组成原理/unit-04-进位计数制.md" \
  --state "teachers/计算机组成原理/learning-state.json" \
  --server-url "http://127.0.0.1:8765"
```

图示 DSL：`flow` / `layers` / `timeline` / `cycle` / `compare` / `bars`；复杂图用 `svg` 代码块。
详见 [`ref/dsh-hosting.md`](ref/dsh-hosting.md)、[`ref/html-first-teaching.md`](ref/html-first-teaching.md) 与 [`ref/html-lessons.md`](ref/html-lessons.md)。

### 自适应教学（v4.0）

不是"讲完就往前走"。每单元练 3 题（概念 / 应用 / 迁移），记录掌握度，再决定下一步：

| 等级 | 判定证据 | 默认动作 |
|------|---------|---------|
| Lv0 未掌握 | 答错、说不清 | 换讲法重讲（补讲页） |
| Lv1 模糊 | 部分正确、需提示 | 2 道针对性练习 |
| Lv2 基本掌握 | 首轮检测通过 | 1 道换场景变式 |
| Lv3 掌握 | 首轮 + 变式通过 | 推进 + 间隔复习 |

- **答案来源**：优先读 `讲义/{课程}/answers/latest.json`，其次聊天里粘贴的答案
- **推进门槛**：首轮 + 变式都通过；只做对原题不算
- **决策顺序**：最近 fail → 重讲；partial → 练习；到期 → 复习（>5 个时只做 3 个，其余顺延）；Lv2 → 变式；全部 Lv3 → 推进
- **动作落成页面**：补讲页 / 练习页 / 复习页 / 下一单元
- **自主权**：单元内自动调整；跨单元、改路线先确认
- **复习**：1/3/7/14/30 天递增；到期 >5 个时本次只处理 3 个

```bash
python scripts/mastery.py record --state "teachers/课程/learning-state.json" \
  --concept "位权" --unit U4 --kind first --result pass
python scripts/mastery.py advise --state "teachers/课程/learning-state.json"
```

详见 [`ref/adaptive-teaching.md`](ref/adaptive-teaching.md)。

### 学科插件（v4.0）

每个 `subjects/*.md` 自带 `type: knowledge | methodology` 和 5 步执行微流程：

| 类型 | 适用 | 教学主线 |
|------|------|---------|
| knowledge | 数学、编程、语文、英语、物理、化学、历史、生物、AI | 概念 → 例子 → 练习 → 检测 → 迁移 |
| methodology | 费曼思维等 | 识别旧模式 → 制造冲突 → 新模型 → 场景练习 → 习惯固化 |

主 SKILL 只负责调度，学科文件负责"这一科具体怎么教"。详见 [`ref/subject-plugins.md`](ref/subject-plugins.md)。

### 轻量启动（v4.0）

"简单讲讲 / 五分钟讲一下 / `/teacher quick`" → 直接生成一张单页 HTML 微课（概念 + 例子 + 1 题），不跑完整 Phase 0-2。结束后问"要不要扩成完整单元"，不强行加课。

### 应试套路教学法（v2.8）

面对真题试卷时，以考点套路为主、真题练习为辅。不逐题刷题，而是将所有题目按解题模型归类重组：

试卷题目 → 提取共同考点 → 归纳为得分模型 → 逐模型讲套路 → 真题验证

每个模型包含：适用题型、核心套路、关键公式、常见陷阱、得分口诀。先画考点-分值地图让学生知道哪块分值最大，再逐模型教学。套路讲完用真题验证。

### 刻意练习循环（v2.5）

基于 Ericsson 刻意练习方法论，单次理解检查升级为刻意练习循环：

```
初次检查 → 不通过 → 诊断（概念偏差/表达不准/迁移失败/记忆混淆）→ 纠正 → 重试
    ↓ 通过
变式练习（换不同场景）→ 不通过 → 诊断 → 纠正 → 重试
    ↓ 通过
确认掌握 → 进入下一单元（最多 3 次循环，超限降级）
```

讲解后先做"心智演练"（在脑子里过一遍），再答题，再变式。不是"做对了就过"，是"换场景还能做对"才算掌握。

### 课前搜索验证（v4.0 修订）

每个新单元开讲前，优先用当前平台可用的联网工具核对至少 2 个权威来源。如果全部网络源不可达：

1. 简洁说明尝试过的工具和失败原因
2. **只问一次**：先用现有资料 + 我的知识继续（标注「未联网核验」），还是先解决网络？
3. 用户选继续后，本次会话不再重复询问；涉及易变事实处标注「未联网核验」
4. 不伪造来源；没搜到就写"依据教材第 X 章"

搜索成功则正常引用来源并继续教学，无需中断。

### 评估检测系统（v2.8）

用出题检测替代口头回顾。每个知识点不是"讲完就过"，而是用检测题验证。

| 检测类型 | 触发时机 | 题型 |
|---------|---------|------|
| **小评估** | 每教完 1-2 个新单元 | 各单元 1-2 道检测题 |
| **大评估** | 大单元（4-5 个单元）结束 | 跨知识点综合题 |

评估流程：出题 → 作答 → 批改反馈 → 下一题。答错的题会用更简单的方式重讲，再出同类型变式题验证。统计各单元正确率，薄弱知识点优先复习。

### 间隔复习系统（v2.6）

基于 Ebbinghaus 遗忘曲线，学习进度持久化后自动安排间隔复习：

- 每次回来学习时，自动检查是否有到期的复习项
- 快速回顾模式（2-3 分钟），非重新教学
- 复习间隔递增：1 天 → 3 天 → 7 天 → 14 天 → 30 天 → 已巩固
- 用户可以选择"先复习"、"先学新的"或"跳过这次"

---

## 项目结构

```
teacher-skills/
├── SKILL.md                              # 主入口：HTML-first 教学调度器（v4.3）
├── README.md                             # 中文文档
├── README_EN.md                          # 英文文档
├── LICENSE                               # MIT 许可证
│
├── config/
│   └── skill-config.json                 # 项目配置（HTML/自适应/学科）
│
├── prompts/
│   ├── lesson_template.md                 # 分步课件 Markdown 模板（v4.0）
│   ├── practice_template.md               # 练习页模板（v4.0）
│   ├── reteach_template.md                # 补讲页模板（v4.0）
│   ├── review_template.md                 # 复习页模板（v4.0）
│   ├── intake.md                       # 教师信息录入（3问+教学标签库）
│   ├── style-extractor.md              # 教学风格六维度提取指南
│   ├── style-profile-template.md       # 教学风格档案模板
│   ├── teaching_analyzer.md            # 教学风格分析 Prompt
│   ├── teaching_builder.md             # 教学档案生成模板（Layer 0-5）
│   ├── merger.md                       # 增量 Merge Prompt
│   └── correction_handler.md           # 对话纠正处理
│
├── scripts/
│   ├── lesson_html.py                   # Markdown → 分步 HTML 课件 + 答题卡 + 目录（v4.3）
│   ├── dsh_host.py                      # 探测 DSH 插件/课程服务/空闲端口（v4.3）
│   ├── dsh_register.py                  # 把 AI 判断的 workspace 写入注册表（v4.3）
│   ├── verify_page.py                   # 验文件完整性 + HTTP 可打开性（v4.3）
│   ├── course_server.py                 # 本地课件服务 + 答题卡提交（v4.3）
│   ├── mastery.py                       # 掌握度/复习/下一步建议引擎（v4.3）
│   ├── generate_quiz.py                # 练习题生成（按等级/题型）
│   ├── evaluate_answer.py              # 答案评估 + 反馈模板
│   ├── track_progress.py               # 学习进度追踪
│   ├── learning_state.py               # 学习状态持久化管理（v4.3）
│   ├── reverse_distill.py              # 反蒸馏分析工具（v2.1）
│   ├── extract_subtitle.py             # 视频/字幕提取工具
│   └── skill_writer.py                 # 教学档案文件管理器
│
├── tests/                              # 单元测试（v4.3）
│   ├── test_lesson_html.py
│   ├── test_mastery.py
│   ├── test_course_server.py
│   ├── test_dsh_host.py
│   ├── test_dsh_register.py
│   └── test_verify_page.py
│
├── examples/                           # 可构建的示例课件/练习
│   ├── lesson-demo.md
│   └── practice-demo.md
│
├── docs/                               # 文档截图
│   ├── html-first-cycle.png
│   └── html-first-quiz.png
│
├── ref/
│   ├── learner-diagnosis.md              # 学情诊断指南
│   ├── teaching-strategies.md            # 三级教学策略（强/中/弱）
│   ├── teaching-techniques.md            # 通俗化讲解技巧 + 类比库 + 表达DNA
│   ├── question-templates.md             # 出题模板库
│   ├── teaching-sop.md                   # 教学 SOP（Phase 0-5 + HTML-first Phase 3）
│   ├── dsh-hosting.md                    # DSH 宿主选择：插件/独立服务/静态（v4.3）
│   ├── html-first-teaching.md            # HTML-first 教学法（v4.3）
│   ├── adaptive-teaching.md              # 自适应教学引擎（v4.3）
│   ├── html-lessons.md                   # HTML 课件格式/图示/答题卡指南（v4.3）
│   ├── subject-plugins.md                # 学科插件协议（v4.3）
│   ├── management-commands.md            # 管理命令表
│   ├── verification-framework.md         # 教学效果验证框架
│   ├── extraction-framework.md           # 统一提取框架（四维提取+三重验证）
│   ├── skill-to-curriculum-guide.md      # 技能教学操作指引
│   ├── cross-disciplinary-thinking.md   # 跨学科思维教学模块
│   ├── deliberate-practice-research.md   # 刻意练习调研报告
│   ├── forgetting-curve-research.md      # 遗忘曲线调研报告
│   ├── nuwa-absorption.md               # 女娲.skill 吸收分析
│   ├── reverse-distillation-report.md   # 技能教学调研报告
│   ├── unified-extraction-research.md    # 统一提取管道调研
│   └── improvement-roadmap.md            # 改进计划与版本路线图
│
├── adapters/
│   └── trae-teacher.md                   # TRAE 平台适配文件
│
├── .github/workflows/
│   └── ci.yml                            # 单元测试 + 编译检查（v4.0）
│
└── subjects/
    ├── _template-SKILL.md                # 学科子Skill模板（含 v4.1 微流程）
    ├── math-teacher-SKILL.md             # 数学教学策略
    ├── programming-teacher-SKILL.md      # 编程教学策略
    ├── chinese-teacher-SKILL.md          # 语文教学策略
    ├── english-teacher-SKILL.md          # 英语教学策略
    ├── physics-teacher-SKILL.md          # 物理教学策略
    ├── chemistry-teacher-SKILL.md        # 化学教学策略
    ├── history-teacher-SKILL.md          # 历史教学策略
    ├── biology-teacher-SKILL.md          # 生物教学策略
    ├── ai-teacher-SKILL.md               # AI人工智能教学策略
    └── feynman-teacher-SKILL.md          # 费曼思维（反蒸馏）
```

---

## 已有学科

| 学科 | 文件 | 重点覆盖 |
|------|------|---------|
| 数学 | `subjects/math-teacher-SKILL.md` | 公式直觉化、几何可视化、证明思路 |
| 编程 | `subjects/programming-teacher-SKILL.md` | 代码思维、调试能力、项目实战 |
| 语文 | `subjects/chinese-teacher-SKILL.md` | 文言文、阅读理解、写作、文学鉴赏 |
| 英语 | `subjects/english-teacher-SKILL.md` | 语法、词汇、口语、听力、应试 |
| 物理 | `subjects/physics-teacher-SKILL.md` | 概念理解、公式推导、实验思维 |
| 化学 | `subjects/chemistry-teacher-SKILL.md` | 反应、方程式、实验操作、计算 |
| 历史 | `subjects/history-teacher-SKILL.md` | 时间线、因果分析、史料解读 |
| 生物 | `subjects/biology-teacher-SKILL.md` | 细胞、基因、生理、进化、生态 |
| AI / 人工智能 | `subjects/ai-teacher-SKILL.md` | 大模型原理、Prompt 工程、Agent、工具链、AI 伦理 |
| 费曼思维（反蒸馏） | `subjects/feynman-teacher-SKILL.md` | 反自欺、命名≠理解、具象化思考、深度游戏、科学思维 |

> v4.1 起，所有学科文件都带 `type: knowledge | methodology` 元数据和 5 步执行微流程；扩展学科时照抄 `_template-SKILL.md` 的格式即可。

## 扩展学科

复制模板创建新的学科子 Skill：

```bash
cp subjects/_template-SKILL.md subjects/your-subject-SKILL.md
```

编辑 `your-subject-SKILL.md`，填入学科特有的教学策略、常见误解和练习设计。欢迎 PR 贡献新学科！

---

## 常见问题

### 需要装 Python 吗？

只聊天不需要；HTML 课件、答题服务、掌握度引擎和进度脚本需要 Python 3.9+。

### 课件保存在哪里？

保存在你启动 AI 的工作区顶层的 `讲义/{课程}/`。例如：

```
讲义/计算机组成原理/unit-04-进位计数制.html
讲义/计算机组成原理/index.html
讲义/计算机组成原理/answers/latest.json
```

### 怎么提交答案？

DSH 上优先用插件：安装 [dsh-Teacher-skill](https://github.com/BTHawake/dsh-Teacher-skill) 后，课件挂在 `/teacher/`，直接在 DSH 同源页面作答、点“提交答案”；回聊天说“答好了”，AI 读取 `answers/latest.json`。

没有插件时再用独立服务：

```bash
python scripts/course_server.py --course "计算机组成原理" --port 8765
```

浏览器打开 `http://127.0.0.1:8765/`，作答后提交。两种方式都没有时，点“复制提交文本”发到聊天。

### 怎么复习？

打开 `讲义/{课程}/index.html`。到期项、薄弱知识点和 AI 建议都在首页；点进单元后答案默认折叠，先自己做再展开核对。

### 掌握度怎么算？

Lv0 未掌握 / Lv1 模糊 / Lv2 基本掌握 / Lv3 掌握。首轮检测通过记 Lv2；再通过一道换场景变式才升到 Lv3 并允许推进。

### 数据会上传吗？

不会。学习状态、课件、答题文件都在本地；`teachers/`、`讲义/`、`.dsh-meow/` 已在 `.gitignore` 中排除。

### 支持哪些资料？

PDF、TXT、Markdown、HTML、DOCX、EPUB。

---

## 注意事项

- ⚠️ 本 Skill 不替代专业教育。复杂学科建议结合正规课程使用。
- ⚠️ AI 可能产生知识幻觉。对关键信息建议回查原始资料。
- 所有教学数据仅本地存储，不会上传至任何服务器。
- 支持的资料格式：PDF、TXT、Markdown、HTML、DOCX、EPUB

---

## 社区生态

| 项目 | 描述 |
|------|------|
| [ex-skill](https://github.com/therealXiaomanChu/ex-skill) | 前任.skill — 灵感来源 |
| [colleague-skill](https://github.com/titanwings/colleague-skill) | 同事.skill — 职场关系蒸馏 |
| [awesome-persona-skills](https://github.com/tmstack/awesome-persona-skills) | 万物皆可 skill 合集 |
| [superpowers](https://github.com/obra/superpowers) | Claude Code 增强技能包 |

---

### 写在最后

教育的本质不是灌满一桶水，而是点燃一把火。

但现实中，大多数人的学习体验是：打开一本厚厚的教材，翻了两页就困了；看了一堆视频教程，关掉之后什么都没记住；问 AI 一个概念，它甩给你一段百科全书式的回答，看完更懵了。

这个 Skill 想做的事情很简单：**让 AI 像一个真正的好老师那样教你**。

不是因为它更聪明，而是因为它更有耐心。它会等你跟上，会换不同的方式解释同一个概念，会在你不懂的时候停下来而不是继续往下讲。它不假设你"应该知道"什么——因为好的老师从不这样。

如果你曾经因为"没人教"而放弃学某个东西，也许可以再试一次。
