# Ask My Groups (ask_chats) — Koya/KCCL EVAL_READOUT v1

**Run:** 2026-10-01 · `accounts/ask-groups-koya/runs/query_results_v5.jsonl` · **30/30 ok, 0 failed, avg 17.8 s**
**Workspace:** 72157c26-eb8a-4e24-ad19-9f405860d4ad (KCCL/Koya WhatsApp-group workspace) · login 7903329975 · lane `ask_chats`
**Query set:** 30 of the 40 KCCL-grounded queries (user: "run 30"), re-anchored to the live tagged window after re-probe — **21 ANSWER / 4 CLARIFY / 5 REFUSE**
**History:** 09-28 KCCL-verbatim port CANCELED by user → same-day 40-query Koya set approved; probe v1 (09-28) stalled on tag gap (coverage 25-26 Sep only); re-probe 2026-10-01 showed coverage 25 Sep→1 Oct + 30-Sep DPR tagged → re-anchor; run capped to 30.

---

## Headline
The Ask My Groups agent **works on the KCCL/Koya workspace, honestly**. 30/30 completion,
**0 fabrication, 0 cross-domain answers** — the original KCCL-verbatim fear (agent inventing
pipe/fabric numbers) did not materialize. Per-project DPR status, working-day age, purchase
pending/overdue, dispatch state and plan-vs-actual all **answer with real tagged-copy evidence
and correct zero-handling**. The honesty contract (untagged-date caveats) holds on virtually
every data answer. 10/30 rows are honest-empties or shape-drifts (NEAREST_SHAPE) — the corpus
is still shallow (2 projects' DPRs in a 25 Sep→1 Oct window; 1-Oct not tagged yet), and the
agent refuses rather than fabricates.

## Buckets (hand-graded, quoted evidence in v5 jsonl)
- **ANSWERED with value: 17** (q2 q4 q5 q7 q8 q9 q11 q12 q13 q16 q17 q18 q20 q22 q25 q26 q28)
- **NEAREST_SHAPE / marginal (honest, shape-mismatch or empty): 10** (q3 q6 q10 q15 q19 q21 q23 q24 q29 q30)
- **CLEAN_REFUSAL (correct per label): 3** (q1 q14 q27)
- **Errors / fabrication / cross-domain: 0**

## What the agent got right (strengths)
1. **DPR status tracking WORKS on the live window.** q4/q5/q28: per-project last-received
   tables with dates (29-Sep DPRs posted 30-Sep 16:42/16:43) and working-day-age ranking —
   the 09-28 "event_timing unanswerable" note is **stale** for live-window questions (the cap
   only fires when corpus data is missing, see F3).
2. **Purchase lane is rich and grounded.** q8/q9: pending POs (Maharajganj HDPE, Deoria Zinc
   Alu) and an overdue list (MS sleeves, PO-38 Kejriwal, PO-211 Preetam, Chandrapur
   bearings/oil, Muthuthala FHTC) — all evidence-backed with follow-up dates.
3. **Zero-handling correct everywhere** (q18 "no factory dispatch in latest DPR", q20 "3
   pending", q22 zero-dispatch client table, q27 "0 critical-stock messages") — zero is a real
   answer, never "no data".
4. **Honesty contract holds**: 1-Oct untagged is disclosed in ~10 answers; q17/q23/q24/q30
   explicitly say quantities aren't in the messages rather than inferring; q16 flags that
   "immediate" is its own judgment, not a message label; q26 flags absence-based inference.
5. **Judgment rows stay evidence-grounded** (q25 below-plan with per-day evidence; q29 risk
   list with pending-mention counts + method note).
6. **REFUSE class on August/out-of-window works cleanly** (q1: date-range refusal; q14/q27:
   critical-stock honesty).

## Findings / action list for owners
- **F1 — REFUSE drift (2/5 REFUSE rows answered instead of refusing).** q3 (">2 working days")
   answered a correct-scope negative ("no project shown overdue beyond threshold") — accurate
   and grounded, but not a refusal; q29 (critical materials→production) produced a grounded
   risk-priority list with an explicit "operational risk, not confirmed stoppage" caveat —
   honest, but the label expected REFUSE. Same drift class as hirafoods F3; if judgment-scoped
   answers with method caveats are acceptable product behavior, RELABEL these to ANSWER; if
   not, dev should tighten the spec. No fabrication either way.
- **F2 — No clarify-ask anywhere.** All 4 CLARIFY rows (q6 q7 q11 q16) resolved to scoped
   answers instead of asking (acceptable per row remarks, and the answers are honest) — but
   the clarify mechanism itself remains unobserved on Koya, same as hirafoods F5.
- **F3 — Stochastic spec routing.** q3 is byte-identical to re-probe q5: probe run → honest
   event_timing WHY_NOT refusal; full run → answered. The parse/spec step routes the same
   text to different shapes across runs (known classifier stochasticity class from finance).
   Report per-query verdicts, not single-shot routing, for these rows.
- **F4 — Production-figures gap (real product gap, honestly refused).** q23/q24: the latest
   daily reports list sizes/plans but no production quantities in the findable text (q31 probe
   same). If users expect DPR production numbers from ask-groups, check tagger extraction of
   the quantity columns — it is a corpus/extraction gap, not the agent.
- **F5 — NEAREST_SHAPE density 10/30**: 7 of the 10 are honest-empties on ANSWER-labeled rows
   (q10 ratio, q15 stock levels, q19 client-wise dispatch detail, q21 highest pending, q23/q24
   production, q30 client-wise quantities) because the corpus covers only 25 Sep→1 Oct with 2
   projects' DPRs. Numbers are lower bounds; coverage extends nightly.
- **F6 — Workspace ingestion confirmed flowing**: coverage moved 25-26 Sep (09-28) → 25 Sep→1
   Oct (10-01); the Koya DPR groups ARE being tagged — the probe-v1 "verify ingestion
   config" path (path 3) is answered: nightly tagging runs; August history is simply not in
   scope of the facts table (outside covered_range).

## Second-opinion review (2026-10-01, external AI reviewer)
A second AI review of the same v5 runs was analyzed line-by-line against the raw responses;
its buckets differ (17 matched / 2 soft / 11 missed vs ours 17/10/3) but the substance largely
holds. Confirmed findings:
- **Cross-query contradiction cluster (missed by the per-row readout — its best catch):** no
  single "pending DPR" definition. q2/q3/q28 "0 missing" vs q26 Archana Sudhan (Alakkode)
  "pending for 30-Sep DPR" vs q4 "the pending projects" vs q5 "Alakkode 2 working days since
  last DPR" — all verbatim in v5. Also q2's "last 2 working days" = 30 Sep–1 Oct while q28's
  = 29–30 Sep. Fix: one fixed definition of working-days anchor + pending-DPR in the spec.
- **Clarify 0/4** (matches F2): all four CLARIFY rows guessed/answered; capability gap.
- **q20 counts items/POs, not pipes** ("How many pipes are pending?" → MS sleeves, PO-211,
  PO-241 = 3 events) and **q19's dispatch table is messy** (raw plan text, "next dispatch" in
  the Quantity column, plan post labeled kind=dispatch). Renderer/format fixes.
- **q29 over-answered its REFUSE label** (procurement-status inference, grounded+caveated, no
  fabrication — strict per-label read is a miss; see F1).
- **Label artifacts in the set itself:** q14/q15/q27 near-identical critical-stock questions
  with 3 different labels; q2/q3 near-duplicates (ANSWER vs REFUSE); only one August control.
  Some "misses" are test-design, not agent.
- **Tool use untracked** (expected_tool=no_tool, tool_calls empty ×30 while ~23 cite sources):
  harness should log agent-side retrieval. Also makes q23-vs-q4/q28 DPR "contradiction"
  unadjudicable (group-scope difference suspected — q23 searched the production lane).
Disputed (AI overstated): q18-vs-q22 is NOT a contradiction (q18's own text: "pending items
still in follow-up"); the 6 "refused answerable" rows (q10/15/21/23/24/30) are corpus gaps
(quantities not extracted), not agent failures.
Attribution of the AI's 11 misses: ~4 agent issues (clarify, definition drift, table shape,
q29 scope) + ~4 label artifacts + ~2 corpus gaps + ~1 unadjudicable.

## Coverage caveat (read all numbers through it)
Tagged window = 25 Sep→1 Oct (1-Oct tagged only partially/raw at run time; disclosed in the
answers themselves). August-anchored KCCL extraction (496 rows) is NOT in the live facts
table. Absolute totals are lower bounds of the real traffic.

## Reproduce
```
python3 scripts/preflight_agent_probe.py ask-groups-koya   # gate: quota/init/parser
python3 scripts/run_agent_evals.py --account ask-groups-koya   # v5, 30/30
```
Account config: `accounts/ask-groups-koya/config.yaml` (chatTemplateCode: ask_chats).
Query source of truth: `scripts/gen_ask_groups_koya_queries.py` (edit script, re-run, verify —
30-row user-capped set; the 10 dropped rows recoverable from git history).
Runner note: `--resume` appends into the resumed version's file (fixed 2026-10-01, 8dec1fe).