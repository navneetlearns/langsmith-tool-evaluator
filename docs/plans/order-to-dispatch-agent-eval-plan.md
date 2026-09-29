# Order to Dispatch Agent — First Eval Plan (2026-09-18)

**Status:** Proposed — NOT approved. Executes only after the user confirms the decision gates in §0.

## Goal

Run the first eval on the newly deployed chat-template agents ("agents") using the
existing copilot eval harness, so owners get a measured readout: completion,
4-bucket response quality, tool-selection accuracy vs an expected_tool label,
refusal correctness, and latency — plus a dashboard, like collections v1/v2.

## Discovery (done 2026-09-18, probe scripts in /tmp/hermes-verify-*.py)

`GET /hub/copilot/api/agent-platform/deployed-chat-templates?sellerWorkspaceId=<ws>`
on the hirafoods workspace (c331ac11-c3e8-4d42-a8d6-b8b04127354c, phone 4040505050)
returns exactly 2 deployed templates:

| Code | id | Prompt | Surface |
|---|---|---|---|
| **order_to_dispatch** | b7d05886-74c2-4ce0-a4ee-a201c9f068d0 | 6,649 ch | NEW agent (this plan's target) |
| **general** | 0b7b0c0a-f9d2-4cdf-a464-7328ddddd0d8 | 21,457 ch | generic Seller Copilot (search_threads + query_types) — also the only template on the surana workspace (surana's entry has an empty code); unifoods ws: none |

Full prompts saved: /tmp/agent-discovery/hirafoods__order_to_dispatch.txt,
/tmp/agent-discovery/hirafoods__general.txt.

### order_to_dispatch system-prompt facts (the grounding for the query set)

- Tools (read-only, strict routing): `list_orders` · `get_order_details` (include_invoice=true)
  · `list_invoices` · `list_dispatch_notes` · `get_receivables` · `get_collections` ·
  `get_sales`/`getCustomerAnalytics`/`getCustomerAccountData`/product tools ·
  `search_customers_master` (resolve named customer FIRST).
- Order statuses are EXACT: Draft/Created/AddingItems/SubmittedByCustomer/Approved/Confirmed/
  Billed/Dispatched/PartiallyDelivered/Delivered/Cancelled. **`Notified` is NOT an order status.**
- Dispatch-note statuses: Draft_Dispatched/Submitted/Accepted/Rejected/Dispatched/Delivered.
  `Accepted` = dispatch note; `Approved` = order.
- Never infer Approved/Billed/Dispatched/Delivered from an earlier status; never infer delivery
  from invoice/payment/sales/ledger; report unmatched order/invoice/dispatch links plainly.
- Unsupported (read-only guard): create/edit/cancel/submit/approve/bill/dispatch/deliver/message
  → correct behavior = `tool_calls: []` + "cannot" answer. These are NO_TOOL queries, not failures.
- Response contract: ONE JSON object `{"message":"...","suggestions":["...","..."]}` — 2-3
  imperative ≤6-word suggestions, matching the seller's latest language/script. ₹ values from
  invoice/receivables/collections tools are ALREADY rupees; never divide.
- `list_invoices` is NOT the source for outstanding/overdue/ageing/due-date facts (use
  get_receivables); `get_collections` only for payments actually received.

## §0 Decision gates (need user answers before any execution)

1. **Scope:** order_to_dispatch only (recommended) — or also `general` on the same workspace
   (second account, same pipeline).
2. **Query set:** 80 queries / 10 categories (parity with surana/hirafoods/collections,
   recommended) or a smaller 40-50 first pass.
3. **Surana untouched rule:** the 2 untracked probe leftovers (accounts/surana/runs/
   query_results_v5.jsonl 3-query probe, accounts/hirafoods/runs/probe_v4_raw.txt) stay as-is
   unless the user says otherwise — no commits touching surana files.
4. **Push:** results will be committed locally; nothing pushed without explicit go (standing rule).

## Phase 1 — Probe gate (interface-changed rule, BEFORE building any query set)

Write /tmp/hermes-verify-o2d-probe.py: raw SSE dump with chatTemplateCode=order_to_dispatch
(POST /threads/init → POST /stream, print event:+data:, split on "\n\n") for 3 queries —
(1) "How many orders are still in draft?", (2) "Show dispatch notes not yet delivered",
(3) "Approve order X" (refusal check). Verify:

- [ ] init returns 200; if flaky, run evidence probe N=10 (scripts/evid_init_flaky.py pattern)
      and log every HTTP status BEFORE calling anything flaky.
- [ ] Event vocabulary matches the parser (agentic status.phase tool_start/tool_done) — if it
      differs (e.g. JSON contract delivered as a ui/token payload), diff against
      references/stream-protocols.md and report the delta; do NOT silently patch the parser.
- [ ] tool_calls captured for real queries; empty for the refusal query.
- [ ] Response language/₹ rendering sane.

Verdict: parser-compatible (proceed) or needs a documented tweak (block, show evidence).

## Phase 2 — Query-set generator (source of truth = the SCRIPT, like collections)

Create `scripts/gen_order_dispatch_queries.py` owning a SECTIONS dict; on run it writes
`accounts/order_to_dispatch/queries.xlsx` (col A query, B reference, C remarks,
D expected_tool = `TOOL:<tool>` | `NO_TOOL`). ~80 queries / 10 categories:

1. Order Status & Counts (8-10) — `TOOL:list_orders` (exact status names, totalRecords)
2. Lifecycle Progress (8-10) — `TOOL:list_orders` → `get_order_details` (include_invoice)
3. Pending Work & Delays (8-10) — `TOOL:list_orders` (pending/delayed/exceptions)
4. Order Details & Lines (8) — `TOOL:get_order_details`
5. Invoices & Documents (8) — `TOOL:list_invoices` (document-number lookups, orderId joins)
6. Dispatch & Delivery (8-10) — `TOOL:list_dispatch_notes` (subset statuses, transport)
7. Receivables & Overdue (8) — `TOOL:get_receivables` (open balances, ageing, follow-up)
8. Collections & Payments (8) — `TOOL:get_collections` (received payments, period compare)
9. Cross-source Joins (6-8) — order→invoice→dispatch on explicit IDs; unmatched links
10. Refusals / Read-Only Guard (8-10) — `NO_TOOL` (approve/bill/dispatch/message/cancel/edit;
    "notified?" from order status; deliver-from-payment inference)

Rules baked in: real customer names resolved by probe first (Radha pattern — a placeholder like
"ABC Industries" dead-ends; use names confirmed in the workspace), exact status vocabulary
(Notified never appears as an order status; Accepted vs Approved), NO_TOOL for EVERY request
type the prompt refuses. Print `queries=N TOOL-expected=X NO_TOOL=Y` on run; assert N==80.

## Phase 3 — Scaffold account

- Create `accounts/order_to_dispatch/config.yaml`: phone 4040505050, workspace_id
  c331ac11-c3e8-4d42-a8d6-b8b04127354c, chatTemplateCode `order_to_dispatch`
  (a confirmed deployed code — the safest class of value, unlike the flaky collections code),
  llm_provider gpt-5.4-mini, base_url https://api.zotok.ai, sse_timeout 300, sse_read_timeout 120.
- `python3 scripts/gen_order_dispatch_queries.py` → verify xlsx count excludes header + category
  rows (assert 80, not 91).
- Verify config with the pipeline's own loader: `python3 scripts/verify_account_config.py
  order_to_dispatch 4040505050` (exits 0; catches the empty-value loader bug if it regressed).

## Phase 4 — Preflight + full run

- `python3 scripts/preflight_otp.py 4040505050` (connectivity/flow check only — OTP echoes for
  any phone; the real gate is the in-run auth step).
- Background run: `python3 copilot_query_pipeline.py --account order_to_dispatch`, tee to
  order_to_dispatch_pipeline_run.log, notify on complete (~80 × 13-17s ≈ 25-30 min).
- Watch incremental jsonl mid-run (`tail -f accounts/order_to_dispatch/runs/query_results_v1.jsonl`);
  on a partial failure resume with `--resume N` — never re-run completed rows.
- No retries on failures (HEART principles); a technical fail (IncompleteRead/timeout) is recorded
  as `fail`, not re-fired.

## Phase 5 — Analysis

- 4-bucket quality via `build_dashboard.classify_quality()` (import, pass the FULL record dict).
- Tool-accuracy vs expected_tool: strict + lenient (lenient = any genuine get_*/search_* data call
  satisfies a TOOL-marked intent — lesson from collections v2); flag NO_TOOL queries that called a
  tool (over-reach) and TOOL queries answered "cannot" (under-delivery).
- Refusal correctness: NO_TOOL queries MUST have empty tool_calls AND a "cannot" answer.
- Tool-surface inventory: any tool called OUTSIDE the prompt's routing list = drift flag for owners.
- Meaningful-response health: records with no error + non-empty response; count sub-100-char
  responses separately (possible no_data, not failure).
- Latency avg/P95. Data caveat: if the workspace lacks order/dispatch data, expect no_data buckets —
  a finding to report, not an eval failure.

## Phase 6 — Deliverables

- `accounts/order_to_dispatch/EVAL_READOUT_v1.md` (the agent-owner artifact): completion/fail counts,
  bucket table, tool-accuracy, what the agent got RIGHT (safe refusals), action list (tool drift,
  mapping errors) — BEFORE the dashboard, same ordering as collections.
- `python3 build_dashboard.py --account order_to_dispatch` → docs/order_to_dispatch/index.html;
  add a hardcoded landing card in langsmith-tool-evaluator/docs/index.html (like surana/collections).
- Visually verify the dashboard with Playwright (headless render, assert stat-card counts, zero JS
  console errors) — never file-size checks alone.
- Commit locally (plan + probe scripts + account + readout + dashboard). Push only on explicit go.
- Update the zotok-copilot-eval skill with the new account row + this prompt summary + any
  protocol/parser deltas found in Phase 1.

## Stretch (only after gates + first-run approval)

- `general` agent eval (second account `accounts/general/`, same pipeline).
- Collections-style maturity: classification churn metric at version 2, quality-gate release
  rule (a vN+1 may only be promoted if it beats-or-matches the vN baseline on the golden set).

## Verification checklist

1. /tmp/hermes-verify-o2d-probe.py: init 200; tool_start/tool_done events present; refusal query
   shows tool_calls [].
2. `verify_account_config.py order_to_dispatch 4040505050` exits 0.
3. Generator prints `queries=80 TOOL-expected≈65 NO_TOOL≈15`; xlsx row count (data rows only) == 80;
   no "ABC" placeholder anywhere.
4. Run completes: manifest v1 row present (success + failed + avg time), jsonl has 80 records.
5. classify_quality buckets parse without AttributeError; counts sum to 80.
6. Meaningful-response count reported (expect ~80 minus technical fails).
7. EVAL_READOUT_v1.md exists and lists ≥1 action item or an explicit "no drift found".
8. Dashboard HTML renders real counts (Playwright check), landing card links to docs/order_to_dispatch/.
9. `git status --short` clean after commit (except pre-existing surana/v5 + probe_v4_raw leftovers
   if user chose to leave them).