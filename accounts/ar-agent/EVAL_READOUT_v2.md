# AR Agent Eval — EVAL_READOUT_v2 (run v3, 35-query re-run)

- **Date:** 2026-10-09 · **Agent:** `collection_and_account_receivables` (ZoChief seller-copilot, AR/collections)
- **Workspace:** Zainab Enterprises `d53279c2-0f92-42ea-876d-1c57770f5184` / 9029012960
- **Run:** `accounts/ar-agent/runs/query_results_v3.jsonl` — **35 live queries** (q1–q35 of the user's 56-row set, run in the set's own order; sections 1–5 = WhatsApp-vs-ERP reconciliation, payment commitments, invoice/bill, UTR, credit notes).
  Rows q36–q56 in that file are the harness's carry-over, byte-identical to v2 (verified) — they were **not** re-run. Sections 6–8 (repeated follow-ups, natural accountant-style) and both CLARIFY controls (q46, q51) were **not** exercised this run.
- **Not run:** per user instruction — no queries beyond q35.
- **Runner:** `scripts/run_agent_evals.py --account ar-agent --only 1..35` (two-turn aware, incremental JSONL, no retries).
  **Analyzer:** `scripts/analyze_ar_run.py --run 3` (fresh-35 scope computed by filtering the run file; same classifier/regexes).
- **Prior:** EVAL_READOUT_v1.md = the 2026-09-24 v2 run (56 queries).

## Headline

Answers that come back are still good — real customers, real commitments, real amounts, zero
format violations — but the run's failure mode has consolidated: **10 of 35 questions got no
answer at all** (7 fast silent parks + 3 long empties where tools ran and the text never
reached the wire), and **all 10 sit in q11–q23** (the commitment and invoice sections). A
second, quieter defect is a **false "WhatsApp data isn't available" refusal class**: five
answers decline on the grounds that chat data can't be read, while other rows in the SAME run
read 116 WhatsApp claims and quote chat messages verbatim.

## Buckets (fresh 35)

Raw classifier vs judged (judged = reading each response; "false-unavailable refusal" is split
out of the honest-refusal class because the availability claim it rests on is contradicted
elsewhere in the same run):

| Bucket | Raw | Judged |
|---|---|---|
| success (data answer) | 22 | 10 solid + 4 partial + 5 honest "can't do" + 5 false-unavailable refusals (q6, q7, q26, q28, q30) |
| marginal | 2 | (folded above) |
| no_data | 1 | (folded into honest class) |
| clarify parks (empty, ≤5s, no tools) | 7 | 7 no-answer (q12, q16, q18, q19, q20, q21, q23) |
| fail/error | 3 | 3 no-answer (q11, q15, q22 — tools ran, 28–50s, empty body) |
| wrong or misleading | — | 1 (q31) |

**Judged totals: 10 solid · 4 partial · 5 honest "can't do" · 5 false-unavailable refusals ·
1 wrong · 10 no-answer = 35.**

Same 35 rows in v2 (2026-09-24): 31 answered / 4 empty / 0 parks. Silent answers went 4 → 10.

## Behavior matrix (expected → observed, 35)

| Expected | Observed | Count |
|---|---|---|
| ANSWER | answer (22 success + 2 marginal + 1 no_data) | 25 |
| ANSWER | empty interrupt park | 7 |
| ANSWER | empty after tool work (no park flag) | 3 |
| CLARIFY | — | 0 (no CLARIFY rows in q1–q35) |

## Finding 1 — the silent-answer class is now the dominant defect (10/35)

- **7 fast parks:** q12, q16, q18, q19, q20, q21, q23 — 2.2–4.6s, `status_sequence`
  `connected→status→status→done`, **no tool call, `ui_payload_type=None`, empty body.** The
  runner flags `possible_clarify`, but the interrupt payload (question + options) is still not
  on the wire, so nothing can be resumed and the user sees silence. Same class as v1's 12
  parks and finance P1 — **not fixed since 2026-09-24.**
- **3 long empties:** q11 (45.4s, `ar_promises`+`getCustomerAnalytics`), q15 (49.7s, same
  pair), q22 (28.0s, `ar_worklist`+`ar_promises`) — tools ran, a `ui` event was emitted, and
  the answer text still never arrived. These are NOT clarify parks (too slow, tools called) —
  they are dropped renders, a second mechanism under the same symptom.
- **Concentration:** q11–q23 is 13 rows and produced 10 of the 10 empty answers. The
  commitment/invoice sections are effectively dark, while reconciliation (q1–q10) answered 10/10.

## Finding 2 — five refusals rest on a false "no WhatsApp data" claim

- Declined on availability: **q6, q7** ("WhatsApp-mentioned amounts are not available in the
  current data"), **q26, q30** ("WhatsApp-shared UTR messages aren't available for
  comparison in this session"), **q28** ("chat-claim data isn't available in the current
  workspace") — all five ask the user to paste the WhatsApp export.
- Same run, same workspace: **q2/q4/q10** return **116 unresolved WhatsApp payment claims**
  with names, amounts and references; **q25** enumerates invoice numbers from payment
  messages; **q32** and **q34** quote chat lines verbatim ("Credit note send kijiye payment
  karta hu"). The data is reachable — routing, not availability, is what fails.
- This is the AR-side copy of HiraFoods' q9-vs-q24 nondeterminism: one question class, two
  paths, one silently useless.

## Finding 3 — tool surface changed again; label remap is (partly) obsolete

Observed on the wire (fresh 35): `get_collections` 10 · `ar_payments_reported` 7 ·
`ar_promises` 6 · `getCustomerAccountData` 4 · `search_threads` 3 · `getCustomerAnalytics` 3 ·
`search_messages` 3 · `spawn_filter_agent` 2 · `search_customers_master` 1 · `ar_worklist` 1 ·
`list_invoices` 1 · `get_receivables` 1.

- v2 (2026-09-24) ran the `query_ar` family (`query_ar`, `get_ar_evidence`, `get_ar_schema`,
  `query_ar_financials`, `resolve_ar_customer`, `get_paid_collections`) and none of the ar_*
  label tools; **this run is the mirror image** — the ar_* family the labels were built from is
  back and `query_ar*` never fired. Three different surfaces across three runs on one workspace.
- Tool accuracy (analyzer, fresh 35): **strict 13/35 (37%)** · lenient (≥1 tool call) 27/35
  (77%). v2's strict was 0/54, so the labels are no longer the problem they were — but a
  strict score that swings 0% → 37% on a backend redeploy is measuring deploy churn, not agent
  skill. Pin the surface per run in the readout, as done here.
- **New tools not in any prior inventory:** `spawn_filter_agent` (q25, q34 — the lane spawns a
  sub-agent), `getCustomerAccountData`, `getCustomerAnalytics`.
- `resolve_ar_customer` was **never called** this run — v1's exact-match resolver defect
  (q5/q19) is therefore untested here, not fixed. The one customer-anchored lookup (q5) went
  through `search_customers_master` and worked.

## Finding 4 — one outright wrong answer, one lost designed anchor

- **q31 "Which payment references are still unresolved?" → "No unresolved payment references
  were found … 0 payments marked as sent, failed, or cancelled."** It answers a *status-flag*
  question, not the asked one, and its headline contradicts q2/q4/q10's **116 unresolved
  claims** in the same run.
- **q20** (Bill 15293 / ₹880 NEFT claimed on WhatsApp — is it in ERP?) **parked empty.** The
  row designed as the WhatsApp-vs-ERP mismatch anchor was never answered. Independently,
  **q25** reports that references 15293 and the ₹880 NEFT claim are **not in the data** and
  that the ₹880 hit is a price quote, not a payment — consistent with v2's q20 finding
  (invoice 15293 not in ERP). Owner decision still open: is 15293 a wrong anchor in the query
  set, or a real doc series the lookup can't reach?

## What went right

- **0 format violations:** no tool/dataset names, no run/thread IDs, no banned words, no
  stray-₹-decimal figures across the 25 non-empty answers.
- **Promise/commitment answers are the run's best work.** q13 names 4 dated overdue
  commitments (THE ARTY GARAGE, SHREE JAIN FOAM & FURNISHINGS-T, MARVEL HOMES) with dates and
  correctly explains that ONCE & AGAIN's acknowledgement is undated, so no overdue date can be
  asserted; q14: 25 customers / 42 broken commitments, 15-Sep → 8-Oct; q17: 3 open promises
  with no payment posted.
- **q34** quotes two customers verbatim and links payment to the credit note — exactly the
  WhatsApp-grounded value the AR lane exists for.
- **q25** is honest in the useful direction: it answers what it found (2 customers, 16 invoice
  refs) and states plainly that 15293/₹880 were not in the results instead of papering over it.
- Refusals are non-fabricating: q8, q9, q24, q33, q35 decline rather than invent, and offer a
  concrete next step.

## Latency (fresh 35)

avg **26.9s** · P95 **69.3s** · max **81.6s** (q34, message search + `spawn_filter_agent`).
By outcome: ANSWER 28.1s · ANSWER-WEAK 52.4s · NO_DATA 71.1s · FAIL 41.1s · parks **3.8s**
(they bail immediately). No SSE errors, no 402 quota trips, token valid for the whole run.
Materially better tail than v2 (max 232.7s).

## Action list (owners)

1. **Ship the interrupt payload (question + options) on the wire** — still the #1 defect, now
   7 fast parks in 35 rows and unchanged since 2026-09-24. Same fix as finance P1.
2. **Fix the 3 dropped renders** (q11, q15, q22): tools complete, `ui` event emitted, no body.
   Distinct from the park bug — do not close #1 thinking it covers these.
3. **Kill the false-unavailable refusal class** (q6, q7, q26, q28, q30): when
   `ar_payments_reported` / `search_messages` / `search_threads` are wired on the workspace,
   the agent must route to them instead of asking the user to paste chat exports.
4. **Scope discipline:** q31 answered a different question than the one asked and its headline
   contradicts three other rows. Answer the asked predicate (unresolved *reference*), not the
   nearest status flag.
5. **Decide the q20 anchor:** invoice 15293 / ₹880 NEFT is either not in this workspace's data
   (q25 says price quote) or unreachable by the lookup — either way the query set's flagship
   mismatch case cannot currently be exercised. Correct the anchor or fix the lookup, then say
   which.
6. **Pin the tool surface per run** before reading any strict-% as skill: three runs, three
   surfaces (ar_* → query_ar* → ar_*+ERP tools). `spawn_filter_agent` also needs an owner — a
   sub-agent spawn inside the receivables lane is not in the declared contract.
7. **Coverage still open:** sections 6–8 and both CLARIFY controls (q46, q51) were not run by
   instruction; no REFUSE rows exist in the set at all (v1 gap, unchanged).
8. **Hedge metric needs its regex extended again:** the analyzer's HINGLISH `HEDGE_RE` scores
   4/25 on this run while most refusals hedge in English ("can't reliably", "without
   guessing", "should not yet be treated as"). Same failure mode as the earlier English-only
   gap, now inverted.

## Files

- Run: `accounts/ar-agent/runs/query_results_v3.jsonl` (35 fresh + 21 carried) + `manifest.json`
- Log: `logs/ar_agent_v3_35q.log`
- Analyzer: `scripts/analyze_ar_run.py --run 3` (use a filtered copy for fresh-35 scope; the
  unfiltered call also counts the 21 carried rows)
- Prior readout: `accounts/ar-agent/EVAL_READOUT_v1.md` (v2 run, 2026-09-24)
- Dashboard: `langsmith-tool-evaluator/docs/ar-agent/index.html`, rebuilt for this run
  (`python3 scripts/render_ar_dashboard.py --account ar-agent`)
