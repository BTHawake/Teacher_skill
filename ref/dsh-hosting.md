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
| `dsh-plugin-register-required` | 插件已装，但 workspace 没注册 | 先 `dsh_register.py`，再 build |
| `dsh-plugin-missing` | DSH 可达，但插件没挂 | 判断是否安装；不装就用 `fallback` |
| `course-server` | 已有或可启动独立服务 | 启动/复用服务，发绝对 URL |

输出还带 `temporary` 与 `recommended`：DSH 上缺插件时 `temporary=true`、`recommended=install-plugin`；正式插件模式为 `false`。

优先级固定：**DSH 插件 > 已有课程服务 > 新开本地端口**。

### 缺插件时：先提醒，不静默回退

`dsh-plugin-missing` 表示 DSH 可达但 `/teacher` 没挂。此时不要直接开 8765，先在聊天里说清楚：

> 检测到你在 DSH 上，但 `/teacher` 插件还没装。  
> 8765 只是临时回退，需要额外端口转发；装插件后链接直接跟着 DSH 域名走。  
> 要现在装吗？（安装需要重启一次 DSH）

- 用户确认后才安装；不装才用 `fallback`，并标注“临时链接”
- `fallback.temporary = true`；不要把临时方案说成正式方案
- 额外端口的定位：**临时/兼容模式**，不是 DSH 的推荐路径

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

新安装不写死任何机器路径：

```yaml
- id: teacher-course
  name: dsh-teacher-skill
  config:
    workspaceRoot: ''   # 可选，仅旧版单根 fallback
    registry: ''        # 默认 ~/.dsh/teacher-workspaces.json
    token: ''
```

映射：

```
<注册的 workspace root>/讲义/<course>/index.html
  → /teacher/<workspace>/<course>/index.html
```

### 注册 workspace（AI 自己判断）

AI 用 `pwd` 决定 workspace root，然后写注册表：

```bash
python scripts/dsh_register.py --workspace-root "$PWD" --workspace "<workspace>"
```

注册表：

```json
{"workspaces":{"操作系统":"D:\\wake\\HarnessWorkspace\\操作系统"}}
```

插件只服务注册过的根；没注册返回 503。旧版插件没有 `workspaces` 字段时，继续按 legacy `workspaceRoot` 工作。

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
[打开第 4 单元课件](/teacher/TeacherSkillEditor/计算机组成原理/unit-04.html)
```

远程 DSH 用 SSH 隧道/域名反代时，**根相对链接**不需要知道公网域名，浏览器会按当前地址解析。

如果必须发绝对 URL（例如远程 DSH 在子路径 `/dsh/`），不要用 `127.0.0.1`；给探测脚本传公网根地址：

```bash
python scripts/dsh_host.py --course "计算机组成原理" \
  --workspace "TeacherSkillEditor" \
  --public-base "https://dsh.example.com/dsh" --json
```

输出里的 `public_url` 才是远程可用的绝对地址；`local_url` 只用于本机调试。子路径场景还需要反代把 `/dsh/teacher/` 转到插件的 `/teacher/`。

答题卡会自动按 `location.pathname` 里的 `/teacher/` 前缀推导 API；所以 `/dsh/teacher/...` 会提交到 `/dsh/teacher/api/answers`，不需要手改 `--api-path`。

> `http://127.0.0.1:3080/...` 只对本机浏览器有效，**不要发给远程用户**。

### 发链接前验活

AI 自己识别 workspace 后，必须验文件 + 验 URL，不能只凭 build 成功就发链接：

```bash
python scripts/verify_page.py \
  --file "$PWD/讲义/计算机组成原理/unit-04.html" \
  --url "http://127.0.0.1:3080/teacher/TeacherSkillEditor/计算机组成原理/unit-04.html"
```

- `RESULT: PASS` 才发链接
- `FAIL` 先修路径/服务；浏览器工具可用时再截图确认不是空白页
- 独立 8765 模式把 URL 换成 `http://127.0.0.1:8765/...`

**`verify_page.py` 的边界：**

- 验：文件存在、非空、完整 HTML、HTTP 200、content-type、标题
- 不验：浏览器 JS 是否执行、是否白屏、远程域名/鉴权、答题 POST、插件 registry
- 浏览器渲染用 browser-skill 截图；答案提交换页面的提交按钮实测；registry 用 `dsh_host.py` 检查

### 网页里的“返回对话”

课件顶部栏有 `← 返回对话`，只在 DSH `/teacher/` 页面显示：

1. 新标签打开且 `window.opener` 可用 → 聚焦回聊天标签
2. 否则用同源 `document.referrer`（聊天页地址）
3. 否则回到 DSH 根路径：`/teacher/...` → `/`，`/dsh/teacher/...` → `/dsh/`

`file://` 或独立 `course_server` 页面不显示这个按钮，避免把课程目录误当聊天。

---

## 3. 模式 B：独立课程服务（临时回退）

没有 DSH 插件、或用户拒绝安装时，才用独立服务；这是**临时/兼容模式**，不是 DSH 推荐路径：

```bash
python scripts/course_server.py --course "计算机组成原理" --port 8765
```

生成时：

```bash
python scripts/lesson_html.py build ... --server-url "http://127.0.0.1:8765"
```

发给用户：

```markdown
[打开第 4 单元课件](http://127.0.0.1:8765/计算机组成原理/unit-04.html)
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
