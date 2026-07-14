# AI-Console

单机自托管 AI 工作站的运行健康与额度预警中心。当前目标部署在 ThinkPad 本机，仅监听 loopback。

## 当前能力

- 定时采集主机资源、Docker 服务和 CPA / Codex 额度。
- 主机 CPU、磁盘/网络吞吐、系统信息与进程资源排行。
- UFW 状态、允许规则以及宿主机 TCP / UDP 监听端口。
- SQLite latest snapshot、指标样本、采集批次和告警恢复记录。
- CPU、内存、网络和磁盘吞吐的 24 小时五分钟聚合趋势。
- 总览、主机、容器、AI 额度、网络存储和告警页面。
- 响应式数据看板，支持跟随系统、明亮、柔和、暗色四种主题。
- 图标式主题与语言菜单，支持简体中文和 English，并保存本地偏好。
- 数据时效标记、统一脱敏和只读 Docker API proxy。
- 本机 Hermes / Codex 会话注册、只读元数据发现、心跳、失联判定和父子关系观测。
- Hermes / Codex 统一会话工作区：按需查看安全历史、继续真实会话、处理审批、归档和强确认源删除。

## 技术规格

项目技术规格说明书见：[`docs/technical-spec.md`](docs/technical-spec.md)。智能体会话注册模块规格见：[`docs/agent-registry-spec.md`](docs/agent-registry-spec.md)。

## 本地开发

```bash
uv run pytest -q
uv run uvicorn qingluo_console.main:app --host 127.0.0.1 --port 8010
```

注册本机最新 Codex 会话并查看结果：

```bash
uv run agentctl bootstrap-local --thread-name ai-console
uv run agentctl list
uv run agentctl tree
```

持续刷新已发现的 Codex 会话：

```bash
uv run agentctl bootstrap-local --thread-name ai-console --watch --interval 60
```

只读发现本机 Hermes Telegram/CLI 会话：

```bash
uv run agentctl discover-hermes --source telegram --source cli --limit 20
```

该命令仅调用 `hermes sessions list` 并解析列表元数据，不调用 `sessions export`，不读取完整对话、token、环境变量或凭据。Preview 仅用于解析列表格式，不写入注册中心；`cron_` ID、`source=cron` 和明确的旧进度跟踪定时会话会被过滤。
Hermes `sessions list` 是历史索引而不是心跳源，因此这类 discovered 会话不会因未再次进入 top-N 而派生为 `lost`；watcher 健康由 `hermes-telegram`、`hermes-cli` discovery source 独立表达，单个来源失败不会影响另一个来源或 `codex-local`。


长期运行建议将 `agentctl` 安装为 uv tool，并启用项目提供的 systemd user unit：

```bash
uv tool install --force --reinstall --refresh-package ai-console .
mkdir -p ~/.config/ai-console ~/.config/systemd/user
printf 'QINGLUO_AGENT_THREAD_NAME=ai-console\nQINGLUO_AGENT_SESSION_PURPOSE=AI-Console implementation session\n' > ~/.config/ai-console/agent-watcher.env
install -m 0644 deploy/systemd/ai-console-agent-watcher.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ai-console-agent-watcher.service
```

查看、停止和重新启动：

```bash
systemctl --user status ai-console-agent-watcher.service
systemctl --user stop ai-console-agent-watcher.service
systemctl --user start ai-console-agent-watcher.service
journalctl --user -u ai-console-agent-watcher.service
```

项目提供的 systemd unit 显式启用 Hermes 发现，每个 `telegram`、`cli` 来源最多读取 20 条，同时刷新 Codex 索引。CLI 的 `bootstrap-local` 默认仍只发现 Codex，只有添加 `--include-hermes` 才会接入 Hermes，避免普通命令意外导入历史会话。

watcher 每轮还会运行 `agentctl reconcile-local` 的等价流程，只读检查已注册的 tmux、process 和 cron carrier。tmux 使用固定 `list-panes` 查询；process 使用 `/proc/PID/stat` 的 start time 防止 PID 重用误判；cron 当前明确显示“不支持”，不会读取或执行用户 crontab。

Hermes 在取得自身 session ID 后使用主动注册方式：

```bash
uv run agentctl register --runtime hermes --external-session-id SESSION_ID --purpose "Hermes 主会话"
uv run agentctl heartbeat hermes-SESSION_ID --status active
```

Codex 发现只读取 `$CODEX_HOME/session_index.jsonl`（默认 `~/.codex/session_index.jsonl`）中的会话 ID、名称和更新时间，不读取 `history.jsonl` 或对话内容。Hermes 发现使用固定的 `hermes sessions list --source telegram|cli --limit N` 参数，只保存 ID、标题、来源和 Last Active。

智能体告警规则：失联和长期等待为 warning，明确失败为 critical；默认等待阈值为 1800 秒，可通过 `QINGLUO_AGENT_WAITING_ALERT_SECONDS` 调整。同一会话同一状态使用固定 fingerprint 去重，恢复后保留已解决记录。

安全查看、恢复提示和审计：

```bash
agentctl inspect SESSION_ID
agentctl resume SESSION_ID
agentctl audit --session-id SESSION_ID
```

`resume` 只打印由 Codex/Hermes adapter 白名单模板生成的提示，不执行命令。inspect、resume hint 和消息操作会记录 action、session、result、source 和时间，不记录消息正文、对话、token 或环境变量。

单机消息收件箱：

```bash
agentctl message send SESSION_ID --type task --body "继续检查 AI-Console"
agentctl message list SESSION_ID
agentctl message ack MESSAGE_ID
```

消息正文最多 2000 字符，敏感键和值模式会在持久化前脱敏。消息仅是本机 SQLite 元数据，不会自动注入 Codex/Hermes 上下文，也不会触发工具或命令执行。

### 真实会话工作区

历史读取和续聊通过宿主侧 Agent Runtime Bridge 完成。AI-Console 容器不挂载整个 `~/.codex` 或 `~/.hermes`，只挂载 Bridge 的 Unix Socket 和 capability token 文件。

```bash
uv tool install --force --reinstall --refresh-package ai-console .
mkdir -p ~/.config/ai-console ~/.config/systemd/user ~/.local/state/ai-console
install -m 0644 deploy/systemd/ai-console-agent-runtime-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ai-console-agent-runtime-bridge.service
systemctl --user status ai-console-agent-runtime-bridge.service
```

在 `.env` 中将 `QINGLUO_AGENT_BRIDGE_DIR` 设置为宿主机的 `~/.local/state/ai-console` 绝对路径，然后重新创建容器。Codex adapter 使用固定的 `codex app-server --stdio` 协议，不修改原会话权限。

Hermes adapter 使用本机 Hermes 安装目录中的 stdio JSON-RPC gateway，不需要向容器暴露端口或 Dashboard token。Bridge 只发送固定白名单方法，不接受网页提交的 shell、argv 或环境变量。

`/agents` 是默认会话工作区，`/agents/status` 展示活动、空闲、等待、失败/失联会话数量以及发现器和 Runtime Bridge 状态。两者通过智能体模块内部导航切换，不增加主侧边栏入口。

会话工作区读取源历史并直接提交新 turn；支持选择运行时实际提供的模型、修改源会话名称，以及发送图片或文件附件。附件一次最多 5 个、单个 10 MB、合计 20 MB，只在 Bridge 临时目录中保存到当前 turn 结束。“任务投递”仍是独立 SQLite inbox，不会自动进入智能体上下文。归档仅在 AI-Console 本地隐藏，可恢复；永久删除要求输入完整外部 Session ID，并调用运行时的源删除接口。

状态页会明确列出 `codex-local`、`hermes-cli`、`hermes-telegram` 等发现源。桌面端会话列表可拖动调整宽度或完全折叠，偏好保存在浏览器 LocalStorage；移动端使用抽屉选择会话。删除成功后页面立即从本地列表移除会话，再从 API 对账刷新。

实时 turn 只显示“正在思考、正在调用工具、等待确认、正在生成回复”等阶段和耗时。Bridge 不返回、前端不展示或保存模型隐藏 reasoning 正文。

前端检查与构建：

```bash
cd web
npm ci
npm run type-check
npm run build
```

## Compose

Compose 默认将 SQLite 数据保存到 ThinkPad 宿主机的 `/mnt/nas/docker/ai-console/data`。其他部署位置可通过 `QINGLUO_DATA_DIR` 覆盖。

```bash
docker compose config
docker compose up -d --build
curl http://127.0.0.1:8010/health
```

部署后访问 `http://127.0.0.1:8010`。生产环境默认每 60 秒采集一次，原始指标样本保留 7 天。

## 主要页面

- **总览**：整体状态、CPU / 内存趋势、AI 额度、核心容器和活动告警。
- **主机监控**：CPU、内存、温度、运行时间、网络/磁盘趋势、系统信息和进程排行。
- **容器服务**：运行状态、健康检查、端口映射和运行时间。
- **智能体**：本机会话状态、注册来源、父子关系、最近心跳和类型化恢复入口。
- **AI 服务**：按账号展示已使用额度、重置时间和可用状态。
- **网络与存储**：存储容量、网络吞吐、UFW 允许规则和主机监听端口。
- **告警记录**：活动告警和最近恢复事件。

## 安全边界

- 默认仅绑定 `127.0.0.1:8010`。
- 第一版只读采集，不执行修复动作。
- 主应用不直接挂载 Docker socket，由只开放容器读取接口的 proxy 访问。
- `/proc`、`/sys`、`/etc/ufw` 和 NAS 均以只读方式挂载。
- 防火墙允许规则与主机监听端口分别展示，避免将“正在监听”误判为“已被防火墙放行”。
- 不在代码、日志、SQLite 或前端保存明文 token、Cookie、API key、密码。
