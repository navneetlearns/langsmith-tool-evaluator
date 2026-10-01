# Ask My Groups — KCCL Query Eval (single-turn, approved scope)

**Status: CANCELED 2026-09-28 (user).** Scope had been confirmed as single-turn KCCL query set
run as-is (this doc §5-7); the run was started and killed after 2 queries. User decision:
*"these are not relevant for ask my groups."* Query set restored to the 12-row RECON probe file
(accounts/ask-groups/queries.xlsx, via scripts/gen_ask_groups_recon.py); KCCL generator +
analyzer scripts removed; partial v2 run artifacts purged. The multi-turn design (§8) and the
metric-porting analysis remain useful reference if ask-groups evals resume — the RELEVANT next
step is the RECON-inventory graded set (strategy Task 1.4), not the KCCL set.

---

## 1. What the KCCL evals were (and their true status)

1. **`evals/multiturn/scenarios_deepeval.json`** — DeepEval multi-turn E2E design: **8 scenarios
   (kccl-mt-001..008), ~30 turns**, 6 metrics (KnowledgeRetention, ConversationCompleteness,
   TurnRelevancy, RoleAdherence, Faithfulness, ToolCallCorrectness), 9 turn types
   (new_query, follow_up, freshness_check, session_recall, ambiguous_query,
   clarification_response, context_switch_back, unambiguous_query, negative-control),
   per-turn expected tool call with resolved search string / channel.
   - SUT (probe-verified, trace 01a0149a): LangGraph agent, **semantic search over ingested
     WhatsApp threads** — tool surface `search_threads`(NL query) + `get_thread_messages`
     (channel_id); no structured APIs; Faithfulness judged against the messages actually
     retrieved.
   - **Status: designed + grounded, NEVER executed.** `eval_plan.md` Part 17 (2026-08-18)
     pivoted the run to the live Direct-API pipeline (LangSmith quota exhausted) — "rewrite
     scenario tool mapping + wire Direct-API multi-turn runner (OUT OF SCOPE — not yet
     started)". No run artifacts exist anywhere in AgentWork.
2. **`dataset.json`** (kccl-prompt-dataset, 25 cases) — WhatsApp message → structured
   extraction cases for the DPR agent (extraction eval, different flavor, not the chat copilot).
3. **`/mnt/c/Users/sumit/ai-prompt-refiner`** — GEPA prompt optimization (results Aug 20,
   best_score 0.47): initial prompt = KCCL "data extraction assistant" flavor. **Repo has since
   been repurposed for order-capture (grains)** — its current config/dataset is NOT KCCL.

**Net:** "the KCCL evals" = the 8-scenario multi-turn chat design. It is a *design to port and
execute*, not a run to replicate.

## 2. Why the port to Ask My Groups is natural (same SUT pattern)

| | KCCL copilot (workspace 72157c26) | Ask My Groups (Zainab d53279c2, `ask_chats`) |
|---|---|---|
| Architecture | LangGraph, search over ingested WA threads | supervisor → `threads_search` → chats_agent; spec-DSL → engine over tagged-message corpus |
| Retrieval | `search_threads` (NL string the agent builds) | `spec` extraction (topics, search_words, group/person, day-band) — observable on the wire as `{"tool":"spec",args}` trace events |
| Answer shape | ThreadCards: summary + matched threads + messages | headline + blocks/table + `evidence_sids[]` |
| Cross-turn state | LangGraph state ("Previous turn: workflow=search") | parse history: 5-10 prior Q/A pairs ride into classifier/parse (trace 2+3 verified) |
| Coverage honesty | (implicit) | first-class: untagged-share + low-volume-day warnings in headline |
| Non-message question | — | graceful intro fallback ("nothing was counted") = the REFUSE class |
| Verified evidence | 2026-08-18 probe | traces 01a0c767/794/7cb (2026-09-22) + recon v1 (12/12) + trace 4 (2026-09-28) |

Both agents answer the same user pattern: follow-ups that must fold prior entities into the
retrieval, freshness re-checks on a moving corpus, no fabrication, no unnecessary fallback.

## 3. Metric porting table

| KCCL metric | Ask My Groups equivalent | How it is observed |
|---|---|---|
| ToolCallCorrectness | **SpecResolution**: spec `topics`/`search_words`/`group`/`person`/day-band must capture the resolved entity from conversation (e.g. follow-up "what about RR?" → spec group/filter resolves RR, not the prior STO) | wire `trace {"tool":"spec",args}` + `request_table` SQL (NOT user-visible tools — never invent expected_tool names) |
| KnowledgeRetention | same name: entity/alias/amount/date retention across turns; pronoun resolution | compare turn N spec args vs turn 1; skip `freshness_check` turns (correct behavior = fresh spec, engine re-reads corpus anyway) |
| Faithfulness | **Groundedness**: every claimed number/count maps to cited `evidence_sids[]`; no invented SIDs; `relaxed[]` flagged | answer payload `evidence_sids[]` + `method` note — STRONGER evidence contract than KCCL (SIDs are explicit) |
| ConversationCompleteness | same: multi-part asks, count vs list vs reasons covered; no stop-after-partial | block/table coverage vs expected shape (count/list/reasons/bars) |
| TurnRelevancy | same: clean entity/group switch, no bleed | spec args + blocks per turn |
| RoleAdherence | **ScopeFallback / refusal**: non-message question → intro fallback (REFUSE), greeting/off-topic → polite refusal; **no unnecessary fallback** on a valid message question (negative control) | `shape=chat` spec + intro response text |
| — *(new)* | **CoverageHonesty**: untagged-share + low-volume-day warnings survive in headline when the answer depends on partial corpus | headline text regex (recon v1 answers already carry both caveats correctly) |
| — *(new)* | **NoFabrication of evidence**: empty/unsupported result → graceful fallback, not invented rows | blocks + SIDs count |

## 4. Scenario set adaptation (8 KCCL scenarios → ask-groups)

Domain entities map: KCCL project/indent/PO/date ↔ ask-groups customer alias/group/
invoice/cheque/request-kind/amount. Real Zainab anchors from `RECON_DATA_INVENTORY.md`:
invoice **B NO 15293**, 02-Sep cheque-not-deposited (Vicky Jain), Al Anwar outstanding
(Idris Contractor), RR/AP/STO amounts ("Stocking Fabric Sales 22-09-2026": RR 25,391 / AP
15,063 / STO 1,56,377), aliases as typed (Finesse Decor, Whistling Wood, Right Choice,
Casa walls, hiteshvthakkar).

| # | KCCL scenario | Ask-groups adaptation (Zainab) |
|---|---|---|
| mt-001 | DI Pipeline follow-up across turns (Alakkode) | "What is the status of the RR outstanding in last week's stock report?" → "What about AP?" → "Why is STO so high?" → "Has it changed now?" (freshness) |
| mt-002 | Plan vs Actual (Elevanchery, two dates) | "What stock enquiries came in this week?" → "Which of those were answered?" → "What came in yesterday?" → "Did the RR enquiry band continue?" (day-band advance + compare) |
| mt-003 | Indent lifecycle (Indent 54 → PO-174) | "What was discussed about invoice B NO 15293?" → "Has it been paid?" → "What is the payment reference?" → "Is it still not deposited?" (freshness, pronoun re-anchor cheque→invoice) → "What about the Al Anwar one?" (new entity, no bleed) |
| mt-004 | Factory action-item status (Kothur → Pamidi) | "What is pending on the Vicky Jain thread?" → "What was the previous status?" (session_recall: no record → say so, no fabrication) → "What about Whistling Wood?" → "And Finesse Decor's quotation?" (entity switch, no cross-contamination) |
| mt-005 | Ambiguous PO-174 → clarify | "What is the status of the payment pending?" (no group/customer qualifier → CLARIFY or scoped spec, never invented customer) → "The one for Finesse Decor." (combined spec) + negative control: fully-qualified query must NOT fall back |
| mt-006 | Same-day multi-project separation | "What's pending in RR?" → "What about STO?" → "Go back to RR — what's pending there?" (context switch back) → "And GST invoices?" (ambiguous entity — must not blindly attach to RR) |
| mt-007 | Heavy-rain blocker follow-up | "Why has no one answered the stock enquiry?" → "When was it asked?" → "Is it still unanswered?" (freshness) → "What was replied after that?" |
| mt-008 | Tender due-date continuity | "What was discussed about the Al Anwar outstanding?" → "When was it due?" → "Has payment been received?" (freshness — must NOT assume not-due = unpaid) → "What is the next action?" (grounded only) |

Coverage-honesty rows added across scenarios (the ask-groups-only class): requests that
touch the untagged 61% or the 3 low-volume days MUST carry the caveat; absence of caveat on
a partial-corpus answer = failure. Trace-4 gap (2026-09-28: repeat-issue queries fall back
to a generic request-list — spec-DSL cap) becomes REFUSE-class cases: "show repeated unpaid
follow-ups for RR" type queries graded on whether the agent admits the cap instead of
silently returning the wrong shape. Scope-gap anchor: "How many groups do I have?" → intro
fallback (known gap, negative-control class).

## 5. Runner + grading work (approved scope)

1. `scripts/run_agent_evals.py --account ask-groups` as-is — single-turn runner, reads
   `accounts/ask-groups/queries.xlsx` (Format A, col E expected_behavior), streams each query
   over SSE, records response/tool_calls/status_sequence/timing/error. No new runner code.
2. **Query set = the KCCL queries themselves** (user-approved, NOT a re-derived ask-groups set):
   - 31 graded DPR queries — `zochief-test-queries-dpr.md` (§A–G: lookup, aggregation,
     per-customer drilling, comparison/ranking, cross-table consistency, anomaly/trap, edge)
   - 10 live demo Q&A — `demo-chat-samples.md` (Koya office, 2026-09-16)
   - 16 standalone scenario turns — `scenarios_deepeval.json` (only self-contained turn
     types: new_query / ambiguous_query / unambiguous negative-control; multi-turn-only
     turns excluded per "no multi-turn")
   - Total ≈ 57. Generator: `scripts/gen_ask_groups_kccl.py` (owns the xlsx; rerun to
     regenerate; never hand-edit).
3. **Labels:** expected_behavior = `REFUSE` for out-of-corpus KCCL queries (correct behavior
   = graceful fallback / "nothing was counted", ZERO fabrication), `CLARIFY` for the
   ambiguous standalone turns (correct = ask for qualifier or fall back, never guess).
   expected_tool = `no_tool` (ask_chats engine has NO user-visible tool events — grade
   behavior/answers/evidence, never tools). Remarks carry the source (DPR# / demo# / mt-N
   turn-N) + the trap intent (zero-handling, anomaly-repro, units, ambiguity).
4. **Grading (post-run):** per-row judgment into buckets:
   - `CLEAN_REFUSAL` — pass: intro/fallback or explicit "not in tagged messages", no
     fabricated pipe/fabric numbers, no wrong-domain answer.
   - `CROSS_DOMAIN` — fail: answered the KCCL query with fabric-corpus data
     (agent treated the pipe query as a fabric message-traffic query).
   - `FABRICATED` — fail: asserted KCCL-domain facts (pipes, Alakkode, GS Kumbhar, 10,387…)
     that cannot exist in the Zainab corpus.
   - `CLARIFY_OK` — pass (ambiguous rows only): asked for qualifier or fell back.
   - `ERROR` — stream failure.
   Headline numbers: correct-refusal rate, fabrication=0 target, cross-domain rate,
   coverage-caveat presence on any partial answers.
5. **Readout:** `EVAL_READOUT_v1.md` in `accounts/ask-groups/` + two-tab dashboard
   (renderer pattern from AR/finance), same verification bar (light theme, no console
   errors, no `../../` links).

## 6. Sequencing & gates (approved)

1. **Probe gate:** 3-query subset (`--only`) — quota, `ask_chats` lane init, parser.
2. **Full run:** 57 queries, ~14s avg → ~15-20 min, no retries (HEART), JWT auto-refresh.
3. **Grading + readout** per §5.
4. **Verification checklist (all must pass before claiming done):**
   - Run manifest: 57/57 succeeded, 0 stream errors (or explicit error list).
   - Every row graded; buckets sum to 57; every FAIL has the offending quote.
   - CLEAN_REFUSAL rate + fabrication count + cross-domain count headline the readout.
   - EVAL_READOUT_v1.md + dashboard render; Playwright QA green (same bar as AR/finance).
   - PROJECTS.md + README updated with run state.
5. **Context caveat for the report:** KCCL queries are pipe/DPR-domain, Zainab corpus is
   fabric-trade — the bulk of this eval exercises the REFUSE/groundedness contract
   (does the agent fabricate, leak cross-domain data, or refuse cleanly). It does NOT test
   answerable traffic-query quality — that stays the ask-groups graded set (strategy
   Task 1.4, RECON inventory) as a separate future run.

## 7. Decision gates (as of 2026-09-28 — then CANCELED)

1. Multi-turn: **NO** (user). Multi-turn proposal archived in §8.
2. Query set: the KCCL queries as-is — **rejected 2026-09-28 by user: "these are not relevant
   for ask my groups."** Full stop; run killed at q2; artifacts reverted.
3. Quota: topped up (user) — unused for this eval; only 3 probe queries + 2 run queries hit
   the live lane before cancellation.
4. Future path: build the graded ask-groups set from `RECON_DATA_INVENTORY.md` (request-kind,
   pending/chasing, response-time, evidence anchors B NO 15293 / 02-Sep cheque / Al Anwar,
   REFUSE/CLARIFY classes from the deployed ask_chats prompt) — strategy Task 1.4, no KCCL
   content.

## 8. Archived — original multi-turn proposal (superseded 2026-09-28)

Prior version of this doc proposed porting the 8 KCCL multi-turn scenarios
(scenarios_deepeval.json, mt-001..008) with fabric-domain anchors, a new
`run_multiturn_scenarios.py` driver, and per-turn spec-resolution grading. User decision:
no multi-turn now. Retained in git history of this file; the metric porting table and
scenario anchors from that version remain reusable if multi-turn comes back — see
`git log -p -- ask-groups-kccl-multiturn-eval-plan.md`.

## Sources

- KCCL scenarios: `~/AgentWork/kccl-prompt-dataset/evals/multiturn/scenarios_deepeval.json`
- KCCL grounding + runner pivot: `eval_plan.md` Part 17 (this repo)
- Strategy umbrella: `agent-eval-strategy.md` § Tasks 1.4, 2.3, 2.4 (this repo, 2026-09-28)
- Agent surface + trace evidence: `~/AgentWork/seller-copilot/agent-profiles/ask-groups-agent.md`,
  `~/AgentWork/seller-copilot/Ask Groups Agent/ask-groups-agent-trace-notes.md`
- Recon/anchors: `accounts/ask-groups/RECON_DATA_INVENTORY.md` + `runs/query_results_v1.jsonl`
  (12/12, avg 14.2s, no tool events) + trace 4 note in README (spec-DSL cap gap, 2026-09-28)