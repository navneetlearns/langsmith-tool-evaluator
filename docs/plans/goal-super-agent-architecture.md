# Goal-Driven Super Agent over the Copilot Agents — Architecture Options

Prepared 2026-09-30. Follows the thread of reflexion-vs-copilot-analysis.md (2026-09-29),
memory-layer-design.md (2026-09-29, PROPOSED, not approved) and agent-eval-strategy.md
(repo root of this thread). This doc does NOT implement anything — it lays out the
approaches, trade-offs, and decision gates for a user-orchestrated "super agent" that
sits on top of the three deployed copilot agents, runs goal-defined, does not stop until
the goal is complete, and only then reports.

## 0. TL;DR / recommendation

Build the super agent as a **harness-first orchestrator (Approach A)** with an LLM planner
inside a code-controlled Reflexion loop — not as a fully autonomous LLM loop (B), and not
as a peer multi-agent team (C). Three non-negotiable design rules carry over from this
repo's own eval history:

1. **The loop's goal-evaluator must be deterministic code reading ground truth** from the
   data sources (KPI telemetry), never the LLM's self-report. The reflect-node test
   (ac02d56) came back negative — naive memory injection did not move quality; only a
   loop with real environment feedback earns its tokens.
2. **Counter-KPIs are mandatory in every goal card.** A "reduce lead growth to 12%" goal
   is trivially gamed by turning campaigns off (the Goodhart problem, now at agent level).
   Goal cards must carry guardrail constraints (CAC ceiling, qualified-lead floor,
   minimum engagement) that the evaluator checks too.
3. **Actions are tiered by irreversibility** (read = auto; draft = auto; WhatsApp send /
   spend = approval-gated with hard caps). First run gets full-plan approval, then
   run-level autonomy within the card's budget and allow-lists.

## 1. The ask, restated

- **Base:** Reflexion (Shinn et al., NeurIPS 2023) — Actor → Evaluator → Self-Reflection →
  episodic memory → retry until success. Proven on benchmarks with free ground truth and
  repeated attempts.
- **Subjects:** the three deployed copilot agents (AR, Finance, Ask My Groups; order-to-
  dispatch joins when it runs), each with its own data source, each today answering one
  question at a time with the merchant manually relaying action (e.g. drafting a WhatsApp
  message the human then sends).
- **Super agent:** sits above all of them. User defines a goal, the tools/data it may use,
  and a cadence. It plans, gets approval once, then iterates autonomously: act through the
  agents, measure the KPI, reflect on failures, retry, until the goal is hit or a stop
  condition fires. Then it generates a report. User can pause, edit the plan, or kill it
  at any point. Claude Code / CLI-agent loop with persistent self-learning is the model.
- **Worked example (used throughout):** reduce new-lead growth rate to ≤12% MoM, using
  customer base, product catalog, campaign budget, and a timeframe; deliver via WhatsApp
  campaigns and report progress.

## 2. Inventory — what already exists (reuse, don't rebuild)

| Asset | Where | What it gives the super agent |
|---|---|---|
| AR agent | copilot graph (gpt-5.6-luna ReAct) | receivables/identity tools; ALREADY has `prepare_whatsapp_message` + `resolve_whatsapp_recipient` — drafting exists, sending is manual |
| Finance agent | copilot graph (gpt-5.4-mini classify) | 34-metric gold-SQL catalogue; campaign spend/CAC queries are expressible today |
| Ask My Groups | copilot graph (ask_chats lane, ~13s/query) | WhatsApp-group demand signals, coverage caveats, datagap lessons (Koya) |
| Eval harness | this repo | judged runs, EVAL_CONTRACT pillars, delta-gated `eval_cli gate` — the *scaffold* for the super agent's own acceptance gate |
| memory-layer-design.md | docs/plans/ | PROPOSED lessons table + post-turn reflection writer + injection slots + guardrails (write-protected, TTL, kill switch) — the super agent's episodic memory, unapproved but designed |
| reflect-node test | ac02d56 / accounts/ask-groups-reflect | NEGATIVE — memory-only reflection without retry showed no delta. Lesson: reflection pays only inside a true act→measure→retry loop |
| whatsapp-service | ~/AgentWork/whatsapp-service | /send API (num 917903329975) — the actual outbound channel when an action is approved |
| Dashboards | docs/ + Pages | readout + two-tab dashboard pattern → the report generator's output shape |
| LangSmith traces | seller-copilot-agent project | online replay layer (agent-eval-strategy Phase 3) → real-traffic KPI measurement |

The true gaps the super agent fills are therefore **four**, not one: (1) the goal/loop
layer (plan → act → measure → reflect → retry), (2) authorized action execution (send /
spend / write), (3) KPI telemetry as the deterministic evaluator, (4) the end-of-goal
report. Everything else exists.

## 3. The core loop (Reflexion generalized to business goals)

```
goal card ──► PLAN ──► APPROVE ──► EXECUTE ──► MEASURE ──► hit? ──yes──► REPORT
   ▲           (planner)  (human,     (agents    (KPI      │
   └───────────── edit /   first run   as tools,  telemetry │no
                  resume   only)       tiered     ground    ▼
                                       actions)   truth)  REFLECT → lessons →
                                                           retry next cycle
```

Mapping against Reflexion (from reflexion-vs-copilot-analysis.md):

| Reflexion part | Super agent equivalent | Notes |
|---|---|---|
| Actor | planner LLM + the three agent tools | the agents are *tools with documented ACIs*, not peers |
| Evaluator | deterministic KPI check on real data | Reflexion assumed a free evaluator; in business it must be BUILT — this is the hardest part, not the loop |
| Self-Reflection | post-cycle lesson writer (nano-class call) | async, never in the action path (memory-layer-design §4.1) |
| Episodic memory | lessons table (write-protected, TTL, per-workspace) | memory-layer-design §4.2-4.3 |
| Retry | next cycle with lessons + updated plan | bounded by attempt cap AND budget cap |
| — (new) | procedural memory: playbook store | Voyager-style: what worked becomes a reusable skill (campaign playbook), eval-gated before reuse |

Self-learning here = episodic reflection (why did the last cycle fail) + procedural
playbooks (what worked, reusable). Neither is the agent writing its own instructions —
both are write-protected (only the reflection job / a human-approved promotion writes).

## 4. The goal card (the interface the user edits)

A goal card is the user's contract with the super agent. The user can always stop, edit,
or modify it mid-run; edits re-plan.

```
goal:            reduce new-lead growth rate to <= 12% MoM
guardrail-KPIs:  CAC <= target, qualified-lead rate >= floor, no blanket campaign kill
data bindings:   customer master, campaign analytics, product catalog, budget ledger
tools:           finance_agent, ask_my_groups, ar_agent, crm_read, whatsapp_send
cadence:         weekly cycle, report every cycle + final
budget:          campaign spend cap ₹X/cycle, hard stop at ₹Y total
approval:        first run: full plan. then auto within allow-lists; send-burst + spend-topup → ask
stop conditions: goal hit, attempts cap, budget cap, KPI regressed 2 cycles, user stop
report:          goal dashboard + PDF summary to merchant (and/or WhatsApp)
```

Notes: KPIs and guardrails must be computable from the bound data sources before the goal
is accepted (an unmeasurable goal is rejected at definition time — that is the evaluator
contract). Cadence can be batch (weekly) or continuous (watch KPI, act on drift).

## 5. Approaches

### A. Harness-first: durable orchestrator, code controls the loop

The Reflexion loop lives in code (LangGraph with interrupts/checkpoints, or Temporal-
style durable execution — the repo already runs a LangGraph graph, so LangGraph +
checkpointing is the native path). The planner LLM is one node inside a fixed loop:
it writes the action plan for the cycle; the three agents are invoked as tools; KPI
measurement, counters, caps, and stop conditions are deterministic code; the reflection
writer is an async node.

- Pros: predictable and debuggable (failure localizes to a node); cheapest token burn
  (LLM only at plan + reflection + agent invocations); checkpoints give stop/edit/resume
  for free (edit the plan artifact, resume from last checkpoint); deterministic gates
  (budget, attempts, KPI) make it safe enough for real merchant money; matches the repo's
  existing graph + eval-gate culture.
- Cons: the control flow is fixed — novel strategy shapes are limited to what the planner
  can express *within* the loop (which is most things, but not arbitrary multi-goal
  tangents); more engineering than a pure agent loop; LLM planner can still under-plan,
  so plan quality gates needed.
- Failure modes: planner produces an infeasible plan; KPI telemetry lags real effects
  (weekly data latency); guardrail conflict (goal vs counter-KPI tension) stalls the loop.

### B. Agent-first: fully autonomous LLM loop (Claude-Code-for-business-goals)

One strong planner model owns the entire loop end-to-end: reads the goal card, chooses
tools, observes, reflects, retries, decides when done — behind a permission system like
Claude Code's (plan mode first, then allow/deny/ask per action class). The three agents
are MCP-style tools. Playbook store for cross-run learning.

- Pros: maximum flexibility — can invent strategy the harness never encoded; the closest
  match to the user's "CLI agent with self-learning loop" mental model; fastest to a
  demo; one mental model to reason about.
- Cons: token burn on long horizons (every step = LLM call, compounding error rate per
  Anthropic); goal "success" must still be verified against ground-truth telemetry
  (self-report is not acceptable — a goal claimed "hit" without a KPI read is a
  hallucination); hardest to debug when the loop drifts; guardrail enforcement lives in
  prompts unless hardened into code anyway — at which point it becomes A; cost spikes
  without a code-level cap.
- Failure modes: runaway loops (mitigated by code-level caps, which shifts it toward A);
  strategy drift (planner rationalizes a stuck loop instead of escalating); spend/send
  accidents if permission engine is prompt-level.

### C. Hierarchical multi-agent: executive + workers + critic + reflector

Role-separated: an executive agent plans strategy; the three copilot agents execute
domain work; a critic agent scores action quality (LLM-judged, where KPI telemetry can't
see — e.g. message quality); a reflector agent writes lessons. Follows Anthropic's
orchestrator-workers + evaluator-optimizer shapes combined.

- Pros: roles are testable in isolation (critic is the eval harness's LLM-judge, reused);
  clear owners for quality vs measurement vs execution; parallelizable.
- Cons: most complex + most token-expensive (multi-agent overhead multiplies); role
  boundaries drift without a strict contract; debugging a disagreement between agents is
  the worst case; this is the pattern the industry is moving away from for production
  unless a role has a *clear measurable value* (Anthropic's "add complexity only when it
  demonstrably improves outcomes"; this repo's reflect-node negative test is the same
  lesson at smaller scale).
- Failure modes: critic/executive disagreement loops; reflector writes lessons that
  conflict with catalog semantics (memory-layer-design §5.5 conflict rule must apply);
  cost blowup from voting/parallel passes.

### D. Product wrapper (orthogonal to A/B/C — the "platform feature" framer)

Whatever the engine, ship it as a **goal-card service**: goal card schema + dashboard
(progress vs KPI, cycle history, actions taken, audit trail) + report generator (existing
two-tab dashboard pattern + merchant-facing PDF) + messenger hooks (whatsapp-service
/send, Telegram). This is what makes it feel like a product ("research report generator
that takes action") instead of an experiment. Not an alternative to A/B/C; the packaging
layer any of them needs.

## 6. Comparative matrix

| Dimension | A. Harness-first | B. Agent-first | C. Hierarchical |
|---|---|---|---|
| Flexibility (novel strategies) | Medium (planner inside fixed loop) | High | Medium-High |
| Token cost / cycle | Lowest | Highest | Highest |
| Debuggability | Best (node-localized) | Hard (loop drift) | Hardest (role disputes) |
| Safety/guardrails | In code (strong) | In permission engine (needs hardening) | Split across roles |
| Time to v1 | Medium | Fastest demo, slowest to trust | Slowest |
| Stop/edit/resume | Native (checkpoints) | Depends on harness | Depends on harness |
| Self-learning | Episodic + playbooks, eval-gated | Full, but unverified | Role-owned |
| Fit for merchant money | High | Medium (needs guardrail hardening) | Medium |

All three converge if built honestly: B without code-level caps is unsafe; B with
code-level caps is A wearing a costume; C without strict contracts is A with extra cost.
The real decision is **where the control flow lives** — code (A) vs model (B) — and how
many LLM roles you pay for (C).

## 7. Recommendation — phased

1. **Phase 1 (Approach A, minimal):** goal card schema + durable loop (LangGraph
   interrupts/checkpoints) over the three agents as tools + deterministic KPI evaluator
   reading the bound data sources + cycle ledger + report (dashboard + PDF). No memory
   yet. Target: merchant picks a real goal (collections chase is the safest first goal —
   AR agent's WhatsApp drafting already exists; sends approval-gated), runs 3-4 cycles,
   human verifies each action until trust.
2. **Phase 2 (episodic memory):** adopt memory-layer-design's lessons table + reflection
   writer, wired to cycle outcomes — **gated by delta** (memory ON vs OFF on a frozen
   goal replay; no positive delta → memory stays off; exactly the `eval_cli gate` pattern
   and the reflect-node test's discipline).
3. **Phase 3 (procedural memory):** playbook store — a cycle that hits the goal promotes
   its strategy to a reusable playbook (human-approved or high-confidence auto), replayed
   on similar goal cards.
4. **Phase 4 (optional, only if a goal type demonstrably needs it):** a critic LLM role
   for action quality where KPI telemetry is blind (message tone/legal-safety), reused
   from the eval harness's calibrated judge.

Feedback loop: every supervised run and every real run lands in the run ledger; failing
runs promote to a golden goal-replay set (the G5 closed loop, now at goal level).

## 8. Guardrails (non-negotiable, all of them)

1. **Ground-truth evaluator:** goal hit ≠ LLM claim. The KPI is read from the bound data
   source by code. Self-reported success without a telemetry read = failure.
2. **Counter-KPIs:** every goal card carries constraints (CAC, quality floor, no blanket
   kill). Evaluator fails a cycle that games the headline KPI.
3. **Action tiers:** read (auto) → internal write/draft (auto) → WhatsApp send (approve
   per burst or allow-listed recipients) → spend (approve with hard cap). First run:
   full plan approval. Claude-Code-style allow/deny/ask, enforced in code.
4. **Hard stops:** attempt cap, cycle budget cap, total budget cap, 2-consecutive-cycle
   regression → planner must escalate to human, not keep flipping levers.
5. **Tenant isolation:** per-workspace state/memory; goals never cross workspaces.
6. **Write-protected memory:** only the reflection job (or human approval) writes lessons;
   lessons may not contradict catalog/gold-SQL; catalog wins (memory-layer-design §5).
7. **Audit + kill switch:** full action journal (what, when, by which node, which
   approval); memory_on / agent_on flags per workspace.
8. **Unmeasurable goal → rejected at definition time** with a diagnostic (which
   KPI/data binding is missing).

## 9. Decision gates (user to confirm before any build)

1. Scope: three agents (AR, Finance, Ask My Groups) or include Order-to-Dispatch the day
   it runs? (This doc assumes the former; nothing in the loop design changes.)
2. First goal type: collections chase (safest — drafting exists, sends are the only new
   action) vs marketing (the 12% lead-growth example — needs campaign analytics bindings
   and spend actions; more data contract work). Recommend collections first.
3. WhatsApp action authorization model: allow-listed recipient + per-burst confirm vs
   one-time standing approval for a goal.
4. Cadence: batch weekly vs continuous watch. (Batch for v1.)
5. Memory: adopt memory-layer-design (decision gates §7 there) at Phase 2 with delta
   gating — confirm now or defer.
6. Where the loop runs: in the copilot graph (new goal-service node + interrupt
   checkpoints) vs a separate worker service (whatsapp-service-style) that calls the
   copilot API. Affects latency budget and quota consumption (402 topup gate is real).
7. Report shape: existing two-tab dashboard + merchant PDF (memory rule: sales/marketing
   get PDF, not md).

## 10. Costs (rough)

- Per cycle: 1 plan call + 3-6 agent invocations (existing per-query cost profile:
  finance ~45-140s/query, ask-groups ~13s, AR ~23s avg; all on metered Zops quota) + 1
  nano reflection call (only on failure) + KPI telemetry reads (free, internal).
- Infra: 1 lessons table, 1 goal/run ledger table, checkpoint store, dashboard section,
  report writer. No new model spend beyond the planner call per cycle.
- The expensive resource is not tokens — it is **campaign spend and irreversible sends**;
  that is what the approval tiers and hard caps protect.

## 11. Sources

- reflexion-vs-copilot-analysis.md (this repo, commit 8d36303); reflexion repo
  github.com/noahshinn/reflexion; paper arxiv.org/abs/2303.11366
- memory-layer-design.md (this repo, PROPOSED) — lessons store, injection, guardrails
- agent-eval-strategy.md (this repo) — pillar contracts, delta gating, G5 closed loop,
  online layer; reflect-node test ac02d56 (negative verdict)
- Anthropic, Building Effective Agents — workflows vs agents taxonomy, agent loop,
  stopping conditions, ACI tool design (anthropic.com/engineering/building-effective-agents)
- Voyager (Wang et al., 2023) — procedural skill library as reusable memory;
  ExpeL (arXiv 2308.10144) — experience accumulation across tasks
- whatsapp-service /send API (~/AgentWork/whatsapp-service); AR agent
  prepare_whatsapp_message / resolve_whatsapp_recipient (agent-design-notes.md)