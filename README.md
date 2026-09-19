# Eval Dashboard

Multi-account evaluation for ZoTok AI agents. Three complementary pipelines:

## Components

### 1. Copilot Eval (Direct API — SSE Streaming)

Tests the ZoTok Seller Copilot via the SSE streaming API. Auto-OTP auth, JWT refresh, per-account test queries from Excel.

```
python3 copilot_query_pipeline.py --account surana     # 80 Tally/ERP queries
python3 copilot_query_pipeline.py --account unifoods   # 60 WhatsApp-group queries
python3 copilot_query_pipeline.py --account hirafoods  # 80 Tally/ERP queries (Surana query set)
python3 scripts/run_agent_evals.py --account finance   # 30 CFO insight queries (agent template, 2026-09-18)
python3 scripts/finance_pipeline.py --print             # derive summary/findings/leaks from the run (writes runs/v1/)
python3 scripts/eval_cli.py summary finance v1          # <=60-line summary (or: eval summary finance v1)
python3 scripts/eval_cli.py findings --open             # ranked actionable findings (or: eval findings)
python3 scripts/eval_cli.py show q21 [--full]           # one query: response, labels, judge, flags
python3 scripts/eval_cli.py diff v1 v2                  # per-query verdict changes + metric deltas
python3 scripts/eval_cli.py rerun --failed              # creates v2 (subset re-run, never overwrites)
python3 scripts/eval_cli.py gate --min-match 0.6        # CI gate: nonzero exit on pass rate < min
python3 build_dashboard.py --account finance            # FINANCE builds a STATIC page (no JS tables)
python3 build_dashboard.py --account surana             # Rebuild dashboard
python3 build_dashboard.py --account unifoods
python3 build_dashboard.py --account hirafoods
python3 build_dashboard.py --account finance
```

**Accounts:**

| Account | Queries | Categories | Focus | Latest Run |
|---------|---------|------------|-------|-------------|
| Surana Polycot | 80 | 9 | Tally, ERP, ledger, sales | v4 (79/80, 16.9s) |
| Unifoods | 60 | 10 | WhatsApp groups, orders, dispatch | v2 (59/60, 17.4s) |
| HiraFoods | 80 | 9 | Tally, ERP (Surana query set) | v4 rerun (79/80, 13.5s) |
| Collections (AR agent) | 80 | 10 | Receivables + WhatsApp confirmation (get_receivables) | v2 (80/80, 16.9s) |
| Finance Agent | 30 | 1 | CFO insight questions, ERP-only, clarify gate | v1 (2026-09-18): 20 answered / 9 clarify-parks / 1 fail |

**Agent-template evals (2026-09-18):** deployed `chatTemplateCode` agents (finance,
collection_and_account_receivables, order_to_dispatch, general) run through
`scripts/run_agent_evals.py` (two-turn-aware: interrupt parks flagged, JSONL schema carries
expected_behavior + expected_tool). Parser fixes landed this session: full answers arrive as
`ui` > payload > data.markdown (were dropped); SSE `error` + `interrupt` events now captured
(402 quota hits no longer misread as no_data). build_dashboard.py is clarify-aware: parks render
as a CLARIFY bucket (not fail), plus an expected-vs-observed behavior matrix and a refusal-trust
banner when records carry expected_behavior. Live: https://navneetlearns.github.io/langsmith-tool-evaluator/finance/
Queries are generator-owned (scripts/gen_finance_queries.py, scripts/gen_ar_agent_queries.py —
AR set of 70 real-entity queries ready, not yet run).

**Derived-artifact pipeline + eval CLI + story-first static page (2026-09-19):**
`scripts/finance_pipeline.py` derives a single source of truth from the raw JSONL
(outcome taxonomy answered/hard_refusal/parked/error, expected-vs-observed verdicts, value mix,
latency by outcome, deterministic content checks, leaks with matched strings + judge provenance)
into `accounts/finance/runs/v<N>/{summary.json, findings.json, judgments.jsonl, leaks.jsonl,
results.jsonl}` — invariants asserted at build (outcomes/verdicts sum == queries; judged+parked+error
== 30; this is what catches "10 failed" vs "1 failed" conflicts). `eval_cli.py` is the agent-facing
surface: `summary / findings --open / show qN / diff / rerun --failed / gate --min-match 0.6`, all
with `--json`; rerun passes `--only` to run_agent_evals.py which pre-seeds untouched rows from the
prior run so v2 stays diffable. Finance dashboards render a fully STATIC story-first page (headline
+ outcome cards + "How This Run Was Done" + "Sources & Reference" above the fold; all 7 detail
tables behind native `<details>` collapse — zero JS, opens on click; links are absolute
raw.githubusercontent.com URLs styled light so they're identifiable on dark surfaces). Tool-selection/
step framing dropped because finance streams no tool events (backend SQL); leaks show matched strings.
Other accounts build byte-identical pages (verified head-vs-head). See
`accounts/finance/runs/v1/summary.json`.

**QA lesson (2026-09-19, user-caught bugs):** structural checks (row counts, section markers, zero
console errors) do NOT catch wrong cell values or dead links — they passed while the behavior matrix
showed all-zeros and the banner JSON links 404'd. Hard build failures now: (1) cross-source
consistency — behavior-matrix column sums must equal summary.outcomes and every per-query row must
carry non-empty outcome/verdict (regression-tested); (2) no relative `../../` hrefs (Pages publishes
only docs/). When verifying a rebuilt page visually: assert VALUES against the derived JSONs and
resolve every data link against the live site; use Playwright `is_visible()` for collapse checks —
`getComputedStyle`/`getBoundingClientRect` on children of a closed `<details>` return phantom
display:block/stale boxes (the UA hides the content slot, not the child style).

**Response-Value analysis (Finance v1, 2026-09-18):** three-phase CFO-lens audit of the 30
answers — value added to an Indian SMB distributor/manufacturer CFO, beyond data fetch and
beyond re-stating the same info. Phase 1: `scripts/analyze_finance_value.py` (deterministic:
boilerplate share, cross-answer repetition, info density, figure consistency ledger — no LLM).
Phase 2: in-session cross-family judge (deepseek-v4 vs producer gpt-5.4-mini, no external API
calls) with binary rubric + FinGAIA error-code axis → `accounts/finance/runs/value_phase2_judge.json`
(every verdict carries a verbatim-asserted quote). Phase 3: shadow-answer skeletons per query
family, graded element-by-element. Result: 13/30 asks delivered decision-grade support (L4/L5),
0 data-dump answers, 5 correct refusals, 0 fabricated figures; the real defect is cross-answer
template reuse (same top-5 customer block in 9–12 answers, same KPI trio, same reconcile
boilerplate ×14). Artifacts in `accounts/finance/`: VALUE_READOUT_v1.md (owner-facing),
VALUE_SCORECARD_phase1.md, VALUE_JUDGE_phase2.md, VALUE_GRADE_phase3.md. build_dashboard.py now
renders a "Response Value" section (L4/L5 · L3 · data-dump · refusals cards + FinGAIA error-code
chips + per-row value badges) automatically when `runs/value_phase2_judge.json` exists — other
accounts build byte-identical pages.

**HiraFoods v2 (items-only subset, 2026-08-08):** 17 queries (Products & Items + Items categories only). 16/17 API success, 1 fail (SSE IncompleteRead). Response quality breakdown: 1 success, 3 marginal, **12 no-data**, 1 fail. Original finding: the HiraFoods workspace appeared to have no product-level data.

**HiraFoods v3 (full run, 2026-08-18):** 79/80 API success, 1 fail (q74 SSE read timeout at 591.9s). Quality: 51 success / 15 marginal / 13 no_data / 1 fail (vs v1: 42/19/19/0). **The v2 "no product data" finding is SUPERSEDED — the workspace gained product-level data** (Items: 5/7 success, Products & Items: 6/10 success vs 12/17 no_data in v2). Avg 13.2s excl. the timeout (v1: 11.5s). Weakest areas: Outstanding & Payments 5/10 marginal (hedged answers), Reports & Analytics 4 no_data ("no customers found" for dormant/decline reports).

**Response quality metric (v3, added 2026-08-08):** the dashboard now classifies responses into 4 buckets instead of 3. The new `no_data` bucket captures responses where the API succeeded technically but returned zero useful data to the user (no products found, couldn't complete request, try again, no matching rows, etc.). This distinguishes "graceful empty responses" from real technical failures. Detection uses pattern matching on response text against ~18 no-data indicators.

**New metrics (v2):**
- **Tool Selection Accuracy** — % of queries where actual tool matches expected_tool from Excel
- **Step Count per Completion** — avg/min/max SSE status transitions per query

**File structure:**
```
accounts/
├── surana/
│   ├── config.yaml          # Phone, workspace, seller details
│   ├── queries.xlsx         # Test queries (Format A: bold headers)
│   └── runs/                # Versioned JSONL + manifest
├── unifoods/
│   ├── config.yaml
│   ├── queries.xlsx         # Test queries (Format B: column-based)
│   └── runs/
├── hirafoods/
│   ├── config.yaml
│   ├── queries.xlsx         # Test queries (Format A: bold headers)
│   └── runs/
langsmith-tool-evaluator/docs/
├── index.html               # Landing page (links to all dashboards)
├── template.html            # HTML template
├── surana/index.html        # Surana dashboard
├── unifoods/index.html      # Unifoods dashboard
└── hirafoods/index.html     # HiraFoods dashboard
scripts/
├── verify_account_config.py # Probe: parse config with pipeline's own loader, assert fields
└── preflight_otp.py         # Probe: confirm phone registered on env before a long run
```

**Pipeline Modes:**

The pipeline supports incremental writes and resume capability:

```bash
# Standard run (auto-increment version)
python3 copilot_query_pipeline.py --account hirafoods

# Explicit version number
python3 copilot_query_pipeline.py --account hirafoods --run 5

# Resume partial run (e.g., after timeout at query 8)
python3 copilot_query_pipeline.py --account hirafoods --resume 4
```

- **Incremental writes**: Each query result is written to JSONL immediately (not buffered until end)
- **Resume capability**: If a run fails or times out, `--resume` picks up from where it left off
- **Version selection**: Use `--run` to specify exact version number

**Dashboard Versioning:**

Build dashboards for any historical version:

```bash
# Build latest version (default)
python3 build_dashboard.py --account hirafoods

# Build specific version
python3 build_dashboard.py --account hirafoods --version 1
python3 build_dashboard.py --account hirafoods --version 2
```

### 2. LangSmith Tool Evaluation

Evaluates tool-selection accuracy in traced LangSmith runs using an external LLM judge (OpenCode/DeepSeek).

- `langsmith-tool-evaluator/evaluate_project.py` — CLI entry point
- `langsmith-tool-evaluator/docs/` — published dashboard

**LangSmith account wiring** (`.env`, gitignored — never commit):

| Var | Value |
|---|---|
| `LANGSMITH_API_KEY` | `lsv2_pt_…` — new ZoTok/ZoChief account (re-attached Aug 7 2026, see eval_plan.md Part 13) |
| `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` |
| `LANGSMITH_PROJECT_NAME` | `seller-copilot-agent` |

Copies exist at `langsmith-tool-evaluator/.env` (runnable) and `eval-dashboard/langsmith-tool-evaluator/.env` (mirror). Old key backed up to `.env.bak-20260807`. Verify connectivity:

```bash
cd langsmith-tool-evaluator && python3 evaluate_project.py --limit 5
```

Note: traced runs currently show `get_sales`, `think`, `write_todos` (plus `*_node` chain/LLM runs). `tool_registry.md` must include every traced tool the judge should recognize, or runs score 0.00 for "tool not in registry".

### 3. Playground Eval (Direct API — REST)

Tests WhatsApp bot preview API (`POST /hub/bot/api/v1/chat/preview`) — welcome bots, intent bots, custom trigger action bots. No auth, single-shot JSON responses.

- `playground/playground_pipeline.py` — main test runner
- `playground/build_dashboard.py` — dashboard generator
- `playground/scenarios/` — per-bot test case definitions

## SSE Dialect Differences

Copilot accounts stream one of two SSE protocols — the stream is determined by the workspace/copilot configuration, not by query type:

| Event | Surana (agentic) | Unifoods (chat-style) | HiraFoods (chat-style) |
|-------|--------|----------|---------|
| Connection | — | `connected` | `connected` |
| Status/thinking | `thinking`, `analyzing` | `status` | `status` |
| Tool planning | `tool_start`, `tool_done` | `todo` (plan steps only) | `todo` (plan steps only) |
| Response text | `message`, `formulating` | `token` (streaming) | `token` (streaming) |
| UI rendering | — | `ui` | `ui` |
| Suggestions | `suggestions` | `suggestions` | `suggestions` |
| Done | `done` | `done` | `done` |

**Key finding (confirmed on 3 accounts)**: Surana streams an agentic protocol where tool executions are exposed (`tool_start`/`tool_done` → captured as tool calls). Unifoods and HiraFoods stream a chat-style protocol — the copilot executes tools server-side and only emits `todo` (plan-step intents, e.g. "Fetch sales grouped by district…", NOT tool calls), `token`, and `ui` events. Tool accuracy truthfully shows 0% for chat-style accounts until the backend surfaces tool events in SSE.

## Live Dashboards

- Landing: https://navneetlearns.github.io/langsmith-tool-evaluator/
- Surana: https://navneetlearns.github.io/langsmith-tool-evaluator/surana/
- Unifoods: https://navneetlearns.github.io/langsmith-tool-evaluator/unifoods/
- HiraFoods: https://navneetlearns.github.io/langsmith-tool-evaluator/hirafoods/

## Principles

See `HEART.md` for the governing eval principles.
