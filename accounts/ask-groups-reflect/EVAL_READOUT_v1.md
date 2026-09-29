# Ask My Groups — Reflect node mechanism test: EVAL READOUT v1 (2026-09-29)

**Test:** memory-only reflect-node simulation (no retry loop). Per docs/plans/ask-groups-reflect-node-test-plan.md.
**Runs:** accounts/ask-groups-reflect/runs/query_results_v2.jsonl (6 pairs) + v3.jsonl (8 pairs incl. 2 replications).
**Total:** 16 live queries · 2 workspaces (Koya 72157c26 probe + Zainab d53279c2 eval) · avg 8.9s · 0 stream errors.
**Writer:** deterministic templates (no LLM — mapping failures derivable from wire record; fixed lesson text = zero sampling confound).
**Judge:** per skill refs/ask-groups-agent.md — behavior/evidence, ANSWER/CLARIFY/REFUSE + evidence contract, honesty caveats = FEATURE, capability gaps = NEAREST_SHAPE (not a fail).

## VERDICT: NO consistent positive delta — lesson injection does not reliably improve ask-groups today

| Pair | Class | Arm A (control, no lesson) | Arm B (lesson injected) | Delta |
|---|---|---|---|---|
| F1 | Koya window (Aug DPR) | no-data + caveat (honest) | identical | 0 |
| F1b | Koya window (raw stock) | no-data + caveat (honest) | identical | 0 |
| F2 | Koya DPR hollow→list | hollow "0 posts / 0 groups" | **1 post listed w/ evidence** | +1 |
| F2b | Koya AMRUT 100 (replication) | **3 posts listed** (already good) | honest cited answer, refused factory framing | 0 |
| F3 | Zainab action ask | converts to evidence answer (native) | same, honest | 0 |
| F4 | Zainab alias (Whistling Wood) | **1 order, resolved** | 475 orders — scope blow-out | −1 |
| F4b | Zainab alias (Finesse Decor, replication) | 7 orders, resolved | identical 7 orders | 0 |
| F5 | Zainab group count | 596 groups (product fixed this) | identical | 0 |

**Per-class read:**
- **F1/F1b (corpus-window):** the agent's built-in honesty contract ALREADY produces the exact behavior the lesson teaches — coverage % in the headline, "nothing tagged in this period" with the ask-again note. The lesson added zero. The floor for a useful memory layer on this class is essentially zero: the system prompt is already honest about windows.
- **F2 (hollow→list):** the ONE encouraging signal. Pair 1 flipped a hollow "0 posts" into an evidence-cited DPR post — the lesson's "fall back to the request-list shape" instruction produced a real gain. But the replication (F2b) shows the agent can produce the listed answer WITHOUT a lesson (control found 3 posts), and the lesson arm over-refused the framing. Net: unreliable; the flip may be sampled behavior, not lesson-driven.
- **F3 (action asks):** native behavior already converts "chase Vicky Jain" into an evidence answer with an honest "rows do not mention a cheque" note. Lessons teach what the prompt already does.
- **F4 (alias resolution):** the control resolves aliases natively (both Finesse Decor and Whistling Wood answered correctly with the right group). The pair-1 lesson arm showed a real FAILURE MODE: the lesson's phrasing "groups like 'Whistling Wood + Zainab'" generalized into a LIKE-match over similar-named groups → 475 orders, 209 customers. That is the memory-layer guardrail §5.5 "lesson overshoot" risk, observed live. The replication (F4b) did not repeat it — so it's a lesson-phrasing hazard, not a deterministic effect.
- **F5 (group count):** STALE SEED — the 09-23 intro-fallback bug is GONE. Both arms answer "596 WhatsApp groups ... by role" cleanly. The product fixed this class between 2026-09-23 and 09-29; the planned "likely flat" hypothesis is moot (it's flat because the class is already resolved).

## What this means for the developer ask

**Do NOT build the reflect node on ask-groups on this evidence.** The mapping-memory hypothesis did not survive contact with the live agent: the corrections we intended to store (window honesty, alias resolution, action→evidence conversion, hollow-answer fallback) are already handled by the agent's prompt-level honesty contract. A memory layer would spend engineering + nano-calls to re-teach behavior the system prompt already encodes, and carries the observed overshoot risk (F4 pair 1).

**Where the REAL gaps are (the dev ticket should target these, not memory):**
1. **F2-class hollow answers** — the one place a lesson (or better: a deterministic shape-fallback rule) showed a real flip. Cheaper than a reflect node: a static rule "topic-match returned 0 fact rows → switch to request-list shape before emitting zeros."
2. **repeat_issues spec shape** — the known capability gap (both workspaces) — no memory fixes this.
3. **Koya corpus ingestion/window logistics** — the August window was never tagged; that's a data-pipeline fix, not a memory fix.
4. **F5 fixed** — verify the 09-23 intro-fallback finding is closed (it now answers) and close the finding.

## Confidence & caveats
- n=8 pairs, 16 arms, 2 workspaces, per-class replications for the two discriminating classes (F2/F4). Mechanism-level signal, not statistical.
- Writer = fixed template: conservative upper bound (dev-written lessons could be phrased better/worse — F4 pair 1 shows phrasing matters and can backfire).
- The lesson rides the USER message (client-side proxy); server-side load_context injection is a different mechanism — placement effects untested.
- Honesty regression: every answer in both arms carried the coverage caveat — injection never erased caveats (guardrail §7.3 passed).
- F5's seed aged out during the plan's own lifecycle (09-23 → 09-29) — itself a lesson for the corpus: seeds must be re-validated before use.

## Artifacts
- runs: accounts/ask-groups-reflect/runs/query_results_v2.jsonl + v3.jsonl (all raw responses)
- buffer: accounts/ask-groups-reflect/memory_buffer.jsonl (raw lessons — NOT committed; gitignored per decision)
- script: scripts/reflect_ask_groups_test.py (reusable for any future agent-class test; --gate mode included)
- plan doc: docs/plans/ask-groups-reflect-node-test-plan.md — status now EXECUTED, verdict recorded

## Next
User decision: (1) close it here with the negative verdict + dev ticket above, or (2) extend with an F5 re-validation + a third F2 replication (10 more queries) if the single positive signal needs more runway. Default recommendation: (1) — the evidence is consistent enough; spend the developer request on the 4 gaps, not memory.