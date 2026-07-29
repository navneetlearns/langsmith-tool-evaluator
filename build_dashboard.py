#!/usr/bin/env python3
"""
Multi-account dashboard builder for Copilot Eval.

Auto-detects the latest run version from accounts/<name>/runs/manifest.json,
loads the corresponding JSONL, and rebuilds the dashboard HTML.

New metrics (v2):
  - Tool Selection Accuracy: % of queries where actual tool matches expected_tool
  - Step Count per Completion: avg/min/max steps per query

Usage:
    python3 build_dashboard.py --account surana
    python3 build_dashboard.py --account unifoods
"""

import json
import re
import collections
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()

# ============================================================
# CONFIG LOADER
# ============================================================

def load_account_config(account_name: str) -> dict:
    config_path = SCRIPT_DIR / "accounts" / account_name / "config.yaml"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    cfg = {}
    current_section = cfg
    with open(config_path) as f:
        for raw_line in f:
            line = raw_line.rstrip()
            if not line or line.startswith("#"):
                continue
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            # Strip inline comments (everything after # preceded by space)
            if "#" in value:
                hash_pos = value.find("#")
                if hash_pos > 0 and value[hash_pos-1] == " ":
                    value = value[:hash_pos].strip().strip('"').strip("'")
            if indent == 0:
                current_section = cfg
                if value == "":
                    current_section[key] = {}
                    current_section = current_section[key]
                else:
                    current_section[key] = value
            else:
                if value == "":
                    if key not in current_section:
                        current_section[key] = {}
                    current_section = current_section[key]
                else:
                    current_section[key] = value

    for k in ("sse_timeout", "sse_read_timeout"):
        if k in cfg:
            cfg[k] = int(cfg[k])

    cfg["account_dir"] = SCRIPT_DIR / "accounts" / account_name
    cfg["runs_dir"] = cfg["account_dir"] / "runs"
    cfg["manifest_file"] = cfg["runs_dir"] / "manifest.json"
    return cfg


# ============================================================
# LEAK + QUALITY CLASSIFICATION
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
# CATEGORY COLOR ASSIGNMENT  (dynamic — handles any category set)
# ============================================================

CAT_COLOR_POOL = ["green", "amber", "red", "blue", "purple", "teal", "orange", "pink", "indigo",
                  "cyan", "lime", "brown", "grey"]


def assign_category_colors(categories: list[str]) -> dict:
    """Assign colors from the pool, cycling if more categories than colors."""
    return {cat: CAT_COLOR_POOL[i % len(CAT_COLOR_POOL)] for i, cat in enumerate(sorted(categories))}


# ============================================================
# MAIN BUILD LOGIC
# ============================================================

def main():
    # Parse --account flag
    account = "surana"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--account" and i + 1 < len(args):
            account = args[i + 1]
        elif arg.startswith("--account="):
            account = arg.split("=", 1)[1]

    cfg = load_account_config(account)
    account_name = cfg["account_name"]

    DASHBOARD_DIR = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / account
    DASHBOARD_FILE = DASHBOARD_DIR / "index.html"
    TEMPLATE = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "template.html"  # base HTML structure

    RUNS_DIR = cfg["runs_dir"]
    MANIFEST_FILE = cfg["manifest_file"]

    # ============================================================
    # LOAD MANIFEST + LATEST DATA
    # ============================================================

    manifest = json.load(open(MANIFEST_FILE))
    all_versions = sorted(manifest["runs"], key=lambda r: r["version"])
    latest = all_versions[-1]
    VERSION = latest["version"]
    LATEST_FILE = RUNS_DIR / latest["file"]

    print(f"Account: {account} ({account_name})")
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
        # Compute step_count from status_sequence if not already present
        if not r.get("step_count") and r.get("status_sequence"):
            r["step_count"] = len(r["status_sequence"])

    # ============================================================
    # COMPUTE ALL DATA OBJECTS
    # ============================================================

    total_queries = len(records)
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
    total_time_min = round(sum(r["response_time_seconds"] for r in records) / 60 + len(records) / 60, 1)

    stats = {
        "success": q_counts.get("success", 0),
        "marginal": q_counts.get("marginal", 0),
        "fail": q_counts.get("fail", 0),
        "leak": leak_count,
    }

    leak_types = dict(leak_type_counts.most_common())

    # ---- catQuality ----
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

    # ---- catData (response time) ----
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

    # ---- catColors (dynamic) ----
    cat_colors = assign_category_colors(list(cat_quality.keys()))

    # ---- toolCounts ----
    tool_counts_dict = collections.Counter()
    for r in records:
        for tc in r.get("tool_calls", []) or []:
            tool_counts_dict[tc.get("tool", "?")] += 1
    tool_counts = dict(tool_counts_dict.most_common())

    # ---- NEW: Tool Selection Accuracy ----
    queries_with_expected = [r for r in records if r.get("expected_tool")]
    correct_tool = 0
    cat_tool_accuracy = {}
    for r in records:
        cat = r["category"]
        if cat not in cat_tool_accuracy:
            cat_tool_accuracy[cat] = {"total": 0, "correct": 0}

        expected = r.get("expected_tool")
        if expected:
            cat_tool_accuracy[cat]["total"] += 1
            actual_tools = [tc.get("tool", "") for tc in r.get("tool_calls", [])]

            # Handle multi-tool sequences (e.g. "get_channel_data → search_threads")
            if "→" in expected:
                expected_tools = [t.strip() for t in expected.split("→")]
                # Check if ALL expected tools were called (strict match)
                if all(et in actual_tools for et in expected_tools):
                    correct_tool += 1
                    cat_tool_accuracy[cat]["correct"] += 1
            else:
                if expected in actual_tools:
                    correct_tool += 1
                    cat_tool_accuracy[cat]["correct"] += 1

    tool_accuracy = {
        "correct": correct_tool,
        "total_with_expected": len(queries_with_expected),
        "pct": round(correct_tool / len(queries_with_expected) * 100, 1) if queries_with_expected else 0,
    }

    # Per-category accuracy pct
    for cat in cat_tool_accuracy:
        d = cat_tool_accuracy[cat]
        d["pct"] = round(d["correct"] / d["total"] * 100, 1) if d["total"] > 0 else None

    # ---- NEW: Step Count ----
    step_counts = [r.get("step_count", 0) for r in records]
    step_stats = {
        "avg": round(sum(step_counts) / len(step_counts), 1),
        "min": min(step_counts),
        "max": max(step_counts),
        "median": round(sorted(step_counts)[len(step_counts) // 2], 1),
    }

    cat_step_data = {}
    for r in records:
        cat = r["category"]
        if cat not in cat_step_data:
            cat_step_data[cat] = []
        cat_step_data[cat].append(r.get("step_count", 0))
    for cat in cat_step_data:
        steps = cat_step_data[cat]
        cat_step_data[cat] = {
            "avg": round(sum(steps) / len(steps), 1),
            "min": min(steps),
            "max": max(steps),
            "n": len(steps),
        }

    print(f"  stats: {stats}")
    print(f"  tool_accuracy: {tool_accuracy}")
    print(f"  step_stats: {step_stats}")
    print(f"  tools_used: {len(tools_used_set)}, no_tool: {no_tool}")

    # ============================================================
    # BUILD RECORDS JS ARRAY  (single-line objects)
    # ============================================================

    print("Building records JS array...")
    record_parts = []
    for r in records:
        part = (
            '{"query_index":%d,'
            '"query":%s,'
            '"copilot_response":%s,'
            '"remarks":%s,'
            '"category":%s,'
            '"expected_tool":%s,'
            '"thread_id":%s,'
            '"tool_calls":%s,'
            '"response":%s,'
            '"info_leak":%s,'
            '"leak_indicators":%s,'
            '"response_quality":%s,'
            '"response_time_seconds":%s,'
            '"step_count":%s,'
            '"error":%s,'
            '"status_sequence":%s,'
            '"suggestions":%s,'
            '"timestamp":%s}'
        ) % (
            r["query_index"],
            json.dumps(str(r["query"]), ensure_ascii=False),
            json.dumps(str(r.get("copilot_response", "")), ensure_ascii=False),
            json.dumps(str(r.get("remarks", "")), ensure_ascii=False),
            json.dumps(str(r["category"]), ensure_ascii=False),
            json.dumps(r.get("expected_tool"), ensure_ascii=False),
            json.dumps(r.get("thread_id"), ensure_ascii=False),
            json.dumps(r.get("tool_calls", []) or [], ensure_ascii=False),
            json.dumps(str(r.get("response", "")), ensure_ascii=False),
            "true" if r["info_leak"] else "false",
            json.dumps(r.get("leak_indicators", []), ensure_ascii=False),
            json.dumps(str(r["response_quality"]), ensure_ascii=False),
            json.dumps(r["response_time_seconds"]),
            json.dumps(r.get("step_count", 0)),
            json.dumps(r.get("error"), ensure_ascii=False),
            json.dumps(r.get("status_sequence", []) or [], ensure_ascii=False),
            json.dumps(r.get("suggestions", []) or [], ensure_ascii=False),
            json.dumps(r.get("timestamp", ""), ensure_ascii=False),
        )
        record_parts.append(part)

    records_js = "const records = [\n" + ",\n".join(record_parts) + "\n];"
    print(f"  Built {len(record_parts)} record strings, total JS length: {len(records_js)}")

    # ============================================================
    # LOAD TEMPLATE HTML  (use Surana v4 as structural template)
    # ============================================================

    print(f"Loading template HTML from {TEMPLATE}...")
    html = TEMPLATE.read_text()
    print(f"  Template size: {len(html)} bytes")

    # ============================================================
    # STEP 1: Replace records array
    # ============================================================

    print("Replacing records array...")
    rec_start = html.find('const records = [')
    rec_end = html.find('];', rec_start) + 2
    assert rec_start >= 0 and rec_end > 2, "records array not found!"
    html = html[:rec_start] + records_js + html[rec_end:]
    print(f"  Records replaced. New size: {len(html)} bytes")

    # ============================================================
    # STEP 2: Replace all data objects
    # ============================================================

    def replace_const(html, name, new_js):
        start_marker = f"const {name} = {{"
        start = html.find(start_marker)
        if start < 0:
            raise ValueError(f"{name} not found in template")
        end = html.find("};", start) + 2
        new_str = f"const {name} = {json.dumps(new_js, ensure_ascii=False)};"
        html = html[:start] + new_str + html[end:]
        print(f"  Replaced {name}")
        return html

    print("Replacing data objects...")
    html = replace_const(html, "stats", stats)
    html = replace_const(html, "leakTypes", leak_types)
    html = replace_const(html, "catQuality", cat_quality)
    html = replace_const(html, "catData", cat_data)
    html = replace_const(html, "catColors", cat_colors)
    html = replace_const(html, "toolCounts", tool_counts)

    # ---- NEW data objects ----
    # Insert after catColors
    insert_after = html.find("const catColors = {")
    insert_after = html.find("};", insert_after) + 2

    new_objects_js = f"""
const toolAccuracy = {json.dumps(tool_accuracy, ensure_ascii=False)};
const catToolAccuracy = {json.dumps(cat_tool_accuracy, ensure_ascii=False)};
const stepStats = {json.dumps(step_stats, ensure_ascii=False)};
const catStepData = {json.dumps(cat_step_data, ensure_ascii=False)};
"""
    html = html[:insert_after] + new_objects_js + html[insert_after:]
    print("  Inserted new data objects: toolAccuracy, catToolAccuracy, stepStats, catStepData")

    # ============================================================
    # STEP 3: Update hardcoded display values
    # ============================================================

    print("Updating hardcoded values...")

    # Title
    html = re.sub(
        r'<title>.*?</title>',
        f'<title>Copilot Eval \u2014 {account_name} Test Suite v{VERSION}</title>',
        html
    )

    # Badge
    run_date = datetime.now().strftime("%B %d, %Y")
    total_elapsed = round(sum(r["response_time_seconds"] for r in records) / 60 + len(records) / 60, 1)
    new_badge = f'Run v{VERSION} &middot; {run_date} &middot; {total_queries} queries &middot; {total_elapsed} min'
    html = re.sub(
        r'Run v\d+ &middot; .*? &middot; \d+ queries &middot; [\d.]+ min',
        new_badge,
        html
    )

    # Replace account name in header
    html = re.sub(r'SVN Woven|Surana Polycot|ZoTok Copilot', account_name, html)

    # Stats grid: keep existing 6 cards + add 2 new ones
    def replace_stat_card(html, label, new_value):
        pattern = r'(<div class="stat-card \w+"><div class="number">)[^<]+(</div><div class="label">' + re.escape(label) + r'</div></div>)'
        new_html, n = re.subn(pattern, lambda m: m.group(1) + str(new_value) + m.group(2), html)
        if n == 0:
            print(f"  WARNING: Stat card '{label}' not found — may need manual addition")
        return new_html

    html = replace_stat_card(html, "Total Queries", total_queries)
    html = replace_stat_card(html, "API Success", latest["success"])
    html = replace_stat_card(html, "API Failed", latest["failed"])
    html = replace_stat_card(html, "Avg Response", f"{latest['avg_response_time_seconds']:.1f}s")
    html = replace_stat_card(html, "No Tool Called", no_tool)
    html = replace_stat_card(html, "Tools Used", len(tools_used_set))

    # Quality buckets
    pct_success = round(stats["success"] / total_queries * 100)
    pct_marginal = round(stats["marginal"] / total_queries * 100)
    pct_fail = round(stats["fail"] / total_queries * 100)

    for label_pct, new_count, new_pct in [
        ("success", stats["success"], pct_success),
        ("marginal", stats["marginal"], pct_marginal),
        ("fail", stats["fail"], pct_fail),
    ]:
        old_count_pattern = rf'(<div class="quality-card {label_pct}">.*?<div class="count">)[^<]+(</div>)'
        html = re.sub(old_count_pattern, lambda m: m.group(1) + str(new_count) + m.group(2), html, flags=re.DOTALL)
        old_pct_pattern = rf'(<div class="quality-card {label_pct}">.*?<div class="pct">)[^<]+(</div>)'
        html = re.sub(old_pct_pattern, lambda m: m.group(1) + str(new_pct) + "% of queries" + m.group(2), html, flags=re.DOTALL)

    # Leak banner
    html = re.sub(
        r'\d+ out of \d+ responses expose internal system details',
        f'{leak_count} out of {total_queries} responses expose internal system details',
        html
    )

    # Filter tab
    html = re.sub(r'All \(\d+\)', f'All ({total_queries})', html)

    # Raw data links
    html = re.sub(
        r'raw\.githubusercontent\.com/[^/]+/[^/]+/main/runs/query_results_v\d+\.jsonl',
        f'raw.githubusercontent.com/navneetlearns/langsmith-tool-evaluator/main/accounts/{account}/runs/query_results_v{VERSION}.jsonl',
        html
    )
    html = re.sub(
        r'&#128206; query_results_v\d+\.jsonl',
        f'&#128206; query_results_v{VERSION}.jsonl',
        html
    )

    # Footer
    html = re.sub(r'Run v\d+</p>', f'Run v{VERSION} &middot; {account_name}</p>', html)

    print("  All hardcoded values updated")

    # ============================================================
    # STEP 4: Add NEW SECTIONS (tool accuracy + step count)
    # ============================================================

    # -- New stat cards (insert after Tools Used card) --
    new_stat_cards = f"""
          <div class="stat-card green">
            <div class="number">{tool_accuracy['pct']}%</div>
            <div class="label">Tool Accuracy</div>
          </div>
          <div class="stat-card purple">
            <div class="number">{step_stats['avg']}</div>
            <div class="label">Avg Steps</div>
          </div>"""

    # Find the Tools Used stat card and append after it
    tools_used_marker = '<div class="label">Tools Used</div></div>'
    tools_used_pos = html.find(tools_used_marker)
    if tools_used_pos >= 0:
        insert_pos = html.find('</div>', tools_used_pos + len(tools_used_marker)) + 6
        html = html[:insert_pos] + new_stat_cards + html[insert_pos:]
        print("  Inserted 2 new stat cards: Tool Accuracy + Avg Steps")
    else:
        print("  WARNING: Could not find Tools Used stat card to insert new ones")

    # -- New section: Tool Accuracy by Category (after Response Quality by Category) --
    tool_acc_section = """
    <section>
      <h2>&#127919; Tool Selection Accuracy by Category</h2>
      <p class="section-desc">Percentage of queries where the agent called the expected tool (only queries with expected_tool specified in test data).</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Category</th><th>Expected Tool Queries</th><th>Correct</th><th>Accuracy</th><th></th></tr></thead>
          <tbody id="tool-acc-tbody"></tbody>
        </table>
      </div>
    </section>"""

    # -- New section: Step Count by Category (after Response Time by Category) --
    step_section = """
    <section>
      <h2>&#128260; Step Count per Completion</h2>
      <p class="section-desc">Number of SSE status transitions per query (thinking → analyzing → tool_start → ... → done). Higher = more complex interactions.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Category</th><th>Queries</th><th>Avg Steps</th><th>Min</th><th>Max</th><th></th></tr></thead>
          <tbody id="step-tbody"></tbody>
        </table>
      </div>
    </section>"""

    # Find section boundaries by heading text
    # Insert tool accuracy section AFTER "Response Quality by Category" section
    qual_cat_heading_pos = html.find("Response Quality by Category</h2>")
    if qual_cat_heading_pos >= 0:
        # Find the closing </section> after this heading
        section_close = html.find("</section>", qual_cat_heading_pos)
        if section_close >= 0:
            insert_pos = section_close + len("</section>")
            html = html[:insert_pos] + tool_acc_section + html[insert_pos:]
            print("  Inserted Tool Accuracy by Category section")
        else:
            print("  WARNING: Could not find </section> after quality by category")
    else:
        print("  WARNING: Could not find 'Response Quality by Category' heading")

    # Insert step count section AFTER "Response Time by Category" section
    # (after the insertion above, positions shifted — re-find)
    resp_time_pos = html.find("Response Time by Category</h2>")
    if resp_time_pos >= 0:
        section_close = html.find("</section>", resp_time_pos)
        if section_close >= 0:
            insert_pos = section_close + len("</section>")
            html = html[:insert_pos] + step_section + html[insert_pos:]
            print("  Inserted Step Count by Category section")
        else:
            print("  WARNING: Could not find </section> after response time by category")
    else:
        print("  WARNING: Could not find 'Response Time by Category' heading")

    # ============================================================
    # STEP 5: Add JS rendering for new sections
    # ============================================================

    # Add JS to populate the new tables (insert before the main query table rendering)
    new_js_code = """
    // === NEW: Tool Accuracy by Category Table ===
    (function() {
      const tbody = document.getElementById('tool-acc-tbody');
      if (!tbody) return;
      const cats = Object.keys(catToolAccuracy).sort();
      cats.forEach(cat => {
        const d = catToolAccuracy[cat];
        const pct = d.pct !== null ? d.pct + '%' : 'N/A';
        const pctNum = d.pct !== null ? d.pct : 0;
        const color = catColors[cat] || 'blue';
        const tr = document.createElement('tr');
        tr.innerHTML = '<td><span class="cat-badge ' + color + '">' + cat + '</span></td>' +
          '<td>' + d.total + '</td>' +
          '<td>' + d.correct + '</td>' +
          '<td><strong>' + pct + '</strong></td>' +
          '<td><div class="mini-bar"><div class="mini-bar-fill ' + color + '" style="width:' + pctNum + '%"></div></div></td>';
        tbody.appendChild(tr);
      });
    })();

    // === NEW: Step Count by Category Table ===
    (function() {
      const tbody = document.getElementById('step-tbody');
      if (!tbody) return;
      const cats = Object.keys(catStepData).sort();
      const maxAvg = Math.max(...cats.map(c => catStepData[c].avg), 1);
      cats.forEach(cat => {
        const d = catStepData[cat];
        const color = catColors[cat] || 'blue';
        const barPct = (d.avg / maxAvg * 100);
        const tr = document.createElement('tr');
        tr.innerHTML = '<td><span class="cat-badge ' + color + '">' + cat + '</span></td>' +
          '<td>' + d.n + '</td>' +
          '<td><strong>' + d.avg + '</strong></td>' +
          '<td>' + d.min + '</td>' +
          '<td>' + d.max + '</td>' +
          '<td><div class="mini-bar"><div class="mini-bar-fill ' + color + '" style="width:' + barPct + '%"></div></div></td>';
        tbody.appendChild(tr);
      });
    })();

    // === Update per-query table columns for expected_tool + step_count ===
    // (the existing table render loop in the template already iterates records —
    //  the new fields will appear if the template references them)
"""
    # Insert before the per-query table rendering or at end of script
    script_end = html.rfind('</script>')
    if script_end >= 0:
        html = html[:script_end] + new_js_code + '\n</script>' + html[script_end + len('</script>'):]
        print("  Added JS rendering for new sections")

    # ============================================================
    # STEP 6: Add CSS for new stat cards + sections
    # ============================================================

    new_css = """
/* NEW: Tool Accuracy + Avg Steps stat cards */
.stat-card.green { border-left: 4px solid var(--green); }
.stat-card.purple { border-left: 4px solid var(--purple); }

/* NEW: Mini bar for accuracy / step count tables */
.mini-bar { height: 8px; background: var(--border); border-radius: 4px; min-width: 60px; overflow: hidden; }
.mini-bar-fill { height: 100%; border-radius: 4px; }
.mini-bar-fill.green { background: var(--green); }
.mini-bar-fill.amber { background: var(--amber); }
.mini-bar-fill.red { background: var(--red); }
.mini-bar-fill.blue { background: var(--primary); }
.mini-bar-fill.purple { background: var(--purple); }
.mini-bar-fill.teal { background: #0d9488; }
.mini-bar-fill.orange { background: #ea580c; }
.mini-bar-fill.pink { background: #db2777; }
.mini-bar-fill.indigo { background: #4f46e5; }

/* NEW: Section spacing */
#tool-accuracy-section, #step-count-section { margin-top: 32px; }
"""
    style_end = html.find('</style>')
    if style_end >= 0:
        html = html[:style_end] + new_css + '\n</style>' + html[style_end + len('</style>'):]
        print("  Added CSS for new sections")

    # ============================================================
    # WRITE OUTPUT
    # ============================================================

    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing dashboard to {DASHBOARD_FILE}...")
    DASHBOARD_FILE.write_text(html)
    print(f"  Final size: {len(html)} bytes")
    print("  DONE!")

    # ============================================================
    # VERIFICATION
    # ============================================================

    print("\n=== VERIFICATION ===")
    errors = []

    rec_start_v = html.find('const records = [')
    rec_end_v = html.find('];', rec_start_v) + 2
    qi_count = html[rec_start_v:rec_end_v].count('"query_index"')
    if qi_count != total_queries:
        errors.append(f"Records count mismatch: {qi_count} != {total_queries}")

    for name in ["stats", "leakTypes", "catQuality", "catData", "catColors", "toolCounts",
                 "toolAccuracy", "catToolAccuracy", "stepStats", "catStepData"]:
        if f"const {name} = " not in html:
            errors.append(f"{name} not found!")

    for marker in ["stats-grid", "quality-grid", "leak-banner",
                   "tool-grid", "query-tbody", "raw-data", "principles",
                   "tool-acc-tbody", "step-tbody"]:
        if marker not in html:
            errors.append(f"Section {marker} not found!")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        print(f"\n  {len(errors)} VERIFICATION FAILURES")
    else:
        print("  [OK] All data objects present")
        print("  [OK] All sections present")
        print("  [OK] Records count matches")
        print(f"\n  ALL CHECKS PASSED")

    return errors


if __name__ == "__main__":
    errors = main()
    if errors:
        sys.exit(1)
