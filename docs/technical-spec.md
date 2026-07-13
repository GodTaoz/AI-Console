# AI-Console 技术规格说明书

## 1. 项目定位

AI-Console 是部署在个人 ThinkPad 服务器上的本地优先 AI 与基础设施控制台，用于统一查看主机资源、Docker 服务、AI 额度、网络与存储状态，并为后续智能体、告警、设置与主题皮肤提供工程化基础。

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
- Docker API socket 只读采集
- CPA Management API 只读采集 AI / Codex 额度
- uv / pip 用于容器内依赖安装

### 前端

- Vue 3
- TypeScript
- Vite
- Naive UI
- 自定义 AppShell / Sidebar / Topbar / PageHeader
- 简短语言切换：`中 / EN`
- Sidebar 支持隐藏 / 显示

## 4. 后端接口

| 路径 | 方法 | 用途 |
|---|---:|---|
| `/health` | GET | 服务健康检查 |
| `/api/resources` | GET | 主机资源、文件系统、网络、温度、电源状态 |
| `/api/docker` | GET | Docker 容器状态、健康检查、端口映射、问题列表 |
| `/api/ai-quota` | GET | CPA / Codex 账号额度、剩余额度、重置倒计时 |
| `/api/collect/run` | POST | 触发统一采集并写入 latest snapshot |
| `/api/summary` | GET | 读取 SQLite latest snapshot 汇总 |

## 5. 当前前端路由

| 路由 | 页面 | 当前状态 |
|---|---|---|
| `/overview` | 总览 | 已接 live resources/docker/ai-quota |
| `/hosts` | 主机监控 | 已接 `/api/resources` |
| `/containers` | 容器服务 | 已接 `/api/docker` |
| `/agents` | 智能体 | 路由骨架，待接真实数据 |
| `/ai-services` | AI 服务 | 已接 `/api/ai-quota` |
| `/network-storage` | 网络与存储 | 已接 `/api/resources` |
| `/alerts` | 告警记录 | 路由骨架，待接真实事件 |
| `/settings` | 系统设置 | 路由骨架，待接真实设置能力 |

## 6. 数据源与安全边界

### 主机资源

`/api/resources` 提供：

- CPU snapshot
- memory / swap
- filesystems：至少包含 `/` 与 `/mnt/nas`
- primary network interface RX/TX
- thermal temperatures
- power / battery / AC 状态
- issues

### Docker

`/api/docker` 通过只读 Docker socket 采集：

- container name
- image
- state
- status_text
- normalized status
- health
- ports
- issues

Docker socket 必须只读挂载；控制台第一阶段只读，不执行 restart / stop / remove 等动作。

### AI 额度

`/api/ai-quota` 通过 CPA Management API 只读采集 Codex 额度：

- account id / display name
- provider
- normalized status
- used / remaining percent
- reset credits available
- reset countdown
- issues

不得在前端、日志、SQLite、文档中输出真实 token、API key、Cookie、密码、连接串、OAuth token 或账号文件路径。需要展示异常时必须产品化并脱敏。

## 7. UI 原则

- 默认主题保持专业 AI Ops 控制台风格。
- 默认 UI 不加入清萝角色、清萝主题、清萝文案或猫娘元素。
- 清萝主题以后作为独立皮肤实现。
- 不伪造指标；没有真实数据时显示空状态或待接入说明。
- 状态中文优先：`正常 / 在线 / 健康 / 关注 / 异常 / 未知`。
- 多语言入口只保留短切换：`中 / EN`。
- Sidebar 必须支持隐藏，隐藏后主内容区域可展开。

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
- 主题切换入口。
- 简短语言切换 `中 / EN`。
- Sidebar 隐藏 / 显示。
- Overview live dashboard。
- 主机监控 live 页面。
- 容器服务 live 页面。
- AI 服务 live 页面。
- 网络与存储 live 页面。
- 默认 UI 去清萝化。
- Docker build timeout/retry 加固。

## 11. 后续计划

优先级建议：

1. 智能体页接入真实智能体 / 任务执行状态。
2. 告警记录页接入真实事件与规则。
3. 系统设置页接入主题、语言、安全边界与集成配置。
4. 给 live 页面补更细的异常态和移动端验收。
5. 最后制作独立清萝主题皮肤。
