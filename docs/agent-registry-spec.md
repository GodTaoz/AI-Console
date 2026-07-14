# AI-Console 智能体会话注册与运行观测技术规格

## 1. 产品定位

智能体注册中心是 AI-Console 的一个运行资源域，用于登记、发现和观测本机 Hermes、Codex 及其子智能体会话，并提供类型化的恢复入口描述。

第一版名称为“智能体会话注册与运行观测模块”，不是完整 Agent Control Plane。它与主机、容器、AI 额度、网络存储处于同一信息层级；总览最多展示少量智能体摘要，详细信息集中在“智能体”页面。

模块保持单机、自托管和本地优先，不改变 AI-Console 的核心定位。没有真实注册数据时显示空状态，不伪造会话或任务。

## 2. 第一版范围

Phase 1 Registry MVP 包含：

- 稳定智能体身份 `agents` 与具体运行会话 `agent_sessions`。
- 会话幂等注册、心跳、状态更新、结束、列表、详情、父子树和 entry 描述 API。
- `agentctl` CLI：`register`、`heartbeat`、`list`、`tree`、`show`、`enter`、`finish`。
- Web 智能体页面：会话列表、状态筛选、运行时筛选、列表/树切换、空状态和复制 `agentctl enter` 命令。
- 基于最后心跳时间派生 `lost` 状态，默认阈值 180 秒。
- Hermes、Codex、tmux、process、cron/job 的类型化 entry 数据模型和能力声明。
- 本机 `agentctl bootstrap-local` 安全读取 Codex `session_index.jsonl`，完成最小发现和周期刷新。
- 本机 `agentctl discover-hermes` 使用固定 `hermes sessions list` 参数发现 Telegram/CLI 会话元数据。

Phase 1 非目标：

- 跨智能体消息路由、共享记忆或完整对话同步。
- Web 页面直接接管终端或执行恢复命令。
- 服务端执行客户端上报的任意 Shell 命令。
- 远程 kill、restart、stop、容器控制或主机修复。
- 多主机注册、分布式一致性、图数据库和事件溯源。
- 多租户、复杂 RBAC、插件市场或工作流编排。
- 自动扫描并导入所有 tmux、进程和 cron；常驻托管与广义自动发现属于 Phase 2。

## 3. 模块边界

后端使用独立模块，不放入 `collectors`：

```text
src/qingluo_console/agent_registry/
  __init__.py
  models.py
  repository.py
  service.py
  api.py
  cli.py
  carriers.py
```

- `models.py`：生命周期、请求、响应和 entry 类型。
- `repository.py`：参数化 SQLite 读写，不包含 HTTP 或 CLI 逻辑。
- `service.py`：幂等注册、状态派生、树构建、安全清洗和 entry 能力。
- `api.py`：FastAPI router，仅负责请求绑定和错误映射。
- `cli.py`：HTTP 客户端，不直接访问 SQLite。
- `carriers.py`：宿主侧固定只读 tmux/process/cron observation，不接受客户端命令。

Phase 1 复用 AI-Console SQLite 文件。注册写入只允许保存运行元数据，不构成系统控制能力。

## 4. 数据模型

### 4.1 agents

`agents` 表表示稳定智能体身份，同一个 Hermes 或 Codex 身份可以拥有多个会话。

| 字段 | 类型 | 约束与含义 |
|---|---|---|
| `agent_id` | TEXT | 主键；调用方稳定 ID，最长 128 字符 |
| `display_name` | TEXT | 用户可识别名称，最长 120 字符 |
| `runtime` | TEXT | `hermes`、`codex`、`generic` 等运行时 |
| `purpose` | TEXT | 智能体长期职责，最长 500 字符 |
| `tags_json` | TEXT | 短标签数组，不保存提示词或凭据 |
| `created_at` | TEXT | UTC ISO 8601 |
| `updated_at` | TEXT | UTC ISO 8601 |

### 4.2 agent_sessions

`agent_sessions` 表表示一次具体对话、子智能体执行或后台任务运行。

| 字段 | 类型 | 约束与含义 |
|---|---|---|
| `session_id` | TEXT | 主键；注册中心会话 ID，最长 128 字符 |
| `agent_id` | TEXT | 对应 `agents.agent_id` |
| `external_session_id` | TEXT | Hermes/Codex 原生会话 ID，可为空 |
| `parent_session_id` | TEXT | 父会话 ID；顶层会话为空 |
| `kind` | TEXT | `interactive`、`subagent`、`job_run` |
| `purpose` | TEXT | 本次会话任务摘要，最长 500 字符 |
| `status` | TEXT | 显式生命周期状态 |
| `registration_source` | TEXT | `self_reported` 或 `discovered` |
| `workspace_id` | TEXT | 工作区别名；不保存或展示敏感绝对路径 |
| `entry_type` | TEXT | 类型化入口类型 |
| `entry_data_json` | TEXT | 经过白名单校验的入口参数 |
| `metadata_json` | TEXT | 递归脱敏后的少量扩展元数据 |
| `started_at` | TEXT | 开始时间 |
| `last_seen_at` | TEXT | 最近注册、心跳或状态更新时间 |
| `ended_at` | TEXT | 完成或失败时间，可为空 |
| `created_at` | TEXT | 记录创建时间 |
| `updated_at` | TEXT | 记录更新时间 |

Phase 2 增加 `status_changed_at`、`carrier_status`、`carrier_observed_at` 和 `carrier_details_json`。carrier 状态为 `not_applicable / available / missing / mismatch / unknown / unsupported`，只表达 entry/execution carrier 是否仍可验证，不把 tmux、PID 或 cron 当成智能体身份。

`agent_discovery_status` 保存发现源、最近扫描结果、扫描周期和发现数量，不保存宿主路径、环境变量或凭据。服务端根据最近扫描时间派生 `running / stale / error`。

### 4.3 agent_audit_events

Phase 3 审计表仅保存 `id / action / session_id / result / source / created_at`。不保存 inspect 输出、resume 命令、消息正文、metadata、对话或凭据。

### 4.4 agent_messages

Phase 4 使用单机 SQLite inbox：`message_id / from_session_id / to_session_id / message_type / body / status / created_at / read_at / acked_at / expires_at / metadata_json`。正文最长 2000 字符，metadata 最大 4 KiB，并在写入前脱敏。状态为 `unread / read / acked / expired`。

索引：

- `(status, last_seen_at)`：状态筛选和失联判断。
- `(agent_id, updated_at)`：按智能体查询。
- `(parent_session_id)`：构建父子树。
- `(agent_id, external_session_id)`：同一运行时身份下定位原生会话。

注册使用 `session_id` 幂等 upsert，同时 upsert 对应 `agent`。父会话可以稍后注册，Phase 1 不使用严格父外键阻塞子会话写入。

## 5. 生命周期状态

状态枚举独立于基础设施健康状态：

| 状态 | 含义 |
|---|---|
| `starting` | 会话已创建，尚未进入稳定运行 |
| `active` | 正在执行或持续对话 |
| `idle` | 可恢复但当前没有执行任务 |
| `waiting` | 等待用户、工具、资源或上游响应 |
| `completed` | 正常结束 |
| `failed` | 明确失败 |
| `lost` | 本应活动但心跳超过阈值 |
| `unknown` | 无法判断 |

`starting`、`active`、`idle`、`waiting` 在 `last_seen_at` 超过 `QINGLUO_AGENT_LOST_AFTER_SECONDS` 后，查询结果派生为 `lost`。派生状态不覆盖数据库中的最后显式状态；新的 heartbeat 可以恢复为请求中指定状态，默认恢复为 `active`。

`completed` 和 `failed` 是终态，不因心跳超时变成 `lost`。`finish` 默认写入 `completed`，也允许明确指定 `failed`。

## 6. Entry 类型与安全校验

Entry 是结构化恢复描述，不是 Shell 字符串：

```json
{
  "type": "codex_session",
  "data": {
    "session_id": "codex-thread-id"
  },
  "capabilities": {
    "inspect": true,
    "resume_hint": true,
    "message_inbox": true,
    "ack_message": true
  }
}
```

Phase 1 白名单：

| entry type | 允许字段 | Phase 1 行为 |
|---|---|---|
| `none` | 无 | 仅观测，不可进入 |
| `hermes_session` | `session_id` | 返回 Hermes 会话标识；实际恢复适配器待能力验证 |
| `codex_session` | `session_id` | 返回 Codex 会话标识；实际恢复适配器待能力验证 |
| `tmux` | `target` | 仅返回 carrier 检查信息，不提供 attach/resume hint |
| `process` | `pid`、`start_time` | 仅 inspect，不声称可恢复对话 |
| `cron_job` | `job_id` | 展示任务标识，不直接执行任务 |

服务端拒绝 `command`、`shell`、`argv`、`env`、`token`、`password`、`secret` 等字段。Web 只复制固定格式的 `agentctl enter <session_id>`，不拼接客户端命令。

## 7. API 设计

协议从第一版使用 `/api/v1`：

| 方法 | 路径 | 行为 |
|---|---|---|
| `PUT` | `/api/v1/agent-sessions/{session_id}` | 幂等注册或更新 agent/session |
| `POST` | `/api/v1/agent-sessions/{session_id}/heartbeat` | 更新最后心跳和可选状态 |
| `PATCH` | `/api/v1/agent-sessions/{session_id}/status` | 更新生命周期状态和可选结束时间 |
| `GET` | `/api/v1/agent-sessions` | 列表；支持 `status`、`runtime`、`agent_id`、`limit` |
| `GET` | `/api/v1/agent-sessions/{session_id}` | 会话详情 |
| `GET` | `/api/v1/agent-sessions/{session_id}/entry` | 类型化 entry、能力和固定 CLI 命令 |
| `GET` | `/api/v1/agent-tree` | 按 `parent_session_id` 返回森林结构 |
| `PUT` | `/api/v1/agent-sessions/{session_id}/observation` | 写入类型化 carrier observation |
| `PUT` | `/api/v1/agent-discovery/{source_id}` | watcher 上报扫描结果 |
| `GET` | `/api/v1/agent-discovery` | 查询发现器状态 |
| `GET` | `/api/v1/agent-sessions/{session_id}/inspect` | 安全摘要、能力与建议命令 |
| `GET` | `/api/v1/agent-sessions/{session_id}/resume-hint` | 白名单恢复提示，`executes=false` |
| `GET` | `/api/v1/agent-audit` | 最近审计事件，可按 session 过滤 |
| `POST` | `/api/v1/agent-sessions/{session_id}/messages` | 发送一条 inbox 消息 |
| `GET` | `/api/v1/agent-sessions/{session_id}/messages` | 查询消息并将 unread 标记为 read |
| `POST` | `/api/v1/agent-messages/{message_id}/ack` | 将消息标记为 acked |

注册请求包含：

```json
{
  "agent": {
    "agent_id": "hermes-main",
    "display_name": "Hermes",
    "runtime": "hermes",
    "purpose": "主智能体",
    "tags": ["primary"]
  },
  "external_session_id": "hermes-session-123",
  "parent_session_id": null,
  "kind": "interactive",
  "purpose": "规划 AI-Console 智能体注册中心",
  "status": "active",
  "workspace_id": "ai-console",
  "entry": {
    "type": "hermes_session",
    "data": {"session_id": "hermes-session-123"}
  },
  "metadata": {}
}
```

错误语义：

- 非法 ID、状态、entry 或字段长度返回 `422`。
- 不存在的 session 返回 `404`。
- 数据库冲突或内部异常不直接暴露原始异常文本。
- 所有输出继续应用敏感字段脱敏。

Phase 1 依赖当前 loopback 单用户部署边界。若 API 暴露到 loopback 之外，必须先增加独立注册令牌；不会复用 CPA 管理凭据。

## 8. agentctl CLI

安装项目后提供 `agentctl` console entry point。CLI 默认访问 `http://127.0.0.1:8010`，可由 `QINGLUO_AGENT_REGISTRY_URL` 覆盖。

```text
agentctl register --runtime codex --external-session-id ... --purpose ...
agentctl heartbeat SESSION_ID [--status active]
agentctl heartbeat SESSION_ID --watch --interval 60
agentctl bootstrap-local [--thread-name ai-console] [--watch --interval 60]
agentctl discover [同 bootstrap-local]
agentctl discover-hermes [--source telegram] [--source cli] [--limit 20]
agentctl reconcile-local [--proc-root /proc]
agentctl inspect SESSION_ID
agentctl resume SESSION_ID
agentctl audit [--session-id SESSION_ID]
agentctl message send SESSION_ID --body ... [--type note|task|status]
agentctl message list SESSION_ID
agentctl message ack MESSAGE_ID
agentctl list [--status active] [--runtime codex] [--json]
agentctl tree [--json]
agentctl show SESSION_ID [--json]
agentctl enter SESSION_ID
agentctl finish SESSION_ID [--failed]
```

- CLI 使用标准 HTTP API，不直接读写数据库。
- `register` 支持父会话、原生会话 ID、kind、workspace、entry type 和 entry data。
- `register` 对 Codex/Hermes 可根据 runtime 和原生会话 ID 推导本地 agent/session/entry 默认值，来源为 `self_reported`。
- `bootstrap-local` 只读取 Codex 会话索引的 `id`、`thread_name`、`updated_at`，来源为 `discovered`；不会读取 `history.jsonl`、prompt 或完整对话。
- `discover-hermes` 默认扫描 `telegram` 和 `cli`，每个来源最多 20 条；只调用 `hermes sessions list`，不调用 export，不读取完整对话或凭据。
- Hermes Preview 仅用于解析 CLI 表格，不写入 session purpose 或 metadata。注册中心只保存 ID、Title、source 和 Last Active；无标题时使用不包含 Preview 的安全回退名称。
- Hermes 发现拒绝 `source=cron`，过滤 `cron_` ID 及明确的旧进度跟踪/汇报定时标题，不注册 cron job run。
- Hermes 历史列表记录使用 `liveness_mode=discovery`，不参与 heartbeat 超时派生；发现器中断由 discovery source 的 `stale/error` 表达，避免历史会话产生虚假 lost 告警。
- Telegram 与 CLI 按来源独立扫描、注册和上报结果；一个来源失败不得丢弃另一个来源的成功结果，也不得覆盖 `codex-local` 状态。
- `bootstrap-local` 默认不包含 Hermes；添加 `--include-hermes` 后才在 watcher 循环中刷新 Hermes。项目 systemd user unit 显式开启该选项并将每来源 limit 固定为 20。
- `bootstrap-local --watch` 和 `heartbeat --watch` 以最短 5 秒、默认 60 秒的间隔持续刷新，Ctrl+C 可安全停止。
- 每轮 bootstrap 会上报 discovery 状态并执行本地 carrier 对账；`--no-reconcile` 可明确关闭 carrier 检查。
- `reconcile-local` 仅使用固定 tmux 查询和只读 procfs；不执行 entry 中的命令，也不读取进程命令参数或环境变量。
- `list` 默认输出紧凑表格；`--json` 输出完整 JSON。
- `enter` 查询 entry 后输出可执行建议和原生会话标识。Phase 1 不自动执行 Hermes/Codex/tmux 命令，避免未验证适配器造成错误接管。
- 网络、非 2xx 和 JSON 错误返回非零退出码，错误正文保持产品化。
- `inspect` 仅显示 runtime、外部 session ID、用途、状态、心跳、entry/carrier、能力和固定建议命令。
- `resume` 只打印 Codex `codex resume ID` 或 Hermes `hermes --resume ID` 模板；服务端和 CLI 均不执行。
- `message` 只操作 AI-Console SQLite inbox，不自动投递到模型上下文，不触发工具执行。

## 9. Web 页面

Sidebar 只保留一个智能体入口；模块内部使用 `/agents` 会话工作区和 `/agents/status` 状态监控两个视图。页面包含：

- 状态页摘要：活动、空闲、等待、失败/失联会话数量。
- 状态筛选和运行时筛选。
- 列表视图：名称、用途、运行时、状态、父会话、最近心跳、entry 能力。
- 树视图：按 `parent_session_id` 缩进展示父子关系，孤儿节点作为根节点并明确标记。
- 详情入口：至少展示 session ID、agent ID 和类型化 entry。
- 固定命令复制：`agentctl enter <session_id>`。
- 查看命令复制：`agentctl show <session_id>`；来源以低干扰标签展示。
- 加载、网络错误、无数据和筛选无结果状态。
- 状态页展示发现器运行状态、最后扫描时间、发现数量和 Runtime Bridge 连接；等待、失联、失败行使用风险提示。
- Phase 3/4 使用详情弹层展示 capability、inspect 摘要、恢复提示、未读消息、发送与 ack；不嵌入终端。

第一版不在网页中打开终端、不执行 attach/resume、不展示完整对话内容。总览暂不加入智能体摘要，避免在数据接入初期改变现有信息层级。

## 10. 适配器能力矩阵

| 类型 | 注册来源 | 父子关系 | 心跳 | Phase 1 enter | 后续能力 |
|---|---|---|---|---|---|
| Hermes session | 主动注册或 `sessions list` 元数据发现 | 支持 | 宿主 watcher 可选刷新 | 展示白名单 resume hint | 仅 Telegram/CLI；过滤 cron，不读取正文 |
| Codex session | 主动注册或本机索引发现 | 支持 | CLI heartbeat/bootstrap watch | 展示 thread/session ID | 验证 Codex resume 后接入 |
| Codex 子智能体 | 创建方传 `parent_session_id` | 支持 | 子智能体或父会话代理 | 取决于是否有独立 session ID | 自动注册 hook |
| tmux | 手动绑定 entry | 作为 entry binding | watcher 固定 `list-panes` 对账 | 仅 available 时声明可恢复 | 不扫描或创建智能体 |
| process | 手动绑定 PID + start time | 不推断 | watcher 只读 `/proc/PID/stat` | 仅 inspect | PID 重用返回 mismatch |
| cron/job | job/run 主动注册 | job run 可挂父任务 | 当前返回 unsupported | 展示 job ID | 等待稳定 Hermes job index，不读取 crontab |

“进程存在”不等于“会话可恢复”；能力由 entry 类型和已验证适配器决定。

## 11. 安全与隐私边界

- 仅保存会话索引和运行元数据，不保存完整 prompt、对话、工具输出或模型上下文。
- 不保存 token、Cookie、API key、密码、环境变量、OAuth 凭据和连接串。
- 不保存客户端上报的任意命令行；entry 字段严格白名单。
- `workspace_id` 使用别名，不通过 API/UI 暴露敏感绝对路径。
- `metadata` 递归脱敏并限制结构大小。
- API/SQLite 错误转换为稳定错误，不返回内部路径或 SQL 文本。
- 不提供 stop、kill、restart、remote exec；Phase 4 message 仅是显式 SQLite inbox，不会执行或注入上下文。
- 注册数据不参与当前主机、容器、额度的聚合健康状态。

## 12. 分阶段路线

### Phase 0：能力验证

- 验证 Hermes 创建、恢复、子会话和 heartbeat 接入点。
- 验证 Codex session/thread、resume 和子智能体标识。
- 记录每个适配器的 `inspect/resume_hint/message_inbox/ack_message` 真实能力。

### Phase 1：Registry MVP

- 本规格定义的 SQLite、repository/service/API、agentctl 和 Web 页面。
- 主动注册、心跳、状态派生和父子树。
- 提供显式启动的 Codex 本机索引发现；不实现常驻自动发现、告警联动和实际终端接管。

### Phase 2：扩展自动发现与告警

- 提供仓库内 systemd user unit，宿主侧持续运行 `agentctl bootstrap-local --watch`，避免容器挂载用户 Home 或 tmux socket。
- systemd unit 显式增加 `--include-hermes --hermes-source telegram --hermes-source cli --hermes-limit 20`；普通 `bootstrap-local` 默认保持 Codex-only。
- watcher 上报 discovery 状态，并对 tmux、process 和 cron carrier 做类型化只读 observation。
- `lost`、`failed` 和长期 `waiting` 接入现有 `alert_events`；fingerprint 按 session/status 去重，恢复后标记 resolved。
- 默认 lost 阈值 180 秒，waiting 告警阈值 1800 秒。failed 为 critical，lost/waiting 为 warning。
- cron 因缺少稳定、安全的 Hermes job index 仅实现接口、unsupported 状态和测试边界。
- 总览摘要仍暂缓，避免智能体域抢占主机、容器和额度层级。

### Phase 3：有限控制

- 已实现 adapter capability：`inspect / resume_hint / message_inbox / ack_message`。
- Codex/Hermes 支持 inspect、resume hint 和 inbox；tmux/process/cron 仅 inspect。
- 已实现白名单 resume hint 和轻量审计；没有真实 resume、stop、kill 或任意客户端命令。

### Phase 4：消息路由

- 已实现最小单机 inbox、read/ack/expiry 状态和 CLI/Web 操作。
- 消息不会自动进入 Hermes/Codex 上下文；智能体需要主动查询 inbox。
- 未实现发布订阅、广播、保证投递、重试队列、跨主机或复杂消息基础设施。

### Phase 5：统一会话工作区

- 新增宿主侧 `agent-runtime-bridge` systemd user service，通过 Unix Socket 与容器通信；容器不挂载整个 Hermes/Codex 用户目录。
- Codex 使用 `codex app-server` 的 `thread/read`、`turn/start`、`turn/interrupt`、审批和 `thread/delete`；不启动 TUI。
- Hermes 使用本机 stdio JSON-RPC gateway 的 `session.resume`、`session.history`、`prompt.submit`、`session.interrupt`、`approval.respond` 和 `session.delete`，不向容器暴露 Dashboard token 或端口。
- 历史只按需返回 user/assistant 可见文本及工具名称、状态、时间；不返回 system/developer prompt、reasoning、工具参数、完整输出、token、环境变量、渠道用户标识或运行时凭据。
- AI-Console SQLite 只保存归档/删除标记、运行操作状态和轻量审计，不复制 prompt、回复正文或完整历史。
- 页面续聊沿用原会话权限，不设置 `approvalPolicy`、`sandboxPolicy` 或 Hermes 自动批准模式；审批必须由用户显式允许或拒绝。
- 模型列表直接来自 Codex `model/list` 或 Hermes `model.options`；选择只传递白名单模型 ID，不允许网页提交 provider endpoint、API key 或自定义启动参数。
- 图片和文件附件通过 base64 传给 Bridge，最多 5 个、单个 10 MB、总计 20 MB。Codex 使用 `localImage`/`mention`，Hermes 使用 `image.attach_bytes`/`file.attach`；临时文件在 turn 完成后清理，不进入 AI-Console SQLite。
- 会话重命名使用 Codex `thread/name/set` 或 Hermes `session.title`，成功后同步更新本地 session purpose。
- 桌面端会话列表可以拖动、完全折叠并在 LocalStorage 保存偏好；移动端使用抽屉。发现器的三个 source 在独立状态页明确展示。
- SSE 使用类型化 `phase` 事件表达 `thinking / tool_running / waiting_approval / responding` 和安全工具名。页面只显示阶段及耗时，不返回、推断或持久化隐藏 reasoning 正文。
- 会话正文使用禁用原始 HTML 的安全 Markdown 渲染；危险链接协议不会生成可点击链接。
- “任务投递”继续作为独立 inbox，不与源历史混合，用户页面不再代替智能体执行 ack。
- 归档是 AI-Console 本地软隐藏；永久删除必须匹配完整 external session ID，成功后保留最小 tombstone 防止 watcher 重新导入。

## 13. 验证计划

后端测试：

- schema 初始化、幂等注册、agent upsert 和父子关系。
- heartbeat、显式状态更新、终态和失联状态派生。
- 正常、缺失、非法状态、非法 entry、敏感 metadata 嵌套结构。
- 列表筛选、详情、树、孤儿节点和 entry 响应。
- API `200/404/422` 契约及 SPA fallback 路由顺序。

CLI 测试：

- 参数解析、请求方法与 URL。
- 表格和 JSON 输出。
- register/heartbeat/finish 请求体。
- Codex 索引安全解析、bootstrap 筛选、来源标记和持续模式参数。
- enter 对不同 entry 类型的安全输出。
- 网络错误、非 2xx 和非法 JSON 的退出码。

前端验证：

- TypeScript contract、i18n 中英文键一致。
- 列表、树、状态/运行时筛选、复制命令和空状态。
- 长 ID、孤儿节点、窄屏、暗色/亮色/柔和主题。
- `npm run type-check` 和 `npm run build`。

完成验证：

```bash
uv run pytest -q
cd web && npm run type-check && npm run build
docker compose config
docker compose build
docker compose up -d
curl -fsS http://127.0.0.1:8010/health
```
