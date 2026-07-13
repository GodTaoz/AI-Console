# AGENTS.md

## 项目概览

AI-Console 是部署在个人 ThinkPad 服务器上的本地优先、只读监控控制台，用于展示主机资源、Docker 服务、AI/Codex 额度、网络和存储状态。

- 后端：Python 3.11、FastAPI、Pydantic、SQLite。
- 前端：Vue 3、TypeScript、Vite、Naive UI、vue-i18n。
- 包管理：Python 使用 `uv`；前端使用 `npm`，锁文件为 `web/package-lock.json`。
- 服务入口：`qingluo_console.main:app`。
- 默认监听：宿主机 `127.0.0.1:8010`。
- 前端构建产物：`src/qingluo_console/static`，由 FastAPI 提供静态文件和 SPA fallback。

开始修改前先阅读 `README.md` 和 `docs/technical-spec.md`。若文档、测试与当前实现互相矛盾，不要静默选择其中一个；根据用户目标确认真实意图，并在同一改动中同步相关文档和测试。

## 仓库结构

- `src/qingluo_console/main.py`：FastAPI app factory、API 路由、静态资源和 SPA fallback。
- `src/qingluo_console/models.py`：共享状态枚举与 Pydantic 模型。
- `src/qingluo_console/collectors/`：系统、Docker、CPA 额度的只读采集器。
- `src/qingluo_console/collector_runner.py`：统一采集、脱敏并写入 latest snapshot。
- `src/qingluo_console/db.py`：SQLite schema 与 latest snapshot 读写。
- `scripts/collect-system-json.py`：系统采集脚本入口。
- `tests/`：pytest 测试；测试通过 fixture 隔离文件系统、socket、HTTP 和静态资源。
- `web/src/api/`：类型化 API client 与显示格式化函数。
- `web/src/types/`：前后端 JSON contract 的 TypeScript 类型。
- `web/src/router/`：轻量 History API 路由，不使用 vue-router。
- `web/src/pages/`：页面级组件。
- `web/src/components/layout/`：AppShell、Sidebar、Topbar、PageHeader 等共享布局。
- `web/src/styles/`：设计 token 和全局样式。
- `docker-compose.yml`：生产部署边界、只读宿主机挂载及运行环境变量。

## 常用命令

在仓库根目录执行：

```bash
uv run pytest -q
uv run pytest -q tests/test_resources_api.py
uv run uvicorn qingluo_console.main:app --host 127.0.0.1 --port 8010
```

前端检查与开发：

```bash
cd web
npm install
npm run type-check
npm run build
npm run dev
```

容器验证：

```bash
docker compose config
docker compose build
docker compose up -d
curl -fsS http://127.0.0.1:8010/health
```

不要在没有必要时运行 `npm install` 或更新锁文件。依赖发生变化时，必须提交对应的 `uv.lock` 或 `web/package-lock.json` 变化。

## 开发流程

1. 先检查 `git status --short`，保留用户已有的未提交改动，不得回退或覆盖无关修改。
2. 后端功能优先按 TDD 开发：先新增或调整最小失败测试，再实现能力。
3. 优先运行与改动最相关的测试，完成后运行完整 pytest。
4. 前端改动至少运行 `npm run type-check` 和 `npm run build`。
5. API contract 改动必须同步 Pydantic 输出、`web/src/types/`、API client、消费页面和测试。
6. 部署前检查 `git diff --stat` 和关键 diff，再按“测试 -> 前端构建 -> Compose 构建 -> 健康检查”的顺序验证。

## 后端约定

- 保持 `create_app(static_dir=...)` 可注入，测试依赖该入口隔离静态资源。
- `/health` 和 `/api/...` 路由必须定义在 `/{frontend_path:path}` SPA fallback 之前。
- collector 必须返回结构化 Pydantic snapshot；状态统一使用 `Status`：`ok`、`warning`、`critical`、`unsupported`、`permission_denied`、`unknown`。
- 采集失败应转换为结构化 `issues` 和可理解状态，不要把原始内部异常直接暴露给 API 或 UI。
- 文件系统、`/proc`、`/sys`、Docker socket 和 HTTP 客户端应保持可注入，以便测试不依赖真实宿主机。
- SQLite 写入使用参数化 SQL。schema 变更必须同步 `REQUIRED_TABLES`、初始化逻辑和数据库测试。
- 聚合状态沿用项目优先级：`critical` > `warning` > `unknown` > `ok`。若要改变语义，先补测试并检查前端映射。
- 环境变量保持 `QINGLUO_` 前缀；新增变量时同步 `.env.example`、Compose 和相关测试/文档。

## 前端约定

- 使用 Vue `<script setup lang="ts">` 和现有 `@/` 路径别名。
- 延续现有 AppShell、设计 token、Naive UI 和 i18n 结构，不要为单个页面重复实现导航、主题或状态样式。
- 不使用 vue-router；新增页面需同步 `web/src/router/index.ts`、Sidebar/i18n 文案和对应页面组件。
- API 请求集中在 `web/src/api/client.ts`，页面不要散落裸 `fetch`。网络、非 2xx 和 JSON 解析错误继续使用 `ApiError` 语义。
- 不伪造监控指标。数据缺失或接口尚未接入时显示明确空状态、未知态或待接入说明。
- 中文状态优先使用产品化文案；新增可见文本时同步 `zh-CN` 与 `en-US` 翻译。
- 保持桌面端和移动端可用，修改布局后检查 Sidebar 隐藏态、长文本、空数据、错误态和窄屏。
- 视觉主题应遵循当前用户目标和技术规格。不要仅因旧测试 fixture 含有历史品牌文案，就把历史主题重新引入产品 UI。

## 安全红线

- 第一阶段仅允许只读观察。不得通过 Docker socket、系统接口或 CPA API 执行 restart、stop、remove、写配置、修复等动作，除非用户明确改变产品边界并要求完整安全设计。
- Docker socket、`/proc`、`/sys`、NAS 和网络状态文件必须保持只读挂载。
- 不得在代码、日志、异常、API、SQLite、前端、测试快照或文档中输出真实 token、API key、Cookie、密码、OAuth 凭据、连接串或账号文件路径。
- 所有持久化 snapshot 必须经过递归脱敏。新增敏感字段名时更新 `SENSITIVE_KEYS` 及脱敏测试。
- UI 展示账号标识时应最小化和脱敏；不要展示内部异常原文或宿主机敏感路径。
- `.env`、运行数据库和构建产物不得提交。示例配置只能包含空值或明确的非秘密占位值。

## 测试要求

- 修复缺陷时必须增加能复现缺陷的回归测试。
- collector 测试应使用临时目录、伪造 sysfs/procfs、mock HTTP 或 fake Unix socket，不依赖开发机实时状态。
- API 测试使用 `FastAPI TestClient` 和 `create_app()`；涉及环境变量时用 pytest `monkeypatch`，测试结束不得污染环境。
- 前端目前以 TypeScript 构建检查和 pytest 中的静态产物契约测试为主。修改设计或文案时检查测试是否验证了真实产品要求，而不是过时实现细节。
- 涉及安全或持久化时，至少覆盖正常数据、缺失数据、权限不足、上游异常和敏感字段嵌套结构。

## 完成标准

- 改动范围聚焦，没有覆盖用户的无关工作。
- 相关测试通过；通常应完成 `uv run pytest -q`。
- 前端改动通过 `npm run type-check` 和 `npm run build`。
- API、类型、文档、环境变量和 Compose 配置保持一致。
- 已检查输出和持久化内容不存在秘密或敏感路径泄露。
- 若未运行某项验证，最终说明具体未运行项及原因。
