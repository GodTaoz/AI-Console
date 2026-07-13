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

## 技术规格

项目技术规格说明书见：[`docs/technical-spec.md`](docs/technical-spec.md)。

## 本地开发

```bash
uv run pytest -q
uv run uvicorn qingluo_console.main:app --host 127.0.0.1 --port 8010
```

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
