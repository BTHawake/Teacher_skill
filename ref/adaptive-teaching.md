---
name: adaptive-teaching
description: >
  teacher.skill v4.1 自适应教学引擎：根据 HTML 答题卡提交与掌握度，
  决定补讲、继续练习、到期复习或推进下一单元。
version: 4.1.0
---

# 自适应教学引擎（v4.0）

> 目标：让 AI 老师不是"讲完就往前走"，而是根据用户真实做题表现调整下一步。
>
> 核心原则：**先诊断，再决定；不凭感觉推进，也不无限刷题。**
>
> v4.0：每一步决策都落成一个 HTML 页面（补讲/练习/复习/下一单元），而不是只在聊天里说。

## 1. 闭环

```
生成 HTML 课件
  ↓
用户阅读 + 做题（HTML 答题卡）
  ↓
提交到 answers/latest.json
  ↓
AI 读取 + 批改
  ↓
记录掌握度（mastery.py record）
  ↓
读建议（mastery.py advise）
  ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ 重讲          │ 继续练习      │ 到期复习      │ 推进下一单元  │
│ 补讲页 HTML   │ 练习页 HTML   │ 复习页 HTML   │ 下一单元 deck │
└──────────────┴──────────────┴──────────────┴──────────────┘
  ↓
更新 index + 掌握度
```

## 2. 掌握度等级

| 等级 | 标签 | 判定证据 | 默认动作 |
|------|------|---------|---------|
| 0 | 未掌握 | 答错、说不清、需要直接给答案 | 换一种讲法重讲，不刷题 |
| 1 | 模糊 | 部分正确、需要提示、能认但不能用 | 2 道针对性练习 |
| 2 | 基本掌握 | 首轮检测通过，但还没换场景验证 | 1 道变式题验证 |
| 3 | 掌握 | 首轮 + 变式都通过，复习仍能答对 | 推进 + 安排间隔复习 |

> **推进门槛（用户已确认）**：首轮检测通过 **且** 一道换场景变式题通过，才允许进入下一单元。
> 只做对一道原题不算掌握；只背出定义也不算。

### 证据记录

每次练习/检测后，调用：

```bash
python scripts/mastery.py record \
  --state "teachers/{课程}/learning-state.json" \
  --concept "位权展开" \
  --unit U4 \
  --kind first \
  --result pass \
  --note "首轮选择题全对"
```

- `--kind first`：首轮检测（讲完后的第一次检查）
- `--kind variant`：换场景变式（推进门槛）
- `--kind review`：到期复习
- `--kind practice`：普通练习/错题重做
- `--result pass|partial|fail`
- `--error` 可重复，记录错误类型（见第 7 节）
- `--complete-unit`：仅在 `first + variant` 都通过后使用，把单元标记为完成

## 3. 状态结构

脚本在原有 `learning-state.json` 上**增量**增加 `mastery` 字段，不破坏旧数据：

```json
{
  "mastery": {
    "version": "4.1.0",
    "concepts": {
      "位权展开": {
        "name": "位权展开",
        "unit": "U4",
        "level": 2,
        "status": "基本掌握",
        "attempts": 2,
        "correct_streak": 1,
        "review_count": 1,
        "last_result": "pass",
        "last_error": "",
        "error_tags": [],
        "next_review_at": "2026-10-29",
        "first_pass_at": "2026-10-28T10:30:00",
        "variant_passed": false,
        "variant_pass_at": "",
        "advance_ready": false,
        "history": [
          {"at": "2026-10-28T10:30:00", "result": "pass", "kind": "first", "level": 2}
        ]
      }
    },
    "next_action": {
      "type": "practice",
      "target": "位权展开",
      "unit": "U4",
      "mode": "variant",
      "reason": "首轮检测已通过，但还没换场景验证；先做 1 道变式题，通过后再推进。",
      "suggested_count": 1
    }
  }
}
```

`mastery` 与原有 `route` / `progress` / `review` 共存。旧状态文件无需迁移，脚本会自动补齐。

## 4. 决策规则

按以下顺序判断（先处理最近一次失败，再看复习，再看薄弱）：

| 顺序 | 条件 | 动作 | 理由 |
|------|------|------|------|
| 1 | 最近一次 `last_result=fail` | **reteach** | 错误概念刷题只会加固错误，先换讲法 |
| 2 | 最近一次 `last_result=partial` | **practice**（2 题） | 先分清是表达问题还是理解问题 |
| 3 | 有到期复习项 | **review**（最多 3 个，其余顺延） | 间隔重复优先，但设上限防止复习积压 |
| 4 | 有 Lv0/Lv1 | **reteach** | 没建立正确表征，先补概念 |
| 5 | Lv2 且未变式通过 | **practice（variant，1 题）** | 首轮通过不等于掌握，换场景验证 |
| 6 | 全部 Lv3 且 `advance_ready` | **advance** | 不浪费时间在已掌握内容上 |
| 7 | 有 Lv3 但未 `advance_ready` | **practice（variant）** | 补齐变式验证 |
| 8 | 没有任何记录 | **start** | 先完成一个单元的教学与检测 |

**动作要落成页面：**

| 建议 | 生成 |
|------|------|
| `reteach` | `reteach-XX-{薄弱点}.html`（换表征 + 2 道变式） |
| `practice` | `practice-XX-{主题}.html`（3 道针对性题） |
| `review` | `review-XX-{主题}.html`（快速回顾 + 1 道检测） |
| `advance` | 下一单元 `unit-XX-{标题}.html` |

脚本输出示例：

```bash
python scripts/mastery.py advise --state "teachers/{课程}/learning-state.json"
# 建议下一步：practice
# 目标：位权展开
# 理由：首轮检测已通过，但还没换场景验证；先做 1 道变式题，通过后再推进。
# 建议题量：1
```

> 建议是默认值，不是铁律。AI 可以基于上下文覆盖，但必须在回复中说明理由，并用 `record` 记录依据。

## 5. 复习调度

### 间隔

通过后按复习次数递增：

```
第 1 次通过 → 1 天后
第 2 次通过 → 3 天后
第 3 次通过 → 7 天后
第 4 次通过 → 14 天后
第 5 次及以后 → 30 天后
```

未通过/部分通过 → 次日复习，并立即安排重讲或针对性练习。

### 到期复习上限（用户已确认）

- 到期项 ≤5 个：本次一次处理完
- 到期项 >5 个：本次最多处理 **3 个**，其余明确告知"顺延到下次"
- 单个复习项 2-3 分钟：唤醒 → 1 道检测 → 更新间隔
- 复习通过：按间隔表推进；复习不通过：回到 reteach/practice，不直接背答案
- 不要因为复习积压而取消新内容；也不要在没复习完时假装"都复习过了"

## 6. 练习生成规则

默认 **3 题**，覆盖三种证据：

| 题号 | 类型 | 目的 |
|------|------|------|
| 1 | 概念辨析 / 正例反例 | 确认概念边界 |
| 2 | 应用 / 计算 | 确认能动手 |
| 3 | 换场景迁移 | 确认不是背例题 |

补充规则：

- 有错题时，优先出 **同型变式**，不要原题重做
- 同一概念连续 3 次未通过 → 停止加题，降级/拆更小/换表征（图、代码、生活例子）
- 练习必须给答案，答案用 `::: answer` 折叠
- 练习结果必须记录；不要只口头说"不错"
- 用户说"再来几道"时，用 `python scripts/mastery.py practice --count 3` 取目标，再生成

### 取练习目标

```bash
python scripts/mastery.py practice --state "teachers/{课程}/learning-state.json" --count 3
```

输出示例：

```json
[
  {
    "concept": "分组转换",
    "unit": "U4",
    "level": 0,
    "status": "未掌握",
    "needs_variant": true,
    "error_tags": ["概念混淆"],
    "question_types": ["概念辨析题", "正例/反例判断", "换场景变式题"]
  }
]
```

## 7. 错误类型标签

记录错误时使用统一标签，便于生成针对性练习：

| 标签 | 含义 | 对应练习 |
|------|------|---------|
| 概念混淆 | 把 A 当成 B / 边界不清 | 概念辨析、正例反例 |
| 步骤遗漏 | 会做但漏一步 | 过程排序、补全步骤 |
| 计算错误 | 思路对、算错 | 计算题、验算题 |
| 读题不完整 | 双分句只读一半 | 双分句拆解、找错题 |
| 表达不清 | 理解了但说不清 | 复述、给外行解释 |
| 迁移失败 | 原题会、换场景不会 | 变式题、应用题 |
| 记忆混淆 | 公式/名词记混 | 对比表、配对题 |

### 根据错误类型调整讲法

| 错误类型 | 重讲时怎么变 |
|---------|-------------|
| 概念混淆 | 用对比表/正反例把两个概念并排放，先让用户说区别 |
| 步骤遗漏 | 把过程拆成编号步骤，每一步配一个"为什么"；用代码/流程图 |
| 计算错误 | 放慢计算、先估算再精算、要求回代验算 |
| 读题不完整 | 教"选项拆分法"：双分句拆成两个独立命题分别判真假 |
| 表达不清 | 让用户用"给外行讲"的方式复述，AI 只补缺口 |
| 迁移失败 | 换 2-3 个场景做同型题，先给半提示再撤掉 |
| 记忆混淆 | 用间隔检索 + 对比表，不要求一次背完 |

> 同一错误连续出现 2 次，就换讲法；连续 3 次未通过，降级/拆更小，而不是继续重复原解释。

## 8. 自主权边界（用户已确认）

| 场景 | AI 自主权 |
|------|----------|
| 单元内：重讲、加练、出变式、换例子 | **自动决定**，不必每次问 |
| 推进下一单元 | 满足 `first + variant` 后自动推进；用户可随时叫停 |
| 跳单元 / 砍内容 / 改学习路线 / 换教材 | **先确认**，说明影响 |
| 用户说"直接讲下一个" | 尊重用户，但记录"跳过验证"，并在下次复习优先补 |
| 用户说"我懂了，别问了" | 停止检测，改为"讲完后给 1 道自愿题"；不要强行考试 |

## 9. 与 HTML 课件的配合

- 单元主课件：`讲义/{课程}/unit-XX-{标题}.html`（`kind: lesson`, `layout: deck`）
- 练习页：`practice-XX-{标题}.html`（`kind: practice`）
- 补讲页：`reteach-XX-{标题}.html`（`kind: reteach`）
- 复习页：`review-XX-{标题}.html`（`kind: review`）
- 答题卡提交：`answers/latest.json`
- `index.html` 显示：
  - 单元总数 / 已完成 / 待复习 / 薄弱知识点
  - 到期复习清单（最多展示 8 项）
  - 薄弱知识点（Lv0/Lv1）
  - AI 建议下一步（来自 `mastery.next_action`）
  - 主课件 / 练习 / 补讲 / 复习页列表，可筛选/搜索
- 答案默认折叠；打印时展开
- 掌握度变化后运行 `lesson_html.py index` 刷新目录即可，不必重建课件

### 用户说“答好了”时的最短路径

1. `cat "讲义/{课程}/answers/latest.json"`
2. 逐题对照答案 + 解析批改
3. `mastery.py record ...`
4. `mastery.py advise ...`
5. 生成对应的补讲/练习/复习/下一单元 HTML
6. 聊天只发链接 + 1-2 句导览

## 10. 维护与边界

- **不要伪造掌握度**：没有做题记录就是 Lv0，不要因为用户说"懂了"直接标 Lv3
- **不要无限练习**：3 次未通过必须换策略，而不是继续出同型题
- **不要跳过诊断**：自适应只在有基线后进行；新用户仍走 Phase 1
- **不要泄露隐私**：状态文件只存学习数据，不存聊天原文/密钥
- **定期归档**：`history` 只保留最近 20 条/概念；长期数据可另存
- 状态文件建议随工作区备份；损坏时脚本会清洗/重建，不会删除讲义

## 11. 快速命令

```bash
# 初始化
python scripts/mastery.py init --state teachers/demo/learning-state.json --name demo

# 记录首轮检测
python scripts/mastery.py record --state ... --concept "位权" --unit U4 --kind first --result pass

# 记录变式
python scripts/mastery.py record --state ... --concept "位权" --unit U4 --kind variant --result pass --complete-unit --unit-title "进位计数制"

# 看建议 / 到期 / 薄弱
python scripts/mastery.py advise --state ...
python scripts/mastery.py due --state ...
python scripts/mastery.py show --state ...

# 取练习目标
python scripts/mastery.py practice --state ... --count 3
```
