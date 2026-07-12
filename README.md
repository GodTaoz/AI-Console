# 清萝基础设施控制台

个人基础设施状态总览服务，目标部署在 ThinkPad 本机，仅监听 loopback。

## 当前阶段

- Phase 1：项目骨架、FastAPI health endpoint、SQLite schema、状态模型。
- 后续 Phase 2 将按 TDD 实现 `system_collector`、`docker_collector`、`cpa_quota_collector`。

## 本地开发

```bash
uv run pytest -q
uv run uvicorn qingluo_console.main:app --host 127.0.0.1 --port 8010
```

## Compose

```bash
docker compose config
docker compose up -d --build
curl http://127.0.0.1:8010/health
```

## 安全边界

- 默认仅绑定 `127.0.0.1:8010`。
- 第一版只读采集，不执行修复动作。
- 不在代码、日志、SQLite 或前端保存明文 token、Cookie、API key、密码。
