# Finance Agent — Value Readout v1 (CFO-lens)

**Run:** v1 (2026-09-18) · Account: `finance` · Workspace: hirafoods (phone 4040505050, ws c331ac11-…) · Template: `chatTemplateCode: "finance"`
**Ask:** 30 user-provided CFO insight questions (ANSWER 9 / CLARIFY 12 / REFUSE 9). Labels + tier tags user-reviewed 2026-09-18.
**Question this readout answers:** how much VALUE does each answer add to a CFO/accountant of an Indian SMB distributor/manufacturer — beyond data fetch and beyond repeating the same information? (Companion to EVAL_READOUT_v1.md, which covers behavior/gate mechanics.)
**Method:** 3-phase, all reproducible: Phase 1 deterministic metrics (`scripts/analyze_finance_value.py`) → Phase 2 in-session cross-family judge, every verdict verified against verbatim evidence (`runs/value_phase2_judge.json`, `VALUE_JUDGE_phase2.md`) → Phase 3 shadow-answer skeletons vs actual answers (`VALUE_GRADE_phase3.md`). No external API calls; no fabricated quotes (20/20 verbatim-checked).

---

## 1. Headline

| Metric | v1 |
|---|---|
| CFO-grade decision support (L4/L5) | **13 of 20 answered** (of 30 asks = 43%) |
| Structured-but-thin (L3) | 2 (q10 overdue-quantify, q26 forward-cash — both honest, both thin) |
| **Data-dump / paraphrase answers (L1/L2)** | **0** — the flagged worst case did not materialize at answer level |
| Correct refusals (REF) | 5 (q12 q13 q17 q18 q27) — clean, boundary-naming, 0 fabrication |
| Clarify parks + tech fail | 9 + 1 (q20 IncompleteRead) — no response to grade |
| Fabricated figures | **0** (zero-tolerance no-fabrication PASSED, again) |
| FinGAIA error codes (judged answers) | Terminological ×5 ("days days") · Data Type ×1 ("[unverified]") · Craft ×5 (refusal ".." glitches + footer) · Hallucination 0 · Entity-Causation 0 |
| Phase 2↔3 agreement | 20/20 consistent (self-consistency only — judge = same model family as grader; a real human calibration check on a 10-answer sample is the open item) |

## 2. The finding that matters: no bad answers, but TEMPLATE REUSE across answers

- Every individual answer is grounded, structured, ends in actions. That part is genuinely good — the format template (warning → 💡 headline → sections → What to do → footnotes → Ask next) is consistent and professional.
- The repetition the user asked about is CROSS-ANSWER, quantified:
  - same reconcile boilerplate opens 14/20 answers (~210 chars each),
  - the same top-customer block (Ganesh ₹4,94,550 / Jai ₹4,50,426 / Om ₹4,43,121 / Krishna ₹4,33,051 / Om W ₹4,19,575) appears in **9–12 of 20 answers**,
  - the same KPI trio (₹17,48,30,219 / DSO 120.8d / 33.8%) is recycled as the "insight" in 4–7 answers.
- Consequence for a CFO: 8 different questions → 8 answers leaning on the same evidence block. Each is fine alone; as a working session it reads repetitive and hides the fact that query-specific evidence EXISTS (q21 found the cross-view discrepancy, q28 the DSO-vs-window ratio, q30 a 6th slow payer — none of it appears in the reused block).

## 3. What the agent does well (keep — do not regress)

- Zero fabrication across all 30 asks (profit/cash/expense figures never invented — hard refusals or hedged boundaries instead).
- Reconcile-guard discipline: ageing/overdue NEVER headlined; "trust reconciled outstanding" consistently.
- Refusals name the boundary precisely and immediately ("Supplier payables … not reliably available", "No expense table or P&L/COGS data").
- Action sections are concrete (call today, dated commitments, escalation triggers).
- q4/q9/q19/q21 are the L5 benchmarks to preserve: portfolio sizing + fastest-worsening, wave-based chase plan, CFO-style challenges, anomaly cross-check with hypotheses.

## 4. Owner action list (value lens)

1. **P1 — Kill cross-answer template reuse:** per-intent evidence selection. Chase-family questions may share exposure data; credit/margin/anomaly questions must fetch query-specific evidence (q21/q28/q30 prove it exists). Most likely a format-node/prompt change, not a model change.
2. **P1 — "days days" duplicate unit** in 6 answers / 30 occurrences (q1 q4 q9 q11 q22 q26).
3. **P1 — Grounding guard must not emit literal "[unverified]"** (q1 ×2): re-probe, reason from adjacent data, or drop the sentence.
4. **P2 — Reconcile warning placement:** emit once per conversation/thread (14× today). Thread-state awareness or first-answer-only rule.
5. **P2 — Refusal craft:** "dataset.. I can work" double-period ×4 (q12 q13 q18 q27); q17's "0 figures verified" footer on a refusal.
6. **P2 — Clarify-gate noise costs answers, not just consistency:** 5+ answerable queries parked (q7 q8 q14 q24 q29; q14 margin-pressure is provably answerable — see q2/q15). Tie to EVAL_READOUT clarify-gate P1 with this count as the business impact.
7. **P3 — Latency:** analysis-heavy answers 35–245s (q20 dropped at 244.7s) — chunking or higher read timeout for the analysis branch.

## 5. Method notes / what NOT to trust

- Value levels are model-graded (deepseek-v4 in-session) with verbatim evidence — consistent across two independent passes, but not human-calibrated. Spot-check a 10-answer sample before treating L-levels as ground truth (calibration target ≥80%).
- "No data-dump" refers to INDIVIDUAL answers; the repetition defect is cross-answer — do not quote "0 data-dumps" as "no repetition problem".
- Q10/q26 L3 verdicts = correct-but-thin (honest quantification refusal; forward-look limited), not failures.
- The 9 clarify-parks and q20 fail carry no value grade; their cost is counted in §4.6-style losses, not in the L-distribution.

## 6. Artifacts

- `runs/query_results_v1.jsonl` (source run) · `runs/value_phase1_v1.json` (deterministic metrics + consistency ledger) · `runs/value_phase2_judge.json` (judge records, verbatim quotes)
- `VALUE_SCORECARD_phase1.md` · `VALUE_JUDGE_phase2.md` · `VALUE_GRADE_phase3.md` · this readout
- Dashboard: docs/finance/index.html — "Response Value" section (13/2/0/5/10 cards + error-code chips + per-row badges); live at https://navneetlearns.github.io/langsmith-tool-evaluator/finance/ once pushed
- Tool: `scripts/analyze_finance_value.py` (rerunnable: `python3 scripts/analyze_finance_value.py finance`)