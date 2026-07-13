# AI-Console 技术规格说明书

## 1. 项目定位

AI-Console 是部署在个人 ThinkPad 服务器上的单机自托管 AI 工作站运行健康与额度预警中心，用于持续采集主机资源、Docker 服务、AI 额度、网络与存储状态，并跟踪异常的出现与恢复。

默认 UI 保持专业控制台风格，不包含清萝角色、清萝文案或猫娘元素；清萝相关视觉以后作为独立主题皮肤实现。

## 2. 当前部署边界

- 服务名：`ai-console`
- 容器镜像：`ai-console-ai-console:latest`
- 监听地址：`127.0.0.1:8010`
- Web 框架：FastAPI
- 前端：Vue 3 + TypeScript + Vite
- 运行入口：`qingluo_console.main:app`
- Docker runtime：`PYTHONPATH=/app/src`
- 静态资源：Vite build 输出到 `src/qingluo_console/static`
- SPA fallback：FastAPI 在 `/health` 与 `/api/...` 路由之后兜底返回 Vue `index.html`

## 3. 技术栈

### 后端

- Python 3.11
- FastAPI
- SQLite
- Docker socket proxy 白名单只读采集
- 后台周期采集与 SQLite 历史样本
- CPA Management API 只读采集 AI / Codex 额度
- uv / pip 用于容器内依赖安装

### 前端

- Vue 3
- TypeScript
- Vite
- Naive UI
- ECharts
- 自定义 AppShell / Sidebar / Topbar / PageHeader；当前布局不包含 Footer
- 图标式语言菜单，默认跟随浏览器语言并使用 LocalStorage 持久化
- 图标式主题菜单：跟随系统、明亮、柔和、暗色
- Naive UI 主题覆盖与 ECharts 24 小时趋势图
- Sidebar 支持隐藏 / 显示
- 页面使用动态导入，表格与图表按路由拆包

## 4. 后端接口

| 路径 | 方法 | 用途 |
|---|---:|---|
| `/health` | GET | 服务健康检查 |
| `/api/resources` | GET | 主机资源、文件系统、网络、温度、电源、防火墙与监听端口 |
| `/api/docker` | GET | Docker 容器状态、健康检查、端口映射、问题列表 |
| `/api/ai-quota` | GET | CPA / Codex 账号额度、剩余额度、重置倒计时 |
| `/api/collect/run` | POST | 触发统一采集并写入 latest snapshot |
| `/api/summary` | GET | 读取 SQLite latest snapshot 汇总 |
| `/api/alerts` | GET | 读取活动告警与最近恢复事件 |
| `/api/metrics/history` | GET | 读取五分钟聚合的 24 小时资源与额度趋势 |

`/api/metrics/history` 当前接受：

- `range=24h`：唯一支持的时间范围，其他值返回 `422`。
- `metrics`：逗号分隔的指标白名单；不传时返回全部允许指标。
- 响应包含 `generated_at`、`range`、`bucket_seconds` 与按标签分组的 `series`。

## 5. 当前前端路由

| 路由 | 页面 | 当前状态 |
|---|---|---|
| `/overview` | 总览 | 已接汇总、活动告警与 CPU / 内存 24 小时趋势 |
| `/hosts` | 主机监控 | 已接资源、系统信息、进程排行与三组 24 小时趋势 |
| `/containers` | 容器服务 | 已接 `/api/docker` |
| `/agents` | 智能体 | 保留路由但不在导航展示，待接真实数据 |
| `/ai-services` | AI 服务 | 已接 `/api/ai-quota` |
| `/network-storage` | 网络与存储 | 已接容量、吞吐、UFW 规则与宿主机监听端口 |
| `/alerts` | 告警记录 | 已接活动与恢复事件 |
| `/settings` | 系统设置 | 保留路由但不在导航展示，待接真实设置能力 |

## 6. 数据源与安全边界

### 主机资源

`/api/resources` 提供：

- CPU snapshot
- memory / swap
- filesystems：至少包含 `/` 与 `/mnt/nas`
- primary network interface RX/TX
- CPU 使用率、核心数与型号
- 主机运行时间、厂商型号、操作系统、内核与主 IP
- 磁盘读写和网络收发实时速率
- CPU / 内存进程 Top 10（不包含命令参数）
- UFW 启用状态与允许规则
- TCP / UDP 实际监听端口、监听地址与暴露范围
- thermal temperatures
- power / battery / AC 状态
- issues

安全数据分为两个不同语义：

- `security.firewall`：从只读挂载的 `/etc/ufw` 读取 UFW 启用状态及 IPv4 / IPv6 `ACCEPT` 规则。
- `security.listening_ports`：读取宿主机 PID 1 网络命名空间下的 `/proc/1/net/tcp*`、`udp*`，返回协议、端口、监听地址和范围。
- 监听范围规范化为 `loopback`、`all_interfaces`、`specific_address`。
- 防火墙规则表示流量策略；监听端口表示服务正在接收连接，两者不可互相替代。

### Docker

`/api/docker` 通过内部 Docker socket proxy 采集：

- container name
- image
- state
- status_text
- normalized status
- health
- ports
- issues

Docker socket 只挂载到 proxy；主应用不接触 socket。proxy 仅开放容器查询且禁用 POST，应用客户端还会校验 API path 白名单。控制台不执行 restart / stop / remove 等动作。

### AI 额度

`/api/ai-quota` 通过 CPA Management API 只读采集 Codex 额度：

- account id / display name
- provider
- normalized status
- used / remaining percent
- reset credits available
- reset countdown
- issues

额度账号在当前 loopback 单用户部署中允许显示完整邮箱，作为用户明确选择的本地展示标识；仍不得输出账号文件路径、token、Cookie 或 OAuth 凭据。账号可用性以实际额度请求结果为准，而不是仅依赖 CPA auth-files 的瞬时状态。

不得在前端、日志、SQLite、文档中输出真实 token、API key、Cookie、密码、连接串、OAuth token 或账号文件路径。需要展示异常时必须产品化并脱敏。

## 7. UI 原则

- 默认主题保持专业 AI Ops 控制台风格。
- 默认 UI 不加入清萝角色、清萝主题、清萝文案或猫娘元素。
- 清萝主题以后作为独立皮肤实现。
- 不伪造指标；没有真实数据时显示空状态或待接入说明。
- 状态中文优先：`正常 / 在线 / 健康 / 关注 / 异常 / 未知`。
- Topbar 只显示主题和语言图标，点击后展开选择菜单；当前选项必须有明确选中状态。
- 语言支持简体中文和 English，新增可见文本必须保持两套文案键一致。
- 主题支持 `system`、`light`、`soft`、`dark`；`system` 实时响应操作系统配色变化。
- 当前布局不展示 Footer，页面底部由内容区域自然结束。
- Sidebar 必须支持隐藏，隐藏后主内容区域可展开。
- 单值、容量、趋势、表格、系统信息和告警分别使用适合的数据组件，不用装饰性卡片替代信息结构。
- 百分比保留一位小数并显示 `%`；温度显示 `℃`；容量使用二进制单位；吞吐显示每秒单位；缺失数据只显示 `—`。

### 趋势图

- 总览展示 CPU 与内存组合趋势。
- 主机页展示 CPU / 内存、网络接收 / 发送、磁盘读取 / 写入三组趋势。
- 图表容器在异步数据返回前始终挂载，避免 ECharts 实例无法初始化。
- 无样本时显示明确空状态，不补零、不连接缺失时间桶。

### 历史指标

- 当前查询范围固定为 `24h`，桶宽为 300 秒，单序列最多 288 点。
- CPU、内存、文件系统和吞吐指标使用桶内平均值。
- 额度指标使用桶内最后一个有效值。
- 原始分钟样本默认保留 7 天，清理操作每小时最多执行一次。

## 8. 开发流程要求

所有后续功能开发必须遵守：

1. **TDD 优先**
   - 新后端能力先补测试或最小失败用例。
   - 新前端能力至少跑 `npm run type-check && npm run build`。

2. **部署前代码审查**
   - 部署前必须查看 `git status --short`。
   - 部署前必须查看 `git diff --stat` 与关键 diff。
   - 不允许等部署后才发现明显文案、路由、状态或类型问题。

3. **验证顺序**
   - 本地测试：`uv run pytest -q`
   - 前端检查：`cd web && npm run type-check && npm run build`
   - Docker 构建：`docker compose build`
   - 上线：`docker compose up -d`
   - 健康检查：`curl -fsS http://127.0.0.1:8010/health`
   - 浏览器逐页验证关键路径

4. **安全审查**
   - 新增 collector / API / 页面时必须检查是否泄露密钥、token、Cookie、路径、账号文件名或内部异常原文。
   - `.env` 与 CPA 管理密钥不得提交、不得输出、不得写入文档。

## 9. Docker 构建注意事项

### 运行配置

| 配置 | 默认值 | 用途 |
|---|---|---|
| `QINGLUO_DATA_DIR` | `/mnt/nas/docker/ai-console/data` | Compose 宿主机数据目录 |
| `QINGLUO_CONSOLE_DB` | `/data/ai-console.sqlite3` | 容器内 SQLite 路径 |
| `QINGLUO_SCHEDULER_ENABLED` | `true` | 是否启用周期采集 |
| `QINGLUO_COLLECTION_INTERVAL_SECONDS` | `60` | 采集间隔 |
| `QINGLUO_STALE_AFTER_SECONDS` | `180` | 快照过期阈值 |
| `QINGLUO_METRIC_RETENTION_DAYS` | `7` | 原始指标保留天数 |
| `QINGLUO_SERVE_LATEST_ONLY` | `true` | API 是否优先返回持久化快照 |
| `QINGLUO_PROC_ROOT` | `/host/proc` | 只读宿主机 procfs |
| `QINGLUO_SYS_ROOT` | `/host/sys` | 只读宿主机 sysfs |
| `QINGLUO_UFW_ROOT` | `/host/etc/ufw` | 只读 UFW 配置目录 |
| `QINGLUO_DOCKER_BASE_URL` | `http://docker-socket-proxy:2375` | 只读 Docker proxy |
| `QINGLUO_CPA_BASE_URL` | `http://cli-proxy-api:8317` | CPA Management API |
| `QINGLUO_CPA_MANAGEMENT_KEY` | 空 | CPA 管理凭据，只能通过环境注入 |

`QINGLUO_DATA_DIR` 是 Compose 变量，其余配置以 `QINGLUO_` 前缀注入应用。示例文件不得包含真实凭据。

Dockerfile 中安装 Python 依赖时使用较长 timeout 与 retry，以降低 PyPI 抖动导致的失败概率：

```dockerfile
RUN pip install --no-cache-dir --retries 5 --timeout 120 uv && \
    uv pip install --system .
```

若构建失败点是 Docker Hub 或 PyPI 超时，应先判断为外部网络问题，不要误判为代码失败；必要时重试或配置镜像源。

## 10. 当前已完成能力

- 项目更名与服务身份统一为 AI-Console / ai-console。
- FastAPI health 与 SPA static serving。
- Vue AppShell / Sidebar / Topbar / PageHeader。
- 跟随系统、明亮、柔和、暗色主题及本地持久化。
- 图标式主题菜单和中英文语言菜单。
- Sidebar 隐藏 / 显示。
- Overview live dashboard。
- 主机监控 live 页面。
- 容器服务 live 页面。
- AI 服务 live 页面。
- 网络与存储 live 页面。
- 默认 UI 去清萝化。
- Docker build timeout/retry 加固。
- 后台周期采集、采集批次与数据过期判断。
- 指标样本、活动告警与恢复记录。
- 24 小时指标趋势与 7 天原始样本保留策略。
- UFW 启用状态、允许规则与宿主机监听端口。
- CPU、内存、温度、容量、吞吐和时间单位统一格式化。
- 响应式 Naive UI 数据表、描述列表、进度条、告警和空状态。
- 页面懒加载及趋势图独立代码块。
- Docker socket proxy 与 API 路径白名单。

## 11. 后续计划

优先级建议：

1. 增加告警阈值配置和通知渠道。
2. 为历史指标增加 `7d` / `30d` 范围和长期降采样。
3. 为监听端口增加可选的进程/服务归属识别。
4. 智能体页接入真实智能体 / 任务执行状态后再开放导航。
5. 给 live 页面补自动化浏览器端到端和视觉回归测试。
