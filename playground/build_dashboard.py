#!/usr/bin/env python3
"""
Build a self-contained eval dashboard HTML file from the latest run results.

Usage:
    python3 build_dashboard.py                    # Latest run
    python3 build_dashboard.py --run run_20260725_143000  # Specific run
    python3 build_dashboard.py --open              # Open in browser (WSL)
"""

import argparse
import json
import os
import sys
from pathlib import Path

RUNS_DIR = Path(__file__).parent / "runs"
DOCS_DIR = Path(__file__).parent / "docs"

TEMPLATE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Playground Eval Dashboard</title>
<style>
  :root { --green: #22c55e; --red: #ef4444; --amber: #f59e0b; --blue: #3b82f6; --gray: #6b7280; --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --muted: #94a3b8; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 24px; }
  h1 { font-size: 1.5rem; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .stat-card { background: var(--card); border-radius: 8px; padding: 16px; }
  .stat-card .value { font-size: 1.8rem; font-weight: 700; }
  .stat-card .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-card .value.green { color: var(--green); }
  .stat-card .value.red { color: var(--red); }
  .stat-card .value.amber { color: var(--amber); }
  .stat-card .value.blue { color: var(--blue); }
  .filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
  .filters input, .filters select { background: var(--card); border: 1px solid #334155; color: var(--text); padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; }
  .filters input { flex: 1; min-width: 200px; }
  .filters select { min-width: 120px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
  th { background: var(--card); text-align: left; padding: 8px 10px; border-bottom: 2px solid #334155; cursor: pointer; white-space: nowrap; user-select: none; }
  th:hover { color: var(--blue); }
  td { padding: 8px 10px; border-bottom: 1px solid #1e293b; }
  tr:hover { background: rgba(255,255,255,0.03); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 600; }
  .badge-pass { background: rgba(34,197,94,0.15); color: var(--green); }
  .badge-fail { background: rgba(239,68,68,0.15); color: var(--red); }
  .badge-success { background: rgba(34,197,94,0.15); color: var(--green); }
  .badge-marginal { background: rgba(245,158,11,0.15); color: var(--amber); }
  .detail-row td { padding: 0; }
  .detail-row .detail { display: none; padding: 12px 16px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; margin: 4px 0; }
  .detail-row.expanded .detail { display: block; }
  .detail pre { white-space: pre-wrap; font-size: 0.75rem; color: var(--muted); }
  .expand-btn { cursor: pointer; background: none; border: none; color: var(--blue); font-size: 0.7rem; }
  .bot-badge { display: inline-block; padding: 2px 6px; background: var(--card); border-radius: 4px; font-size: 0.7rem; }
  @media (max-width: 600px) { .stats { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<h1>🤖 Playground Eval Dashboard</h1>
<p class="subtitle" id="subtitle">Loading...</p>

<div class="stats" id="stats"></div>

<div class="filters">
  <input type="text" id="search" placeholder="Search queries, responses..." oninput="filterTable()">
  <select id="statusFilter" onchange="filterTable()">
    <option value="all">All Status</option>
    <option value="pass">Passed</option>
    <option value="fail">Failed</option>
  </select>
  <select id="qualityFilter" onchange="filterTable()">
    <option value="all">All Quality</option>
    <option value="success">Success</option>
    <option value="marginal">Marginal</option>
    <option value="fail">Fail</option>
  </select>
  <select id="categoryFilter" onchange="filterTable()">
    <option value="all">All Categories</option>
  </select>
  <select id="botFilter" onchange="filterTable()">
    <option value="all">All Bots</option>
  </select>
</div>

<table><thead><tr>
  <th onclick="sortTable(0)">ID</th>
  <th onclick="sortTable(1)">Bot</th>
  <th onclick="sortTable(2)">Category</th>
  <th onclick="sortTable(3)">Query</th>
  <th onclick="sortTable(4)">Type</th>
  <th onclick="sortTable(5)">Status</th>
  <th onclick="sortTable(6)">Quality</th>
  <th onclick="sortTable(7)">Time (s)</th>
  <th></th>
</tr></thead><tbody id="tbody"></tbody></table>

<script>
const RECORDS = %JSON_DATA%;

function init() {
  const run = RECORDS.run || {};
  document.getElementById('subtitle').textContent =
    `Run: ${run.run_id || 'N/A'} | ${run.timestamp || ''} | ${RECORDS.results.length} queries`;

  // Stats
  const r = RECORDS.results;
  const total = r.length;
  const passed = r.filter(x => x.passed).length;
  const failed = total - passed;
  const success = r.filter(x => x.response_quality === 'success').length;
  const marginal = r.filter(x => x.response_quality === 'marginal').length;
  const qualityFail = r.filter(x => x.response_quality === 'fail').length;
  const avgTime = total ? (r.reduce((s, x) => s + x.response_time_seconds, 0) / total).toFixed(1) : 0;
  const bots = new Set(r.map(x => x.bot_name)).size;

  document.getElementById('stats').innerHTML = `
    <div class="stat-card"><div class="value blue">${total}</div><div class="label">Total</div></div>
    <div class="stat-card"><div class="value green">${passed}</div><div class="label">Passed</div></div>
    <div class="stat-card"><div class="value red">${failed}</div><div class="label">Failed</div></div>
    <div class="stat-card"><div class="value ${total && passed/total >= 0.8 ? 'green' : passed/total >= 0.5 ? 'amber' : 'red'}">${total ? (passed/total*100).toFixed(0) : 0}%</div><div class="label">Pass Rate</div></div>
    <div class="stat-card"><div class="value blue">${avgTime}s</div><div class="label">Avg Time</div></div>
    <div class="stat-card"><div class="value blue">${bots}</div><div class="label">Bots</div></div>
  `;

  // Filter dropdowns
  const cats = new Set(r.map(x => x.category).filter(Boolean));
  const botsSet = new Set(r.map(x => x.bot_name));
  const catSel = document.getElementById('categoryFilter');
  for (const c of cats) { const o = document.createElement('option'); o.value = c; o.textContent = c; catSel.appendChild(o); }
  const botSel = document.getElementById('botFilter');
  for (const b of botsSet) { const o = document.createElement('option'); o.value = b; o.textContent = b; botSel.appendChild(o); }

  renderTable();
}

function renderTable() {
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  for (let i = 0; i < RECORDS.results.length; i++) {
    const row = document.createElement('tr');
    row.dataset.idx = i;

    const r = RECORDS.results[i];
    const passBadge = r.passed ? '<span class="badge badge-pass">PASS</span>' : '<span class="badge badge-fail">FAIL</span>';
    const qualBadge = r.response_quality === 'success' ? '<span class="badge badge-success">success</span>'
      : r.response_quality === 'marginal' ? '<span class="badge badge-marginal">marginal</span>'
      : '<span class="badge badge-fail">fail</span>';
    const typeLabel = r.response_type || '—';
    const truncated = r.query.length > 50 ? r.query.slice(0, 50) + '…' : r.query;

    row.innerHTML = `
      <td>${r.query_id || '?'}</td>
      <td><span class="bot-badge">${r.bot_name || '?'}</span></td>
      <td>${r.category || '—'}</td>
      <td title="${r.query.replace(/"/g, '&quot;')}">${truncated}</td>
      <td>${typeLabel}</td>
      <td>${passBadge}</td>
      <td>${qualBadge}</td>
      <td>${r.response_time_seconds?.toFixed(1) || '—'}</td>
      <td><button class="expand-btn" onclick="toggleDetail(${i})">▶</button></td>
    `;
    tbody.appendChild(row);

    // Detail row
    const detailRow = document.createElement('tr');
    detailRow.className = 'detail-row';
    detailRow.id = `detail-${i}`;
    const detailCell = document.createElement('td');
    detailCell.colSpan = 9;
    detailCell.innerHTML = `<div class="detail"><pre>${escapeHtml(JSON.stringify(r, null, 2))}</pre></div>`;
    detailRow.appendChild(detailCell);
    tbody.appendChild(detailRow);
  }
  filterTable();
}

function toggleDetail(idx) {
  const row = document.getElementById(`detail-${idx}`);
  row.classList.toggle('expanded');
  const btn = row.previousElementSibling?.querySelector('.expand-btn');
  if (btn) btn.textContent = row.classList.contains('expanded') ? '▼' : '▶';
}

function filterTable() {
  const q = document.getElementById('search').value.toLowerCase();
  const status = document.getElementById('statusFilter').value;
  const quality = document.getElementById('qualityFilter').value;
  const category = document.getElementById('categoryFilter').value;
  const bot = document.getElementById('botFilter').value;
  const rows = document.querySelectorAll('#tbody tr');
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const idx = parseInt(row.dataset.idx);
    if (isNaN(idx)) continue;
    const r = RECORDS.results[idx];
    const match = (!q || r.query.toLowerCase().includes(q) || r.response_text?.toLowerCase().includes(q) || (r.query_id || '').toLowerCase().includes(q));
    const sMatch = status === 'all' || (status === 'pass' && r.passed) || (status === 'fail' && !r.passed);
    const qMatch = quality === 'all' || r.response_quality === quality;
    const cMatch = category === 'all' || r.category === category;
    const bMatch = bot === 'all' || r.bot_name === bot;
    row.style.display = (match && sMatch && qMatch && cMatch && bMatch) ? '' : 'none';
  }
}

function sortTable(col) {
  const keyMap = ['query_id', 'bot_name', 'category', 'query', 'response_type', 'passed', 'response_quality', 'response_time_seconds'];
  const key = keyMap[col];
  if (!key) return;
  const asc = RECORDS._sortKey !== key || RECORDS._sortAsc === false;
  RECORDS._sortKey = key;
  RECORDS._sortAsc = asc;
  RECORDS.results.sort((a, b) => {
    let va = a[key], vb = b[key];
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va === undefined || va === null) va = '';
    if (vb === undefined || vb === null) vb = '';
    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  });
  renderTable();
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

init();
</script>
</body>
</html>
"""


def escape_json_for_html(data: str) -> str:
    """Escape JSON string for safe embedding in a <script> tag."""
    # Escape </script> and HTML entities
    escaped = data.replace("</script>", "<\\/script>").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return escaped


def load_latest_results() -> list[dict]:
    """Load the most recent results JSONL file from RUNS_DIR."""
    if not RUNS_DIR.exists():
        print("ERROR: runs/ directory not found. Run the pipeline first.")
        sys.exit(1)

    manifest_path = RUNS_DIR / "manifest.json"
    if not manifest_path.exists():
        print("ERROR: no manifest.json found in runs/")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    runs = manifest.get("runs", [])
    if not runs:
        print("ERROR: no runs in manifest.")
        sys.exit(1)

    latest = runs[0]
    results_path = RUNS_DIR / latest["results_file"]
    if not results_path.exists():
        print(f"ERROR: results file not found: {results_path}")
        sys.exit(1)

    results = []
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    return results, manifest, latest


def build_dashboard(results: list[dict], manifest: dict, run_info: dict):
    """Write the dashboard HTML file."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "run": run_info,
        "manifest": manifest,
        "results": results,
    }
    json_str = json.dumps(data, indent=2)
    escaped = escape_json_for_html(json_str)
    html = TEMPLATE_HTML.replace("%JSON_DATA%", escaped)

    output_path = DOCS_DIR / "index.html"
    with open(output_path, "w") as f:
        f.write(html)

    print(f"✅ Dashboard built: {output_path.resolve()}")
    print(f"   Results: {len(results)} queries, "
          f"{sum(1 for r in results if r['passed'])} passed, "
          f"{sum(1 for r in results if not r['passed'])} failed")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Build Playground Eval Dashboard")
    parser.add_argument("--run", help="Specific run ID (default: latest)")
    parser.add_argument("--open", action="store_true", help="Open in browser")
    args = parser.parse_args()

    results, manifest, run_info = load_latest_results()
    path = build_dashboard(results, manifest, run_info)

    if args.open:
        # Try to open in Windows browser via WSL interop
        import subprocess
        wsl_path = str(path.resolve())
        # Convert to Windows path
        win_path = wsl_path.replace("/mnt/d/", "D:\\").replace("/", "\\")
        subprocess.run(["cmd.exe", "/c", "start", win_path], shell=True)
        print(f"   Opened: {win_path}")


if __name__ == "__main__":
    main()
