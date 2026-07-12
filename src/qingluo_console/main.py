from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from qingluo_console.collector_runner import run_collectors_once
from qingluo_console.collectors.cpa_quota import collect_cpa_quota
from qingluo_console.collectors.docker import collect_docker_containers
from qingluo_console.collectors.system import collect_system_resources
from qingluo_console.db import read_latest_status


def create_app() -> FastAPI:
    app = FastAPI(title="Qingluo Console", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return '<!doctype html>\n<html lang="zh-CN">\n<head>\n  <meta charset="utf-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1">\n  <title>清萝基础设施控制台</title>\n  <style>\n    /* Mint Cyber Ops / Qingluo Mint / Midnight Kernel */\n    :root{color-scheme:dark;--kernel:#07111F;--navy:#0D1B2E;--glass:#102033cc;--mint:#7CE7C8;--ok:#68E6A1;--amber:#FFD166;--coral:#FF6B6B;--text:#E8F7FF;--muted:#98ABC2;--line:#23435d;--violet:#9EA7FF;}\n    *{box-sizing:border-box} body{margin:0;min-height:100vh;background:radial-gradient(circle at 12% 0%,#17476c 0,#07111F 42%),linear-gradient(135deg,#07111F,#0b1526);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,\'Segoe UI\',\'PingFang SC\',\'Microsoft YaHei\',sans-serif;}\n    body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(124,231,200,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(124,231,200,.045) 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(to bottom,#000,transparent 88%)}\n    main{position:relative;max-width:1220px;margin:0 auto;padding:28px}.topbar{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:18px}.eyebrow{font:700 12px/1.2 SFMono-Regular,Consolas,monospace;letter-spacing:.18em;color:var(--mint);text-transform:uppercase}.title{margin:6px 0 4px;font-size:clamp(30px,4vw,54px);line-height:1.02;letter-spacing:-.04em}.subtitle{color:var(--muted)}button{border:1px solid rgba(124,231,200,.45);border-radius:14px;padding:11px 16px;background:linear-gradient(135deg,var(--mint),#b7ffe8);color:#031014;font-weight:900;box-shadow:0 0 28px rgba(124,231,200,.26);cursor:pointer}.hero-shell{display:grid;grid-template-columns:310px 1fr;gap:18px;align-items:stretch;margin:18px 0}.status-orb{position:relative;min-height:265px;border:1px solid rgba(124,231,200,.28);border-radius:30px;background:radial-gradient(circle at 50% 28%,rgba(124,231,200,.24),transparent 36%),var(--glass);display:grid;place-items:center;overflow:hidden}.status-orb:before{content:"";position:absolute;width:190px;height:190px;border-radius:50%;border:22px solid rgba(124,231,200,.2);box-shadow:0 0 60px rgba(124,231,200,.28),inset 0 0 45px rgba(124,231,200,.16)}.orb-inner{position:relative;text-align:center}.orb-state{font-size:54px;font-weight:950;letter-spacing:-.06em;color:var(--mint)}.orb-copy{margin-top:6px;color:var(--muted)}.hero-copy{border:1px solid rgba(255,255,255,.08);border-radius:30px;background:linear-gradient(135deg,rgba(16,32,51,.92),rgba(13,27,46,.72));padding:24px}.hero-copy h2{margin:0;font-size:30px;letter-spacing:-.03em}.hero-copy p{color:var(--muted);max-width:680px}.module-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:18px}.module-pill,.card{border:1px solid rgba(255,255,255,.08);background:rgba(16,32,51,.78);border-radius:18px;padding:14px}.badge{display:inline-flex;padding:4px 10px;border-radius:99px;background:#22364c;font-weight:850}.ok{color:var(--ok)}.warning,.unknown{color:var(--amber)}.critical{color:var(--coral)}.command-grid{display:grid;grid-template-columns:1.1fr 1.1fr .9fr;gap:16px}.card h3{margin:0 0 14px;font-size:18px}.metric{display:flex;justify-content:space-between;gap:14px;align-items:center;color:var(--muted);margin:10px 0}.metric b{color:var(--text);font-family:SFMono-Regular,Consolas,monospace}.resource-bar,.quota-bar{height:10px;background:#1a2c42;border-radius:999px;overflow:hidden;margin:6px 0 12px}.resource-fill,.quota-fill{height:100%;width:0;background:linear-gradient(90deg,var(--mint),var(--ok));border-radius:999px;box-shadow:0 0 18px rgba(124,231,200,.35)}.quota-cell{padding:12px;border:1px solid rgba(124,231,200,.16);border-radius:16px;margin:10px 0;background:rgba(7,17,31,.34)}.quota-title{display:flex;justify-content:space-between;gap:8px}.service-formation{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.service{display:flex;justify-content:space-between;gap:10px;padding:10px 12px;border-radius:13px;background:rgba(7,17,31,.38);border:1px solid rgba(255,255,255,.06)}.service span:first-child,.quota-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.non-core-containers summary{cursor:pointer;color:var(--amber);margin-top:12px}.advice{margin-top:16px;border:1px solid rgba(124,231,200,.18);border-radius:22px;padding:16px;background:linear-gradient(135deg,rgba(124,231,200,.08),rgba(158,167,255,.06))}.advice-title{font-weight:900;color:var(--mint);margin-bottom:8px}.mono{font-family:SFMono-Regular,Consolas,monospace}.wide{grid-column:1/-1}@media(max-width:880px){main{padding:16px}.topbar,.hero-shell{display:block}.hero-copy{margin-top:14px}.command-grid,.module-strip,.service-formation{grid-template-columns:1fr}.title{font-size:34px}button{margin-top:14px;width:100%}}\n  </style>\n</head>\n<body>\n<main>\n  <header class="topbar"><div><div class="eyebrow">QINGLUO OPS · Mint Cyber Ops</div><h1 class="title">清萝基础设施控制台</h1><div class="subtitle">ThinkPad · Docker · CPA/Codex · NAS 实时状态</div></div><button onclick="refreshAll()">刷新状态</button></header>\n  <section class="hero-shell"><article class="status-orb" data-testid="summary-card"><div class="orb-inner"><div id="orb-state" class="orb-state">--</div><div class="orb-copy">清萝正在值守</div><div id="orb-issues" class="orb-copy mono">issues: --</div></div></article><article class="hero-copy"><h2>给主人看的稳定性结论</h2><p id="hero-line">正在读取 latest snapshot。清萝会优先告诉主人现在稳不稳，再把细节放进下方卡片。</p><div id="summary" class="module-strip"></div></article></section>\n  <section class="command-grid"><article class="card"><h3>服务器资源</h3><div id="resources">加载中...</div></article><article class="card"><h3>AI 额度中心</h3><div id="quota">加载中...</div></article><article class="card"><h3>NAS / 磁盘</h3><div id="storage">加载中...</div></article><article class="card wide"><h3>Docker 服务编队</h3><div id="docker">加载中...</div></article><article class="card wide advice"><div class="advice-title">清萝建议</div><div id="issues">暂无异常，清萝继续看守中。</div></article></section>\n</main>\n<script>\nconst statusClass=s=>[\'ok\',\'warning\',\'critical\',\'unknown\'].includes(s)?s:\'unknown\';\nconst badge=s=>`<span class="badge ${statusClass(s)}">${s||\'unknown\'}</span>`;\nconst pct=n=>Number.isFinite(n)?`${n.toFixed(1)}%`:\'—\';\nconst clamp=n=>Math.max(0,Math.min(100,Number(n)||0));\nconst bytesUsedPercent=item=>item?.total_bytes?((item.used_bytes||0)/item.total_bytes*100):NaN;\nconst usedPercent=memory=>memory?.total_bytes?((memory.total_bytes-memory.available_bytes)/memory.total_bytes*100):NaN;\nfunction bar(value,cls=\'resource-fill\'){return `<div class="resource-bar"><div class="${cls}" style="width:${clamp(value)}%"></div></div>`}\nfunction shortAccountName(name=\'\'){return name.replace(/^codex-/,\'\').replace(/-plus\\.json$/,\'\').replace(/@.*/,\'\').slice(0,18)}\nasync function getJson(url){const r=await fetch(url);if(!r.ok)throw new Error(`${url} ${r.status}`);return await r.json()}\nasync function refreshAll(){\n const [summary,resources,quota,docker]=await Promise.all([getJson(\'/api/summary\').catch(()=>({status:\'unknown\',modules:{}})),getJson(\'/api/resources\'),getJson(\'/api/ai-quota\'),getJson(\'/api/docker\')]);\n const issues=[...(resources.issues||[]),...(quota.issues||[]),...(docker.issues||[])];\n document.getElementById(\'orb-state\').textContent=(summary.status||\'unknown\').toUpperCase();document.getElementById(\'orb-state\').className=`orb-state ${statusClass(summary.status)}`;document.getElementById(\'orb-issues\').textContent=`issues: ${issues.length}`;\n document.getElementById(\'hero-line\').textContent=summary.status===\'ok\'?\'主人，当前核心基础设施稳定。资源、Docker 与 AI 额度均可用。\':\'主人，有状态需要关注，清萝已经把异常放到建议区。\';\n document.getElementById(\'summary\').innerHTML=Object.entries(summary.modules||{}).map(([k,v])=>`<div class="module-pill"><div class="eyebrow">${k}</div>${badge(v.status)}</div>`).join(\'\');\n const mem=usedPercent(resources.memory);document.getElementById(\'resources\').innerHTML=`<div class="metric"><span>状态</span><b>${badge(resources.status)}</b></div><div class="metric"><span>内存</span><b>${pct(mem)}</b></div>${bar(mem)}<div class="metric"><span>温度</span><b>${Object.values(resources.thermal?.temperatures_c||{})[0]??\'—\'} ℃</b></div><div class="metric"><span>电池</span><b>${resources.power?.battery_percent??\'—\'}%</b></div>`;\n document.getElementById(\'storage\').innerHTML=(resources.filesystems||[]).map(f=>{const u=bytesUsedPercent(f);return `<div class="metric"><span>${f.mount}</span><b>${pct(u)} used</b></div>${bar(u)}`}).join(\'\');\n document.getElementById(\'quota\').innerHTML=`<div class="metric"><span>状态</span><b>${badge(quota.status)}</b></div>`+(quota.accounts||[]).map(a=>`<div class="quota-cell"><div class="quota-title"><span class="quota-name">${shortAccountName(a.name)}</span><b>${pct(a.used_percent)}</b></div><div class="quota-bar"><div class="quota-fill" style="width:${clamp(a.used_percent)}%"></div></div><div class="metric"><span>reset</span><b>${a.reset_after_seconds??\'—\'}s · credits ${a.reset_credits_available??\'—\'}</b></div></div>`).join(\'\');\n const core=new Set([\'qingluo-console\',\'cli-proxy-api\',\'filebrowser-nas-root\',\'webdav-nas-root\',\'hindsight\',\'redis\',\'mysql\']);const all=docker.containers||[];const coreList=all.filter(c=>core.has(c.name));const other=all.filter(c=>!core.has(c.name));\n document.getElementById(\'docker\').innerHTML=`<div class="metric"><span>状态</span><b>${badge(docker.status)}</b></div><div class="service-formation">${coreList.map(c=>`<div class="service"><span>${c.name}</span><b>${c.state} · ${c.health||c.status}</b></div>`).join(\'\')}</div><details class="non-core-containers"><summary>${other.length} 个非核心/历史容器</summary>${other.map(c=>`<div class="service"><span>${c.name}</span><b>${c.state} · ${c.status}</b></div>`).join(\'\')}</details>`;\n document.getElementById(\'issues\').innerHTML=issues.length?`<pre>${JSON.stringify(issues,null,2)}</pre>`:\'暂无需要主人处理的问题。我会继续监控资源、Docker 服务和 AI 额度。\';\n}\nrefreshAll().catch(err=>{document.getElementById(\'issues\').textContent=err.message});\n</script>\n</body>\n</html>'

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "qingluo-console",
        }

    @app.get("/api/resources")
    def resources() -> dict[str, object]:
        snapshot = collect_system_resources(
            proc_root=Path(os.getenv("QINGLUO_PROC_ROOT", "/proc")),
            sys_root=Path(os.getenv("QINGLUO_SYS_ROOT", "/sys")),
            mount_paths=[Path("/"), Path("/mnt/nas")],
            primary_interface=os.getenv("QINGLUO_PRIMARY_INTERFACE", "enp4s0"),
        )
        return snapshot.model_dump(mode="json")

    @app.get("/api/docker")
    def docker() -> dict[str, object]:
        core_names = [
            name.strip()
            for name in os.getenv(
                "QINGLUO_CORE_CONTAINERS",
                "hindsight,cli-proxy-api,mysql,redis,filebrowser-nas-root,webdav-nas-root,qingluo-console",
            ).split(",")
            if name.strip()
        ]
        snapshot = collect_docker_containers(
            core_names=core_names,
            socket_path=Path(os.getenv("QINGLUO_DOCKER_SOCKET", "/var/run/docker.sock")),
        )
        return snapshot.model_dump(mode="json")

    @app.get("/api/ai-quota")
    def ai_quota() -> dict[str, object]:
        snapshot = collect_cpa_quota(
            management_key=os.getenv("QINGLUO_CPA_MANAGEMENT_KEY"),
            base_url=os.getenv("QINGLUO_CPA_BASE_URL", "http://127.0.0.1:8317"),
        )
        return snapshot.model_dump(mode="json")

    @app.post("/api/collect/run")
    def collect_run() -> dict[str, object]:
        return run_collectors_once(db_path=Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/qingluo-console.sqlite3")))

    @app.get("/api/summary")
    def summary() -> dict[str, object]:
        latest = read_latest_status(Path(os.getenv("QINGLUO_CONSOLE_DB", "/data/qingluo-console.sqlite3")))
        modules = {module: {"status": data["status"], "updated_at": data["updated_at"], "payload": data["payload"]} for module, data in latest.items()}
        statuses = [data["status"] for data in latest.values()]
        if "critical" in statuses:
            status = "critical"
        elif "warning" in statuses:
            status = "warning"
        elif "unknown" in statuses:
            status = "unknown"
        else:
            status = "ok" if statuses else "unknown"
        return {"status": status, "modules": modules}

    return app


app = create_app()
