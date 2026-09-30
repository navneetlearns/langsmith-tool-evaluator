# Ask My Groups (ask_chats) — HiraFoods EVAL_READOUT v1

**Run:** 2026-09-30 · `accounts/hirafoods-askgroups/runs/query_results_v1.jsonl` · **30/30 ok, 0 failed, avg 13.2 s**
**Workspace:** c331ac11-c3e8-4d42-a8d6-b8b04127354c (HiraFoods demo, prod) · phone 4040505050 · lane `ask_chats`
**ask_chats deployment:** CONFIRMED (enumerated 2026-09-30, id 71d19eb3-3423-4105-9263-c844c334c98e, created 2026-09-27); template system_prompt is empty — lane routes to chats_agent subgraph
**Query set:** 30 rows user-approved 2026-09-30 (25 ANSWER / 2 CLARIFY / 3 REFUSE) — entity-free, no placeholders

---

## Headline
Ask My Groups is **LIVE and VIABLE on HiraFoods** — real tagged corpus, real customers, real
amounts, and the honesty contract working on nearly every numeric answer. 30/30 completion,
0 errors, 0 fabrications detected. The 09-23 "hirafoods has no WhatsApp data" finding is
**stale — reversed by this run** (6 groups, 366 requests in a 5-working-day band).

## Buckets (hand-graded, quoted evidence below)
- **ANSWERED with value: 21** (q1-q12, q14-q17, q19-q20, q22, q27-q28)
- **NEAREST_SHAPE / marginal (honest, shape-mismatch): 8** (q13, q18, q21, q23, q25, q26, q29, q30)
- **Clean REFUSE (correct per label): 1** (q24)
- **Errors / fabrication: 0**

## What the agent got right (strengths)
1. **Coverage honesty contract confirmed working.** 21 of the count-answers carry the
   low-volume-day warning in the headline (q2-q16, q19, q22-q29); the ones without it are
   stable facts (q1 group count) or full-coverage summaries (q17/q20).
2. **Response-time claim VERIFIED working** (was unverified): q7 → median first reaction
   23.9 h, slowest tenth > 23.9 h, per-asker table (Lakshmi Agencies 23.9 h/9 reqs vs Om
   Agencies 0.7 min/19 reqs).
3. **F5 intro-fallback gap CONFIRMED FIXED**: q1 answers "6 WhatsApp groups" (not the old
   "nothing was counted" fallback). Matches the 2026-09-29 reflect-test finding.
4. **Evidence contract populated on analysis answers**: q17/q19/q20/q22 carry [1]..[15]
   citation markers; row-level tables (When/Group/Who/Text) on all list answers.
5. **Hinglish + multi-step handled natively**: q18 (kal dispatch kitne hue the → 4 shipping
   posts), q27/q28 (2-part Hinglish asks answered with breakdowns).
6. **Honest about tagger noise**: q27 discloses "_14 of these carry none of those categories:
   they came back because their own words match_" — self-aware keyword-match caveat.
7. **Clean domain refusal**: q24 ("ledger balance" → "balances and invoices live in the
   ledger, not in chat messages") — correct scope refused, no fabrication.

## Findings / action list for owners
- **F1 — RECON-data confirmed live on HiraFoods.** Real entities visible in answers:
  customers "Om Agencies Pvt Ltd 923", "Krishna Traders Industries 332", "Lakshmi Agencies &
  Co 84", "Ganesh Wholesalers & Co 454"; amounts INV-4007 ₹2,18,000 overdue, INV-4012
  ₹6,79,000, ₹16.02 L payment mentions in 4 chased messages. Task 1.4 entity-anchored
  queries are now possible on this workspace (v2 option).
- **F2 — CAPABILITY GAP reproduced (repeat_issues).** q26 ("customers raised the same
  issue multiple times...") executed as a plain **chase-count** ("0 acknowledged but never
  answered general communication requests chased 1+ times") — no grouping by customer×issue,
  no promise-breach correlation. Same class as the 2026-09-28 Zainab trace. Graded
  NEAREST_SHAPE (not fail), as designed. Dev ticket unchanged: add `repeat_issues` spec shape.
- **F3 — REFUSE classes have drifted since the 2026-09-28 trace.** Neither cap row refused:
  - q23 (photo_content cap) → answered "73 dispatch posts, 24-29 Sep" (nearest kind;
    photos not counted as photos). Cap appears lifted OR substituted by the dispatch-posts
    shape — needs verifier confirmation; if intentional the expected_behavior label should
    move to ANSWER/NEAREST_SHAPE.
  - q25 (event_timing cap) → answered order counts + a raw timestamp table (no hour-of-day
    aggregation). Cap gone as a refusal; aggregation still missing.
- **F4 — Coverage-proportion query answered with the wrong shape.** q30 ("how much of my
  group traffic is covered/tagged") returned the group-count shape ("6 WhatsApp groups... by
  role dealer 6") — the F2 static shape-fallback rule fired toward the closest shape but it
  is not an answer to the disclosure question. Needs a coverage/untagged-proportion shape.
- **F5 — Clarify behavior is inconsistent and effectively absent.** q21 (CLARIFY-labeled)
  refused honestly ("no related messages found... searched for 'big order'; no matches") —
  acceptable, but it did NOT ask a clarifying question; q22 (CLARIFY-labeled) interpreted
  "them" as delivery-related messages and answered directly. No working clarify-ask observed
  in this set.
- **F6 — Document-kind confusion in shipping counts.** q18 counts "4 shipping delivery
  posts" but the evidence rows include a Ledger Extract (INV-4013) and a Tax Invoice
  (INV-4008) — media documents classified as dispatch posts. Count may be slightly inflated.

## Coverage caveat (read all numbers through it)
Multiple working days in the band have almost no tagged messages (23/24/26 Sep; normal day
≈ 104 msgs) — volume counts are far below reality for those days. Agent disclosed this
itself; treat absolute totals as lower bounds.

## Reproduce
```
python3 scripts/preflight_agent_probe.py hirafoods-askgroups   # gate: quota/init/parser
python3 scripts/run_agent_evals.py --account hirafoods-askgroups
```
Account config: `accounts/hirafoods-askgroups/config.yaml` (chatTemplateCode: ask_chats).
Query source of truth: `scripts/gen_ask_groups_hirafoods_queries.py` (edit script, re-run, verify).