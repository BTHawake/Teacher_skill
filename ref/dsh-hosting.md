---
name: dsh-hosting
description: >
  生成 HTML 课件后，先探测当前 Agent 的 Web 入口，再决定挂到 DSH
  插件、独立课程服务还是静态导出；最后发给用户可直接打开的链接。
version: 4.1.0
---

# DSH 宿主选择（v4.1）

> 目标：用户只收到一个**能直接打开的链接**，不需要自己判断端口、启动服务或拼 URL。
>
> 插件本体在独立仓库：`git@github.com:BTHawake/dsh-Teacher-skill.git`。
> 本 skill 只负责探测、决策和调用，不把插件代码复制进来。

---

## 1. 先探测，再决定

```bash
python scripts/dsh_host.py --course "计算机组成原理" \
  --workspace "TeacherSkillEditor" --json
```

输出里的 `mode` 就是决策：

| mode | 含义 | 下一步 |
|------|------|--------|
| `dsh-plugin` | DSH 已挂 `/teacher` 插件 | 用同源 `/teacher/api/answers`，发相对链接 |
| `dsh-plugin-missing` | DSH 可达，但插件没挂 | 判断是否安装；不装就用 `fallback` |
| `course-server` | 已有或可启动独立服务 | 启动/复用服务，发绝对 URL |

优先级固定：**DSH 插件 > 已有课程服务 > 新开本地端口**。

---

## 2. 模式 A：DSH 插件（远程 DSH 首选）

插件把课件挂到 DSH 自己的 Web 服务器：

```
DSH 3080
├── /                        DSH
├── /teacher/                讲义/ 静态课件
└── /teacher/api/answers     答题卡提交
```

### 安装（一次性，需用户同意）

```bash
git clone git@github.com:BTHawake/dsh-Teacher-skill.git
cd dsh-Teacher-skill
dsh plugin --profile web add "link:$PWD"
# 重启 dsh web
```

安装前先探测；**已经安装就不要重复装**。安装/重启会中断当前会话，必须先问用户，不能偷偷做。

### 配置

```yaml
- id: teacher-course
  name: dsh-teacher-skill
  config:
    workspaceRoot: 'D:\wake\HarnessWorkspace'
    token: ''
```

`workspaceRoot` 是课程工作区的父目录；URL 映射：

```
<workspaceRoot>/<workspace>/讲义/<course>/index.html
  → /teacher/<workspace>/<course>/index.html
```

### 生成课件

```bash
python scripts/lesson_html.py build --course "计算机组成原理" \
  --file "讲义/计算机组成原理/unit-04.md" \
  --state "teachers/计算机组成原理/learning-state.json" \
  --api-path "/teacher/api/answers" \
  --workspace "TeacherSkillEditor"
```

### 发给用户

优先发**根相对链接**，它会跟着用户当前 DSH 地址解析：

```markdown
[打开第 4 单元课件](/teacher/TeacherSkillEditor/计算机组成原理/unit-04-进位计数制.html)
```

如果知道完整地址，也可以发绝对 URL：

```
http://127.0.0.1:3080/teacher/TeacherSkillEditor/计算机组成原理/unit-04-进位计数制.html
```

远程 DSH 用 SSH 隧道/域名反代时，根相对链接不需要知道公网域名；绝对 URL 只在确认 Host 后使用。

---

## 3. 模式 B：独立课程服务

没有 DSH 插件，或用户拒绝安装时：

```bash
python scripts/course_server.py --course "计算机组成原理" --port 8765
```

生成时：

```bash
python scripts/lesson_html.py build ... --server-url "http://127.0.0.1:8765"
```

发给用户：

```markdown
[打开第 4 单元课件](http://127.0.0.1:8765/计算机组成原理/unit-04-进位计数制.html)
```

- 本机浏览器可直接打开
- 远程 DSH 需要把 8765 和 3080 一起转发；不能假装它可用
- 不启动服务时，答题卡走“复制提交文本”

---

## 4. 模式 C：静态导出

只想复习、不需要自动提交：

- 直接发 `讲义/...html` 文件路径（本地）
- 或上传到 GitHub Pages / Cloudflare Pages，发公网链接
- 答题卡只能用“复制提交文本”

---

## 5. 决策规则

1. 探测到 `dsh-plugin` → 直接用，不再起 8765
2. 在 DSH 上但没插件：
   - 用户长期用 DSH → 建议安装；说明需要重启一次
   - 用户拒绝/不能重启 → 回退 `course-server`
3. 不在 DSH → `course-server` 或静态导出
4. 已有 `course-server` 在跑 → 复用，不重复启动
5. 用户只说“打开/发我” → 不要回文件路径，先探测再发链接

### 不要做的事

- 不要把插件代码复制进 teacher_skill
- 不要在用户没同意时改 `~/.dsh` 或重启 DSH
- 不要把 `--host 0.0.0.0` 直接开到公网
- 不要发一个用户打不开的 `127.0.0.1` 链接却不说明远程转发

---

## 6. 安全

- 插件默认无登录，依赖 DSH 自身的访问控制/隧道
- 公网 DSH 必须设置插件 `token`，并在反代层加认证
- `answers/` 不通过静态路由暴露
- 答题文件只存学习数据，不存聊天原文/密钥

---

## 7. 排错

| 现象 | 检查 |
|------|------|
| `/teacher/api/health` 404 | 插件没装/没重启；看 `dsh plugin --profile web list` |
| 页面 404 | `workspaceRoot`、`workspace`、`course` 三层路径是否一致 |
| 答题 401 | 插件配置了 token，但生成时没带 `--api-token` |
| 链接能开但资源 404 | 确认访问的是 `/teacher/<workspace>/<course>/...`，不是 `/teacher/<course>/...` |
| 远程打不开 | 用根相对链接；或确认 DSH 反代也转发了 `/teacher` |
| 插件重复注册 | 重启 DSH；同一 id 只保留一份 |
