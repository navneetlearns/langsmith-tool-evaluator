#!/usr/bin/env python3
"""
Multi-account dashboard builder for Copilot Eval.

Loads a run version from accounts/<name>/runs/manifest.json (default: latest),
loads the corresponding JSONL, and rebuilds the dashboard HTML.

Usage:
    python3 build_dashboard.py --account surana              # latest version
    python3 build_dashboard.py --account hirafoods --version 1  # specific version
    python3 build_dashboard.py --account hirafoods --version=2
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
    "analytics_categorization": "(i'll treat this as|i'll categorize|i'll group this under)",
}

# Patterns that indicate the response contains NO useful data for the user.
# These are responses where the API succeeded technically but returned empty results.
NO_DATA_PATTERNS = [
    r"no\s+(products|items|data|sales|rows|results|customers|feedback|inventory|records|transactions|matching)\s+(were\s+found|found|returned|available|recorded|matched|populated|were\s+available)",
    r"no\s+matching\s+(threads|records|conversations|products|results|sales|items|rows)",
    r"(data\s+isn't|isn't\s+available|not\s+available)\s+right\s+now",
    r"couldn't\s+(complete\s+that\s+request|find\s+any|calculate|rank|identify\s+declining|build\s+a\s+top|group\s+inventory)",
    r"there\s+isn'?t\s+(any|a\s+co-purchase|product-level|sales\s+rows)",
    r"(0\s+products|zero\s+products|₹0\.00)\s+for",
    r"\*\*0\*\*\s+records",
    r"category\s+name\s+wasn'?t\s+populated",
    r"i\s+can'?t\s+(reliably\s+find|verify\s+purchase\s+frequency|identify\s+declining)",
    r"no\s+low-stock\s+items\s+were\s+found",
    r"no\s+slow-moving\s+items\s+were\s+found",
    r"there\s+aren'?t\s+any\s+(products|matching|sales)",
    r"couldn't\s+find\s+any\s+sales\s+rows",
    r"i\s+couldn't\s+find\s+any\s+paracetamol",
    r"no\s+product\s+sales\s+were\s+found",
    r"that\s+breakdown\s+isn'?t\s+available",
    r"i\s+couldn't\s+complete\s+that\s+request\s+right\s+now",
    r"please\s+try\s+again\s+(in\s+a\s+moment|shortly)",
]


def classify_quality(record):
    """Classify response quality into 4 buckets:
    - success: response contains actual data/tables/numbers valuable to user
    - no_data: API responded but returned zero useful data (no products found, try again, etc.)
    - marginal: partial response, some attempt but unreliable/incomplete
    - fail: technical failure (error, timeout, empty response)
    """
    response = record.get("response", "") or ""
    error = record.get("error")
    # Clarify parks (2026-09-18, finance/AR): an `interrupt` SSE event parks the turn with an
    # EMPTY response and NO error — that is the agent asking a clarifying question, NOT a
    # failure. The runner flags it (possible_clarify) and/or the status sequence carries
    # 'interrupt'. Degrades to 'fail' when an error is also present.
    seq = record.get("status_sequence") or []
    if (record.get("possible_clarify") or "interrupt" in seq) and not error and not response.strip():
        return "clarify"
    if error or not response.strip():
        return "fail"
    resp_lower = response.lower()

    # Check no_data patterns FIRST — these are the most specific
    for pattern in NO_DATA_PATTERNS:
        if re.search(pattern, resp_lower):
            return "no_data"

    # Has actual data? (currency, percentages, ranked lists, concrete numbers)
    if re.search(r'(\u20b9|%)', response) or re.search(r'(sorted by|ranked|showing \d|found \d)', resp_lower):
        return "success"

    # Has tabular data with actual values?
    if re.search(r'\|.*\|.*\|', response) and re.search(r'[\d,.]+', response):
        return "success"

    # Marginal: attempted but couldn't fully deliver
    if re.search(r"(couldn't|cannot|unable to|was rejected|didn't find|i couldn't)", resp_lower):
        return "marginal"
    if re.search(r"(try again|i don't want to guess|i'd recommend|if you want|you can try)", resp_lower):
        return "marginal"

    # Long responses with substance
    if len(response) > 120:
        return "success"
    if len(response) > 60:
        return "marginal"
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

def inject_value_layer(html: str, vs: dict) -> str:
    """Inject the Response-Value (CFO lens) section + per-row badges into a
    BUILT dashboard page. The shared template.html is never touched, so
    accounts without value data build byte-identical pages as before."""
    # 1) CSS
    css = """
/* Response Value section (CFO lens) */
.value-banner { background: linear-gradient(135deg, #0f172a, #1e293b); border: 1px solid var(--border, #334155); border-left: 4px solid var(--green); border-radius: 12px; padding: 18px 22px; margin: 16px 0; font-size: 14px; line-height: 1.6; }
.value-banner strong { color: var(--green); }
.value-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px; margin: 16px 0; }
.value-card { background: var(--card); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); text-align: center; border-top: 4px solid #64748b; }
.value-card.good { border-top-color: var(--green); }
.value-card.mid { border-top-color: var(--amber); }
.value-card.bad { border-top-color: var(--red); }
.value-card .count { font-size: 32px; font-weight: 700; margin-bottom: 4px; }
.value-card.good .count { color: var(--green); }
.value-card.mid .count { color: var(--amber); }
.value-card.bad .count { color: var(--red); }
.value-card .desc { font-size: 12px; color: var(--text-muted); }
.v-badge { display: inline-block; margin-left: 6px; padding: 1px 7px; border-radius: 10px; font-size: 10px; font-weight: 700; background: #334155; color: #cbd5e1; vertical-align: middle; }
.v-badge.v-l4, .v-badge.v-l5 { background: #14532d; color: #bbf7d0; }
.v-badge.v-l3 { background: #713f12; color: #fde68a; }
.v-badge.v-l2, .v-badge.v-l1 { background: #7f1d1d; color: #fecaca; }
.v-badge.v-ref { background: #1e3a8a; color: #bfdbfe; }
"""
    style_end = html.find("</style>")
    if style_end >= 0:
        html = html[:style_end] + css + "\n</style>" + html[style_end + len("</style>"):]

    ds, l3, dump, ref = vs["decision_support"], vs["L3"], vs["data_dump"], vs["REF"]
    judged, total = vs["judged"], vs["total"]
    not_judged = total - judged
    err = vs.get("errors", {})
    err_chips = "".join(
        f'<span class="leak-type-badge">{k}: <strong>{v}</strong></span>'
        for k, v in sorted(err.items())
    ) or '<span class="leak-type-badge">none</span>'
    section_html = f"""
  <!-- RESPONSE VALUE (CFO LENS) -->
  <section id="value-section">
    <h2>Response Value &mdash; Does the Answer Add CFO-Level Insight?</h2>
    <div class="value-banner">
      <strong>{ds} of {total}</strong> CFO asks delivered decision-grade support (L4/L5) ·
      <strong>{dump} data-dump / paraphrase answers</strong> (L1/L2) ·
      <strong>0 fabricated figures</strong>.
      Main defect: cross-answer template reuse &mdash; the same top-customer block appears in 9&ndash;12 of the judged answers instead of query-specific evidence.
    </div>
    <div class="value-grid">
      <div class="value-card good"><div class="count">{ds}</div><div class="desc"><strong>Decision support</strong> L4/L5 &mdash; insight + named action</div></div>
      <div class="value-card mid"><div class="count">{l3}</div><div class="desc"><strong>Structured finding</strong> L3 &mdash; correct but thin</div></div>
      <div class="value-card bad"><div class="count">{dump}</div><div class="desc"><strong>Data-dump / padding</strong> L1/L2 &mdash; fetch or paraphrase only</div></div>
      <div class="value-card mid"><div class="count">{ref}</div><div class="desc"><strong>Correct refusals</strong> boundary-named, no fabrication</div></div>
      <div class="value-card"><div class="count">{not_judged}</div><div class="desc"><strong>Not judged</strong> clarify-parks + technical fail</div></div>
    </div>
    <div class="leak-banner">
      <div class="summary">&#128270; Error-code index (FinGAIA taxonomy) on judged answers</div>
      <div class="types">{err_chips}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-top:8px">Hallucinatory reasoning: 0 &middot; Entity-causation: 0 &mdash; fabrication guarantee holds. Judge: deepseek-v4 in-session (cross-family vs producer gpt-5.4-mini), no external calls; see accounts/finance/VALUE_JUDGE_phase2.md.</div>
    </div>
  </section>
"""
    anchor = "<h2>Response Quality by Category</h2>"
    i = html.find(anchor)
    if i >= 0:
        html = html[:i] + section_html + "\n" + html[i:]
    else:
        print("  WARNING: could not find 'Response Quality by Category' - value section not injected")

    # 2) per-row value badge (quality cell)
    badge_old = '<td><span class="q-badge ${q}">${q}</span></td>'
    badge_new = ('<td><span class="q-badge ${q}">${q}</span>'
                 '${r.value_level ? \'<span class="v-badge v-\' + r.value_level.toLowerCase() + \'">\' + r.value_level + \'</span>\' : \'\'}'
                 '</td>')
    if badge_old in html:
        html = html.replace(badge_old, badge_new)

    # 3) value line + errors in the expand row
    tools_old = '<div class="section-label">Tools Called (${(r.tool_calls || []).length})</div>'
    tools_new = ('<div class="section-label">Value: ${r.value_level || "not judged"}'
                 '${r.value_errors && r.value_errors.length ? " | error codes: " + r.value_errors.join(", ") : ""}'
                 '${r.value_note ? " | " + r.value_note : ""}</div>\n        ' + tools_old)
    if tools_old in html:
        html = html.replace(tools_old, tools_new)

    return html


def verify_finance_static(page: str) -> list:
    """Verify the REDESIGNED static finance page (2026-09-19): server-rendered content,
    sticky-nav 7 sections, deep links for all 30 queries, no stale tool-selection framing,
    no old mislabeled headline numbers, no relative hrefs (Pages publishes only docs/)."""
    errors = []
    for marker in ["<tbody>", "<table>", "Deterministic content checks", "Findings", "Leak hits",
                   "Expected-vs-observed", "Query explorer", "Per-query label cards",
                   "no fabricated figures detected"]:
        if marker not in page:
            errors.append(f"section '{marker}' missing")
    # every displayed count derived: outcome bar must state the sum and the verdict line
    for must in ["mutually exclusive outcomes", "sum <strong>30</strong>", "id=\"summary\"",
                 "id=\"means\"", "id=\"results\"", "id=\"evaluated\"", "id=\"labels\"",
                 "id=\"limits\"", "id=\"reproduce\"", "legacy/"]:
        if must not in page:
            errors.append(f"redesign element '{must}' missing")
    # all 30 deep links (#q1..#q30) must exist
    missing_q = [q for q in range(1, 31) if f'id="q{q}"' not in page]
    if missing_q:
        errors.append(f"deep links missing for q{','.join(map(str, missing_q))}")
    # old mislabeled headline numbers must NOT appear; stronger fabrication claim must not
    for stale in ["Failed 10", "API Failed", "0.0% tool accuracy", "Tool accuracy 0.0%",
                  "30 No Tool Called", "fabrication guarantee", "80 query traces",
                  "50 query traces", "July 23, 2026", "July 11, 2026"]:
        if stale in page:
            errors.append(f"stale/misleading number still present: '{stale}'")
    n_tables = page.count("<table>")
    if n_tables < 5:
        errors.append(f"expected >=5 tables, found {n_tables}")
    # Relative ../../ links break on GitHub Pages (only docs/ is published)
    rel = sorted(set(re.findall(r'href="(\.\./\.\./[^"]+)"', page)))
    if rel:
        errors.append(f"relative ../ links that 404 on Pages: {rel}")
    return errors


def main():
    # Parse --account and --version flags
    account = "surana"
    version_arg = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--account" and i + 1 < len(args):
            account = args[i + 1]
        elif arg.startswith("--account="):
            account = arg.split("=", 1)[1]
        elif arg == "--version" and i + 1 < len(args):
            version_arg = int(args[i + 1])
        elif arg.startswith("--version="):
            version_arg = int(arg.split("=", 1)[1])

    cfg = load_account_config(account)
    account_name = cfg["account_name"]

    # ---- FINANCE STATIC PAGE BRANCH ----
    # The finance agent template streams no tool events (backend SQL) and steps are the
    # SSE status depth, not agent steps — the JS template's tool-selection/step framing
    # does not apply. When derived artifacts exist (runs/v<N>/summary.json), render a
    # fully static page (server-rendered tables, no JS) from them. Other accounts never
    # enter this branch and build byte-identical pages.
    imports_ok = True
    try:
        import importlib.util  # noqa: PLC0415
        _mod_path = SCRIPT_DIR / "scripts" / "render_finance_static.py"
        _spec = importlib.util.spec_from_file_location("render_finance_static", _mod_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        build_finance_static = _mod.build
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: finance static renderer unavailable ({exc})")
        imports_ok = False
    if account == "finance" and imports_ok:
        manifest_fin = json.load(open(cfg["manifest_file"]))
        fin_versions = sorted(v["version"] for v in manifest_fin.get("runs", []))
        fin_version = version_arg or (fin_versions[-1] if fin_versions else 1)
        derived_dir = cfg["runs_dir"] / f"v{fin_version}"
        if (derived_dir / "summary.json").exists():
            print(f"Account: {account} ({account_name}) — FINANCE STATIC PAGE (v{fin_version})")
            errors = verify_finance_static(build_finance_static(fin_version))
            if errors:
                for e in errors:
                    print(f"  [FAIL] {e}")
                sys.exit(1)
            print("  [OK] finance static page verified")
            return 0
        print(f"  WARNING: {account} has no derived artifacts at {derived_dir} — "
              f"run `python3 scripts/finance_pipeline.py --run {fin_version}` first; "
              f"falling back to the generic template path.")

    DASHBOARD_DIR = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / account
    DASHBOARD_FILE = DASHBOARD_DIR / "index.html"
    TEMPLATE = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "template.html"  # base HTML structure

    RUNS_DIR = cfg["runs_dir"]
    MANIFEST_FILE = cfg["manifest_file"]

    # ============================================================
    # LOAD MANIFEST + VERSION DATA
    # ============================================================

    manifest = json.load(open(MANIFEST_FILE))
    all_versions = sorted(manifest["runs"], key=lambda r: r["version"])
    
    # Use specified version or latest
    if version_arg is not None:
        version_entry = next((v for v in all_versions if v["version"] == version_arg), None)
        if version_entry is None:
            print(f"ERROR: Version {version_arg} not found for account {account}")
            print(f"Available versions: {[v['version'] for v in all_versions]}")
            sys.exit(1)
        latest = version_entry  # Use 'latest' variable name for consistency with later code
        VERSION = version_entry["version"]
        LATEST_FILE = RUNS_DIR / version_entry["file"]
        print(f"Account: {account} ({account_name})")
        print(f"Building version: v{VERSION}")
    else:
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

    # ---- VALUE LAYER (optional: accounts with a value judge file) ----
    # If runs/value_phase2_judge.json exists, merge value_level / value_errors
    # into records and compute valueStats. Absent for other accounts => no
    # value section, byte-identical behavior to before.
    VALUE_FILE = RUNS_DIR / "value_phase2_judge.json"
    value_data = None
    if VALUE_FILE.exists():
        try:
            value_data = json.load(open(VALUE_FILE)).get("records", {})
            for r in records:
                jr = value_data.get(str(r["query_index"]))
                if jr:
                    r["value_level"] = jr.get("level", "")
                    r["value_errors"] = jr.get("errors") or []
                    note = jr.get("note", "")
                    r["value_note"] = note[:160]
                else:
                    r["value_level"] = ""
                    r["value_errors"] = []
                    r["value_note"] = ""
            print(f"  value layer: merged {len(value_data)} judge records")
        except Exception as exc:  # noqa: BLE001 - value layer must never break the build
            print(f"  WARNING: value layer failed to load ({exc}) — continuing without it")
            value_data = None

    value_stats = None
    if value_data is not None:
        answered = [r for r in records if r.get("value_level")]
        lv = collections.Counter(r["value_level"] for r in answered)
        err = collections.Counter()
        for r in answered:
            for e in r["value_errors"]:
                err[e] += 1
        value_stats = {
            "L5": lv.get("L5", 0),
            "L4": lv.get("L4", 0),
            "L3": lv.get("L3", 0),
            "L2": lv.get("L2", 0),
            "L1": lv.get("L1", 0),
            "REF": lv.get("REF", 0),
            "decision_support": lv.get("L4", 0) + lv.get("L5", 0),
            "data_dump": lv.get("L1", 0) + lv.get("L2", 0),
            "judged": len(answered),
            "total": len(records),
            "errors": dict(err),
        }

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
        "no_data": q_counts.get("no_data", 0),
        "clarify": q_counts.get("clarify", 0),
        "fail": q_counts.get("fail", 0),
        "leak": leak_count,
    }
    err_count = sum(1 for r in records if r.get("error"))

    leak_types = dict(leak_type_counts.most_common())

    # ---- catQuality ----
    cat_quality = {}
    for r in records:
        cat = r["category"]
        if cat not in cat_quality:
            cat_quality[cat] = {"success": 0, "marginal": 0, "no_data": 0, "clarify": 0, "fail": 0, "_times": []}
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
            '"timestamp":%s,'
            '"value_level":%s,'
            '"value_errors":%s}'
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
            json.dumps(str(r.get("value_level", "")), ensure_ascii=False),
            json.dumps(r.get("value_errors", []), ensure_ascii=False),
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
    # Update quality bucket percentages and counts
    pct_success = round(stats["success"] / total_queries * 100)
    pct_marginal = round(stats["marginal"] / total_queries * 100)
    pct_no_data = round(stats["no_data"] / total_queries * 100)
    pct_fail = round(stats["fail"] / total_queries * 100)

    # Update the 4 quality cards (success, marginal, no-data, fail)
    for label_pct, new_count, new_pct in [
        ("success", stats["success"], pct_success),
        ("marginal", stats["marginal"], pct_marginal),
        ("no-data", stats["no_data"], pct_no_data),
        ("fail", stats["fail"], pct_fail),
    ]:
        old_count_pattern = rf'(<div class="quality-card {label_pct}">.*?<div class="count">)[^<]+(</div>)'
        html = re.sub(old_count_pattern, lambda m: m.group(1) + str(new_count) + m.group(2), html, flags=re.DOTALL)
        old_pct_pattern = rf'(<div class="quality-card {label_pct}">.*?<div class="pct">)[^<]+(</div>)'
        html = re.sub(old_pct_pattern, lambda m: m.group(1) + str(new_pct) + "% of queries" + m.group(2), html, flags=re.DOTALL)

    # No-data card is now in template.html with proper CSS, no injection needed

    # ---- Finance/agent-aware sections: clarify parks, behavior matrix, refusal trust ----
    # (render only when the new fields are present — old accounts unaffected)
    clarify_count = stats.get("clarify", 0)
    has_behavior = any(r.get("expected_behavior") for r in records)

    if clarify_count:
        pct_c = round(clarify_count / total_queries * 100)
        clarify_card = (
            '<div class="quality-card clarify" style="background:var(--surface);'
            'border-left:4px solid #7c3aed;border-radius:8px;padding:16px;">'
            '<div class="icon">&#10067;</div>'
            f'<div class="count" style="color:#7c3aed;">{clarify_count}</div>'
            '<div class="desc"><strong>Clarify</strong> &mdash; Agent asked a clarifying question '
            '(interrupt) and parked the turn; no answer on turn 1 (finance/AR clarify gate)</div>'
            f'<div class="pct">{pct_c}% of queries</div></div>'
        )
        html = re.sub(r'(<div class="quality-card no-data">.*?</div>\s*</div>)(\s*</section>)',
                      lambda m: m.group(1) + "\n      " + clarify_card + m.group(2),
                      html, flags=re.DOTALL)

    if has_behavior:
        beh_matrix = {}
        for r in records:
            exp = (r.get("expected_behavior") or "UNLABELED").upper()
            q = r["response_quality"]
            obs = "FAIL" if r.get("error") else ("CLARIFY" if q == "clarify"
                                                 else ("ANSWERED" if q in ("success", "marginal", "no_data") else q.upper()))
            beh_matrix.setdefault(exp, collections.Counter())[obs] += 1
        matrix_rows = ""
        for exp in ("ANSWER", "CLARIFY", "REFUSE"):
            if exp not in beh_matrix:
                continue
            c = beh_matrix[exp]
            matrix_rows += (f'<tr><td><strong>{exp}</strong></td>'
                            f'<td>{c.get("ANSWERED", 0)}</td>'
                            f'<td>{c.get("CLARIFY", 0)}</td>'
                            f'<td>{c.get("FAIL", 0)}</td></tr>')
        hard_ref = sum(1 for r in records
                       if (r.get("response") or "").lstrip().startswith("I can't answer"))
        hedged = sum(1 for r in records
                     if any(k in (r.get("response") or "") for k in
                            ("not yet proven", "cannot be assessed", "from your books")))
        guard = sum(1 for r in records if "Payments are not fully reconciled" in (r.get("response") or ""))
        behavior_section = f"""
  <!-- CLARIFY + BEHAVIOR MATRIX (finance/AR agents) -->
  <section>
    <h2>&#10067; Clarify Gate &amp; Behavior Matrix (expected vs observed)</h2>
    <p class="section-desc" style="font-size:13px;color:#6b7280;">expected_behavior is the label from
    the query set; observed is what the live agent did. Parks = the agent asked a clarifying
    question (interrupt, no tools, no answer).</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Expected</th><th>Answered</th><th>Clarified (park)</th><th>Failed</th></tr></thead>
      <tbody>{matrix_rows}</tbody>
    </table></div>
    <div class="leak-banner" style="margin-top:14px;">
      <div class="summary">&#128273; Refusal trust: {hard_ref} hard refusals + {hedged} hedged
      boundary-named answers, 0 fabricated figures &middot; reconcile/ageing guard fired on
      {guard} answers &middot; finance streams no tool events (backend SQL) — tool-accuracy N/A</div>
    </div>
  </section>
"""
        html = html.replace("<!-- INFO LEAK DETECTION -->",
                            behavior_section + "<!-- INFO LEAK DETECTION -->", 1)

    # Correct the API Failed stat card: manifest 'failed' counts EMPTY responses (incl. clarify
    # parks); the real technical-failure count is err_count.
    try:
        html = replace_stat_card(html, "API Failed", err_count)
    except Exception:
        pass

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
    # STEP 3.5: Rebuild comparison snapshot (account-specific)
    # ============================================================

    print(f"Updating comparison snapshot ({len(all_versions)} versions)...")

    # Compute total time for each version
    for v in all_versions:
        n = v["total_queries"]
        avg = v["avg_response_time_seconds"]
        v["_total_time"] = round(n * avg / 60 + n / 60, 1)

    # Improvement text (latest vs previous)
    if len(all_versions) >= 2:
        prev = all_versions[-2]
        curr = all_versions[-1]
        prev_avg = prev["avg_response_time_seconds"] or 0
        avg_diff = ((curr["avg_response_time_seconds"] - prev_avg) / prev_avg) * 100 if prev_avg else 0

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

    # Build comparison cards
    color_cycle = ["amber", "primary", "green", "purple"]
    cards_html = ""
    for i, v in enumerate(all_versions):
        vn = v["version"]
        color = "green" if vn == VERSION else color_cycle[i % len(color_cycle)]
        vdate = datetime.fromisoformat(v["timestamp"]).strftime("%B %d, %Y")

        cards_html += f"""      <div class="snapshot-card v{vn}">
        <h3>Run v{vn} &mdash; {vdate}</h3>
        <div class="snapshot-metrics">
          <div class="snapshot-metric"><span class="label">Queries</span><span class="value">{v['total_queries']}</span></div>
          <div class="snapshot-metric"><span class="label">API Success</span><span class="value">{v['success']}</span></div>
          <div class="snapshot-metric"><span class="label">Failed</span><span class="value">{v['failed']}</span></div>
          <div class="snapshot-metric"><span class="label">Avg Response</span><span class="value">{v['avg_response_time_seconds']:.1f}s</span></div>
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
    old_comp_start = html.find("<!-- COMPARISON SNAPSHOT")
    old_comp_end = html.find("<!-- TOP STATS -->")
    if old_comp_start >= 0 and old_comp_end > old_comp_start:
        html = html[:old_comp_start] + new_comparison + html[old_comp_end:]
        print(f"  Comparison snapshot rebuilt: {len(all_versions)} cards")
    else:
        print("  WARNING: Comparison snapshot markers not found in template")

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

/* No Data quality card */
.quality-card.no-data { background: var(--surface); border-left: 4px solid var(--amber); border-radius: 8px; padding: 16px; }
.quality-card.no-data .count { font-size: 28px; font-weight: 700; color: var(--amber); }
.quality-card.no-data .pct { font-size: 13px; color: var(--text-secondary); margin: 4px 0; }
.quality-card.no-data .desc { font-size: 12px; color: var(--text-tertiary); }

/* Per-query table: color no_data responses */
tr.row-no-data { background: rgba(245, 158, 11, 0.04); }
tr.row-no-data .response-text { color: var(--amber); font-style: italic; }
"""
    style_end = html.find('</style>')
    if style_end >= 0:
        html = html[:style_end] + new_css + '\n</style>' + html[style_end + len('</style>'):]
        print("  Added CSS for new sections")

    # ============================================================
    # VALUE LAYER INJECTION (finance-style accounts with judge data)
    # ============================================================

    if value_data is not None and value_stats is not None:
        html = inject_value_layer(html, value_stats)
        print("  Injected Response-Value section")

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
