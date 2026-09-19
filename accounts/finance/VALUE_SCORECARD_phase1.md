# Finance Agent — Value Analysis Phase 1 (deterministic scorecard)

**Run:** v1 (2026-09-18) · account `finance` · 30 CFO queries · tool: `scripts/analyze_finance_value.py` (no LLM, regex + structure only — rerunnable: `python3 scripts/analyze_finance_value.py finance`)
**Scope:** measures repetition (inner + cross-answer + boilerplate), value signals (comparative/action/priority language), info density, and figure consistency per response. Verdicts are AUTO-HINTS for review, not final grades — Phase 2 (judge) + Phase 3 (shadow answers) refine.

## 1. Headline numbers (answered = 20; 9 clarify-parks + 1 tech fail)

- Avg response length: **2048 chars** (range 265–3,328)
- Responses opening with the SAME reconcile boilerplate: **14/20**
- Avg boilerplate share of an answer: **7.9%** (the prefix itself is ~210 chars; share is diluted by answer length)
- Avg info density: **0.68 signals per 100 chars** (unique figures + comparative + action + priority language) — i.e. 1 meaningful signal per ~150 chars of text
- Answers with >30% cross-answer repeated text: **2** · exact inner-sentence duplicates: **0**

## 2. The repeated boilerplate (14 of 20 data answers)

> > ⚠ Payments are not fully reconciled onto invoices — only ~3% of collected amounts are allocated to invoices in this workspace. Overdue and ageing are computed from invoice status and are OVERSTATED. Trust the outstanding balance (reconciled ledger), not the overdue/ageing figures.

💡 ** …

Top verbatim sentences shared across answers:

- x14  trust the outstanding balance (reconciled ledger), not the overdue/ageing figures.
- x14  overdue and ageing are computed from invoice status and are overstated.
- x14  > ⚠ payments are not fully reconciled onto invoices — only ~3% of collected amounts are allocated to invoices in this workspace.
- x4  i can work from sales, payments, the customer ledger, and outstanding/overdue instead.
- x3  > inventory value at cost, cash and bank balances, expenses, profit and loss, and supplier payables are not tracked in your books.
- x2  > inventory value at cost, cash and bank balances, expenses, profit or loss, and supplier payables are not tracked in your books.
- x2  ### cash conversion pressure

Reading: the 3-sentence reconcile warning (x14) is CORRECT content that only needs to appear once per conversation — its repetition is the L2 padding signal. The '### cash conversion pressure' header (x2) hints at a shared answer skeleton/template across queries (candidate for Phase 3 template-drift check).

## 3. Per-query scorecard (tier = FinGAIA business-depth tag, FOR YOUR REVIEW)

Legend: figs=figure mentions · dist=distinct figures · cmp=comparative signals · act=action signals · pri=priority signals · dens=density/100ch · bp%=boilerplate share · xrep%=cross-answer repeat share · hints are auto, refusals are CORRECT behavior not value-miss (graded separately in the final readout)

| q | tier | outcome | len | figs | dist | cmp | act | pri | dens | bp% | xrep% | auto-hint |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | T1 | answer | 2756 | 8 | 7 | 6 | 3 | 8 | 0.87 | 10.5 | 10.2 | L3+ (comparative + action signals present) |
| 2 | T1 | answer | 2411 | 14 | 13 | 1 | 3 | 5 | 0.91 | 12.0 | 11.7 | L2/L3 (mixed) |
| 3 | T2 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 4 | T2 | answer | 2635 | 11 | 10 | 10 | 4 | 7 | 1.18 | 11.0 | 15.6 | L3+ (comparative + action signals present) |
| 5 | T3 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 6 | T3 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 7 | T3 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 8 | T3 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 9 | T2 | answer | 2614 | 11 | 9 | 9 | 8 | 3 | 1.11 | 11.1 | 10.7 | L3+ (comparative + action signals present) |
| 10 | T1 | answer | 1777 | 2 | 1 | 4 | 3 | 1 | 0.51 | 16.3 | 15.8 | L2/L3 (mixed) |
| 11 | T2 | answer | 2771 | 9 | 9 | 3 | 5 | 3 | 0.72 | 10.4 | 14.8 | L3+ (comparative + action signals present) |
| 12 | T1 | REFUSAL | 341 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0 | 25.2 | L1 (fetch/refusal, no value signals) |
| 13 | T1 | REFUSAL | 406 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0 | 21.2 | L1 (fetch/refusal, no value signals) |
| 14 | T2 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 15 | T2 | answer | 2388 | 6 | 5 | 6 | 2 | 1 | 0.59 | 12.1 | 11.8 | L3+ (comparative + action signals present) |
| 16 | T2 | answer | 2280 | 10 | 10 | 2 | 6 | 3 | 0.92 | 0.0 | 0.0 | L2/L3 (mixed) |
| 17 | T1 | REFUSAL | 631 | 0 | 0 | 1 | 1 | 0 | 0.32 | 0.0 | 0.0 | L1/L2 (thin data, minimal interpretation) |
| 18 | T1 | REFUSAL | 279 | 0 | 0 | 1 | 0 | 0 | 0.36 | 0.0 | 30.8 | L1/L2 (thin data, minimal interpretation) |
| 19 | T3 | answer | 3328 | 6 | 5 | 3 | 6 | 5 | 0.57 | 8.7 | 8.4 | L3+ (comparative + action signals present) |
| 20 | T3 | error | — | — | — | — | — | — | — | — | — | no response |
| 21 | T3 | answer | 2874 | 19 | 18 | 4 | 4 | 3 | 1.01 | 10.1 | 9.8 | L3+ (comparative + action signals present) |
| 22 | T3 | answer | 2366 | 10 | 9 | 4 | 1 | 6 | 0.85 | 12.2 | 17.3 | L2/L3 (mixed) |
| 23 | T2 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 24 | T3 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 25 | T3 | answer | 3161 | 15 | 13 | 1 | 7 | 6 | 0.85 | 9.1 | 13.0 | L2/L3 (mixed) |
| 26 | T2 | answer | 2096 | 13 | 9 | 3 | 3 | 3 | 0.86 | 13.8 | 14.8 | L3+ (comparative + action signals present) |
| 27 | T1 | REFUSAL | 265 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.0 | 32.5 | L1 (fetch/refusal, no value signals) |
| 28 | T2 | answer | 2758 | 13 | 13 | 1 | 5 | 5 | 0.87 | 10.5 | 16.0 | L2/L3 (mixed) |
| 29 | T3 | interrupt | — | — | — | — | — | — | — | — | — | no response |
| 30 | T3 | answer | 2832 | 10 | 7 | 9 | 7 | 8 | 1.09 | 10.2 | 9.9 | L3+ (comparative + action signals present) |

Tier tag (FinGAIA): T1 = operational fetch/refusal · T2 = decision support · T3 = strategic risk. 7×T1, 10×T2, 13×T3 — most of the set is Tier 2/3 (the user's point: fetch+restate is not enough there).

## 4. Figure consistency ledger note

Per-answer ₹ figures extracted into `value_phase1_v1.json` (consistency_ledger). Cross-checks against the v1 known set (outstanding ₹17,48,30,219 · 1,549 debtors · DSO 120.8d · ₹24,17,71,682 invoiced · ₹8,16,34,549 collected): all matches so far are consistent; q1/q21 carry additional figures (₹5,70,49,359; ₹9,77,65,078 revenue peak area) that are visible in the ledger for manual spot-check. Raw paise units: none observed (Data Type gate passes).

## 5. Next steps

1. **User review:** confirm the tier tags in §3 (esp. q1/q16/q21/q30 boundaries) and the refusal bucket list.
2. **Phase 2:** calibrated judge pass (cross-family, error-code axis per FinGAIA taxonomy) on the 20 answers.
3. **Phase 3:** shadow-answer skeletons per query family; grade response vs skeleton.
4. **Phase 4:** VALUE_READOUT_v1.md + dashboard value bucket; docs refresh.

Data: `runs/value_phase1_v1.json` (full JSON incl. ledger + per-record detail) · script: `scripts/analyze_finance_value.py` · source run: `runs/query_results_v1.jsonl`
