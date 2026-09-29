# Reflexion (Noah Shinn) vs ZoChief Copilot Agents — Architecture Comparison

Analysis 2026-09-29. Companion to agent-eval-strategy.md (this repo) and
~/AgentWork/research/instinct-ai-agent-architecture.md (research repo). Trigger: user
explored github.com/noahshinn/reflexion (the NeurIPS 2023 Reflexion codebase, 3.3K★ MIT,
canonical repo moved from noahshinn024/reflexion — that URL now 404s) after Instinct's
$1B Series C (Sep 28, 2026). Grounded in: reflexion repo code read (hotpotqa_runs/agents.py,
prompts.py, llm.py, alfworld_runs/main.py) + this repo's agent-design-notes.md
(seller-copilot) + eval docs.

## One-line each
- Reflexion: single flat loop — try task, fail, write a verbal lesson into episodic memory,
  retry — proven on benchmarks WITH ground truth and REPEATED attempts at the same task.
- ZoChief copilot: one LangGraph graph hosting several specialized agents (AR, Finance,
  Ask My Groups) that get the FIRST answer right on unseen live questions, because a
  merchant asks each question once.

## Architecture
Reflexion: Actor (action LLM) → Evaluator (environment ground truth: EM match / unit tests /
task success) → Self-Reflection LLM (writes a paragraph diagnosing the failure + a plan,
"COT_REFLECT_INSTRUCTION" in prompts.py) → reflections list injected into the next trial's
prompt. The whole loop lives in ~40 lines: `if step_n > 0 and not is_correct() and strategy
!= NONE: reflect()` then reset and re-run (hotpotqa_runs/agents.py CoTAgent.run). Ablations
live as an enum: NONE / LAST_ATTEMPT / REFLEXION / LAST_ATTEMPT_AND_REFLEXION. Token-budget
management = truncate_scratchpad (drops largest Wikipedia observations to stay in window).
No auth, no tenants, no product infra; OpenAI-only (gpt-3.5-turbo default), langchain-era.

Copilot: supervisor_router = LLM intent classifier (gpt-5.4-nano, strict JSON, full thread +
prior classification) → deterministic workflow_router (chatTemplateCode → agent node).
- finance_agent: classify gate (gpt-5.4-mini) → clarify-interrupt (parks the turn) OR plan
  over 34-metric gold-SQL catalogue → guarded pipeline (receipts, gold crosscheck P4,
  reconcile refuse-to-headline, dedup + 8-SQL cap, grounding, narrative/table split; money
  is raw paise /100 at render).
- ar_agent: load_context → ReAct loop (gpt-5.6-luna) over semantic catalog + tool surface
  (query_ar / query_ar_financials / get_ar_evidence / get_ar_schema / resolve_ar_identity /
  get_paid_collections / get_ar_conversation_snapshot / resolve_whatsapp_recipient /
  prepare_whatsapp_message) → format node. Identity discipline: bound-identity mode, resolve
  via resolve_ar_identity only, never guess, shortlist always needs explicit selection.
Multi-tenant state (workspaces surana/unifoods/hirafoods/Zainab/Koya), thread-scoped
sessions, SSE, auto-OTP auth, 24-step budget.

## Where learning lives — the defining difference
Reflexion learns ACROSS trials on the SAME question via verbal reflection memory. The
copilot's ReAct loop is in-turn iteration only (4-5 steps until answerable): there is NO
cross-turn verbal-reflection memory — a failed turn produces no lesson the agent reads on
the next turn of the thread. Correctness is frozen INTO the system instead: gold SQL
catalogue, guardrail chain, catalog semantics, refusal boundaries, identity discipline.
First-try correctness via engineering, not retry learning.

## Goal / purpose / use case
- Reflexion: prove verbal RL — performance gain over repeated attempts without weight
  updates. Benchmarks: ALFWorld (+22% in 12 steps), HotPotQA (+20%), HumanEval 91% pass@1,
  WebShop, LeetCodeHardGym. Assumes evaluator for free + task re-runs allowed.
- Copilot: per-question correctness contract on one-shot, high-stakes financial questions
  (7-300s latency, partial ground truth). The evaluator had to be BUILT — this repo's
  harness (ANSWER/CLARIFY/REFUSE judgments, hallucination + tool-adherence checks, versioned
  runs, GitHub Pages dashboards) — Reflexion assumed that layer for free.

## Overlap (where the founder's playbook already runs in this harness)
- "Task-completion rate on a fixed suite" = run-level dashboards.
- "Frozen regression sets from real failures" = versioned runs replayed + F1-F9 findings.
- EM ground-truth discipline = hard checks (ledger reconciles, ₹-paise /100, receipts).
- His τ-bench (tool-agent-user benchmark, realistic customer service) is the closest domain
  match — AR tool-adherence 46/54 lives in exactly that shape.

## Gap (Reflexion-style upgrade available)
No runtime self-reflection on failures. Cheap high-value version: after turns judged wrong
(parked clarify that was answerable, wrong refusal, low-judged answer), write a one-paragraph
lesson stored per-thread/workspace and injected like the semantic catalog on that thread's
next turn. The harness already produces the judgments; they just don't feed back as memory.
This is the mechanism Instinct's founder turned into consumer-scale "the model learns from
its own failures."

## Sources
- reflexion repo: github.com/noahshinn/reflexion (cloned /tmp/reflexion on 2026-09-29)
- paper: arxiv.org/abs/2303.11366
- this repo: agent-design-notes.md (seller-copilot), EVAL_READOUT docs, agent-eval-strategy.md
- research repo: instinct-ai-agent-architecture.md (commit 57f0ff8, link fix 6c4ba3e)