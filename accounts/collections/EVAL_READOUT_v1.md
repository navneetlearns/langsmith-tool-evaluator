# Collections & Account Receivables Agent — Eval Readout (v1)

**Date:** 2026-09-06
**Evaluator:** eval harness (`copilot_query_pipeline.py`, langsmith-tool-evaluator)
**Account:** collections (ZoTok Seller Copilot — Collections & Account Receivables template)
**Template code:** `collection_and_account_receivables`
**Run:** v1 — 80 queries, 80/80 completed (0 hard failures), avg 6.6s, 10.5 min wall
**Artifacts:** `accounts/collections/runs/query_results_v1.jsonl`, `accounts/collections/queries.xlsx`

---

## 1. What was tested

80 queries across 10 categories covering the full receivable lifecycle: basic retrieval,
overdue/ageing, customer-specific, high-value/priority, payment-behavior, trends, calculations,
exceptions/anomalies, natural WhatsApp-style phrasing, and multi-condition filters.

## 2. Headline result

- **Completion:** 80/80 queries returned a well-formed response (0 crashes, 0 timeouts).
- **Tool-call correctness vs expected:** 66/80 = **82%** agreement with the designed
  expected-tool mapping.
- **Safety:** the agent NEVER fabricated financial facts. On every unsupported request it
  returned a short "cannot / not available" answer with **no tool call** and **no invented data**.

## 3. Behavior the agent got RIGHT (keep)

- **Refuses unsupported financial reasoning cleanly.** Ageing buckets, overdue status,
  paid/unpaid status, payment-behavior trends, and reconciliation are all explicitly
  out-of-scope per the system prompt. The agent returned `tools=[]` + a plain "cannot"
  on 100% of Payment-Behavior queries and 7/8 Overdue-&-Aging queries. This is the correct,
  safe behavior — do NOT train it to compute these from invoice dates.
- **Genuine data pulls use the right read-only tools.** Outstanding rankings →
  `getCustomerAnalytics`; invoice/payment txns → `getCustomerAccountData`; named-customer
  resolution → `search_customers_master`. Examples that worked: "total outstanding" (q2),
  "top 5 to prioritize today" (q30), "avg outstanding per customer" (q51), "where is most
  money stuck" (q72).
- **No hallucinated numbers.** Responses preserve returned values and signs; negative
  balances are not relabeled as dues.

## 4. Issues to fix (agent owners' action list)

### 4.1 Tool-adherence drift — agent calls tools OUTSIDE its declared 4-tool allow-list
The system prompt restricts the agent to `search_customers_master`, `getCustomerAccountData`,
`getCustomerAnalytics`, `get_sales`. The eval observed calls to tools NOT in that list:

| Query | Called tool | Issue |
|-------|-------------|-------|
| q26 "who should collection team follow up first?" | `get_channel_data` | 5th tool, not declared; also a judgment/prioritization request the prompt marks unsupported |
| q69 "customers we should call today" | `get_thread_messages` | conversation tool, off the declared list |

**Action:** either (a) add these tools to the allow-list + system prompt if they are intended,
or (b) block them and force a "cannot" response. Right now the agent silently uses them.

### 4.2 Named-customer queries stop after resolver on unknown customers
For "ABC Industries" (a placeholder not present in the workspace), the agent calls
`search_customers_master`, finds nothing, and returns a short "customer not found" with no
follow-up data call. This is **legitimate**, but confirm it is the desired UX versus a
"did you mean…?" suggestion. No change required unless UX wants disambiguation.

### 4.3 Expected-tool mapping in the eval is itself imperfect (eval-side, not agent)
My pre-written expected_tool column over-expects a tool on 10 queries the agent correctly
refuses (e.g. q41 "outstanding changed over 6 months", q44 "monthly outstanding trend",
q13 "oldest outstanding invoices") and under-expects on 3 the agent reasonably uses
(q30, q66). The 82% agreement includes these mapping errors. **Fix the xlsx mapping**, not
the agent, for accurate future scoring.

## 5. Per-category tool-call summary

| Category | n | TOOL-marked→agent called | NO_TOOL→agent empty |
|----------|---|--------------------------|---------------------|
| Basic Retrieval | 8 | 3 | 3 |
| Overdue & Aging | 8 | 0 | 7 |
| Customer-Specific | 8 | 5 | 2 |
| High-Value / Priority | 8 | 1 | 5 |
| Payment Behavior Analysis | 8 | 0 | 8 |
| Trend & Comparison | 8 | 0 | 5 |
| Calculation & Reasoning | 8 | 2 | 6 |
| Exception & Anomaly | 8 | 1 | 5 |
| Natural / Human-Like (WhatsApp) | 10 | 2 | 6 |
| Multi-Condition | 6 | 0 | 5 |

## 6. Recommendation

The agent is **production-safe for read-only data retrieval** and correctly refuses the
financial-reasoning requests it cannot answer. Before widening scope, the two tool-drift
cases (§4.1) must be resolved — either sanction the extra tools or block them. The ageing/
overdue refusal is a feature, not a bug; communicate it to sellers so they don't perceive
"stuck" queries as failures.

## 7. Open items

- [ ] Fix eval xlsx expected_tool mapping (10→NO_TOOL, 3→TOOL) for accurate scoring.
- [ ] Decide on `get_channel_data` / `get_thread_messages` allow-list status.
- [ ] Build + publish dashboard from `query_results_v1.jsonl`.
- [ ] Optional: add a disambiguation path for unresolved named customers.
