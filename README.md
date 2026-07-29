# Eval Dashboard

Multi-account evaluation for ZoTok AI agents. Three complementary pipelines:

## Components

### 1. Copilot Eval (Direct API — SSE Streaming)

Tests the ZoTok Seller Copilot via the SSE streaming API. Auto-OTP auth, JWT refresh, per-account test queries from Excel.

```
python3 copilot_query_pipeline.py --account surana     # 80 Tally/ERP queries
python3 copilot_query_pipeline.py --account unifoods   # 60 WhatsApp-group queries
python3 build_dashboard.py --account surana            # Rebuild dashboard
python3 build_dashboard.py --account unifoods
```

**Accounts:**

| Account | Queries | Categories | Focus | Latest Run |
|---------|---------|------------|-------|-------------|
| Surana Polycot | 80 | 9 | Tally, ERP, ledger, sales | v4 (79/80, 16.9s) |
| Unifoods | 60 | 10 | WhatsApp groups, orders, dispatch | v2 (59/60, 17.4s) |

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
langsmith-tool-evaluator/docs/
├── index.html               # Landing page (links to both dashboards)
├── template.html            # HTML template
├── surana/index.html        # Surana dashboard
└── unifoods/index.html      # Unifoods dashboard
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

Surana and Unifoods copilots use different SSE event types:

| Event | Surana | Unifoods |
|-------|--------|----------|
| Connection | — | `connected` |
| Status/thinking | `thinking`, `analyzing` | `status` |
| Tool planning | `tool_start`, `tool_done` | `todo` (server-side, not exposed) |
| Response text | `message`, `formulating` | `token` (streaming) |
| UI rendering | — | `ui` |
| Suggestions | `suggestions` | `suggestions` |
| Done | `done` | `done` |

**Key finding**: Unifoods copilot executes tools server-side and doesn't expose tool names via SSE events. Tool accuracy will show 0% for Unifoods until tool events are surfaced by the backend.

## Live Dashboards

- Landing: https://navneetlearns.github.io/langsmith-tool-evaluator/
- Surana: https://navneetlearns.github.io/langsmith-tool-evaluator/surana/
- Unifoods: https://navneetlearns.github.io/langsmith-tool-evaluator/unifoods/

## Principles

See `HEART.md` for the governing eval principles.
