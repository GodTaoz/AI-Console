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
  <main class="app-shell" data-theme="light">
    <header class="topbar">
      <h1 class="title">AI-Console</h1>
      <div class="subtitle">Self-hosted AI workstation operations</div>
    </header>
    <section class="dashboard-grid" data-testid="summary-card">
      <article class="data-panel-v2">Host status</article>
      <article class="metric-chart">24 hour trend</article>
      <article class="data-table-v2">Container status</article>
    </section>
  </main>
  <script type="module" src="/static/assets/main.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )
    return static_dir
