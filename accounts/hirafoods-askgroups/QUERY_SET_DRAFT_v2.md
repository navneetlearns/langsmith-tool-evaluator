# HiraFoods Ask-My-Groups v2 — query set DRAFT (user gate, not yet approved)

Status: **PROPOSED 2026-10-09 — awaiting approval. Do not write queries.xlsx or run until approved.**
Prep done: Step-0 gates GREEN (`runs/gate_probe_v1.jsonl` + `gate_probe_v2.jsonl`, 8/8),
live-window re-anchor probe + entity-grounding probe GREEN (`runs/entity_probe_v1.jsonl`, 6/6).

## Re-anchor refresh (2026-10-13) — all gates re-run, plant is READY

Every gate re-verified four days later, before anything was generated or run. Generator now
emits this draft (`scripts/gen_ask_groups_hirafoods_queries.py`), validated via
`--out /tmp/x.xlsx` so the committed v1 `queries.xlsx` stays untouched (sha256
`ba21f843…` unchanged). **Still blocked only on your approval of the rows below.**

| Gate | 2026-10-09 | 2026-10-13 | Verdict |
|---|---|---|---|
| ask_chats deployed | id `71d19eb3`, `prompt_chars=0` | id `71d19eb3`, `prompt_chars=0` | GREEN — unchanged |
| W-gate (`gate_probe_v3.jsonl`) | 8/8 | 8/8 | GREEN |
| Entity probe (`entity_probe_v2.jsonl`) | 6/6 | 6/6 | GREEN |
| `preflight_agent_probe` | GATE-PASS | GATE-PASS (5.8s, 15,950 chars, quota alive) | GREEN |

**Corpus figures are STALE in this draft and were re-measured.** The live tagged window is
now **29 Sep → 12 Oct 2026**, **1,447 of 1,741 messages tagged (83.1% coverage)**, last-7d
band **734 messages over 6–12 Oct (6 active days)**. Row 2's note below ("715, 2–8 Oct") and
the 10 Aug – 8 Oct / 2,567-message figure in point 1 are superseded. Re-read row-level
numbers off `gate_probe_v3.jsonl`, not off this prose.

**Two findings out of the gate chain — worth your eyes before the run:**

- **W4 contradicts W1 and W3 in the same run, minutes apart.** The 24-Sep control answered
  *"No messages after 29 September 2026 are available in this workspace"*, while W1 discloses a
  29 Sep → 12 Oct window and W3 counts 734 messages in 6–12 Oct. The agent holds two
  incompatible coverage statements. This is a real agent-side defect, not an artifact — and it
  lands exactly on row 30, so that row is now the **regression test for this contradiction**,
  not a zero-control.
- **Paridhi Apparels is a live customer in the HiraFoods groups.** The 13-Oct today-anchor
  probe returned them as a named counterpart: 11 posts on 12 Oct, "40 cases Ultra Biscuits
  Regular reserved in your name, invoice ₹4,869.60", plus INV-4010 dispatch chatter. They are
  a separate ZoTok workspace with no eval account of their own — cross-link, not a scope change
  here, but it means HiraFoods is not a clean single-client corpus.

**Defects still reproducing on 2026-10-13** (both have a dedicated row): E6 top-sender renders
as `-` (302 msgs labelled "Hirafoods staff (`-`)") and the same empty-sender artifact runs
through the E4 table. photo_content still answers a nearest shape instead of refusing (W7:
114 dispatch posts), confirming the F3 relabel was right.

## Why v2 (what changed since v1, 2026-09-30)

1. **Corpus moved.** v1 was anchored to a 24–29 Sep band that turned out to be a tag gap
   (24 Sep now returns 0). Live tagged window is **10 Aug → 8 Oct 2026, 2,567 messages,
   11 groups** (top: Order Group 699, Dispatch Group 662, Hirafoods backend team 653).
   Traffic now: 109 msgs today, 715 in the last 7 days.
2. **F1 unlocked: entity-anchored rows.** v1 was entity-free by design. Real entities now
   probe-answer cleanly → 5 new ANSWER rows + 1 ambiguity CLARIFY.
3. **F3 confirmed: two REFUSE classes drifted.** photo_content and event_timing now ANSWER
   (probed twice, 2026-10-09). Relabelled — keeping them REFUSE would grade the label, not
   the agent. Ledger still refuses cleanly (kept REFUSE).

## Entity grounding (probe 2026-10-09, read-only, 6/6 answered)

| Probe | Result |
|---|---|
| E1 Laxmi Agency this week | resolves — 15 requests 3–8 Oct, 13 answered / 2 waiting, sender `Lakshmi Agencies & Co 84` |
| E2 chasing list | 26 unanswered 3–8 Oct (24 no reply, 2 "checking"); Order 14 / Other 5 / Dispatch 3 / Ledger 2 / Payment 2 |
| E3 INV-4007 + INV-4012 | both anchor richly — INV-4007: ₹4,88,000 hold, MP45 EF 3081, Diamond Juice Strong partial fulfilment; INV-4012: ₹8,13,000 outstanding, Power Soap 20 cases hold |
| E4 Pragya Traders | 29 Sep–4 Oct: INV-4008 ₹89,000 · INV-4007 ₹4,88,000 · INV-4013 ₹3,06,000 · ₹7,87,000 transferred; dispatches CG07 CQ 2990 / GJ03 AK 6407 |
| E5 payment follow-up | 2 unanswered: Lakshmi Agencies & Co 84 (₹6,42,000 transferred, "checking"), Ganesh Agencies Industries 1258 (₹3.49 L receipt waiting) |
| E6 top senders | **DEFECT:** answer names top sender as `-` (261 of 715 msgs) — sender-name renders empty; table below it is by-group. Row 11 grades this. |

Real entities usable in rows: customers `Lakshmi Agencies & Co 84`, `Laxmi Agency`,
`Om Agencies Pvt Ltd 923`, `Ganesh Wholesalers LLP 58`, `Ganesh Wholesalers & Co 454`,
`Ganesh Agencies Industries 1258`, `Pragya Traders`, `Durga Agency`; invoices
INV-4007 / 4008 / 4012 / 4013; vehicles CG07 CQ 2990, GJ03 AK 6407; products
Power Soap Strong, Diamond Juice Strong, Fresh Shampoo Fresh.

## The 30 rows (24 ANSWER / 3 CLARIFY / 3 REFUSE)

expected_tool = `no_tool` on every row (ask_chats has no user-visible tool events — grade
answer content + evidence_sids).

### A. Group Activity (3)
| # | Query | Label | Design note |
|---|---|---|---|
| 1 | How many WhatsApp groups do I have? | ANSWER | F5 intro-fallback confirmed fixed in v1; regression row. |
| 2 | How many messages were exchanged across my groups in the last 7 days? | ANSWER | W3 green (715, 2–8 Oct). Coverage caveat graded. |
| 3 | Which groups are the most active in the last 7 days? | ANSWER | List/rank shape over the live window. |

### B. Pending & Chasing (3)
| # | Query | Label | Design note |
|---|---|---|---|
| 4 | What is pending across all groups right now? | ANSWER | Request-state machine + untagged-share caveat. |
| 5 | Which customers are chasing us for a reply? | ANSWER | E2 green (26 waiting). AR-relevant. |
| 6 | Which customers are slow to reply to us? | ANSWER | Response-time claim — VERIFIED working in v1 (median 23.9 h). |

### C. Requests by Kind (7d) (4)
| # | Query | Label | Design note |
|---|---|---|---|
| 7 | How many order requests came in the last 7 days? | ANSWER | By-kind count, live band. |
| 8 | List dispatch requests from the last 7 days. | ANSWER | By-kind list; F6 document-kind confusion re-tested (invoices miscounted as dispatch in v1). |
| 9 | How many payment follow-up requests came in the last 7 days? | ANSWER | Collections-core topic. |
| 10 | Who shared tax invoices in the last 7 days? | ANSWER | Invoice chatter = AR evidence surface. |

### D. Senders (1)
| # | Query | Label | Design note |
|---|---|---|---|
| 11 | Last 7 days me sabse zyada kisne messages kiye? | ANSWER | NEW wording for the E6 defect: v1 had no sender-ranking row. Must name senders — top sender rendering as `-` = FAIL shape. |

### E. Entity-anchored — NEW section (5)
| # | Query | Label | Design note |
|---|---|---|---|
| 12 | What did Laxmi Agency ask us for this week? | ANSWER | E1 green — named-customer request state, week band. |
| 13 | Pragya Traders ke saath pichle hafte kya hua? | ANSWER | E4 green — group IS the customer; expects holds/dispatches/payments summary. |
| 14 | INV-4007 ke baare me pichle hafte kya bola gaya? | ANSWER | E3 green — invoice-anchored chat history with amounts. |
| 15 | INV-4012 par abhi kya chal raha hai? | ANSWER | E3 green — outstanding + hold discussion. |
| 16 | Payment follow-up pending kaun kaun hai? | ANSWER | E5 green — 2 customers + ₹3.49 L; entity list with amounts/status. |

### F. Clarify (3)
| # | Query | Label | Design note |
|---|---|---|---|
| 17 | Ganesh ke saath last 7 days me kya hua? | CLARIFY | NEW, real ambiguity: THREE Ganesh entities live (Wholesalers & Co 454, Wholesalers LLP 58, Agencies Industries 1258). Guessing one = FAIL. |
| 18 | What's the status of the big order from last week? | CLARIFY | carryover — no named order; guessing = FAIL. |
| 19 | Did we reply to them about the delivery? | CLARIFY | carryover — unresolved pronoun; v1 answered directly (F5) — retest. |

### G. Unsupported / engine caps (5)
| # | Query | Label | Design note |
|---|---|---|---|
| 20 | How many photos were shared as proof of delivery this week? | **ANSWER** | **RELABELLED from REFUSE (v1 q23).** Probed twice 2026-10-09: answers "0 PoD photos + photo-type caveat". Zero is a real answer — PASS when it reports 0 with caveat, FAIL on fabrication. |
| 21 | What time of day do most orders get placed? | **ANSWER** | **RELABELLED from REFUSE (v1 q25).** W8 answered day-bucket counts; hour-of-day aggregation still absent → if the answer still has no hour-of-day view, grade NEAREST_SHAPE (honest, shape-mismatch), not fail. |
| 22 | Show me the ledger balance for our top customers. | REFUSE | W6 clean refuse (unchanged) — honest scope refusal = PASS. |
| 23 | Warehouse me abhi kitna stock hai? | REFUSE | NEW ledger-class control: stock lives in ERP, not message traffic. Fabricated count = FAIL. |
| 24 | Should I give Pragya Traders a discount on the pending amount? | REFUSE | NEW `advice` cap control: no decision advice from chat traffic. Naming facts is fine; recommending a decision = FAIL. |

### H. Capability Gap (1)
| # | Query | Label | Design note |
|---|---|---|---|
| 25 | Which customers have raised the same issue multiple times even after our team said it would be resolved? | ANSWER | grade NEAREST_SHAPE (no repeat_issues shape in spec-DSL) — honest grounded list passes, dev ticket unchanged. |

### I. WhatsApp-style / multi-step (2)
| # | Query | Label | Design note |
|---|---|---|---|
| 26 | Order ka status batao aur batao kaun pending hai. | ANSWER | Hinglish imperative, 2-part. |
| 27 | Check what's pending and also list the most active groups this week. | ANSWER | Multi-step (2-part) ask. |

### J. Coverage honesty (3)
| # | Query | Label | Design note |
|---|---|---|---|
| 28 | How much of my group traffic is covered or tagged right now? | ANSWER | **F4 retest:** v1 returned the wrong (group-count) shape; W1 probe now returns the proper tagged/untagged breakdown → defect may be fixed; this row is the regression test. |
| 29 | Across all my groups including inactive ones, how many requests are unanswered right now? | ANSWER | Untagged-share + inactive-group caveat REQUIRED in headline. |
| 30 | How many messages were exchanged in my groups on 24 September? | ANSWER (date-range control, was zero-control) | **Re-labelled 2026-10-13.** W4 now answers *"outside the available workspace date range — no messages after 29 Sep 2026"* rather than "0". Per corpus rules an explicit date-range refusal is CORRECT behaviour = PASS. "no data" or a fabricated count = FAIL. This row is ALSO the regression test for the W1/W3/W4 coverage contradiction above. |

## Label delta vs v1 (exact, recomputed by query-text diff of generator v1 vs this draft)

30 rows = **20 carried** (same wording) + **10 new**; **10 dropped**; **2 label changes**.

| v1 row | v1 label | v2 | Why |
|---|---|---|---|
| How many photos were shared as proof of delivery this week? (q23) | REFUSE | **ANSWER** (row 20) | cap drifted — probed 2026-10-09, answers "0 + photo-type caveat" |
| What time of day do most orders get placed? (q25) | REFUSE | **ANSWER / NEAREST_SHAPE** (row 21) | cap drifted — day-bucket answer, hour-of-day still missing |
| Show me the ledger balance for our top customers. (q24) | REFUSE | REFUSE (row 22) | unchanged — W6 still refuses cleanly |
| How much of my group traffic is covered …? (q30) | ANSWER (F4 defect) | ANSWER (row 28) | label same, now a regression test — W1 shape looks fixed |

New rows (10): 11 sender-ranking (E6 defect), 12–16 entity-anchored (E1–E5), 17 Ganesh-ambiguity
CLARIFY, 23 warehouse-stock REFUSE, 24 advice REFUSE, 30 24-Sep zero-control.

Dropped from v1 (10, all ANSWER paraphrase/style twins — no controls lost):
"Show me requests we have not answered in the last 10 days" (twin of rows 4–5) ·
"stock enquiries 7d" / "price queries this week" / "complaints this week" (by-kind twins of
rows 7–10) · "customers who sent messages 7d" + "billing team this week" (superseded by row 11) ·
"order dispatch yesterday" (day-band twin of row 8) · "Kal dispatch kitne hue the?" +
"discussed … Monday" (style/day-band twins) · Hinglish "payment follow-up pending kaun kaun"
(superseded by entity row 16, same ask).

## Run plan (after approval)

```
# PLANT READY 2026-10-13 — gates already green, so this is one command each, not a setup job.
python3 scripts/gen_ask_groups_hirafoods_queries.py       # writes queries.xlsx, verifies 30 (24/3/3)
python3 scripts/preflight_agent_probe.py hirafoods-askgroups   # re-confirm quota/init/parser on the day
python3 scripts/run_agent_evals.py --account hirafoods-askgroups  # BACKGROUND, ~8-10 min
# hand-grade -> EVAL_READOUT_v2.md -> build_dashboard.py --account hirafoods-askgroups
# -> qa_dashboards.py -> commit (push only on request)
```

Run-harness note: 30 queries x ~13s is ~7-10 min, which blows past the terminal foreground cap
and kills the runner mid-file (partial JSONL, no manifest entry). Launch the run as a
background process, never long-timeout foreground. After any interrupt + resume, check
`wc -l runs/query_results_v2.jsonl` against the manifest success count before believing it.

Known cross-cutting grading notes: coverage caveats graded on every numeric answer; bare-sids
output = tag-gap artifact (finding, not fabrication); zero is a real answer; all 8 controls
(3 CLARIFY + 3 REFUSE + zero-control + NEAREST_SHAPE rows) stay in any subset run.
