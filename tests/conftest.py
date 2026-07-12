from pathlib import Path

import pytest


@pytest.fixture
def frontend_static_dir(tmp_path: Path) -> Path:
    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "main.js").write_text("console.log('built ai-console');\n", encoding="utf-8")
    (static_dir / "index.html").write_text(
        """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI-Console</title>
</head>
<body>
  <main>
    <header class="topbar">
      <div class="eyebrow">QINGLUO OPS · Mint Cyber Ops</div>
      <h1 class="title">AI-Console</h1>
      <div class="subtitle">Qingluo Mint · Midnight Kernel</div>
    </header>
    <section class="hero-shell">
      <article class="status-orb" data-testid="summary-card">
        <div class="orb-inner">
          <div id="orb-state" class="orb-state">--</div>
          <div class="orb-copy">清萝正在值守</div>
        </div>
      </article>
      <article class="hero-copy">
        <h2>给主人看的稳定性结论</h2>
        <div id="summary" class="module-strip"></div>
      </article>
    </section>
    <section class="command-grid">
      <article class="card">
        <h3>服务器资源</h3>
        <div class="resource-bar"></div>
        <div id="resources">加载中...</div>
      </article>
      <article class="card">
        <h3>AI 额度中心</h3>
        <div class="quota-cell"></div>
        <div id="quota">加载中...</div>
      </article>
      <article class="card">
        <h3>NAS / 磁盘</h3>
        <div id="storage">加载中...</div>
      </article>
      <article class="card wide">
        <h3>Docker 服务编队</h3>
        <div class="service-formation"></div>
        <details class="non-core-containers">
          <summary>0 个非核心/历史容器</summary>
        </details>
        <div id="docker">加载中...</div>
      </article>
      <article class="card wide advice">
        <div class="advice-title">清萝建议</div>
        <div id="issues">暂无异常，清萝继续看守中。</div>
      </article>
    </section>
  </main>
  <!-- shortAccountName replace(/@.*/,'') -->
  <script type="module" src="/static/assets/main.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )
    return static_dir
