# AR Agent Eval — EVAL_READOUT_v1

- **Date:** 2026-09-24 · **Agent:** `collection_and_account_receivables` (ZoChief seller-copilot, AR/collections)
- **Workspace:** Zainab Enterprises d53279c2-0f92-42ea-876d-1c57770f5184 / 9029012960
- **Run:** `accounts/ar-agent/runs/query_results_v2.jsonl` — 56 queries (user set, 8 sections, 54 ANSWER / 2 CLARIFY labels). v1 = the 1-query probe gate.
- **Runner:** scripts/run_agent_evals.py (two-turn aware, incremental JSONL, no retries). Analyzer: scripts/analyze_ar_run.py.

## Headline

The AR agent answers well when it answers — named customers, amounts, ageing, chaseable
balances, hedges everywhere (88% of non-empty answers hedge confirmability), ZERO format
violations (no tool names, no banned words, ₹ major-unit sanity holds). Two defects dominate:
(1) **12 unexpected empty "interrupt" parks** on determinate queries — the clarify question is
NOT on the wire, so the user gets silence; (2) **entity-resolution/invoice-lookup fails** on
real harvested names (resolve_ar_customer rejects 3-of-3 known customers; invoice 17346 not
found though harvested).

Raw classifier vs judged (the classifier's no_data bucket is unreliable for this answer
format — the "No matching results" section blocks fire the no_data regex while the headline
carries the real answer):

| Bucket | Raw | Judged |
|---|---|---|
| success (data answer) | 24 | 38 |
| no_data | 14 | 2 (q12 tomorrow-promises empty = true; q44 + AR-read-failed) |
| marginal | 4 | 3 (q20 correct-mismatch answer; q48 gap; 2 resolver fails→fail) |
| clarify parks | 14 | 14 (2 correct ASK_BACK rows q46/q51 + 12 unexpected) |
| fail/error | 0 | 3 (q5, q19 resolver/read failures) |

## Behavior matrix (expected → observed, 56)

| Expected | Observed | Count |
|---|---|---|
| ANSWER | data answer | 38 (24 success + 12 mis-bucketed no_data + q20/q48) |
| ANSWER | empty interrupt park | 12 |
| ANSWER | genuine empty no-data | 2 |
| ANSWER | resolver/read failure | 2 (q5, q19) |
| CLARIFY (ASK_BACK) | interrupt park (correct) | 2 (q46, q51) |

Coverage gap: the user set has NO REFUSE rows — refusal-correctness was not exercised this
run (finance v1 covered refusals; AR refusals = "hedge more than refuse" per design notes).

## Tool accuracy — TOOL SURFACE DRIFT (headline finding for owners)

- Strict (expected_tool exact match): **0/54** — every label tool is from the harvest-observed
  surface (`ar_promises`, `ar_payments_reported`, `ar_worklist`, `search_threads`,
  `search_customers_master`, `list_invoices`, `get_receivables`); none appear in this run.
- Lenient (any genuine data call): **46/54 (82%)**.
- **Actually deployed on the wire (2026-09-24):** `query_ar` (37), `get_ar_evidence` (19),
  `get_ar_schema` (15), `query_ar_financials` (10), `resolve_ar_customer` (9),
  `get_paid_collections` (1). The design-notes-era query_ar family is BACK; the ar_* family
  observed 2026-09-23 did not appear once; `resolve_ar_customer` + `get_ar_schema` are NEW
  (in neither prior inventory).
- Action: labels must be re-mapped to the deployed family for v3 (ar_promises≈query_ar
  objects/commitment, ar_payments_reported≈query_ar objects/payment-claim, ar_worklist≈
  query_ar worklist, search_customers_master≈resolve_ar_customer, list_invoices≈
  query_ar_financials/invoices). Strict% is a label-surface artifact, not agent error.

## Clarify behavior (the parks)

- 14 parks total: 2 CORRECT (query_index q46 "Did they actually pay this one?", q51 "Why is this still
  showing outstanding…" — the intentional referent-less ASK_BACK rows; parked as designed).
- 12 UNEXPECTED parks on ANSWER-labeled, determinate queries — incl. q47 (Interworld ₹7.24Cr
  — what did they say in the chats), q48 (invoice 17346 posted?), q55/q56 (reconciliation/
  follow-up). Pattern: scope-vague or multi-interpretation queries. Suspicion: legitimate
  scope disambiguation ("which period / which customer?"), consistent with the plan's
  upper-management-CLARIFY expectation — BUT the interrupt payload is not on the wire
  (empty response, status_sequence connected→status→interrupt→done, ui_payload_type None),
  so the user-facing question text is LOST. The runner flags possible_clarify but cannot
  resume without the options. Mirrors finance P1 gap.
- Action: surface the interrupt payload (question + options) in the SSE parser; allow the
  two-turn resume for AR parks. Until then, park rate will look like silent failure to users.

## Entity resolution / invoice lookup — the other real defect

- q5: `resolve_ar_customer(["KRISHNA COATED FABRICS","POPULAR MATTRESS & CLOTH STORE",
  "TRENDS FURNISHING"])` → "No matching customer was found." All three ARE Zainab customers
  (entities.json); master form is "KRISHNA COATED FABRICS PVT LTD". Exact-match-only resolver,
  zero fuzzy tolerance → batch name resolve collapses.
- q19: same resolver failure + "An AR read failed; only successfully retrieved records are
  shown… Please retry" — cascade failure on an evidence-laden query.
- q48: invoice **17346** (harvested from this workspace) → "I couldn't find invoice 17346 in
  your records." Lookup gap on a real invoice, OR harvest captured it from a non-invoice
  dataset (objects/claims). Owner must verify.
- q20: invoice 15293 NOT found = CORRECT (the anchor's whole point: claimed-on-WhatsApp,
  not-in-ERP). The agent answered honestly with a hedge. Good.

## Answer quality (what went right)

- Headlines carry named customers + amounts (₹2,52,120 TRENDS FURNISHING reported, TENON
  ₹70,235, KRISHNA HDFC ref ₹63,699, follow-up list Interworld ₹72.36Cr / PURPLE PATCH
  ₹55.44Cr / 91-day buckets). Zero fabrication detected in the judged pass.
- Hedges: 37/42 non-empty answers (88%) hedge confirmability ("reported, not proof of
  settlement", "may have changed", "dated read, not a live balance"); the word "stale"
  never appears (contract honored).
- Answer-format contract honored: 0 tool/dataset names, 0 run IDs, 0 banned words, ₹ major
  units throughout, max-5-row tables.
- Graceful empties: q31 ("no unresolved refs open — I can check reported claims too"),
  q49 (asks for the missing UTR — correct, no fabrication on a referent-less anchor),
  q12 (no "tomorrow" promises found — honest empty).
- No errors (0 SSE errors, 0 402 quota trips this run; token auto-refreshed mid-run at q38).

## Latency (by outcome, avg)

ANSWER 34.0s · NO_DATA 25.9s · marginal 14.3s · parks 5.2s (they bail fast) · total avg 23.4s,
P95 45.0s, max 232.7s (q38, 5-tool chain).

## Action list (owners)

1. **Surface the clarify/interrupt payload on the wire** (question + options) — without it,
   AR parks are silent; the runner also cannot resume them (finance P1 same fix).
2. **Resolver robustness:** exact-name-only resolve_ar_customer rejects real customers
   ("KRISHNA COATED FABRICS" vs "…PVT LTD"). Needs fuzzy alias matching or a master-name
   canonical lookup; batch resolves must not hard-fail the whole turn.
3. **Verify invoice 17346** — harvested from Zainab but not found via invoice lookup; decide
   whether it is a docs-series mismatch or a lookup gap.
4. **Re-map expected_tool labels to the deployed surface** (see Tool accuracy) before v3 so
   strict accuracy is meaningful; decide whether both tool families legitimately coexist.
5. **Investigate the 12 unexpected parks** — once payloads are visible, classify each as
   legitimate scope-clarify (normal for upper-management sets) vs premature park.
6. Known wire gap confirmed: interrupt carries no text (ui_payload_type None) — same class
   as finance P1; combined fix recommended.
7. **NUMBER-CONSISTENCY FLAG (user should look):** the live run shows Interworld's chaseable
   balance as **₹72,36,78,400 (₹72.37Cr)** — 10x the ₹7.24Cr anchor in the user query set
   (q47, which parked so never answered) and nowhere near the harvest's recorded top-balance
   ₹1.22Cr (entities.json amount_anchors). Three different top-customer figures across anchor,
   harvest, and live run. Before trusting q22/q54 numbers, verify: (a) what the true
   outstanding is on the Zainab dashboard, (b) whether the AR render layer mis-scales (a
   paise/major-unit bug is the worry — finance had exactly that class of bug, fixed in v2).

## Files

- Runs: `accounts/ar-agent/runs/query_results_v2.jsonl` (56 records) + `manifest.json`
- Analyzer: `scripts/analyze_ar_run.py` (deterministic; --json for programmatic reuse)
- Dashboard: built next (Phase 6); landing card + push pending user go.