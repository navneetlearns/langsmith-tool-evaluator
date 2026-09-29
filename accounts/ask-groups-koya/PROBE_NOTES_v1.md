# Ask Groups (Koya ws 72157c26) — Probe v1 (2026-09-28)

**Run:** `accounts/ask-groups-koya/runs/query_results_v1.jsonl` — 8 live queries total
(5 via run_agent_evals q1/q5/q11/q22/q31 + 3 ad-hoc), 0 errors, avg ~12s, lane `ask_chats` on
workspace 72157c26-eb8a-4e24-ad19-9f405860d4ad, login 7903329975.

## Verdict: lane + auth + engine all LIVE; corpus is the blocker, not the agent

- **Tagged corpus window = 2026-09-25 → 09-26 ONLY** (2 days, ~53 messages, 35 still
  untagged at probe time; "Tagging runs overnight"). 5 active groups in last 7 days.
- **The extracted sheet (`Project Status Update-KCCL.xlsx`, Status Tracker--V1 = 496 rows,
  20-Jul → 12-Aug) is NOT what the live agent serves.** August-anchored queries return
  "nothing in this period is tagged" (q1, q22) — the August DPR content is not in the live
  tagged window.
- **DPR topic DOES exist in the live corpus:** "12 DPR-related hits" but **no fact rows were
  returned** (evidence rendered as bare IDs) — the trace-4 spec-DSL cap (repeat-issue queries
  fall back to request-list / categorized-matches shape) **reproduces on Koya**. q31's method
  note confirms: "Used the supplied categorized matches; no message search was performed."
- q5 (working-day DPR gaps): honest REFUSE — "Messages are not linked into order lifecycles
  yet" — correct refusal class, spec can't do event-diffing.
- q11 (pending purchase): WORKS — answered from live corpus (1 unanswered request in
  "Purchase HO team", 20-26 Sep) with coverage caveat + evidence.

## Implication for the 40-query set

August-anchored fine-tuning cannot produce data answers on the current live window — same
degenerate-result risk as the earlier KCCL-verbatim attempt, but now for CORPUS reasons.
Paths (user decision):
1. Wait for overnight tagging to extend the window, re-probe, then run (recommended if the
   Koya team's DPR groups are expected to flow into this workspace).
2. Re-anchor the 40 set to the live window (25-26 Sep / "this week") keeping all excel
   entity grounding (projects, Purchase HO team group, DPR topic, statuses) — small-corpus
   answers + honesty gates; DPR numeric rows become REFUSE-expectation until corpus grows.
3. Verify the workspace actually ingests the Koya DPR groups (ingestion/tagging config) —
   if the Aug corpus is not being re-tagged, no amount of waiting fixes it.

## Reusable findings (feed the F-series)
- F: DPR-topic hits with no fact rows (spec-DSL cap) — reproduced on Koya ws, same as Zainab trace 4.
- F: "Messages are not linked into order lifecycles yet" — no event-diffing; working-day-since-last-DPR is unanswerable today.
- F: 35/53 untagged in-window; every numeric answer correctly carries the coverage caveat (honesty contract holds).