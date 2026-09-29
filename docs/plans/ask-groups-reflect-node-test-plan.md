# Ask My Groups — Reflect Node Test Plan (runtime mapping memory, memory-only)

**Status: EXECUTED 2026-09-29 — VERDICT: negative (no consistent positive delta). See
accounts/ask-groups-reflect/EVAL_READOUT_v1.md. Reflect node NOT recommended on this evidence;
dev ticket = the 4 real gaps (F2 shape-fallback rule, repeat_issues shape, Koya ingestion,
close F5 finding).**
**NOT a production change, NOT a contract with the agent team.**
**Date:** 2026-09-29 · **By:** eval harness worker
**Goal:** evidence for the developer that a reflect node + episodic memory buffer inside
ask_chats improves query→data MAPPING on subsequent queries. Explicitly NOT a retry loop:
the user-facing request is served once; memory applies to the NEXT query of the same class.

## 0. Premise (revised after web research + user framing)

Reflexion (Shinn et al., NeurIPS 2023) is a loop: try → Evaluator → Self-Reflection → verbal
lesson in episodic memory → injected into the NEXT trial's prompt. The τ-bench paper (Yao,
Shinn, Razavi, Narasimhan — Sierra, arxiv 2406.12045) explicitly rejects the loop for
user-in-the-loop systems: "self-reflection is unrealistic as real-world agents only have one
chance to serve the user" (verified verbatim). Field data (KAIST HPCA 2026: 136x energy on
HotpotQA; Stevens agent-economics: reflection loop 10-30x tokens, 30s vs 300ms with a
memory cache hit) confirms: the RETRY LOOP is the part that doesn't transfer to chat.

BUT the copilot is not a general chat system. Failure space = query→data mapping:
the LLM selects a shape / SQL / window / alias over a facts table the seller already holds.
Mapping corrections are discrete and checkable — they are precisely what verbal episodic
memory stores reliably — and the failed wire record plus the harness label already IS
the lesson (no separate oracle needed). Hence: memory-only variant. Reflect ON failures,
inject ACROSS queries of the same class. No re-attempt of the failed query.

Companion docs: docs/plans/reflexion-vs-copilot-analysis.md (gap), docs/plans/memory-layer-design.md
(writer schema §4.1, buffer §4.2, injection slots §4.3 — reused verbatim), skill
refs/ask-groups-agent.md (grading rules), skill refs/chats-agent-architecture.md (subgraph).

## 1. What this test does and does not claim

- DOES test: a lesson written from failure F improves a LATER query of the same class
  (measured vs a control WITHOUT the lesson).
- DOES NOT test: retrying the failed query in front of the user (rejected — see §0).
- DOES NOT claim: memory can add spec shapes (repeat_issues, event-diffing) or conjure data
  that isn't tagged. Capability gaps are excluded and stay developer findings.
- NOT a golden-set eval: ask-groups has no graded baseline yet. Mechanism experiment, sized
  for signal.

## 2. Failure classes (mapping failures only, from the existing runs)

From accounts/ask-groups/RECON_DATA_INVENTORY.md (Zainab 2026-09-23) + accounts/ask-groups-koya/
PROBE_NOTES_v1.md (2026-09-28):

- **F1 Corpus-window mismatch** (STRONGEST): Koya tagged window = 25-26 Sep ONLY; August-
  anchored queries return bare "nothing in this period is tagged". Lesson: window exists,
  use it + hedge, or say the window explicitly. Pure mapping correction; data exists.
- **F2 Hollow answer where data exists**: DPR-topic hits with no fact rows (evidence as bare
  IDs; spec-cap repro both workspaces). Lesson: fall back to the request-list shape the spec
  CAN do + carry the caveat. Map-to-shape correction.
- **F3 REFUSE that a rephrase answers**: refused on phrasing, not capability. Lesson: teach
  the working phrasing / supported shape.
- **F4 Alias→entity clarify-park**: parked clarify on alias ambiguity (recon list: "Finesse
  Decor", "Whistling Wood", "Right Choice"). Lesson: alias → canonical group mapping.
- **F5 Intro fallback despite data**: "How many groups do I have?" → "nothing was counted"
  though 570-group inventory sits in parse memory. Likely NOT memory-fixable (routing) —
  a zero delta here is still evidence + a developer finding.

Predicted: F1 > F4 > F3 > F2 > F5.

## 3. Design (memory-only; control vs injection)

### 3.1 Pair structure (per failure class, per workspace)
- **SEED failure**: take a real judged failure from the existing run JSONLs (or fire it once
  fresh to capture the wire record). Write lesson from it.
- **Arm A (CONTROL)**: a NEW query of the same class, fresh thread, NO lesson.
- **Arm B (MEMORY)**: the SAME new query text, fresh thread, WITH the lesson block prepended:
  `[Workspace lesson (internal, do not quote to the customer): <lesson>] <query>`
  — mimics load_context injection server-side (same content, same context position).

Delta = Arm B verdict − Arm A verdict, per class. n = 2-3 pairs per class.

### 3.2 Reflection writer
Reuse memory-layer-design §4.1 schema VERBATIM (so the test doubles as a spec dry-run):
gpt-5.4-nano (or template, if the failure record is unambiguous — mapping failures are
mostly template-able): `[diagnose failure + correction in 1-2 sentences; applies_to:
thread|workspace; confidence 0-1]` → JSON lesson. Buffer:
accounts/ask-groups-reflect/memory_buffer.jsonl per memory-layer §4.2 schema.

### 3.3 Class detection (how a subsequent query knows it's "same class")
Use the intent classifier output / query-shape signature (the harness already classifies
strict JSON) — NOT embeddings. Threshold = same class label. This mirrors the near-dup
proxy in memory-layer §3 and is the retrieval story the developer would implement.

## 4. Test set (12-15 pairs, grounded — no placeholders)

F1 (2-3): Koya August-anchored shapes (q1/q22 style) + "this week" control. Workspace 72157c26.
F2 (2-3): DPR-topic / grouped-request shapes (Koya + Zainab).
F3 (2-3): REFUSE-class from the ask_chats prompt's UNSUPPORTED section, rephrase variants.
F4 (2-3): alias queries ("Finesse Decor", "Whistling Wood", "Right Choice") — Zainab d53279c2.
F5 (2): "How many groups…" + window variant — Zainab.

Live queries: ~12-15 seeds (reuse existing failures where possible) + 2 arms × ~12 ≈ 30-40
× ~14s ≈ 8-10 min wall + ~1 reflect call per seed. No new infra, no new accounts — reuse
accounts/ask-groups (Zainab eval creds) + accounts/ask-groups-koya configs as-is.

## 5. Gates before running (all must pass)

1. Quota probe per workspace (scripts/preflight_agent_probe.py; hard fail on 402 /
   thread-init failure / empty-response-no-error).
2. Lane confirmed: ask_chats on both workspaces (Zainab trace-confirmed; Koya probe 2026-09-28).
3. scripts/verify_account_config.py on both account dirs.
4. Judge calibration: 2 gold rows judged by hand (F1 Koya + F4 Zainab) against skill rules.

## 6. Judging (harness rules unchanged — skill refs/ask-groups-agent.md)

- Grade behavior/evidence (no tool events; chats engine). ANSWER/CLARIFY/REFUSE + evidence
  contract (cited_sids/evidence_sids).
- Honesty caveats are a FEATURE — presence in Arm B is a PASS and a regression check
  (injection must not erase caveats the control carried).
- Capability-gap shapes grade NEAREST_SHAPE (no_data/marginal, NOT fail) — a lesson is
  judged on whether a map-able answer appeared, not on inventing a shape.
- Contradiction check (memory-layer §5.5): lesson contradicts catalog/observed behavior →
  lesson yields, flagged.

## 7. Measurables (developer evidence packet)

1. **Mapping delta** per class: Arm B vs Arm A verdicts (and caveat-quality where verdicts tie).
2. **Lesson quality**: n lessons structurally valid, factually consistent with run data,
   actually used (answer reflects the lesson vs ignored).
3. **Honesty regression**: caveat presence Arm B ≥ Arm A.
4. **Buffer dump**: memory_buffer.jsonl — what ask-groups episodic memory literally contains.
5. **Per-pair table**: seed failure / Arm A verdict / Arm B verdict / lesson / delta — ready
   for a dev ticket.

## 8. Expected outcome (honest)

F1: Arm B converts bare no-data → window-honest answer; Arm A repeats bare no-data. Delta +
F4: + if alias lesson routes; agent lacks entity resolution in ask_chats (AR toolbox) — may
stay parked; still a finding. F3: + on rephraseable classes. F2: caveat-quality gain, not
recovery. F5: likely 0 — routing finding for the developer.

**Dev ask (if delta positive):** "ask_chats subgraph gains a reflect node after engine_answer,
gated on verdict ≠ ANSWER: write structured lesson → per-workspace episodic buffer → inject
into load_context on subsequent queries of the same intent class (near-dup signals). No
user-facing retry. Ship only if eval delta vs no-memory baseline is positive." **If delta
flat:** don't build; spend on repeat_issues shape and Koya ingestion instead.

## 9. Costs & risks

- ~30-40 live queries, two eval workspaces (NO prod accounts), ~10 min wall, ~1 nano call
  per seed failure. Zero infra.
- Lesson-leak risk: buffer file under the account dir; keep it out of the pushed repo unless
  user says otherwise (gitignore, or push a redacted excerpt in the readout).
- Confound: Arm A/B same query text in fresh threads — fresh threads isolate state; judge
  calibrates on 2 gold rows before the batch (§5.4).

## 10. Deliverables

1. This doc (committed).
2. After run: EVAL_READOUT-style md with §7 measurables + dev ask.
3. Skill update: refs/ask-groups-agent.md gains the reflect-test verdict + lesson samples.

## 11. Decisions needed before execution (user)

1. Workspaces OK: Zainab d53279c2 (eval) + Koya 72157c26 (probe) — both non-prod sandboxes?
2. Buffer handling: gitignore, or push redacted lessons excerpt in the readout?
3. Writer mode: nano-LLM reflection call, or TEMPLATE the lesson from the wire record +
   harness label where unambiguous (recommended for F1/F5 - cheaper, fully deterministic)?
4. If F5 delta is zero: spin straight to developer as routing finding, or keep internal?