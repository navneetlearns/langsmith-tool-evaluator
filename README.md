# Eval Dashboard

Multi-account evaluation for ZoTok AI agents. Three complementary pipelines:

## Components

### 1. Copilot Eval (Direct API — SSE Streaming)

Tests the ZoTok Seller Copilot via the SSE streaming API. Auto-OTP auth, JWT refresh, per-account test queries from Excel.

```
python3 copilot_query_pipeline.py --account surana     # 80 Tally/ERP queries
python3 copilot_query_pipeline.py --account unifoods   # 60 WhatsApp-group queries
python3 copilot_query_pipeline.py --account hirafoods  # 80 Tally/ERP queries (Surana query set)
python3 build_dashboard.py --account surana            # Rebuild dashboard
python3 build_dashboard.py --account unifoods
python3 build_dashboard.py --account hirafoods
```

**Accounts:**

| Account | Queries | Categories | Focus | Latest Run |
|---------|---------|------------|-------|-------------|
| Surana Polycot | 80 | 9 | Tally, ERP, ledger, sales | v4 (79/80, 16.9s) |
| Unifoods | 60 | 10 | WhatsApp groups, orders, dispatch | v2 (59/60, 17.4s) |
| HiraFoods | 80 | 9 | Tally, ERP (Surana query set) | v3 (79/80, 13.2s) |

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
