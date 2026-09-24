# Finance Agent — EVAL READOUT v2

Run: 2026-09-24 · hirafoods workspace (4040505050 / c331ac11) · same 30-query CFO set as v1 ·
post PR #20789 (BE 983a4293b3 latency + b87d4113ff correctness, engine = Athena prod)
Raw: `accounts/finance/runs/query_results_v2.jsonl` · Derived: `accounts/finance/runs/v2/` · Page: `docs/finance/index.html`

## Headline

| metric | v1 (09-18) | v2 (09-24) | delta |
|---|---|---|---|
| answered | 16 (20 incl. hedged) | 20 | +4 |
| hard refusals | 4 | 5 | +1 |
| clarify parks | 9 | 5 | −4 |
| errors | 1 (q20 IncompleteRead @244.7s) | 0 | −1 |
| verdict match | 13/30 | 15/30 | +2 |
| verdict partial | 4 | 3 | −1 |
| verdict mismatch | 12 | 12 | same count, different composition |
| L4/L5 (value) | 13 (4×L5) | 14 (0×L5) | +1, lost all L5 |
| L3 / L2 / REF / parked | 2 / 0 / 5 / 9 | 4 / 1 / 6 / 5 | — |
| answered latency median | 47.2s | 21.4s | −55% |
| answered latency max | 211.9s | 30.7s | −85% |

## What PR #20789 FIXED (measured, not guessed)

- "days days" duplication: **30 → 0** (F12; was q1/q4/q9/q11/q22/q26)
- "[unverified] to [unverified]" ranges: **2 → 0** (F2)
- Reconcile boilerplate opening answers: **14/20 → 0/20** — answers open with the finding now
- Latency: parallel vote + adaptive poll + client reuse delivered a real cut (median 21.4s, tail gone)
- q20 (v1's 244.7s technical fail) now **answers in 20.6s** — zero technical errors in 30 queries
- Gate recalls recovered: q8, q29 (ANSWER-labeled, parked in v1 → answered in v2)
- Refusals corrected: q14 (parked → clean hard refusal), q17 (hedged → clean hard refusal)
- Answer-stats footer live: "N figures verified from your data · M unverified removed by the grounding guard"

## The REGRESSION — grounding placeholder leak (P0)

literal `[unverified]` in answers: **v1 = 2 occurrences (q1) → v2 = 48 across 15 of 25 answers.**

It strikes the decision-critical figures, not the margins: q9's whole recommendation is
hollow ("Focus first on [unverified], [unverified], and [unverified]" — 12 figures stripped);
q8/q10/q19/q22 counts, amounts and comparison values eaten. The footer simultaneously claims
"1–12 unverified figures removed by the grounding guard" while 40+ placeholders ship in prose.

Root cause (from the text, needs the owner's code check): F16's keyed figure references —
the model writes `{total_outstanding}`-style keys in prose and the resolver substitutes
`[unverified]` when the key has no match. With positional `{fN}` refs (v1) a reference always
existed, so placeholders were rare; with free semantic keys the model invents/paraphrases
keys (record-start dates, counts, "the biggest recent gap") that never resolve. The grounding
guard's removal tally (1–12) does not match the 48 rendered placeholders — most are
unresolvable-key artifacts, not grounding removals.

Fix direction for owners: on ref-miss, drop the sentence fragment (never emit the token), or
have `analyse` reuse only keys from the emitted figures array (strict schema union), or
render ungrounded figures as "—" and suppress the whole clause.

## NOT fixed (untouched by #20789)

1. **Clarify gate drift (P1, was P1 in v1):** 12 verdict mismatches = 9 CLARIFY→answered
   (q1 q3 q11 q19 q20 q21 q22 q25 q30) + 2 ANSWER→parked (q7 q24) + 1 REFUSE→answered.
   Gate remains a ~30% stochastic park rate; the interrupt payload is still not captured on
   the wire (pipeline-side, eval harness — not a dev fix).
2. **Cross-answer template reuse (P1 value):** same top-5 block (Ganesh/Jai/Krishna/Om ×2,
   ₹4,94,550 / ₹4,50,426 / ₹4,43,121 / ₹4,33,051 / ₹4,19,575) in ~15 of 20 answers; KPI trio
   (outstanding ≈₹17,50,35,089 / DSO 126.6 / 33.8%) recycled. The v1 recommendation
   (per-intent evidence selection, prompt-level) is still open.
3. Craft nits: ".. I can work" double-period still in q17/q18/q27; q17 "0 figures verified"
   footer on a refusal still once; q16 renders a broken range ("surged in ₹9,71,68,124 to
   ₹9,71,68,124") and its headline sales figure (₹24,20,47,712) contradicts the bullets.
4. Zops quota: metered; probe passed this run, but a full 30-query run drains it — keep the
   pre-flight probe in the runbook.
5. Value: **0 L5 answers** (v1 had 4, incl. q9/q19/q21). The rigid What/Why/Watch/Actions
   template stopped proactive unasked-item answers — the L5 class came from more organic
   composition; flag to owners before chasing it.

## Query-level verdict changes (v1 → v2, 7 rows)

- q3: parked → answered (CLARIFY) — gate drift
- q8: parked → answered (ANSWER) — recall recovered ✓
- q13: hard_refusal → answered (REFUSE) — hedged answer instead (partial)
- q14: parked → hard_refusal (REFUSE) — proper refusal ✓
- q17: answered-hedged → hard_refusal (REFUSE) — proper refusal ✓
- q20: error → answered (CLARIFY) — the 244.7s fail fixed by latency work ✓
- q29: parked → answered (ANSWER) — recall recovered ✓

## Runner/tooling fixes applied during this run (host-side)

- `render_finance_static.py` invariant compared zero-valued outcome/verdict keys with a
  missing-key dict → hard fail on any all-clean run; both comparisons now `{k: .get(k,0)}`.
- Findings section was hardcoded v1 analysis (evidence strings, query lists, "q16 percentages
  FAIL", "47.2s", 43%, Radha) rendered on every version — `seed_findings` rebuilt to compute
  F1–F10 from the current run's rows + content checks, with `resolved` state for checks that
  pass; KPI cards + pipeline steps + TL;DR + latency desc now version-sourced.
- `value_phase2_judge.json` was v1's file being read for v2 (invariant blew, value column was
  v1); v2 judged in-session (anchored L-ladder, refusals graded REF per v1 convention), v1
  file backed up to `value_phase2_judge_v1.json`. Both versions' derives now pass invariants.

## Files

- `accounts/finance/runs/query_results_v2.jsonl` — raw run (30 records, incremental)
- `accounts/finance/runs/v2/` — summary.json / findings.json / judgments.jsonl / leaks.jsonl
- `accounts/finance/runs/value_phase1_v2.json` — deterministic value analysis (0 boilerplate-open, top-5 repeat 10/20)
- `accounts/finance/runs/value_phase2_judge.json` (v2) + `value_phase2_judge_v1.json` (backup)
- `accounts/finance/EVAL_READOUT_v2.md` — this file
- `langsmith-tool-evaluator/docs/finance/index.html` — static dashboard (rebuilt, Playwright-verified PASS)

Nothing pushed to GitHub — push on explicit go.