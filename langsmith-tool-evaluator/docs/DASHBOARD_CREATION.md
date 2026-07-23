# Dashboard Creation Guide — Copilot Eval

> **Mandatory reference for all AI agents.** Do not deviate from this guide.
> Every future version of the dashboard MUST follow these steps exactly,
> in this order. Skipping steps or inventing new approaches will break
> the dashboard.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Pipeline Prerequisites](#2-pipeline-prerequisites)
3. [Running the Pipeline](#3-running-the-pipeline)
4. [Dashboard Architecture](#4-dashboard-architecture)
5. [Dashboard Creation Steps](#5-dashboard-creation-steps)
6. [Data Sections Reference](#6-data-sections-reference)
7. [Quality & Leak Classification](#7-quality--leak-classification)
8. [Comparison Section](#8-comparison-section)
9. [Critical Pitfalls](#9-critical-pitfalls)
10. [Checklist](#10-checklist)
11. [Version History](#11-version-history)

---

## 1. Overview

The dashboard is a **self-contained HTML file** (`docs/index.html`) deployed via
GitHub Pages at https://navneetlearns.github.io/langsmith-tool-evaluator/.

It embeds all 80+ query records as a JavaScript array and renders them with
zero external dependencies. Every data section (stats, quality, leaks, tool
usage, per-query table) is computed from the embedded records array.

### File Structure

```
langsmith-tool-evaluator/
├── copilot_query_pipeline.py    # Pipeline: runs queries, produces JSONL
├── runs/
│   ├── query_results_v1.jsonl   # Previous run data (DO NOT MODIFY)
│   ├── query_results_v2.jsonl   # Current run data
│   └── manifest.json            # Run version tracker
├── langsmith-tool-evaluator/
│   └── docs/
│       └── index.html           # Dashboard (must rebuild for each run)
└── docs/
    └── DASHBOARD_CREATION.md    # This file
```

---

## 2. Pipeline Prerequisites

Before creating a dashboard, the pipeline must have been run successfully.

### Pipeline Config

| Setting | Value |
|---------|-------|
| Phone | `9595259595` (Surana's number) |
| Workspace ID | `6c4ad886-8bf6-4202-8dfb-10ae6905dd3f` |
| API Base | `https://api.zotok.ai` |
| SSE Timeout | 300s per query |
| Read Timeout | 120s |

### Running the Pipeline

```bash
cd /mnt/d/AgentWork/langsmith-tool-evaluator
python3 -u copilot_query_pipeline.py
```

**Expected output:** `runs/query_results_v{N}.jsonl` (one JSON line per query)
and `runs/manifest.json` updated with the new version.

**Runtime:** ~20 minutes for 80 queries (avg ~13s/query).

**IMPORTANT:** Always use `-u` (unbuffered) flag. The pipeline has `log_msg()`
writes to `pipeline_run.log` for progress tracking in the repo root.

### Output Record Schema

Each line in the JSONL file has these fields:

| Field | Type | Description |
|-------|------|-------------|
| `query_index` | int | 1-based position |
| `query` | string | The user query text |
| `copilot_response` | string | Original response from Excel |
| `response` | string | Actual copilot response (SSE captured) |
| `category` | string | Section category (e.g. "Sales", "Dashboard") |
| `tool_calls` | array | `[{tool, input}, ...]` |
| `status_sequence` | array | `["thinking", "analyzing", ...]` |
| `suggestions` | array | Follow-up suggestion objects |
| `response_time_seconds` | float | Wall-clock time for this query |
| `error` | string | Error message if failed |
| `timestamp` | string | ISO timestamp of the run |
| `run_version` | int | Version number |
| `thread_id` | string | UUID of the conversation thread |
| `remarks` | string | Human remarks from Excel |

---

## 3. Dashboard Architecture

### Design Rules (ABSOLUTE — do not change)

1. **Every section from the original v1 dashboard MUST be preserved:**
   - Stats grid (6 cards)
   - Response quality buckets (3 buckets)
   - Info leak detection (banner + table)
   - Quality by category (table with distribution bars)
   - Response time by category (table with visual bars)
   - Tool usage frequency (card grid)
   - Per-query results (search + filter + sortable table + expandable rows)
   - Raw data links (4 links)
   - HEART principles

2. **No new sections may be added** except the comparison snapshot
   (which is now mandatory).

3. **Colors, CSS variables, layout, and spacing must be identical**
   to the original. The CSS uses these variables:
   ```css
   --bg: #f8f9fb;  --card: #ffffff;  --primary: #2563eb;
   --primary-light: #dbeafe;  --text: #1e293b;  --text-muted: #64748b;
   --border: #e2e8f0;  --green: #16a34a;  --green-light: #dcfce7;
   --red: #dc2626;  --red-light: #fee2e2;  --amber: #d97706;
   --amber-light: #fef3c7;  --purple: #7c3aed;  --purple-light: #ede9fe;
   --shadow: 0 1px 3px rgba(0,0,0,0.08);  --radius: 10px;
   ```

4. **The comparison snapshot section is mandatory** and must appear
   immediately after the `<header>` and before the stats grid.

5. **The footer must read** `Run v{N}` matching the current version.

### JS Data Architecture

The dashboard has **7 critical data objects** embedded as `const` variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `records` | Array of all query records | From JSONL |
| `stats` | `{success, marginal, fail, leak}` | Computed from records |
| `leakTypes` | `{type: count}` | Computed from records |
| `catQuality` | `{category: {success, marginal, fail, avg, n}}` | Computed from records |
| `catData` | `{category: {avg, min, max, n, success, fail}}` | Computed from records |
| `catColors` | `{category: colorName}` | Hardcoded (9 categories) |
| `toolCounts` | `{tool: count}` | Computed from records |

---

## 4. Dashboard Creation Steps

### Step 1: Restore the previous dashboard as template

```bash
cd /mnt/d/AgentWork/langsmith-tool-evaluator
# Get the last GOOD dashboard version from git
# Check git log for the version with all sections intact
git log --oneline -- langsmith-tool-evaluator/docs/index.html
git show <COMMIT_HASH>:langsmith-tool-evaluator/docs/index.html \
  > langsmith-tool-evaluator/docs/index.html
```

Use `5b2d018` as the base (it has quality buckets + info leak detection).
Do NOT use the initial `976685a` version (missing quality/leak sections).

### Step 2: Load and classify the new run data

Use Python to load `runs/query_results_v{N}.jsonl` and compute:
- `response_quality` (see §7)
- `info_leak` (boolean)
- `leak_indicators` (array of strings)

**CRITICAL:** Add these fields to each record BEFORE building the JS array.

### Step 3: Build the records JS array

Build a JavaScript array string. Each record is a single-line JSON-like object.

**ABSOLUTE RULE:** Records MUST be formatted as single-line objects separated
by commas. Do NOT pretty-print or use multi-line formatting. This prevents
the `];` regex matching bug (see §9).

```python
record_parts.append(
    '{"query_index":%d,...,"response_quality":"%s",...,"timestamp":"%s"}'
)
```

All fields that the expand row references MUST be included:
- `query_index`, `query`, `copilot_response`, `remarks`, `category`
- `thread_id`, `tool_calls`, `response`, `info_leak`, `leak_indicators`
- `response_quality`, `response_time_seconds`, `error`
- `status_sequence`, `suggestions`, `timestamp`

**CRITICAL:** The `response` field (actual copilot response text) MUST be
included. Without it, the per-query table response column shows empty and
the expand-row response section displays `[empty]`. This field is required
by both `respPreview` in the table row and the `Response (N chars)` section
in the expand row.

### Step 4: Replace the records array in the HTML

Find the exact boundary:
```python
rec_start = html.find('const records = [')
rec_end = html.find('];', rec_start) + 2
```

Then replace `html[rec_start:rec_end]` with the new records JS.

**DO NOT USE REGEX for this replacement.** Use exact string positions.
The regex `r'const records = \[.*?\];'` with DOTALL is unsafe because
response text may contain `];` sequences.

### Step 5: Update all other data sections

Replace each of these using exact string matching:

1. `const stats = {...};`
2. `const leakTypes = {...};`
3. `const catQuality = {...};`
4. `const catData = {...};`
5. `const catColors = {...};`
6. `const toolCounts = {...};`

For objects (catQuality, catData, toolCounts), find by `const NAME = {`
and replace through the matching `};`:
```python
start = html.find('const NAME = {')
end = html.find('};', start) + 2
html = html[:start] + 'const NAME = ' + json.dumps(new_data) + ';' + html[end:]
```

### Step 6: Update hardcoded display values

Replace these exact strings in the HTML:

| Old Value | New Value |
|-----------|-----------|
| `<title>...v1</title>` | `<title>...v{N}</title>` |
| `Run v1 &middot; July 11, 2026 &middot; 50 queries &middot; 21.9 min` | `Run v{N} &middot; {date} &middot; {N} queries &middot; {time} min` |
| Stats grid numbers (50, 49, 1, 25.1s, 10, 6) | New computed values |
| Quality bucket counts (21, 14, 15) | New computed values |
| Quality percentages (42%, 28%, 30%) | New computed percentages |
| Leak banner (`X out of Y responses`) | New values |
| Filter tab `All (50)` → `All (80)` | `All ({total})` |
| Raw data description (`with all 50 query traces`) | New count |
| Footer `Run v1` → `Run v{N}` | New version |

### Step 7: Add/update the comparison snapshot

The comparison section is added by replacing the `<!-- TOP STATS -->` comment
with the comparison HTML block (see §8 for full HTML).

The comparison section must:
- Show v1 metrics on the left (amber card)
- Show v{N} metrics on the right (green card)
- Include an improvement banner at the bottom
- Reference the correct run dates and metrics

### Step 8: Add comparison CSS

Add the comparison snapshot CSS block just before `</style>`.
This CSS is fixed — do not modify it.

### Step 9: Update raw data links

Replace the v1 link row with:
1. v{N} link (primary)
2. v1 link (v1 baseline)
3. manifest link
4. GitHub link

### Step 10: Verify and commit

Run the verification script (see §10 Checklist). All checks must pass.
Then:

```bash
git add langsmith-tool-evaluator/docs/index.html
git commit -m "Dashboard v{N}: ..."
git push origin main
```

---

## 5. Data Sections Reference

### Stats Grid (6 cards)

```javascript
// Order: Total Queries, API Success, API Failed, Avg Response,
//        No Tool Called, Tools Used
const stats = { success: N, marginal: N, fail: N, leak: N };
```

### Quality Buckets (3 cards)

Classified by `classify_quality()` heuristic (see §7).
Display order: Success | Marginal | Fail.

### Info Leak Detection

Rendered from `records.filter(r => r.info_leak)`.
Leak types banner rendered from `leakTypes` object.
Leak detail table shows each leaking query with type labels.

### Quality by Category

```javascript
const catQuality = {
  "CategoryName": { "success": N, "marginal": N, "fail": N, "avg": F, "n": N },
  ...
};
```
Distribution bar shows S/M/F percentages.

### Response Time by Category

```javascript
const catData = {
  "CategoryName": { "avg": F, "min": F, "max": F, "n": N, "success": N, "fail": N },
  ...
};
```
Sorted by avg descending. Visual bar width proportional to avg/maxAvg.

### catColors Mapping

Must include ALL 9 categories (as of v2):
```javascript
const catColors = {
  "Dashboard": "green", "Items": "purple", "Ledger": "red",
  "Orders & Invoices": "green", "Outstanding & Payments": "amber",
  "Payments": "blue", "Products & Items": "purple",
  "Reports & Analytics": "red", "Sales": "amber"
};
```

If new categories are added in future runs, add them here.

### Tool Usage

```javascript
const toolCounts = {
  "toolName": count,
  ...
};
```
Sorted by count descending. Bar width proportional to count/maxTool.

---

## 6. Quality & Leak Classification

### Quality Classification Rules

Applied to every record via `classify_quality()`:

1. **`fail`** — Record has an `error` field, or response is empty.
2. **`marginal`** — Response matches: couldn't, cannot, unable to,
   was rejected, didn't find, I couldn't.
3. **`success`** — Response contains: ₹, %, customer/product counts,
   "sorted by", "ranked", "showing N", "found N".
4. **`marginal`** — Response contains hedge phrases: "try again",
   "i don't want to guess", "i'd recommend", "if you want",
   "you can try".
5. **`success`** — Response length > 60 chars (has substance).
6. **`marginal`** — Everything else.

**Rule order is important.** Check patterns before falling through
to length-based heuristics.

### Leak Detection Rules

Applied to every record via `detect_leaks()`:

| Pattern | Leak Type | Example Triggers |
|---------|-----------|-----------------|
| `\b(card\|result preview\|show more\|scroll\|view more\|the card has)\b` | `ui_component` | "the card shows...", "scroll for more" |
| `\b(available tools\|current tools\|tool called\|i can use\|my tools\|i have access to)\b` | `tool_capability` | "my available tools are..." |
| `\b(workspace)\b` | `workspace_ref` | "in this workspace" |
| `\b(log out\|log back in\|session expired\|reauthenticate)\b` | `auth_session` | "log out and log back in" |
| `\b(lifecycle group\|debtor group\|customer group\|aging bucket)\b` | `internal_data_model` | "aging bucket" |
| `(i'll treat this as\|i'll categorize\|i'll group this under)` | `analytics_categorization` | "I'll treat this as..." |

### Adding New Patterns

If the copilot starts leaking new types of information, add new patterns
to LEAK_PATTERNS and update `leakTypeLabels` in the HTML.

---

## 7. Comparison Section

### HTML Structure

The comparison snapshot is an **N-column grid** (one card per run version) with a full-width banner:

```html
<div class="comparison-snapshot">
  <div class="snapshot-grid">
    <div class="snapshot-card v1">    <!-- Amber top border -->
      <h3>Run v1 &mdash; {date}</h3>
      <div class="snapshot-metrics">
        <!-- 6 metrics: Queries, API Success, Failed, Avg Response,
             Categories, Total Time -->
      </div>
    </div>
    <div class="snapshot-card v2">    <!-- Blue (primary) top border -->
      <h3>Run v2 &mdash; {date}</h3>
      <div class="snapshot-metrics">
        <!-- 6 metrics -->
      </div>
    </div>
    <!-- ... one card per previous version ... -->
    <div class="snapshot-card v{N}">  <!-- Green top border (latest) -->
      <h3>Run v{N} &mdash; {date}</h3>
      <div class="snapshot-metrics">
        <!-- 6 metrics -->
      </div>
    </div>
    <div class="snapshot-improvement"> <!-- Full-width green banner -->
      <strong>{improvement summary comparing latest vs previous}</strong>
    </div>
  </div>
</div>
```

### CSS (fixed — append before `</style>`)

```css
.comparison-snapshot { margin: 0 0 40px; }
/* N columns — one per version. Update count as versions grow. */
.snapshot-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 16px; }
.snapshot-card { background: var(--card); border-radius: var(--radius);
  padding: 20px 24px; box-shadow: var(--shadow); }
.snapshot-card.v1 { border-top: 4px solid var(--amber); }
.snapshot-card.v2 { border-top: 4px solid var(--primary); }
.snapshot-card.v{N} { border-top: 4px solid var(--green); }
.snapshot-card h3 { font-size: 15px; margin-bottom: 12px; }
.snapshot-card.v1 h3 { color: var(--amber); }
.snapshot-card.v2 h3 { color: var(--primary); }
.snapshot-card.v{N} h3 { color: var(--green); }
.snapshot-metrics { display: grid; grid-template-columns: 1fr 1fr;
  gap: 8px 16px; }
.snapshot-metric { display: flex; justify-content: space-between;
  font-size: 13px; padding: 4px 0; border-bottom: 1px solid #f1f5f9; }
.snapshot-metric .label { color: var(--text-muted); }
.snapshot-metric .value { font-weight: 700; }
.snapshot-card.v1 .snapshot-metric .value { color: var(--amber); }
.snapshot-card.v2 .snapshot-metric .value { color: var(--primary); }
.snapshot-card.v{N} .snapshot-metric .value { color: var(--green); }
.snapshot-improvement { grid-column: 1 / -1;
  background: var(--green-light); border: 1px solid #86efac;
  border-radius: 8px; padding: 14px 20px; text-align: center;
  font-size: 14px; color: #166534; }
.snapshot-improvement strong { font-size: 18px; }
```

### Mandatory Data Points

The comparison must show these metrics for ALL runs (v1, v2, v{N}):
- Queries (total count)
- API Success (count)
- Failed (count)
- Avg Response (seconds)
- Categories (count)
- Total Time (minutes)

---

## 8. Critical Pitfalls

### Pitfall 1: Records Array `];` Bug

**Problem:** The regex `r'const records = \[.*?\];'` with DOTALL matches
the FIRST `];` sequence. If any record's response text contains `];`,
the match ends prematurely, deleting all rendering code after it.

**Solution:** Use exact string position matching:
```python
rec_start = html.find('const records = [')
rec_end = html.find('];', rec_start) + 2
```
And format records as single-line objects to avoid `];` in data.

### Pitfall 2: Missing Record Fields

**Problem:** The expand rows reference `status_sequence`, `suggestions`,
`timestamp`. If these are missing from the records JS, the expand section
shows `[none]` or `undefined`.

**Solution:** Always include ALL fields in the records JS array.

### Pitfall 3: Wrong Base Template

**Problem:** Using `976685a` (original v1) instead of `5b2d018` (v1 with
quality/leak sections). The older version is missing the quality buckets
and info leak detection sections.

**Solution:** Always use `5b2d018` or the most recent dashboard that has
all sections. Check by grepping for `leak-banner` and `quality-grid`.

### Pitfall 4: Stale v1 Data in Data Sections

**Problem:** After replacing the records array, the `stats`, `catQuality`,
`catData`, `toolCounts` objects still contain v1 values because they were
not replaced.

**Solution:** Update ALL 6 data objects (step 5). Verify each one exists
in the final HTML with the correct values.

### Pitfall 5: v1 Reference in Comparison Header

**Problem:** A global find-and-replace of "Run v1" → "Run v{N}" also
changes the v1 card heading in the comparison section to "Run v{N}".

**Solution:** Replace "Run v2 &mdash; July 11, 2026" with
"Run v1 &mdash; July 11, 2026" after the global replace.

### Pitfall 6: Records Not Minified

**Problem:** Multi-line record formatting makes the file larger and
increases the chance of `];` appearing in string data.

**Solution:** Keep each record as a single line in the JS array.

### Pitfall 7: Python stdout Buffering

**Problem:** The pipeline produces no output when run in background mode
because Python buffers stdout.

**Solution:** Use `python3 -u` flag and include `log_msg()` function that
writes to `pipeline_run.log`.

### Pitfall 8: Missing `response` Field in Records

**Problem:** The records JS array omits the `response` field (actual copilot
response text). The per-query table response column renders empty, and the
expand-row "Response (N chars)" section shows `[empty]` or `0 chars`.

**Root cause:** The field list (Step 3) and the checklist previously
omitted `response` from the required fields, even though the JS rendering
code uses `r.response` for `respPreview` (table column) and the expand-row
response section.

**Solution:** Always include `"response":%s` in the record format string,
populated from `r.get("response", "")`.

---

## 9. Checklist

Before committing, verify ALL of these:

### Data Integrity

- [ ] Records array has exactly N entries (match pipeline count)
- [ ] All records have `query_index` from 1 to N sequentially
- [ ] Each record has ALL required fields (query_index, query, copilot_response,
      response, remarks, category, thread_id, tool_calls, info_leak,
      leak_indicators, response_quality, response_time_seconds, error,
      status_sequence, suggestions, timestamp)
- [ ] `stats` values match computed counts
- [ ] `leakTypes` values match computed leak analysis
- [ ] `catQuality` has all categories with correct counts
- [ ] `catData` has all categories with correct timing
- [ ] `catColors` has all categories mapped
- [ ] `toolCounts` has all used tools with correct counts

### Sections Preserved

- [ ] Comparison snapshot present and correct
- [ ] Stats grid (6 cards) shows v{N} numbers
- [ ] Quality buckets show correct counts and percentages
- [ ] Info leak banner shows correct count
- [ ] Info leak table renders leak details
- [ ] Quality by category table shows distribution bars
- [ ] Response time table shows visual bars
- [ ] Tool usage grid shows all tools with bars
- [ ] Per-query table has search, filter tabs, sortable columns
- [ ] Expand rows show full query, response, tools, status, suggestions, timing
- [ ] Raw data has v{N} and v1 links
- [ ] HEART principles section intact
- [ ] Footer shows correct version

### Visual Consistency

- [ ] Header gradient matches original (blue to purple)
- [ ] CSS variables unchanged
- [ ] All section headings use same font/size
- [ ] Filter tabs use same style
- [ ] Quality badges use green/amber/red
- [ ] Leak dots use amber/gray

### Code Quality

- [ ] Records are single-line (minified) format
- [ ] No `];` appears inside any record's string data
- [ ] All string escaping is correct (quotes, newlines)
- [ ] No `console.log` or debug statements left in JS
- [ ] HTML is valid (closing tags match)

### Comparison Section

- [ ] v1 card shows correct v1 metrics (50 queries, 49 success, etc.)
- [ ] v{N} card shows correct v{N} metrics
- [ ] Improvement banner shows percentage change
- [ ] Run dates are correct
- [ ] Category counts are correct

### Final Verification

- [ ] `git diff` shows only intended changes
- [ ] Dashboard renders without JS errors (test in browser or check structure)
- [ ] Commit message follows format: `Dashboard v{N}: description of changes`

---

## 10. Version History

| Version | Date | Key Changes | Agent |
|---------|------|-------------|-------|
| v1 | 2026-07-11 | Initial dashboard. 50 queries, 5 categories. Stats, quality buckets, info leak, quality by category, response time, tool usage, per-query table, raw data, HEART principles. | Manual |
| v2 | 2026-07-21 | Added 28 queries (Sales, Payments, Items, Dashboard). 80 queries, 9 categories. Added comparison snapshot section. Rebuilt all data sections. Pipeline: 79 success, 1 fail, avg 13.7s (45% faster than v1). | Hermes Agent |
| v3 | 2026-07-22 | 80 queries, 80 success, 0 failures (first zero-failure run). 9 categories. Comparison expanded to 3-column (v1/v2/v3). New tool `spawn_filter_agent` surfaced. 21/80 queries changed tool selection vs v2. Quality: 56 success, 24 marginal, 0 fail. Leaks: 28/80 (down from 33). Added `build_dashboard.py` for reproducible rebuilds. Fixed missing `response` field bug (Pitfall 8). | Hermes Agent |
| v4 | 2026-07-23 | 80 queries, 79 success, 1 failure (Q78 IncompleteRead, Dashboard). 9 categories. Comparison expanded to 4-column (v1/v2/v3/v4). New tool `get_sales` appeared and was adopted 23x — biggest tool selection shift ever (32/80 queries changed). `build_dashboard.py` rewritten to be version-agnostic (auto-detects latest version from manifest, regex-based replacements, N-column comparison). Quality: 56 success, 22 marginal, 2 fail. Leaks: 27/80. Avg response 16.9s (+18% vs v3, within noise). | Hermes Agent |

### Future Version Template

When creating v{N+1}, copy this section and fill in:

```markdown
| v{N} | {date} | {key changes}. {N} queries, {M} categories. ... | {agent} |
```

---

*This document is part of the langsmith-tool-evaluator repository.
Last updated: 2026-07-23.*
