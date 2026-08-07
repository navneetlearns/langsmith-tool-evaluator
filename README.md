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
| HiraFoods | 80 | 9 | Tally, ERP (Surana query set) | v1 (80/80, 11.5s) |

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
```

### 2. LangSmith Tool Evaluation

Evaluates tool-selection accuracy in traced LangSmith runs using an external LLM judge (OpenCode/DeepSeek).

- `langsmith-tool-evaluator/evaluate_project.py` — CLI entry point
- `langsmith-tool-evaluator/docs/` — published dashboard

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
