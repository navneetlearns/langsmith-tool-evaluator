# Finance Agent — Value Analysis Phase 2 (in-session judge pass)

**Run:** v1 (2026-09-18) · account `finance` · 30 CFO queries (20 judged)
**Judge:** deepseek-v4 (this session's model), rubric v1 — zero external API calls, no data left the machine.
**Cross-family property:** judge (deepseek family) differs from the producing agent model (gpt-5.4-mini), per the self-family-bias rule (Zheng et al. 2023; MT-Bench).
**Anti-bias instructions applied:** length is NOT rewarded — a complete two-sentence answer beats a padded one; every verdict carries a verbatim evidence quote; scores are anchored to the L-ladder, not a 1-10 feel.
**Limitation (stated honestly):** this judge and the Phase 3 grader are the same model, so the calibration below measures SELF-CONSISTENCY, not independent-human agreement. True calibration would need an independent rater (the user scoring a 10-answer sample); until then judge labels are triage signals, not verdicts.

## 1. Results

- **4 × L5,** 9 × L4, 2 × L3, 5 × REF (correct refusals) — of 20 judged
- **13 of 30** original asks got CFO-grade decision support (L4/L5); 5 correct refusals; 9 parks; 1 tech fail
- FinGAIA error-code tally across the set: Financial Terminological Bias ×5 (the 'days days' unit duplication) · Data Type Handling ×1 (literal '[unverified]' in q1) · Craft ×5 ('.. I can' double-period glitches + q17's '0 figures verified' footer on a refusal) · **Hallucinatory Financial Reasoning: 0 · Entity-Causation Misidentification: 0** — the no-fabrication guarantee holds

## 2. Per-query judge card

| q | tier | level | answered Q | adds interpretation | names decision/action | hygiene | errors | evidence (verbatim) |
|---|---|---|---|---|---|---|---|---|
| 1 | T1 | L4 | yes | yes | yes | issue | DataTypeHandling | "Call the listed priority customers today, starting with the largest outstanding amounts and longest payment…" |
| 2 | T3 | L4 | partial | yes | yes | ok | — | "Treat purchases as a cost-base indicator only; do not label the business profitable until cost of goods sol…" |
| 4 | T2 | L5 | yes | yes | yes | issue | FinancialTerminologicalBias | "Escalate accounts with both high outstanding balances and long gaps since the last payment to senior commer…" |
| 9 | T2 | L5 | yes | yes | yes | issue | FinancialTerminologicalBias | "Launch the first-wave calls immediately and record a firm payment commitment for each account." |
| 10 | T1 | L3 | partial | yes | yes | ok | — | "No reliable overdue amount or recoverability estimate is provided." |
| 11 | T2 | L4 | yes | yes | yes | issue | FinancialTerminologicalBias | "Review credit limits, payment terms, and order release controls for customers with persistently high outsta…" |
| 12 | T1 | REF | yes | y-refusal | no | issue | Craft | "I can't answer that from your books — Supplier payables / amount owed to suppliers is not reliably availabl…" |
| 13 | T1 | REF | yes | y-refusal | no | issue | Craft | "it does not reliably contain supplier payables, cash/bank balances, or actual supplier payment timing." |
| 15 | T3 | L4 | partial | yes | yes | ok | — | "Sales fell from ₹1,59,48,487 in the prior month to ₹11,97,739 in the latest month, while invoices declined …" |
| 16 | T3 | L4 | yes | yes | yes | ok | — | "Ganesh Retail Traders combines sales of ₹3,62,161 with the largest reported outstanding amount of ₹4,94,550…" |
| 17 | T1 | REF | yes | y-refusal | no | issue | Craft | "Expense accounts and a general ledger are not tracked in your books, so no expense account can be prioritis…" |
| 18 | T1 | REF | yes | y-refusal | no | issue | Craft | "No expense table or P&L/COGS data is available, so expenses and their growth cannot be measured or compared…" |
| 19 | T3 | L5 | yes | yes | yes | ok | — | "Invoice counts moved from 1,640 in the earliest reported month to 5,642 at the peak and 117 in the latest r…" |
| 21 | T3 | L5 | yes | yes | yes | ok | — | "Ganesh Retail Traders appears at ₹8,01,148 in the latest movement view but ₹4,94,550 in the outstanding ran…" |
| 22 | T3 | L4 | yes | yes | yes | issue | FinancialTerminologicalBias | "Track receivables conversion and collections separately from reported P&L; cash and receivables risk are no…" |
| 25 | T3 | L4 | yes | yes | yes | ok | — | "Pause or tightly gate replenishment for the listed products with no recorded last sale; run a product-level…" |
| 26 | T2 | L3 | partial | yes | yes | issue | FinancialTerminologicalBias | "Cash and bank balances are not tracked in your books, so this indicates receivables-driven cash-flow pressu…" |
| 27 | T3 | REF | yes | y-refusal | no | issue | Craft | "Accounting profit and cash situation require profit & loss data, cost/COGS, and cash/bank balances, which a…" |
| 28 | T2 | L4 | yes | yes | yes | ok | — | "DSO is 120.8 days against a measured period of 167.0 days, indicating slow conversion of sales into cash." |
| 30 | T3 | L4 | yes | yes | yes | ok | — | "Jai Enterprises Traders is also notable for 151.0 days since its last payment, despite its listed outstandi…" |

## 3. Calibration vs Phase 3 (same-model consistency check)

- Agreement: **20/20** (100%) on the L-level; the only non-exact row is q26 (Phase 3 'L3/L4' narrowed to 'L3' by the judge — consistent, not contradictory)
- No verdict flipped between phases; the error-code axis is new in Phase 2 (5 Terminological, 1 DataTypeHandling, 5 Craft, 0 hallucination, 0 entity-causation)

## 4. What the judge pass adds beyond Phase 3

- **Anchored re-scoring with mandated evidence:** every L-level now cites a verbatim line; no unsupported verdict survived the quote check (all 20 quotes verified exact against the run file).
- **Error-code indexing (FinGAIA taxonomy):** the defects are now categorized for owners (terminology/units vs data-type vs craft), which maps to prompt fixes (format node vs grounding guard vs template).
- **Confirmed no-inflation:** q10 (1,777 chars, 1 figure) scored L3 and the 5 refusals (265-631 chars) scored REF — length did not inflate any score.

## 5. Consolidated verdict (Phase 2-3 agreement)

- **No data-dump problem inside any answer** — L1/L2: 0 of 20. The user's worst-case hypothesis is falsified at the answer level.
- **The real issue is cross-answer template reuse** (same top-5 block in 9-12 answers, same KPI trio, same skeleton) — an evidence-selection/format problem, not a model-capability one (q21/q28/q30 proved query-specific evidence exists).
- **Worth-keeping strengths:** zero fabrication; reconcile-guard discipline (ageing never headlined); refusals clean and boundary-naming; actions always present.
- **Fix list (owners):** kill template reuse by intent (P1) · 'days days' (P1, 6 answers/30 occurrences) · '[unverified]' artifact (P1) · reconcile warning once per thread (P2) · refusal '..' glitch (P2) · classify-gate noise costing 5+ answerable queries (P2, ties to EVAL_READOUT P1).

Data: `runs/value_phase2_judge.json` · Phase 1: `runs/value_phase1_v1.json` · Phase 3: `VALUE_GRADE_phase3.md` · source run: `runs/query_results_v1.jsonl`