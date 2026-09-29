# Ask My Groups — Reflexion Mechanism Test Plan (reflect node + episodic memory buffer)

**Status: PROPOSED — test-only. NOT a production change, NOT a contract with the agent team.**
**Date:** 2026-09-29 · **By:** eval harness worker
**Goal:** produce evidence (recovery delta + lesson samples) for the developer to evaluate a
reflect node + episodic memory buffer inside the ask_chats subgraph. The test SIMULATES the
node client-side; a positive delta argues for the server-side implementation, nothing more.

## 0. Why this test exists

Reflexion (Shinn et al., NeurIPS 2023) = try task → Evaluator → Self-Reflection writes a
verbal lesson → episodic memory buffer → lesson injected into the next trial's prompt.
Three assumptions: (1) repeated attempts on the SAME task, (2) a free correct Evaluator,
(3) the actor's prompt is injectable between trials.

The ask-groups copilot violates all three today: one-shot questions, the evaluator had to be
built (this repo's harness), and the agent is a black-box SSE API — we cannot touch the
server-side prompt. The developer COULD add a reflect node after `engine_answer` (server-side
memory + injection into load_context-equivalent). Before asking them to, we test whether the
mechanism transfers: client-side, we simulate exactly what the node would do and measure
whether re-asking WITH the lesson recovers failures that a plain re-ask does not.

Companion docs: docs/plans/reflexion-vs-copilot-analysis.md (gap), docs/plans/memory-layer-design.md
(the writer schema + injection slots this test reuses), skill refs/ask-groups-agent.md
(grading rules), skill refs/chats-agent-architecture.md (subgraph).

## 1. What we are NOT testing (honest scope)

- NOT testing capability gaps. The spec-DSL has no repeat_issues shape and no event-diffing
  (Koya q5 REFUSE "Messages are not linked into order lifecycles yet" is CORRECT). Memory can
  change what the agent SAYS, not what the engine COMPUTES. Capability-gap rows are excluded.
- NOT a golden-set eval: ask-groups has no graded baseline yet (hirafoods plan Step-0 gated).
  This is a mechanism experiment, sized for signal, not a scorecard.
- NOT a claim that the node belongs in the graph. The test can only show the loop recovers
  real ask-groups failures when lessons are injected. Where the node lives is the developer's.

## 2. Failure classes in the existing runs (what "failure" means here)

From accounts/ask-groups/RECON_DATA_INVENTORY.md (Zainab, 2026-09-23, 12/12 ok) and
accounts/ask-groups-koya/PROBE_NOTES_v1.md (2026-09-28, 8/8 ok):

- **F1 Corpus-window mismatch** (STRONGEST case — the memory-layer §4.3 datagap lesson):
  Koya tagged window = 25-26 Sep ONLY; August-anchored queries return bare "nothing in this
  period is tagged" (q1, q22). Data EXISTS in the extracted sheet/inventory but is not in the
  live tagged window. A lesson can change the answer from bare no-data to an honest
  window+caveat answer, or route to "say the window, don't raw-search". Measurable delta.
- **F2 Hollow answer where data exists** (no_data/marginal grades): DPR-topic hits with no
  fact rows (evidence as bare IDs, trace-4 spec-cap repro on both workspaces). Lesson can
  enforce the honesty contract + switch shape to the request-list the spec CAN do.
- **F3 REFUSE that a rephrase/broader phrasing answers**: refused because of phrasing, not
  capability. The lesson teaches the working phrasing ("re-ask as <shape the spec supports>").
- **F4 Clarify-park that was answerable**: parked clarify on identity/alias ambiguity
  (recon alias list, e.g. "Finesse Decor" vs ERP master). Lesson maps alias → canonical
  group/entity so the next turn resolves instead of re-parking.
- **F5 Intro fallback despite data**: "How many groups do I have?" → "nothing was counted"
  although 570-group inventory sits in parse memory (repro'd on Zainab 2026-09-22). If a
  lesson explicitly points at the parse-memory shape, does the agent route correctly? If it
  still falls back, that's a routing/capability issue — lesson can't fix it (send to developer
  as a routing finding instead).

Predicted strength: F1 > F4 > F3 > F2 > F5. F5 may be unfixable by memory — that outcome is
itself evidence (memory fixes behavior policy, not routing).

## 3. Design (client-side simulation of the reflect node)

### 3.1 Arms (ablation, mirroring the paper's NONE/LAST_ATTEMPT/REFLEXION enum)
Per failed query, two re-asks in FRESH threads (never mutate the baseline thread):
- **NAIVE (LAST_ATTEMPT control)**: plain re-ask of the same question. Required because
  LLM stochasticity means retry-alone recovery > 0; REFLEXION delta is measured OVER this.
- **REFLEXION**: re-ask with the lesson block prepended to the user message:
  `[Workspace lesson (internal, do not quote to the customer): <lesson>] <same question>`
  This mimics what load_context injection would deliver server-side — same content, same
  context position. Baseline (first ask) = NONE arm.

Order per query: baseline → judge → on fail: NAIVE and REFLEXION (both, fresh threads).
One retry each. Budget-light and covers both arms.

### 3.2 Reflection writer (reuse memory-layer-design §4.1 schema VERBATIM)
One nano-class LLM call (gpt-5.4-nano) per FAILURE, after the judge:
`[diagnose this failure + new plan in 1-2 sentences; applies_to: thread|workspace; confidence 0-1]`
→ structured JSON lesson. Because we reuse the exact schema, the test doubles as a dry-run
spec check for the eventual implementation. Lessons stored in a buffer file
`accounts/ask-groups-reflect/memory_buffer.jsonl` (workspace_id, class F1-F5, text,
source_turn, verdict, confidence, created_at, expires_at — schema per memory-layer §4.2).

### 3.3 Injection (client-side proxy)
Server-side the lesson would ride the chat template context. Client-side the only injection
point is the user message (above). Limitation stated honestly: this proves the lesson CONTENT
recovers failures; server-side placement/routing is the developer's implementation.

## 4. Test set (12-15 rows, grounded in existing runs — NO placeholders)

Built from RECON_DATA_INVENTORY + PROBE_NOTES + skill refs; real entities AS TYPED:

F1 (2-3): Koya August-anchored rows (q1/q22 shapes — "DPR for <Aug period>", "status of
<project> in August"), Koya "this week" control. Workspace: 72157c26.
F2 (2-3): DPR-topic with evidence-as-bare-IDs shape (Koya), grouped-request shape (Zainab).
F3 (2-3): REFUSE-class from the ask_chats prompt's UNSUPPORTED section, rephraseable variants.
F4 (2-3): alias→entity identity queries ("Finesse Decor", "Whistling Wood", "Right Choice")
   on Zainab d53279c2.
F5 (2): "How many groups do I have?" + one window/count variant, Zainab.

Expected live queries: 12-15 baseline + ~2× failures ≈ 30-40 total × ~14s ≈ 8-10 min wall.
Plus 1 nano-reflect per failure (~2-4s). No new infra, no new accounts — reuse
accounts/ask-groups (Zainab eval creds) + accounts/ask-groups-koya configs as-is.

## 5. Gates before running (all must pass)

1. **Quota probe**: one query per workspace; hard fail on 402 topup_required / thread-init
   failure / empty-response-no-error (pattern: scripts/preflight_agent_probe.py).
2. **Lane confirmed**: ask_chats deployed on BOTH workspaces (Zainab already trace-confirmed;
   Koya probe v1 confirmed 2026-09-28).
3. **Config sanity**: scripts/verify_account_config.py on both account dirs.
4. **Judge calibration**: 2 gold rows judged by hand first (F1 Koya + F4 Zainab) — the judge
   must agree with the skill grading rules before the batch.

## 6. Judging (harness rules, unchanged — skill refs/ask-groups-agent.md)

- Grade behavior/evidence (no tool events — chats engine). ANSWER/CLARIFY/REFUSE + evidence
  contract (cited_sids/evidence_sids).
- Honesty caveats (tagging coverage %, low-volume days) are a FEATURE — their presence in a
  REFLEXION-arm answer is a PASS, and a regression check: lesson injection must NOT erase
  caveats that the baseline carried.
- Capability-gap shapes grade NEAREST_SHAPE (no_data/marginal, NOT fail) — if the spec still
  can't do the shape, REFLEXION arm should NOT be punished; the lesson has failed only if the
  agent could have answered and didn't.
- Contradiction check (memory-layer §5.5): if a lesson contradicts the catalog/observed
  behavior, lesson yields, flagged.

## 7. Measurables (the developer evidence packet)

1. **Recovery delta**: REFLEXION recovery rate − NAIVE recovery rate, per class F1-F5 and
   overall. Positive class-level delta = mechanism works for that class; zero/negative =
   memory can't fix it (still a finding).
2. **Lesson quality**: n/12-15 lessons that were (a) structurally valid JSON, (b) factually
   consistent with the run data, (c) ACTUALLY used (agent's answer reflects the lesson vs.
   ignored it). "Lesson ignored" ≠ failure of mechanism if the answer was already correct.
3. **Honesty regression**: caveat-presence in REFLEXION arm ≥ baseline.
4. **Buffer dump**: the memory_buffer.jsonl itself — the artifact showing the developer what
   ask-groups episodic memory would literally contain (text, confidence, applies_to, expiry).
5. **Per-query trace table**: baseline verdict / NAIVE verdict / REFLEXION verdict / lesson /
   delta — ready to paste into a dev ticket.

## 8. Expected outcome (honest prediction)

F1: REFLEXION recovers the no-data → window-honest-answer conversion; NAIVE repeats the bare
no-data. Delta positive. F4: positive if alias lesson routes; the agent has no entity
resolution in ask_chats (that's the AR agent's toolbox) — may stay parked; still a finding.
F3: positive on rephraseable classes. F2: caveat-quality delta (hollow → honest), not
recovery. F5: likely NO delta — routing issue, not memory issue → becomes a developer finding.

**What a positive result hands the developer (verbatim ask):** "ask_chats subgraph gains a
reflect node after engine_answer, gated on verdict=F/partial: nano-LLM writes a structured
lesson → per-workspace episodic buffer → injected on the next turn of the thread (and
near-dup re-asks). Ship it only if the eval delta vs baseline is positive (this test's
pattern)." **Negative result:** mechanism doesn't transfer → don't build it; spend on other
fixes (repeat_issues shape etc.).

## 9. Costs & risks

- Cost: ~30-40 live queries across two eval workspaces (Zainab eval creds + Koya ws 72157c26,
  the probe sandbox — NO prod accounts), ~10 min wall, ~1 nano-call per failure. Zero infra.
- Risk: lesson injection alters framing — mitigated by fresh-thread NAIVE control + the
  honesty-regression check (§6/§7.3).
- Risk: leaks — lessons contain workspace data; buffer file lives under the account dir
  (gitignored by *.jsonl? no — runs/*.jsonl are tracked; explicit decision below).
- The buffer FILE is a test artifact; keep it out of the pushed repo unless the user says
  otherwise (add accounts/ask-groups-reflect/ to .gitignore for the run, or push only a
  redacted lessons excerpt in the readout).

## 10. Deliverables

1. docs/plans/ask-groups-reflect-node-test-plan.md (this doc — committed).
2. After run: EVAL_READOUT-style md (this repo pattern) with §7 measurables + the dev ask.
3. Skill update: refs/ask-groups-agent.md gains a "reflexion test" note with the delta
   verdict + lesson samples, if the run happens.

## 11. Decisions needed before execution (user)

1. Approve the two workspaces (Zainab d53279c2 eval + Koya 72157c26 probe) — both non-prod
   eval sandboxes already in use for this agent?
2. Buffer file handling: gitignore the buffer, or push redacted lessons excerpt in the readout?
3. Retry budget: 1 retry per arm (recommended) or 2 (more tokens, thinner marginal signal)?
4. If F5 (intro fallback) shows zero delta — OK to spin the finding straight to the developer
   as a routing issue, or keep it internal?