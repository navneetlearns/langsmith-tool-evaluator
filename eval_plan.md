# LangSmith Tool Evaluator — Copilot API Query Pipeline

## Context

LangSmith tracing limit has been exceeded, so we can no longer pull tool traces
from LangSmith for evaluation. Instead, we will call the ZoTok Copilot API
directly — send each user query from the Surana Polycot test cases to the
copilot and record the response, building our own evaluation dataset.

---

## Part 1: Knowledge Gathered

### 1.1 HAR File Analysis (copiiiilot.zotok.ai.har / copilot.zotok.ai.har)

Two HAR (HTTP Archive) files captured from Chrome DevTools while using the
copilot at https://copilot.zotok.ai/.

### 1.2 API Endpoints (api.zotok.ai)

All endpoints are under https://api.zotok.ai/hub/copilot/ or /hub/orgs/api/.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST   | /hub/copilot/threads/init            | Create/resume a conversation thread |
| PATCH  | /hub/copilot/threads/{thread_id}     | Set thread title |
| POST   | /hub/copilot/stream                  | Send message, receive SSE response |
| GET    | /hub/copilot/threads                 | List threads |
| GET    | /hub/copilot/threads/{id}/messages   | Get message history |
| GET    | /hub/copilot/api/agent-platform/templates | Get templates |
| GET    | /hub/copilot/api/agent-platform/agents    | Get agent configs |
| GET    | /hub/orgs/api/copilot/usage/summary       | Usage metrics |
| POST   | /hub/orgs/api/copilot/refresh-token       | Refresh JWT |
| Various connector endpoints under /hub/copilot/connectors/* | |

### 1.3 Authentication

- **Method**: Bearer JWT token
- **Header**: `Authorization: Bearer <jwt_token>`
- **Refresh**: `POST /hub/orgs/api/copilot/refresh-token` with body
  `{"refreshToken": "eyJ..."}` returns `{"success":true,"data":{"token":"eyJ..."}}`
- **Observation**: HAR files did NOT capture the Authorization header (Chrome's
  HAR export strips it), but the user's Copilot.docx curl commands confirm it.
- **NOTE**: The JWT has an expiry. We need either a long-lived token or a
  refresh-token flow.

### 1.4 Conversation Flow (Thread Lifecycle)

```
1. POST /hub/copilot/threads/init
     Body: {"thread_id": "<uuid>", "sellerWorkspaceId": "<uuid>"}
     → Creates a new thread. thread_id can be pre-generated client-side.
     → Response: {"thread_id": "..."}

2. PATCH /hub/copilot/threads/{thread_id}  (optional)
     Body: {"title": "...", "sellerWorkspaceId": "<uuid>"}
     → Sets the thread title (derived from the first user message).

3. POST /hub/copilot/stream  ← MAIN
     Body: {
       "thread_id": "<uuid>",
       "message": "<user query>",
       "sellerWorkspaceId": "<uuid>",
       "wa_config_id": "<workspaceId>_<phone>",  (optional)
       "seller_details": {                         (optional)
         "firstName": "...",
         "lastName": "...",
         "email": "...",
         "mobile": "..."
       },
       "llm_provider": "gpt-5.4-mini"              (optional)
     }
     → Response: SSE (Server-Sent Events) stream
     → One stream call per message in the conversation.

4. GET /hub/copilot/threads/{thread_id}/messages  (optional)
     → Returns full message history as JSON.
```

### 1.5 SSE Response Format

The `/stream` endpoint returns a Server-Sent Events stream.
Each event is line-delimited (`event: <type>\ndata: <json>\n\n`).

**Event types:**

1. `event: connected`
   ```json
   {"thread_id": "uuid", "assistant_id": "seller_copilot", "langgraph_url": "http://localhost:8000"}
   ```
   Always the first event. Confirms connection.

2. `event: status`
   ```json
   {"phase": "<phase>", "label": "<human label>"}
   ```
   Phases observed:
   - `thinking` — Initial processing
   - `analyzing` — Analyzing the request
   - `formulating` — Formulating response
   - `tool_start` — Starting a tool call. Includes extra fields:
     ```json
     {"phase": "tool_start", "tool": "getCustomerAccountData",
      "label": "Fetching account data",
      "input": {"start_date": "2026-07-01", "end_date": "2026-07-10",
                "page_no": 1, "page_size": 1, "filter_value": ["PYMNT"]}}
     ```
   - `tool_done` — Tool call completed:
     ```json
     {"phase": "tool_done", "tool": "getCustomerAccountData",
      "label": "Fetching account data"}
     ```
     NOTE: `tool_done` does NOT include the tool's output/result.

3. `event: token`
   ```json
   {"content": "Payment"}
   ```
   Streaming text fragments. Reconstruct the full response by concatenating
   all token contents in order.

4. `event: message` (fallback, when SSE tokens aren't used)
   ```json
   {"content": "Full message text in one shot..."}
   ```

5. `event: suggestions`
   ```json
   {"suggestions": ["Follow-up suggestion 1", "..."]}
   ```

6. `event: done`
   ```json
   {}
   ```
   Signals end of stream.

### 1.6 Known Workspace & Seller Details (from HAR)

**Workspace** (for Surana Polycot tests):
```
sellerWorkspaceId = "6c4ad886-8bf6-4202-8dfb-10ae6905dd3f"
```

**Seller details** (from the stream request body):
```json
{
  "firstName": "Sarthak Rajendra Surana",
  "lastName": "",
  "email": "sarthak@suranagroup.co.in",
  "mobile": "919595259595"
}
```

**wa_config_id**: `<workspaceId>_<phone>` = `6c4ad886-..._917262960095`

**llm_provider**: `gpt-5.4-mini`

### 1.7 Tool Registry (from evaluator project)

The seller copilot's tool registry (as defined in
`registry/tool_registry.md`) lists 8 tools:

| Tool | Family | Description |
|------|--------|-------------|
| search_threads | conversation_read | Search threads by topic, category, time |
| search_messages | conversation_read | Search message content across threads |
| get_thread_messages | conversation_read | Full channel dump |
| get_channel_data | conversation_read | Channel metadata lookup |
| search_customers_master | customer_master | Resolve customers by name/mobile/code |
| getCustomerAnalytics | customer_analytics | Outstanding + ageing analytics |
| getCustomerAccountData | customer_finance | Detailed ledger entries (invoices, payments) |
| search_product_master | product_master | Product catalog search |
| get_product_analytics | product_analytics | Product performance + inventory |

NOTE: The HAR shows `get_invoice_data` being called, which is NOT in this
registry — this is the "Phantom Tool" problem (documented in
problems-and-solutions.md).

### 1.8 Test Cases (Excel)

**File**: `Copilot Test Cases ---Surana Polycot.xlsx`

Sheet: **Chat Queries** (57 queries × 3 columns)
- Column A: User Queries (the test input)
- Column B: Copilot Response (previously recorded response, human-captured)
- Column C: Remarks (human annotations)

Other sheets: Test (UI flow), Issues (bugs), Connector Test Cases, Sequence
Diagram, API Flow Diagram.

### 1.9 Existing Evaluator Code (in langsmith-tool-evaluator/)

| File | Purpose |
|------|---------|
| evaluate_project.py | CLI entry point |
| evaluators/tool_selection.py | Per-run evaluation loop |
| evaluators/experiment.py | LangSmith experiment mode |
| evaluators/prompt_builder.py | Tool registry parser + prompt builder |
| utils/langsmith_client.py | LangSmith connection |
| utils/opencode_client.py | OpenCode (LLM Judge) client |
| utils/trace_parser.py | Run parser (handles 4+ msg formats) |
| prompts/tool_selection_prompt.txt | 7-step LLM judge prompt |

The evaluator is designed for LangSmith runs. We need a new pipeline that:
- Replaces the LangSmith client with direct copilot API calls
- Parses SSE responses instead of LangSmith run dicts
- Outputs a JSONL file that can later be fed to the LLM judge

### 1.10 Known Limitations / Gaps

1. **No Authorization header in HAR** — JWT token needed from user.
2. **No tool output data** — SSE `tool_done` does not include results.
3. **`get_invoice_data` is not in the registry** — phantom tool.
4. **Multi-turn context lost** — each query sent to a fresh thread.
5. **JWT expiry** — need refresh flow for sustained runs.

---

## Part 2: Implementation Plan

### Step 1 — Get a Fresh JWT Token
- User provides a valid `Authorization: Bearer <token>` from their browser.
- Verify it works with a test `GET /hub/copilot/threads` call.

### Step 2 — Build `copilot_query_pipeline.py`
A Python script that:

**2a. Reads test queries from Excel**
- Parse `Copilot Test Cases ---Surana Polycot.xlsx`, sheet "Chat Queries"
- Extract: query text, category (inferred from Excel groupings), remarks

**2b. For each query, calls the copilot API**
- Generate a unique `thread_id` (UUID v4)
- `POST /hub/copilot/threads/init` → init thread
- `PATCH /hub/copilot/threads/{id}` → set title (truncated query)
- `POST /hub/copilot/stream` → send query, parse SSE in real-time
- Extract: tool_start events (tool + args), token events (final response),
  suggestions, status sequence
- Wait for `event: done` before proceeding

**2c. Stores results as JSONL**
```json
{
  "query_index": 1,
  "query": "Show me the sales report...",
  "category": "Reports & Analytics",
  "copilot_response": "...",
  "tools_used": [
    {"tool": "getCustomerAnalytics", "input": {...}}
  ],
  "status_sequence": ["thinking", "analyzing", "tool_start", "tool_done", "formulating"],
  "suggestions": ["..."],
  "thread_id": "uuid",
  "timestamp": "2026-07-10T...",
  "remarks": "Report generated but not insights."
}
```

**2d. Error handling (per HEART.md principles)**
- NO retry on failed queries — errors are real user-visible results
- Auth errors (401): silently re-auth via auto-OTP and continue (user never sees this)
- SSE stream timeout: 300s per query (multi-turn, data-driven responses take time)
- Socket hang detection: 120s no-data cutoff (catches genuine hangs)
- All errors recorded in JSONL with: error message, partial response, tools called before failure, time elapsed
- Response time measured per query: POST /stream → event: done

### Step 3 — Run the Pipeline
- Execute `python3 copilot_query_pipeline.py`
- 57 queries, each takes ~10-30 seconds (waiting for SSE stream)
- Estimated total: 10-30 minutes
- Monitor progress, handle any failures

### Step 4 — Build Offline LLM Judge Adapter
**Why**: The existing LLM judge was designed for LangSmith run dicts. We need
an adapter that reads our JSONL format and runs the judge against each entry.

**What it does**:
- Reads `query_results.jsonl`
- For each entry: builds the judge prompt with
  `{TOOL_REGISTRY, USER_QUERY, SELECTED_TOOL, SELECTED_TOOL_ARGS}`
- Calls OpenCode (deepseek-v4-flash) for a score
- Stores result: `score, expected_tool, reason, candidate_tools`
- Outputs `eval_results.jsonl`

### Step 5 — Build Summary Dashboard (Optional)
- Compute aggregate metrics:
  - Average tool selection score
  - Tool usage frequency histogram
  - Phantom tool count (tools not in registry)
  - Category-wise performance breakdown
- Compare against human remarks from Excel for accuracy

---

## Part 3: Authentication Flow (RESOLVED)

### Auth Endpoints

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| /hub/orgs/api/copilot/sendOtp | POST | `{"mobile": "9595259595"}` (10-digit, NO country code) | `{data: {otp: "6294", otpToken: "eyJ...", flow: "SIGNIN"}}` |
| /hub/orgs/api/copilot/verifyOtp | POST | `{"mobile": "9595259595", "otp": "6294", "otpToken": "eyJ..."}` | `{data: {token: "eyJ...", refreshToken: "eyJ...", workspaces: [{id: "6c4ad886-..."}]}}` |

### Token Details
- **Bearer token**: 20-minute lifetime, scope `copilot-otp`
- **Refresh token**: Included in verifyOtp response, used to get new Bearer tokens
- **refresh-token endpoint**: `POST /hub/orgs/api/copilot/refresh-token` with body `{"refreshToken": "eyJ..."}`
- **Storage keys** (from JS bundle): `seller_token`, `seller_refresh_token`, `seller_workspace_id`

### Auth Flow in Pipeline
```
1. sendOtp(mobile="9595259595")
2. verifyOtp(mobile, otp, otpToken) → get token + refreshToken
3. For each batch of queries, if token expires, call refresh-token
```

---

## Part 4: Required Inputs from User

| Item | Status |
|------|--------|
| Fresh JWT Bearer token | ✅ RESOLVED — auto-auth via sendOtp+verifyOtp |
| Confirm workspaceId is correct | ✅ Verified from HAR |
| Phone number (10-digit) | ✅ 9595259595 (without country code) |
| Rate limit concerns | unknown |

---

## Part 5: File Structure

```
/mnt/f/Langsmith/COPILOT/                   (git root: navneetlearns/langsmith-tool-evaluator)
├── copilot_query_pipeline.py               ← Main pipeline script (COMPLETED, 652 lines)
├── HEART.md                                ← Key principles of eval testing (6 principles)
├── eval_plan.md                            ← THIS FILE: plan + knowledge
├── Copilot.docx                            ← curl commands reference
├── copiiiilot.zotok.ai.har                 ← reference HAR (new)
├── copilot.zotok.ai.har                    ← reference HAR (old)
├── Tool_Selection_Eval.py                  ← connectivity test script
├── tool_registry.md                        ← root-level registry
├── runs/                                    ← Versioned pipeline outputs
│   ├── query_results_v1.jsonl              ← Run v1 raw results (50 records, 55KB)
│   └── manifest.json                       ← Versioned run manifest
├── .github/workflows/
│   └── deploy-pages.yml                    ← GitHub Actions: auto-deploy dashboard on push
└── langsmith-tool-evaluator/                ← Evaluator project (existing)
    ├── docs/
    │   └── index.html                      ← Eval dashboard (live on GitHub Pages)
    ├── runs/
    │   ├── query_results_v1.jsonl           ← Copy of v1 results in repo
    │   └── manifest.json                    ← Copy of manifest in repo
    ├── registry/tool_registry.md           ← 8-tool registry
    ├── evaluators/                          ← LangSmith-based evaluators (legacy)
    ├── utils/                               ← LLM judge client + trace parser (reusable)
    ├── prompts/                             ← 7-step judge prompt
    ├── problems-and-solutions.md           ← Known issues doc
    └── .env                                 ← API credentials
```

---

## Part 6: Phase 1 Results — Run v1 (July 11, 2026)

### Pipeline Execution

- Script: `copilot_query_pipeline.py` (652 lines, auto-OTP auth, SSE parser, versioned output)
- Queries: 50 (from Excel "Chat Queries" sheet, 5 categories × 10 queries)
- Total runtime: ~22 minutes
- Output: `runs/query_results_v1.jsonl` (50 records, 55KB)
- Manifest: `runs/manifest.json`
- Dashboard: https://navneetlearns.github.io/langsmith-tool-evaluator/

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total queries | 50 |
| Succeeded | 49 |
| Failed | 1 (query #24: SSE read timeout at 306.6s) |
| Avg response time | 25.1s |
| Queries with no tool called | 10 (20%) |
| Distinct tools used | 6 of 8 registered |
| Phantom tools | 0 |

### Response Time by Category

| Category | Avg | Min | Max | Status |
|----------|-----|-----|-----|--------|
| Ledger | 84.9s | 10.7s | 306.6s | 9 OK, 1 FAIL |
| Reports & Analytics | 11.2s | 7.1s | 25.1s | 10 OK |
| Outstanding & Payments | 12.0s | 4.4s | 16.1s | 10 OK |
| Orders & Invoices | 9.7s | 6.8s | 14.5s | 10 OK |
| Products & Items | 7.8s | 5.0s | 9.2s | 10 OK |

Key finding: Ledger category is 6-8x slower than all other categories.

### Tool Usage Frequency

| Tool | Times Called |
|------|-------------|
| getCustomerAnalytics | 15 |
| search_customers_master | 13 |
| get_product_analytics | 11 |
| getCustomerAccountData | 9 |
| search_threads | 1 |
| search_product_master | 1 |
| (no tool called) | 10 queries |

Tools NEVER used: search_messages, get_thread_messages, get_channel_data.

### Notable Issues Found

1. Query #24 (Ledger): SSE read timeout at 306.6s — backend completely hung
2. Query #28 (Ledger): Empty response (0 chars) after 58s — no error, just nothing returned
3. 10/50 queries called NO tool — copilot answered from "general knowledge" without data lookup
4. get_product_analytics responses are suspiciously short (67-88 chars) — likely returning "no data" messages
5. Ledger queries are extremely slow (84.9s avg vs 7-12s for others) — backend performance issue

---

## Part 7: Immediate Next Steps

1. ✅ Understand the HAR files (done)
2. ✅ Understand the API format (done)
3. ✅ Understand auth mechanism (done — auto-OTP via sendOtp/verifyOtp)
4. ✅ Build `copilot_query_pipeline.py` (652 lines, HEART.md principles)
5. ✅ Run pipeline against 50 queries → `runs/query_results_v1.jsonl`
6. ✅ Deploy interactive dashboard to GitHub Pages
7. ⬜ Build offline LLM judge adapter → `eval_results_v{N}.jsonl`
8. ⬜ Build summary dashboard with score distribution + cross-version comparison
9. ⬜ Commit eval results and push to repo
