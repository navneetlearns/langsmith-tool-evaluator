# Eval Dashboard

Evaluation tools for ZoTok AI agents. Three complementary pipelines:

## Components

### 1. Copilot Eval (Direct API — SSE Streaming)

Tests the ZoTok Seller Copilot via the SSE streaming API. Auto-OTP auth, JWT refresh, 50+ test queries from Excel.

- `copilot_query_pipeline.py` — main test runner
- `build_dashboard.py` — dashboard generator (output → `langsmith-tool-evaluator/docs/`)

### 2. LangSmith Tool Evaluation

Evaluates tool-selection accuracy in traced LangSmith runs using an external LLM judge (OpenCode/DeepSeek).

- `langsmith-tool-evaluator/evaluate_project.py` — CLI entry point
- `langsmith-tool-evaluator/docs/` — published dashboard

### 3. Playground Eval (Direct API — REST)

Tests WhatsApp bot preview API (`POST /hub/bot/api/v1/chat/preview`) — welcome bots, intent bots, custom trigger action bots. No auth, single-shot JSON responses. Declarative JSON scenarios.

- `playground/playground_pipeline.py` — main test runner
- `playground/build_dashboard.py` — dashboard generator (output → `playground/docs/`)
- `playground/scenarios/` — per-bot test case definitions

## Repo

Originally `langsmith-tool-evaluator`, consolidated into a multi-pipeline eval dashboard.

## Principles

See `HEART.md` for the governing eval principles.
