# Finance Agent — Eval Readout v1

**Run:** v1 (2026-09-18) · Account: `finance` · Workspace: hirafoods (phone 4040505050, ws c331ac11-…)
**Template:** `chatTemplateCode: "finance"` · Query set: **30 user-provided CFO insight questions** (verbatim, in user order)
**Labels:** ANSWER 9 / CLARIFY 12 / REFUSE 9 (per the classify-gate rules) · **Runner:** scripts/run_agent_evals.py
**Parser:** fixed 2026-09-18 (full ui-markdown answers + SSE error/interrupt capture) — a pre-fix run would have recorded most of these answers as empty
**Data:** accounts/finance/runs/query_results_v1.jsonl (30 records) · manifest v1

---

## 1. Headline

| Metric | v1 |
|---|---|
| Streams completed | 30/30 |
| Data answers | **20** |
| Clarify parks (interrupt) | **9** |
| Technical failures | 1 (q20, IncompleteRead @ 244.7s — backend drop, not retried per HEART) |
| Quality (4-bucket, text classifier) | 16 success · 4 marginal · 9 park · 1 fail |
| Avg / p50 / p95 latency | 44.2s / 38.6s / 142.1s (max 244.7s; parks are 2-3s) |
| Tool events observed | **0** (finance = backend SQL; status.phase labels reveal the metric set) |
| Fabricated profit/cash/expense figures | **0** (zero-tolerance no-fabrication PASSED) |

The 4 "marginal" are ALL hedged refusals (q2/q15/q16/q17) — data-adjacent answers that correctly
name the data boundary ("profitability is not yet proven from this ledger", "Expense accounts …
cannot be assessed from the tracked books"). The text classifier underrates them; per the leniency
rule they are CORRECT behavior, not misses.

## 2. Clarify behavior — the headline finding

**9 of 30 queries parked** with an `interrupt` SSE event: empty response, no tools, 2-3s.
(q3 cash-stuck · q5 working-capital problem · q6 cash-flow risk · q7 good-business-poor-collections ·
q8 outstanding-outgrowing-business · q14 margin pressure · q23 credit-vs-payment-history ·
q24 materially-different · q29 concentration customers-vs-suppliers) — exactly the
multi-reading/scope family the classify prompt tells the gate to clarify. This is the clarifying
behavior, observed live.

**The gate is NON-DETERMINISTIC (sampling noise):** q3 ("Where is our cash getting stuck?") parked in
the run, but the identical query ANSWERED on a re-probe minutes later (full analysis, 40s+). Do NOT
grade clarify per-query; grade it as a probability over clarify-prone queries (~30% park rate here).

**Classify drift vs the 2026-09-17 trace:**
- The trace's canonical clarify example (q20 "Forget the standard reports… what looks unusual")
  now RUNS the analysis branch (244.7s — heavy, dropped mid-stream). The Sep-17 trace predates a
  prompt change; the live gate is more permissive.
- 7 of the 12 CLARIFY-labeled queries were ANSWERED (q1 health overview · q11 too-much-credit ·
  q19 CFO challenge · q21 unusual movements · q22 biggest risks · q25 management attention ·
  q30 first-look worry) — the analysis branch handles open-review questions directly with
  multi-metric answers.
- 4 of 9 ANSWER-labeled queries PARKED (q7/q8/q24/q29) — all genuinely multi-reading ("concentration"
  is literally customers OR suppliers).

**Open item for owners:** parked streams carry the `interrupt` event but no question/options payload
was observed on the wire in this run — the SSE client cannot render the clarification, and the
resume path remains unverifiable from the API. (Parser now captures any future interrupt payload.)

## 3. Refusals — clean, boundary-naming, no fabrication

8/9 REFUSE-labeled queries delivered a correct refusal; 1 (q14 margins) parked→clarify instead.
- **Hard refusals** (q12 payables · q13 pay-suppliers-before-collect · q17 expenses · q18 expense
  trend · q27 profit-vs-cash): "I can't answer that from your books — Supplier payables / amount
  owed to suppliers is not [tracked]", "No expense table or P&L/COGS data is available…". 265-631
  chars, ~2s. ✓
- **Hedged data answers** (q2 profitability · q15 margins trend · q16 revenue-vs-profitability):
  closest real data + explicit disclaimer ("profitability is not yet proven from this ledger"). ✓

## 4. Answer quality & consistency (the guardrails WORK)

- **Reconcile refuse-to-headline fired on ~16 answers:** "Payments are not fully reconciled onto
  invoices — only ~3% of collected amounts are allocated… Overdue and ageing are OVERSTATED. Trust
  the outstanding balance (reconciled ledger)". Exactly the designed guard; ageing is never headlined.
- **Numbers are consistent across every answer:** outstanding ₹17,48,30,219 / 1,549 debtors ·
  DSO 120.8 days · collection rate 33.8% (₹8,16,34,549 collected vs ₹24,17,71,682 invoiced) ·
  top exposures Ganesh Retail Traders ₹4,94,550 (79d) / Jai Wholesalers & Co ₹4,50,426 (74d) /
  Radha Distributors & Co movement +₹9,66,376. No figure drift between queries — same source, same
  values.
- ₹-sanity: all amounts in ₹ with 2dp; raw paise never observed. ✓

## 5. Latency vs query type

| Type | Observed |
|---|---|
| Data answers (analysis-heavy) | 35-245s (p50 43.8s) |
| Hard refusals | ~2s |
| Clarify parks | 2-3s |
| q20 (heaviest) | 244.7s then backend drop |

## 6. Behavior matrix: expected labels vs observed

| expected | answered | parked | failed |
|---|---|---|---|
| ANSWER (9) | 5 | 4 | 0 |
| CLARIFY (12) | 7 | 4 | 1 |
| REFUSE (9) | 8 | 1 | 0 |
| Total | 20 | 9 | 1 |

Interpretation: the classify gate is MORE permissive than the trace suggested (analyses first,
clarifies ~30% of scope-ambiguous inputs, refuses only when data is truly absent). Agreements with
the labels are coincidental per-query given the stochasticity — the readout's valid claim is the
BEHAVIOR MIX, not per-query accuracy.

## 7. Action list for agent owners

1. **Clarify gate noise (P1):** identical input parks or answers across runs (gpt-5.4-mini sampling).
   Decide: temperature down on the classify call, force-clarify on multi-reading terms, or accept
   analysis-first with a scope note. Tests depending on deterministic clarify will stay flaky until
   then.
2. **Clarify payload not on the wire (P1):** the SSE client never receives the clarification question/
   options — the interrupt carries no visible payload. Clients can't render the clarify menu;
   resume-from-API unverifiable. (Parser now captures interrupt data if it ever rides the stream.)
3. **"days days" duplication (P2):** "DSO is 120.8 days days", "79.0 days days", "74.0 days days" —
   duplicate-unit in the analysis narration.
4. **Live customer names ≠ WA-spec names (P2):** live answers show Ganesh Retail Traders /
   Jai Wholesalers & Co / Radha Distributors & Co; the synthetic WA spec + AR query set use
   "Ganesh Wholesalers Pvt Ltd 955" etc. Reconcile the two before AR eval leans on spec names.
5. **Heaviest queries drop (P2):** q20's 244s analysis died mid-stream. Consider chunking or raising
   the SSE read timeout for analysis branches.
6. **Quota gate (P3):** the agent-template meter (Zops) drained during one probing+run session
   (402 topup_required; surana's legacy path unaffected). Budget/top-up Zops before any
   multi-account agent-template run.

## 8. Method notes (what NOT to trust)

- expected_tool col = review-intent only — finance streams NO tool events (backend SQL); no
  tool-accuracy scoring applies.
- Text classifier underrates hedged refusals (buckets them marginal) — judged pass for q2/q15/q16/q17.
- answerable ≠ data-correct: this eval grades behavior + answer quality, NOT ledger truth (no
  ground-truth DB in the loop).
- q20 fail = technical (IncompleteRead), not a quality verdict.