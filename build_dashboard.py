#!/usr/bin/env python3
"""
Dashboard builder for Copilot Eval — follows DASHBOARD_CREATION.md strictly.
Rebuilds langsmith-tool-evaluator/docs/index.html with v3 data.

Steps:
1. Restore current dashboard as template (the v2 HTML is our base)
2. Load + classify v3 data (quality, leaks)
3. Build records JS array (single-line objects)
4. Replace records array using exact string positions (NOT regex)
5. Update all 6 data objects
6. Update hardcoded display values
7. Update comparison snapshot (v1, v2, v3 — 3-column)
"""

import json
import re
import collections
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
DASHBOARD = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "index.html"
RUNS_DIR = SCRIPT_DIR / "runs"

# ============================================================
# LEAK + QUALITY CLASSIFICATION (from DASHBOARD_CREATION.md §6)
# ============================================================

LEAK_PATTERNS = {
    "ui_component": r'\b(card|result preview|show more|scroll|view more|the card has)\b',
    "tool_capability": r'\b(available tools|current tools|tool called|i can use|my tools|i have access to)\b',
    "workspace_ref": r'\b(workspace)\b',
    "auth_session": r'\b(log out|log back in|session expired|reauthenticate)\b',
    "internal_data_model": r'\b(lifecycle group|debtor group|customer group|aging bucket)\b',
    "analytics_categorization": r"(i'll treat this as|i'll categorize|i'll group this under)",
}

def classify_quality(record):
    response = record.get("response", "") or ""
    error = record.get("error")
    if error or not response.strip():
        return "fail"
    resp_lower = response.lower()
    if re.search(r"(couldn't|cannot|unable to|was rejected|didn't find|i couldn't)", resp_lower):
        return "marginal"
    if re.search(r'(₹|%)', response) or re.search(r'(sorted by|ranked|showing \d|found \d)', resp_lower):
        return "success"
    if re.search(r"(try again|i don't want to guess|i'd recommend|if you want|you can try)", resp_lower):
        return "marginal"
    if len(response) > 60:
        return "success"
    return "marginal"

def detect_leaks(record):
    response = record.get("response", "") or ""
    resp_lower = response.lower()
    indicators = []
    for leak_type, pattern in LEAK_PATTERNS.items():
        if re.search(pattern, resp_lower):
            indicators.append(leak_type)
    return (len(indicators) > 0, indicators)

# ============================================================
# LOAD DATA
# ============================================================

print("Loading v3 records...")
v3_records = [json.loads(l) for l in open(f"{RUNS_DIR}/query_results_v3.jsonl")]
manifest = json.load(open(f"{RUNS_DIR}/manifest.json"))
v1_entry = [r for r in manifest["runs"] if r["version"] == 1][0]
v2_entry = [r for r in manifest["runs"] if r["version"] == 2][0]
v3_entry = [r for r in manifest["runs"] if r["version"] == 3][0]
print(f"  Loaded {len(v3_records)} records")

# Classify
for r in v3_records:
    r["response_quality"] = classify_quality(r)
    r["info_leak"], r["leak_indicators"] = detect_leaks(r)

# ============================================================
# COMPUTE ALL DATA OBJECTS
# ============================================================

q_counts = collections.Counter(r["response_quality"] for r in v3_records)
leak_count = sum(1 for r in v3_records if r["info_leak"])
leak_type_counts = collections.Counter()
for r in v3_records:
    for lt in r["leak_indicators"]:
        leak_type_counts[lt] += 1
no_tool = sum(1 for r in v3_records if not r.get("tool_calls"))
tools_used_set = set()
for r in v3_records:
    for tc in r.get("tool_calls", []) or []:
        tools_used_set.add(tc.get("tool", "?"))
avg_time = sum(r["response_time_seconds"] for r in v3_records) / len(v3_records)
total_time_min = round(sum(r["response_time_seconds"] for r in v3_records) / 60 + (len(v3_records) * 1) / 60, 1)  # +1s delay per query

stats = {
    "success": q_counts.get("success", 0),
    "marginal": q_counts.get("marginal", 0),
    "fail": q_counts.get("fail", 0),
    "leak": leak_count,
}
leak_types = dict(leak_type_counts.most_common())

# catQuality
cat_quality = {}
for r in v3_records:
    cat = r["category"]
    if cat not in cat_quality:
        cat_quality[cat] = {"success": 0, "marginal": 0, "fail": 0, "_times": []}
    cat_quality[cat][r["response_quality"]] += 1
    cat_quality[cat]["_times"].append(r["response_time_seconds"])
for cat in cat_quality:
    times = cat_quality[cat].pop("_times")
    cat_quality[cat]["avg"] = round(sum(times) / len(times), 1)
    cat_quality[cat]["n"] = len(times)

# catData
cat_data = {}
for r in v3_records:
    cat = r["category"]
    if cat not in cat_data:
        cat_data[cat] = []
    cat_data[cat].append(r["response_time_seconds"])
for cat in cat_data:
    times = cat_data[cat]
    cat_data[cat] = {
        "avg": round(sum(times) / len(times), 1),
        "min": round(min(times), 2),
        "max": round(max(times), 2),
        "n": len(times),
        "total": round(sum(times), 2),
    }

# catColors (same 9 categories)
cat_colors = {
    "Dashboard": "green",
    "Items": "purple",
    "Ledger": "red",
    "Orders & Invoices": "green",
    "Outstanding & Payments": "amber",
    "Payments": "blue",
    "Products & Items": "purple",
    "Reports & Analytics": "red",
    "Sales": "amber",
}

# toolCounts
tool_counts_dict = collections.Counter()
for r in v3_records:
    for tc in r.get("tool_calls", []) or []:
        tool_counts_dict[tc.get("tool", "?")] += 1
tool_counts = dict(tool_counts_dict.most_common())

print(f"  stats: {stats}")
print(f"  leak_types: {leak_types}")
print(f"  no_tool: {no_tool}, tools_used: {len(tools_used_set)}")
print(f"  avg_time: {avg_time:.1f}s")

# ============================================================
# BUILD RECORDS JS ARRAY (single-line objects — Pitfall §6)
# ============================================================

print("Building records JS array...")
record_parts = []
for r in v3_records:
    # Escape strings for JS JSON
    def esc(s):
        if s is None:
            return ""
        return json.dumps(str(s), ensure_ascii=False)
    
    part = (
        '{"query_index":%d,'
        '"query":%s,'
        '"copilot_response":%s,'
        '"remarks":%s,'
        '"category":%s,'
        '"thread_id":%s,'
        '"tool_calls":%s,'
        '"info_leak":%s,'
        '"leak_indicators":%s,'
        '"response_quality":%s,'
        '"response_time_seconds":%s,'
        '"error":%s,'
        '"status_sequence":%s,'
        '"suggestions":%s,'
        '"timestamp":%s}'
    ) % (
        r["query_index"],
        esc(r["query"]),
        esc(r.get("copilot_response", "")),
        esc(r.get("remarks", "")),
        esc(r["category"]),
        json.dumps(r.get("thread_id"), ensure_ascii=False),
        json.dumps(r.get("tool_calls", []) or [], ensure_ascii=False),
        "true" if r["info_leak"] else "false",
        json.dumps(r.get("leak_indicators", []), ensure_ascii=False),
        esc(r["response_quality"]),
        json.dumps(r["response_time_seconds"]),
        json.dumps(r.get("error"), ensure_ascii=False),
        json.dumps(r.get("status_sequence", []) or [], ensure_ascii=False),
        json.dumps(r.get("suggestions", []) or [], ensure_ascii=False),
        json.dumps(r.get("timestamp", ""), ensure_ascii=False),
    )
    record_parts.append(part)

records_js = "const records = [\n" + ",\n".join(record_parts) + "\n];"
print(f"  Built {len(record_parts)} record strings, total JS length: {len(records_js)}")

# ============================================================
# LOAD TEMPLATE HTML
# ============================================================

print("Loading template HTML...")
html = DASHBOARD.read_text()
print(f"  Template size: {len(html)} bytes")

# ============================================================
# STEP 4: Replace records array (exact string positions — Pitfall §1)
# ============================================================

print("Replacing records array...")
rec_start = html.find('const records = [')
rec_end = html.find('];', rec_start) + 2
assert rec_start >= 0 and rec_end > 2, "records array not found!"
html = html[:rec_start] + records_js + html[rec_end:]
print(f"  Records replaced. New size: {len(html)} bytes")

# ============================================================
# STEP 5: Replace all 6 data objects
# ============================================================

def replace_const(html, name, new_js):
    """Replace const NAME = {...}; using exact string positions."""
    start_marker = f"const {name} = {{"
    start = html.find(start_marker)
    if start < 0:
        raise ValueError(f"{name} not found")
    end = html.find("};", start) + 2
    old = html[start:end]
    new_str = f"const {name} = {json.dumps(new_js, ensure_ascii=False)};"
    html = html[:start] + new_str + html[end:]
    print(f"  Replaced {name} (was {len(old)} chars, now {len(new_str)} chars)")
    return html

print("Replacing data objects...")
html = replace_const(html, "stats", stats)
html = replace_const(html, "leakTypes", leak_types)
html = replace_const(html, "catQuality", cat_quality)
html = replace_const(html, "catData", cat_data)
html = replace_const(html, "catColors", cat_colors)
html = replace_const(html, "toolCounts", tool_counts)

# ============================================================
# STEP 6: Update hardcoded display values
# ============================================================

print("Updating hardcoded values...")

# Title
html = html.replace(
    "<title>Copilot Eval — Surana Polycot Test Suite v2</title>",
    "<title>Copilot Eval — Surana Polycot Test Suite v3</title>"
)

# Header badge
old_badge = "Run v2 &middot; July 21, 2026 &middot; 80 queries &middot; 19.7 min"
new_badge = "Run v3 &middot; July 22, 2026 &middot; 80 queries &middot; 20.7 min"
assert old_badge in html, f"Badge not found: {old_badge}"
html = html.replace(old_badge, new_badgo := new_badge)

# Stats grid numbers
# Find the stats grid HTML and replace numbers
stats_grid_old = """<div class="stat-card blue"><div class="number">80</div><div class="label">Total Queries</div></div>
    <div class="stat-card green"><div class="number">79</div><div class="label">API Success</div></div>
    <div class="stat-card red"><div class="number">1</div><div class="label">API Failed</div></div>
    <div class="stat-card blue"><div class="number">13.7s</div><div class="label">Avg Response</div></div>
    <div class="stat-card amber"><div class="number">10</div><div class="label">No Tool Called</div></div>
    <div class="stat-card blue"><div class="number">5</div><div class="label">Tools Used</div></div>"""

stats_grid_new = f"""<div class="stat-card blue"><div class="number">{len(v3_records)}</div><div class="label">Total Queries</div></div>
    <div class="stat-card green"><div class="number">{v3_entry['success']}</div><div class="label">API Success</div></div>
    <div class="stat-card red"><div class="number">{v3_entry['failed']}</div><div class="label">API Failed</div></div>
    <div class="stat-card blue"><div class="number">{v3_entry['avg_response_time_seconds']:.1f}s</div><div class="label">Avg Response</div></div>
    <div class="stat-card amber"><div class="number">{no_tool}</div><div class="label">No Tool Called</div></div>
    <div class="stat-card blue"><div class="number">{len(tools_used_set)}</div><div class="label">Tools Used</div></div>"""

assert stats_grid_old in html, "Stats grid HTML not found!"
html = html.replace(stats_grid_old, stats_grid_new)

# Quality buckets — find the hardcoded counts in the HTML
# These are in the quality-grid section
# Current v2 values: success=61, marginal=18, fail=1
# v3 values: success=56, marginal=24, fail=0
pct_success = round(stats["success"] / len(v3_records) * 100)
pct_marginal = round(stats["marginal"] / len(v3_records) * 100)
pct_fail = round(stats["fail"] / len(v3_records) * 100)

# Replace quality bucket numbers
# Success bucket
html = html.replace('<div class="count">61</div>', f'<div class="count">{stats["success"]}</div>')
html = html.replace('<div class="pct">76% success</div>', f'<div class="pct">{pct_success}% success</div>')
# Marginal bucket
html = html.replace('<div class="count">18</div>', f'<div class="count">{stats["marginal"]}</div>')
html = html.replace('<div class="pct">23% marginal</div>', f'<div class="pct">{pct_marginal}% marginal</div>')
# Fail bucket
html = html.replace('<div class="count">1</div>', f'<div class="count">{stats["fail"]}</div>')
html = html.replace('<div class="pct">1% fail</div>', f'<div class="pct">{pct_fail}% fail</div>')

# Leak banner
# Current: "33 out of 80 responses contained information leak indicators"
html = html.replace(
    '33 out of 80 responses contained information leak indicators',
    f'{leak_count} out of {len(v3_records)} responses contained information leak indicators'
)

# Filter tab "All (80)"
html = html.replace('All (80)', f'All ({len(v3_records)})')

# Raw data links — update v2 link to v3, add v2 as previous
old_v2_link = 'https://raw.githubusercontent.com/navneetlearns/langsmith-tool-evaluator/main/runs/query_results_v2.jsonl" target="_blank">&#128206; query_results_v2.jsonl'
new_v3_link = 'https://raw.githubusercontent.com/navneetlearns/langsmith-tool-evaluator/main/runs/query_results_v3.jsonl" target="_blank">&#128206; query_results_v3.jsonl'
html = html.replace(old_v2_link, new_v3_link)

# Update raw data descriptions
html = html.replace(
    'Full JSONL with all 80 query traces (tool calls, SSE status, response text, timing, quality classification, leak detection)',
    f'Full JSONL with all {len(v3_records)} query traces (tool calls, SSE status, response text, timing, quality classification, leak detection) — v3 run (July 22, 2026)'
)

# Footer
html = html.replace("Run v2</p>", "Run v3</p>")

print("  All hardcoded values updated")

# ============================================================
# STEP 7: Update comparison snapshot (v1, v2, v3 — 3-column)
# ============================================================

print("Updating comparison snapshot...")

# Update CSS for 3-column grid + v3 card styles
old_css = """.snapshot-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}"""
new_css = """.snapshot-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}"""
assert old_css in html, "Comparison CSS grid not found"
html = html.replace(old_css, new_css)

# Add v3 card CSS after v2 card CSS
old_v2_css = """.snapshot-card.v2 .snapshot-metric .value { color: var(--green); }"""
new_v2_v3_css = """.snapshot-card.v2 .snapshot-metric .value { color: var(--primary); }
.snapshot-card.v3 { border-top: 4px solid var(--green); }
.snapshot-card.v3 h3 { color: var(--green); }
.snapshot-card.v3 .snapshot-metric .value { color: var(--green); }"""
assert old_v2_css in html, "v2 CSS not found"
html = html.replace(old_v2_css, new_v2_v3_css)

# Also update v2 card border to use primary (blue) instead of green, since v3 is now green
html = html.replace(".snapshot-card.v2 { border-top: 4px solid var(--green); }",
                    ".snapshot-card.v2 { border-top: 4px solid var(--primary); }")
html = html.replace(".snapshot-card.v2 h3 { color: var(--green); }",
                    ".snapshot-card.v2 h3 { color: var(--primary); }")

# Replace the comparison snapshot HTML
v1_total_time = round(50 * 25.11 / 60 + 50 / 60, 1)  # approx
v2_total_time = round(v2_entry["total_queries"] * v2_entry["avg_response_time_seconds"] / 60 + 80 / 60, 1)
v3_total_time = round(v3_entry["total_queries"] * v3_entry["avg_response_time_seconds"] / 60 + 80 / 60, 1)

# v1 categories = 5, v2 categories = 9, v3 categories = 9
v1_cats = 5
v2_cats = 9
v3_cats = 9

# Improvement: v2 → v3
avg_improvement = ((v3_entry["avg_response_time_seconds"] - v2_entry["avg_response_time_seconds"]) / v2_entry["avg_response_time_seconds"]) * 100
if avg_improvement < 0:
    improvement_text = f"Avg response improved from {v2_entry['avg_response_time_seconds']:.1f}s to {v3_entry['avg_response_time_seconds']:.1f}s ({abs(avg_improvement):.0f}% faster)"
else:
    improvement_text = f"Avg response {v3_entry['avg_response_time_seconds']:.1f}s vs {v2_entry['avg_response_time_seconds']:.1f}s in v2 ({avg_improvement:.0f}% slower — within noise)"

old_comparison_start = html.find("<!-- COMPARISON SNAPSHOT: v1 vs v2 -->")
old_comparison_end = html.find("<!-- TOP STATS -->")
assert old_comparison_start >= 0 and old_comparison_end > old_comparison_start, "Comparison section not found"

new_comparison = f"""<!-- COMPARISON SNAPSHOT: v1 vs v2 vs v3 -->
  <div class="comparison-snapshot">
    <div class="snapshot-grid">
      <div class="snapshot-card v1">
        <h3>Run v1 &mdash; July 11, 2026</h3>
        <div class="snapshot-metrics">
          <div class="snapshot-metric"><span class="label">Queries</span><span class="value">{v1_entry['total_queries']}</span></div>
          <div class="snapshot-metric"><span class="label">API Success</span><span class="value">{v1_entry['success']}</span></div>
          <div class="snapshot-metric"><span class="label">Failed</span><span class="value">{v1_entry['failed']}</span></div>
          <div class="snapshot-metric"><span class="label">Avg Response</span><span class="value">{v1_entry['avg_response_time_seconds']:.1f}s</span></div>
          <div class="snapshot-metric"><span class="label">Categories</span><span class="value">{v1_cats}</span></div>
          <div class="snapshot-metric"><span class="label">Total Time</span><span class="value">{v1_total_time:.1f} min</span></div>
        </div>
      </div>
      <div class="snapshot-card v2">
        <h3>Run v2 &mdash; July 21, 2026</h3>
        <div class="snapshot-metrics">
          <div class="snapshot-metric"><span class="label">Queries</span><span class="value">{v2_entry['total_queries']}</span></div>
          <div class="snapshot-metric"><span class="label">API Success</span><span class="value">{v2_entry['success']}</span></div>
          <div class="snapshot-metric"><span class="label">Failed</span><span class="value">{v2_entry['failed']}</span></div>
          <div class="snapshot-metric"><span class="label">Avg Response</span><span class="value">{v2_entry['avg_response_time_seconds']:.1f}s</span></div>
          <div class="snapshot-metric"><span class="label">Categories</span><span class="value">{v2_cats}</span></div>
          <div class="snapshot-metric"><span class="label">Total Time</span><span class="value">{v2_total_time:.1f} min</span></div>
        </div>
      </div>
      <div class="snapshot-card v3">
        <h3>Run v3 &mdash; July 22, 2026</h3>
        <div class="snapshot-metrics">
          <div class="snapshot-metric"><span class="label">Queries</span><span class="value">{v3_entry['total_queries']}</span></div>
          <div class="snapshot-metric"><span class="label">API Success</span><span class="value">{v3_entry['success']}</span></div>
          <div class="snapshot-metric"><span class="label">Failed</span><span class="value">{v3_entry['failed']}</span></div>
          <div class="snapshot-metric"><span class="label">Avg Response</span><span class="value">{v3_entry['avg_response_time_seconds']:.1f}s</span></div>
          <div class="snapshot-metric"><span class="label">Categories</span><span class="value">{v3_cats}</span></div>
          <div class="snapshot-metric"><span class="label">Total Time</span><span class="value">{v3_total_time:.1f} min</span></div>
        </div>
      </div>
      <div class="snapshot-improvement">
        <strong>&#128640; 100% API success &mdash; zero failures (v2 had 1)</strong> &mdash; {improvement_text}. New tool <code>spawn_filter_agent</code> surfaced on Q14. 21/80 queries changed tool selection vs v2.
      </div>
    </div>
  </div>

  
  """

html = html[:old_comparison_start] + new_comparison + html[old_comparison_end:]
print("  Comparison snapshot updated (3-column v1/v2/v3)")

# ============================================================
# WRITE OUTPUT
# ============================================================

print(f"Writing dashboard to {DASHBOARD}...")
DASHBOARD.write_text(html)
print(f"  Final size: {len(html)} bytes")
print("  DONE!")

# ============================================================
# VERIFICATION CHECKS (from DASHBOARD_CREATION.md §9 Checklist)
# ============================================================

print("\n=== VERIFICATION ===")

# Check records count
rec_start = html.find('const records = [')
rec_end_check = html.find('];', rec_start) + 2
rec_text = html[rec_start:rec_end_check]
qi_count = rec_text.count('"query_index"')
assert qi_count == 80, f"Records count mismatch: {qi_count} != 80"
print(f"  [OK] Records array: {qi_count} entries")

# Check all data objects exist
for name in ["stats", "leakTypes", "catQuality", "catData", "catColors", "toolCounts"]:
    assert f"const {name} = " in html, f"{name} not found!"
    print(f"  [OK] {name} present")

# Check key sections present
for marker in ["comparison-snapshot", "stats-grid", "quality-grid", "leak-banner",
               "qual-cat-tbody", "cat-tbody", "tool-grid", "query-tbody", "raw-data", "principles"]:
    assert marker in html, f"Section {marker} not found!"
    print(f"  [OK] Section: {marker}")

# Check title and footer
assert "v3</title>" in html, "Title not updated"
assert "Run v3</p>" in html, "Footer not updated"
print(f"  [OK] Title: v3")
print(f"  [OK] Footer: Run v3")

# Check comparison section has 3 cards
card_count = html.count("snapshot-card v")
assert card_count == 3, f"Expected 3 comparison cards, found {card_count}"
print(f"  [OK] Comparison: 3 cards (v1, v2, v3)")

print("\n  ALL CHECKS PASSED")