# Memory Layer Design — Runtime Self-Reflection for Copilot Agents

Design doc 2026-09-29. Status: PROPOSED — not approved; executes only after user confirms
the decision gates in §7. Companion to agent-eval-strategy.md (four-agent strategy, G5
closed loop) and reflexion-vs-copilot-analysis.md (the gap this design closes). Rooted in
the Reflexion pattern (Shinn et al., NeurIPS 2023; github.com/noahshinn/reflexion) applied
to the ZoChief LangGraph graph (agent-design-notes.md).

## 1. Problem
The copilot's correctness is frozen into the system (gold-SQL catalogue, guardrails,
catalog semantics, refusal boundaries) — there is NO runtime learning from failures. A
merchant's failed turn (parked clarify that was answerable, wrong refusal, wrong or hollow
answer) produces no lesson the agent reads on the next turn of the thread or workspace.
The eval harness labels these failures offline; nothing feeds them back at runtime.

## 2. What this is NOT
NOT vector-RAG over chat history (search_threads already exists and covers recall of past
messages). This is episodic REFLECTION memory: one-paragraph verbal lessons about how the
agent itself should behave, written after failures, injected into future context. It
augments the semantic catalog, never replaces it; catalog wins, memory yields.

## 3. Runtime failure signals (proxies — production has no labels)
The harness stays the ground-truth labeler; runtime uses cheap proxies:
- parked clarify the user never resumes, or resumes with a different option than offered
- near-dup intent re-asked in a different thread within N days (use the intent classifier
  output, not embeddings — the classifier already runs and is strict JSON)
- out_of_scope refusal followed by a rephrase of the same question
- tool exception / empty result on a question shape that previously returned data
- thread abandonment mid-clarify
Known weakness: proxies are noisy; confidence field + expiry mitigate.

## 4. Components

### 4.1 Reflection writer (post-turn, async — never in the response path)
One cheap LLM call (gpt-5.4-nano class) after a flagged failing turn:
`[diagnose failure + new plan in 1-2 sentences; applies_to: thread|workspace; confidence 0-1]`
→ structured JSON lesson. Cost: one nano call per FAILURE, not per turn. Zero impact on
response latency (7-300s) and the SSE stream — it runs after the response is delivered.

### 4.2 Lesson store
Small table: `lessons(workspace_id, agent, thread_id, text, source_turn, verdict,
confidence, created_at, expires_at)`. MySQL backend already exists. v1 = no retrieval:
per workspace fetch active (unexpired) lessons ordered recency, cap 5, ~200 tokens each.
OpenSearch only if similarity retrieval is wanted later.

### 4.3 Injection per agent (reuse existing slots)
- ar_agent: a "Workspace lessons" block rides into load_context next to the semantic
  catalog (cap 5 × ~200 tokens).
- finance_agent: lessons about clarify quality appended to the classify prompt
  (e.g. "this customer's 'dues' = reconciled PAB only, not invoice ageing"). The gold-SQL
  pipeline stays static — memory never rewrites data semantics.
- ask-groups: STRONGEST case — workspace datagap lessons ("answers only over
  MessageFacts-tagged days; Koya August window NOT tagged; say so, don't raw-search").
  The KOYA recon already wrote this as a doc; this makes such lessons runtime-checked.

### 4.4 Offline bootstrap
One-off job converts labeled harness failures (EVAL_READOUT / run JSONLs) into the initial
lesson rows per workspace — the closed loop start (G5), not a blank slate.

## 5. Guardrails (non-negotiable)
1. Write-protected store: ONLY the reflection job writes lessons; the agent never does
   ("untrusted data never instructs" rule).
2. Per-workspace isolation. No cross-tenant bleed.
3. Expiry + cap: windowed memory, not permanent (the Koya datagap lesson must expire when
   nightly tagging backfill lands). Default TTL per lesson (e.g. 30d thread/7d workspace),
   revisable.
4. Audit + kill switch: memory_on flag per workspace/agent; eval runs output a "memory
   effects" section (lessons injected, which fired, verdicts).
5. Conflict rule: an injected lesson may not contradict the semantic catalog / gold SQL.
   Catalog wins. Contradiction → lesson yields, flagged to audit.

## 6. Verification (delta-vs-baseline, already in the four-agent strategy)
- Run each agent's suite with memory ON vs OFF on the SAME golden sets → gate on delta
  (eval_cli gate --min-match pattern). No positive delta → memory stays off for that agent.
- Latency delta measured (injection adds prompt tokens; must stay within budget).
- Regression replay continues to run against the frozen sets — memory never bypasses the
  offline regression gate.

## 7. Decision gates (user to confirm)
1. Scope: which agents first? (recommend ask-groups for the datagap case + AR for identity
   lessons; finance last — most constrained, least to gain)
2. Failure proxies acceptable as runtime signal, with harness as offline labeler?
3. TTL defaults (30d thread / 7d workspace?) and per-workspace kill-switch behavior.
4. Who reviews injected lessons before they take effect? (auto after confidence ≥ X, else
   queue for human/offline review — pending user preference)

## 8. Costs
- 1 table; 1 async post-turn job; 1 context block per agent; bootstrap job; gating run.
- No new infra, no new model spend beyond nano-call-per-failure.

## 9. Open questions
- Finance: does the clarify resume re-run the classifier? (affects where clarify-quality
  lessons inject) — see agent-design-notes §5.
- Near-dup detection quality on intent-classifier output (measure false-positive rate
  before trusting the proxy).
- Expiry↔backfill coupling for ask-groups (Koya): lesson should auto-expire when the
  covered_range covers the re-anchored window.

## 10. Sources
- reflexion-vs-copilot-analysis.md (this repo, commit 8d36303)
- agent-eval-strategy.md (this repo) — G5 closed loop, delta-vs-baseline gating
- agent-design-notes.md (~/AgentWork/seller-copilot) — graph architecture, tool surface
- reflexion repo: github.com/noahshinn/reflexion; paper arxiv.org/abs/2303.11366