#!/usr/bin/env python3
"""
Version-agnostic dashboard builder for Copilot Eval.

Auto-detects the latest run version from manifest.json,
loads the corresponding JSONL, and rebuilds
langsmith-tool-evaluator/docs/index.html.

Follows DASHBOARD_CREATION.md rules:
- Uses current dashboard HTML as template (preserves all CSS/layout)
- Replaces records array via exact string positions (NOT regex)
- Single-line records (prevents ]; matching bug)
- All 8 mandatory sections preserved
- Comparison snapshot rebuilt with ALL versions (N-column)

Usage:
    python3 build_dashboard.py
"""

import json
import re
import collections
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASHBOARD = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "index.html"
RUNS_DIR = SCRIPT_DIR / "runs"
MANIFEST_FILE = RUNS_DIR / "manifest.json"

# ============================================================
# LEAK + QUALITY CLASSIFICATION (from DASHBOARD_CREATION.md §7)
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
# LOAD MANIFEST + LATEST DATA
# ============================================================

manifest = json.load(open(MANIFEST_FILE))
all_versions = sorted(manifest["runs"], key=lambda r: r["version"])
latest = all_versions[-1]
VERSION = latest["version"]
LATEST_FILE = RUNS_DIR / latest["file"]

print(f"Latest version: v{VERSION}")
print(f"Loading {LATEST_FILE.name}...")

records = [json.loads(l) for l in open(LATEST_FILE)]
print(f"  Loaded {len(records)} records")

# ============================================================
# CLASSIFY RECORDS
# ============================================================

for r in records:
    r["response_quality"] = classify_quality(r)
    r["info_leak"], r["leak_indicators"] = detect_leaks(r)

# ============================================================
# COMPUTE ALL DATA OBJECTS
# ============================================================

q_counts = collections.Counter(r["response_quality"] for r in records)
leak_count = sum(1 for r in records if r["info_leak"])
leak_type_counts = collections.Counter()
for r in records:
    for lt in r["leak_indicators"]:
        leak_type_counts[lt] += 1
no_tool = sum(1 for r in records if not r.get("tool_calls"))
tools_used_set = set()
for r in records:
    for tc in r.get("tool_calls", []) or []:
        tools_used_set.add(tc.get("tool", "?"))
avg_time = sum(r["response_time_seconds"] for r in records) / len(records)
total_time_min = round(sum(r["response_time_seconds"] for r in records) / 60 + (len(records) * 1) / 60, 1)

stats = {
    "success": q_counts.get("success", 0),
    "marginal": q_counts.get("marginal", 0),
    "fail": q_counts.get("fail", 0),
    "leak": leak_count,
}
leak_types = dict(leak_type_counts.most_common())
total_queries = len(records)

# catQuality
cat_quality = {}
for r in records:
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
for r in records:
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
for r in records:
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
for r in records:
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
        '"response":%s,'
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
        esc(r.get("response", "")),
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

# Determine old version from the HTML
old_version_match = re.search(r'Surana Polycot Test Suite v(\d+)', html)
old_version = int(old_version_match.group(1)) if old_version_match else VERSION - 1
print(f"  Old version in template: v{old_version}")

# ============================================================
# STEP 1: Replace records array (exact string positions)
# ============================================================

print("Replacing records array...")
rec_start = html.find('const records = [')
rec_end = html.find('];', rec_start) + 2
assert rec_start >= 0 and rec_end > 2, "records array not found!"
html = html[:rec_start] + records_js + html[rec_end:]
print(f"  Records replaced. New size: {len(html)} bytes")

# ============================================================
# STEP 2: Replace all 6 data objects
# ============================================================

def replace_const(html, name, new_js):
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
# STEP 3: Update hardcoded display values (regex-based)
# ============================================================

print("Updating hardcoded values...")

# Title: v{old} → v{new}
html = re.sub(
    r'Surana Polycot Test Suite v\d+',
    f'Surana Polycot Test Suite v{VERSION}',
    html
)

# Badge: Run v{old} · {date} · {N} queries · {time} min
run_date = datetime.now().strftime("%B %d, %Y")
# Get total elapsed time from manifest (query_time + 1s delay per query)
total_elapsed = round(sum(r["response_time_seconds"] for r in records) / 60 + len(records) / 60, 1)
new_badge = f'Run v{VERSION} &middot; {run_date} &middot; {total_queries} queries &middot; {total_elapsed:.1f} min'
html = re.sub(
    r'Run v\d+ &middot; .*? &middot; \d+ queries &middot; [\d.]+ min',
    new_badge,
    html
)

# Stats grid: replace numbers in the 6 stat cards
# Pattern: stat-card CLASS"><div class="number">VALUE</div><div class="label">LABEL</div>
def replace_stat_card(html, label, new_value):
    pattern = r'(<div class="stat-card \w+"><div class="number">)[^<]+(</div><div class="label">' + re.escape(label) + r'</div></div>)'
    new_html, n = re.subn(pattern, lambda m: m.group(1) + str(new_value) + m.group(2), html)
    assert n > 0, f"Stat card '{label}' not found!"
    return new_html

html = replace_stat_card(html, "Total Queries", total_queries)
html = replace_stat_card(html, "API Success", latest["success"])
html = replace_stat_card(html, "API Failed", latest["failed"])
html = replace_stat_card(html, "Avg Response", f"{latest['avg_response_time_seconds']:.1f}s")
html = replace_stat_card(html, "No Tool Called", no_tool)
html = replace_stat_card(html, "Tools Used", len(tools_used_set))

# Quality bucket counts and percentages
pct_success = round(stats["success"] / total_queries * 100)
pct_marginal = round(stats["marginal"] / total_queries * 100)
pct_fail = round(stats["fail"] / total_queries * 100)

# Quality buckets: replace count + percentage in each quality card
# Pattern: <div class="count">NN</div> followed by <div class="pct">NN% label</div>
for label_pct, new_count, new_pct in [
    ("success", stats["success"], pct_success),
    ("marginal", stats["marginal"], pct_marginal),
    ("fail", stats["fail"], pct_fail),
]:
    # Replace count
    # Find the quality-card div for this label, then replace its count
    # The count div appears right before the desc div
    old_count_pattern = rf'(<div class="quality-card {label_pct}">.*?<div class="count">)[^<]+(</div>)'
    html = re.sub(old_count_pattern, lambda m: m.group(1) + str(new_count) + m.group(2), html, flags=re.DOTALL)
    # Replace percentage
    old_pct_pattern = rf'(<div class="quality-card {label_pct}">.*?<div class="pct">)[^<]+(</div>)'
    html = re.sub(old_pct_pattern, lambda m: m.group(1) + str(new_pct) + f"% of queries" + m.group(2), html, flags=re.DOTALL)

# Leak banner: "X out of Y responses"
html = re.sub(
    r'\d+ out of \d+ responses expose internal system details',
    f'{leak_count} out of {total_queries} responses expose internal system details',
    html
)

# Filter tab "All (NN)"
html = re.sub(r'All \(\d+\)', f'All ({total_queries})', html)

# Raw data links: replace old version JSONL link with latest
old_jsonl_link = f'query_results_v{old_version}.jsonl'
new_jsonl_link = f'query_results_v{VERSION}.jsonl'
# Replace the primary link
html = re.sub(
    rf'raw\.githubusercontent\.com/navneetlearns/langsmith-tool-evaluator/main/runs/query_results_v\d+\.jsonl',
    f'raw.githubusercontent.com/navneetlearns/langsmith-tool-evaluator/main/runs/query_results_v{VERSION}.jsonl',
    html
)
# Replace the link text
html = re.sub(
    rf'&#128206; query_results_v\d+\.jsonl',
    f'&#128206; query_results_v{VERSION}.jsonl',
    html
)
# Update raw data description
html = re.sub(
    r'Full JSONL with all \d+ query traces.*?— v\d+ run.*?(?=</div>)',
    f'Full JSONL with all {total_queries} query traces (tool calls, SSE status, response text, timing, quality classification, leak detection) — v{VERSION} run ({run_date})',
    html
)

# Footer: Run v{old} → Run v{new}
html = re.sub(r'Run v\d+</p>', f'Run v{VERSION}</p>', html)

print("  All hardcoded values updated")

# ============================================================
# STEP 4: Rebuild comparison snapshot (N-column, all versions)
# ============================================================

print(f"Updating comparison snapshot ({len(all_versions)}-column)...")

# Category counts per version (v1=5, v2+=9)
def cats_for_version(v):
    return 5 if v["version"] == 1 else 9

# Compute total time for each version
for v in all_versions:
    n = v["total_queries"]
    avg = v["avg_response_time_seconds"]
    v["_total_time"] = round(n * avg / 60 + n / 60, 1)

# Improvement text (latest vs previous)
if len(all_versions) >= 2:
    prev = all_versions[-2]
    curr = all_versions[-1]
    avg_diff = ((curr["avg_response_time_seconds"] - prev["avg_response_time_seconds"]) / prev["avg_response_time_seconds"]) * 100

    parts = []
    if curr["failed"] == 0 and prev["failed"] > 0:
        parts.append(f"&#128640; 100% API success &mdash; zero failures (v{prev['version']} had {prev['failed']})")
    elif curr["failed"] < prev["failed"]:
        parts.append(f"&#128640; Failures reduced from {prev['failed']} to {curr['failed']}")
    elif curr["failed"] > prev["failed"]:
        parts.append(f"&#9888;&#65039; {curr['failed']} failure(s) this run (v{prev['version']} had {prev['failed']})")

    if avg_diff < 0:
        parts.append(f"Avg response improved from {prev['avg_response_time_seconds']:.1f}s to {curr['avg_response_time_seconds']:.1f}s ({abs(avg_diff):.0f}% faster)")
    elif avg_diff > 5:
        parts.append(f"Avg response {curr['avg_response_time_seconds']:.1f}s vs {prev['avg_response_time_seconds']:.1f}s in v{prev['version']} ({avg_diff:.0f}% slower)")
    else:
        parts.append(f"Avg response {curr['avg_response_time_seconds']:.1f}s vs {prev['avg_response_time_seconds']:.1f}s in v{prev['version']} (within noise)")

    improvement_text = " &mdash; ".join(parts)
else:
    improvement_text = f"&#128640; First run v{VERSION} complete"

# Build comparison HTML
cols = " ".join(["1fr"] * len(all_versions))
cards_html = ""
# Color rotation for old versions (latest gets green)
color_map = {1: "amber", 2: "primary"}  # v1=amber, v2=blue (or primary)
# All versions except latest cycle through amber → primary
for i, v in enumerate(all_versions):
    vn = v["version"]
    if vn == VERSION:
        color = "green"
    elif vn in color_map:
        color = color_map[vn]
    elif vn == 1:
        color = "amber"
    else:
        color = "primary"

    vdate = datetime.fromisoformat(v["timestamp"]).strftime("%B %d, %Y")
    cards_html += f"""      <div class="snapshot-card v{vn}">
        <h3>Run v{vn} &mdash; {vdate}</h3>
        <div class="snapshot-metrics">
          <div class="snapshot-metric"><span class="label">Queries</span><span class="value">{v['total_queries']}</span></div>
          <div class="snapshot-metric"><span class="label">API Success</span><span class="value">{v['success']}</span></div>
          <div class="snapshot-metric"><span class="label">Failed</span><span class="value">{v['failed']}</span></div>
          <div class="snapshot-metric"><span class="label">Avg Response</span><span class="value">{v['avg_response_time_seconds']:.1f}s</span></div>
          <div class="snapshot-metric"><span class="label">Categories</span><span class="value">{cats_for_version(v)}</span></div>
          <div class="snapshot-metric"><span class="label">Total Time</span><span class="value">{v['_total_time']:.1f} min</span></div>
        </div>
      </div>
"""

new_comparison = f"""<!-- COMPARISON SNAPSHOT: v1..v{VERSION} -->
  <div class="comparison-snapshot">
    <div class="snapshot-grid">
{cards_html}      <div class="snapshot-improvement">
        <strong>{improvement_text}</strong>
      </div>
    </div>
  </div>

  <!-- TOP STATS -->"""

# Replace old comparison snapshot
old_comparison_start = html.find("<!-- COMPARISON SNAPSHOT")
old_comparison_end = html.find("<!-- TOP STATS -->")
assert old_comparison_start >= 0 and old_comparison_end > old_comparison_start, "Comparison section not found"
html = html[:old_comparison_start] + new_comparison + html[old_comparison_end:]
print(f"  Comparison snapshot updated ({len(all_versions)}-column)")

# ============================================================
# STEP 5: Update comparison CSS (N-column grid + version colors)
# ============================================================

# Replace grid-template-columns for snapshot-grid
html = re.sub(
    r'\.snapshot-grid\s*\{[^}]*grid-template-columns:\s*[^;]+;',
    f'.snapshot-grid {{\n  display: grid;\n  grid-template-columns: {" ".join(["1fr"] * len(all_versions))};',
    html
)

# Remove old version-specific snapshot card CSS rules (v1, v2, v3...)
html = re.sub(r'\.snapshot-card\.v\d+\s*\{[^}]+\}', '', html)
html = re.sub(r'\.snapshot-card\.v\d+\s*h3\s*\{[^}]+\}', '', html)
html = re.sub(r'\.snapshot-card\.v\d+\s*\.snapshot-metric\s*\.value\s*\{[^}]+\}', '', html)

# Add unified CSS for all versions
version_css = ""
color_css_map = {1: "amber", 2: "primary"}
for v in all_versions:
    vn = v["version"]
    if vn == VERSION:
        color = "green"
    elif vn in color_css_map:
        color = color_css_map[vn]
    elif vn == 1:
        color = "amber"
    else:
        color = "primary"
    if vn != 1:  # v1 already has border + h3 from original CSS
        version_css += f".snapshot-card.v{vn} {{ border-top: 4px solid var(--{color}); }}\n"
        version_css += f".snapshot-card.v{vn} h3 {{ color: var(--{color}); }}\n"
    version_css += f".snapshot-card.v{vn} .snapshot-metric .value {{ color: var(--{color}); }}\n"

# Insert before .snapshot-improvement
html = html.replace(".snapshot-improvement {", version_css + "\n.snapshot-improvement {")

print("  Comparison CSS updated")

# ============================================================
# WRITE OUTPUT
# ============================================================

print(f"Writing dashboard to {DASHBOARD}...")
DASHBOARD.write_text(html)
print(f"  Final size: {len(html)} bytes")
print("  DONE!")

# ============================================================
# VERIFICATION CHECKS
# ============================================================

print("\n=== VERIFICATION ===")

# Check records count
rec_start = html.find('const records = [')
rec_end_check = html.find('];', rec_start) + 2
rec_text = html[rec_start:rec_end_check]
qi_count = rec_text.count('"query_index"')
assert qi_count == total_queries, f"Records count mismatch: {qi_count} != {total_queries}"
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
assert f"v{VERSION}</title>" in html, "Title not updated"
assert f"Run v{VERSION}</p>" in html, "Footer not updated"
print(f"  [OK] Title: v{VERSION}")
print(f"  [OK] Footer: Run v{VERSION}")

# Check comparison section has N cards
card_count = html.count("snapshot-card v")
assert card_count == len(all_versions), f"Expected {len(all_versions)} comparison cards, found {card_count}"
print(f"  [OK] Comparison: {card_count} cards (v1..v{VERSION})")

print("\n  ALL CHECKS PASSED")