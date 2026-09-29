# Agent Evaluation — Learning Resources (curated 2026-09-28)

What to read in what order, each with the one idea that matters for OUR harness
(eval-dashboard / ZoTok agents). All links verified live at curation time. Companion to
`agent-eval-strategy.md` — read that first for the operating model these feed.

## 1. Orientation — start here (2-3 hrs)

1. **LangChain — "LLM Evals: The Feedback Loop Behind Reliable AI Agents"**
   https://www.langchain.com/resources/llm-evals
   Lifecycle map: evals do their clearest work at two points — before ship (catch
   regressions) and after ship (catch drift). Test uses curated data + reference
   answers; monitor uses production traces + promoted failures. **Take for us:** the
   "name failures before scoring" rule — write the failure mode list first (tool drift,
   stale citation, policy skip), then pick the evaluator that can observe each. Our
   expected_tool column is this rule made concrete.

2. **LangChain — "Evaluating LLMs and Agents: Benchmarks, Evals & Guardrails"**
   https://www.langchain.com/resources/how-to-evaluate-llms
   Benchmarks ≠ agent evals; match evaluation METHOD to failure mode (table inside).
   LLM-as-judge reached 80%+ human agreement on MT-Bench — but only after calibration.
   **Take for us:** judge discipline (narrow binary questions, anchored rubrics) is a
   classifier problem, not a vibe.

3. **Red Hat — "Behavioral testing for AI agents"** (2026-07-30)
   https://developers.redhat.com/articles/2026/07/30/behavioral-testing-for-ai-agents
   The exact mental model our harness already implements: behavioral testing = golden
   queries with expected_elements substring match + expected_tools set comparison,
   deterministic, belongs in CI; agent evaluation = LLM judge on quality, belongs in
   experiment workflows. **Take for us:** we are red-hat-compliant on the behavioral
   layer; the missing half is treating tool-selection as a regression gate (pass@k,
   per-agent threshold ~90% tool accuracy).

## 2. Designing eval suites — core (day 2-3)

4. **Google Cloud — "A methodical approach to agent evaluation"**
   https://cloud.google.com/blog/topics/developers-practitioners/a-methodical-approach-to-agent-evaluation
   Purpose-driven framework: establish ground truth from real failure modes FIRST, then
   scale with LLM judge aligned to human labels; code-based evals for anything
   checkable by logic (JSON validity, length, tool params). **Take for us:** the pillar
   ordering — human/domain ground truth before any automated scorer.

5. **Octomind — "AI Evals Design" (2026 playbook)**
   https://octomind.run/tap/skills/ai-evals-design
   The five parts of any real eval: behavior spec (falsifiable — "be helpful" is not a
   spec) · golden dataset (stratified, versioned, sized to the effect you care about —
   ~200 paired examples to detect a 5pt change at 80% power) · one metric per behavior
   (composite scores hide regressions) · judge from a DIFFERENT model family than the
   generator · statistical test (McNemar/paired/bootstrap), not point estimates.
   Includes the framework-selection table (Promptfoo/DeepEval/LangSmith/Braintrust/
   Phoenix/Galileo/Patronus). **Take for us:** power analysis explains why 30-query sets
   can't resolve small changes — report CIs, target ~60-80 stratified.

6. **arXiv 2503.16416 — "Survey on Evaluation of LLM-based Agents"**
   https://arxiv.org/pdf/2503.16416
   The field in five perspectives: core LLM capabilities for agentic work (planning,
   tool use), application benchmarks, generalist agents, benchmark dimensions, tools.
   **Take for us:** the vocabulary — decision-level vs execution-level failure taxonomy
   (reasoning deficit vs tool invocation error vs timeout) is what our EVAL_READOUT
   action list should classify.

7. **arXiv 2503.22458 — survey of multi-turn conversational agent evaluation**
   https://arxiv.org/pdf/2503.22458
   Two taxonomies: WHAT to evaluate (task completion, response quality, user experience,
   memory/context retention, planning + tool integration) and HOW (annotation,
   automated, hybrid, self-judging). Tool-use graded in 3 layers: execute commands →
   chain across turns → reliability ("action hallucination" = invoking non-existent
   tools or misreading outputs). **Take for us:** the missing dimension list for our
   clarify-resume and multi-turn suites.

## 3. Production / online evals — the layer we're missing (day 4-5)

8. **Agents Honestly (book, online-evals chapter) — "Online Evals and Guardrails"**
   https://agentshonestly.com/book/evals/online-evals
   Four rollout stages (shadow → canary 1-5% → ramp → full), each answering a different
   question. Scoring production = stratified sampling: baseline % of everything +
   OVERsample escalations, retries, repeated errors, cost outliers, stated uncertainty,
   recently-changed routes. "Wire the evaluator into the pipeline that ingests the
   shadow trace, or do not run shadow" — unscored mirroring is waste. Guardrails ≠
   evals (inline/blocking vs after-the-fact/measuring; 200-1000ms judge latency.
   **Take for us:** the exact sampling rule for Phase 3.

9. **Armalo — "How Armalo Prevents Eval Gaming with Production Sampling"**
   https://trust.armalo.ai/blog/community-goodharts-law
   The Goodhart gap measured: agent scores 87 on eval queries, 71 on novel production
   queries (200-sample, consistent) — the eval set was being optimized against. Gap
   severity bands: low 5-10% / moderate 10-20% / high >20%. **Take for us:** the lab-vs-
   prod delta is a first-class metric, and production samples are PII-cleared before
   storage.

10. **Armalo — "Live Production Eval: Sampling Real Traffic Without Slowing It Down"**
    https://trust.armalo.ai/blog/live-production-eval-sampling-real-traffic-without-slowing-it-down
    Four shapes (full inline / full shadow / sampled shadow / sampled inline) and when
    each is right; sampled shadow is the default for non-safety-critical agents. The
    "lab said 90, production said 71" story with a remediation loop. Includes a 9-section
    Live Eval Sampling Plan template. **Take for us:** the template for our own sampling
    plan, and the three silent bias sources to audit (sampling mechanism, evidence
    capture, eval pipeline robustness).

11. **"Agent CI/CD Eval Pipeline Integration Guide 2026"**
    https://baeseokjae.github.io/posts/agent-ci-cd-eval-pipeline-integration-guide-2026
    The five gates: golden offline eval per PR · regression blocks (delta vs baseline,
    not absolute) · cost gate (block >15% token/API regression) · shadow eval before
    deploy · canary + auto-rollback. 3-tier architecture (deterministic per commit /
    LLM-judge nightly / production monitoring with error budgets). Reference thresholds:
    task completion >85% CI, hallucination <5%, policy violations 0, p95 latency <4s.
    **Take for us:** concrete numbers to adapt for EVAL_CONTRACT.md; the cost gate maps
    to our 402 quota reality.

12. **MLflow — "Regression Testing and CI/CD" (GenAI platform docs)**
    https://mlflow.org/docs/latest/genai/eval-monitor/regression-testing
    Agent behavior tests as ordinary pytest functions (`@mlflow.test` + scorers + assert).
    "The best regression suites are not written up front, they are grown from real
    failures: each time the agent does something wrong, capture it as a test."
    **Take for us:** the closed-loop principle for G5 — our failing traces should land in
    the query sets.

## 4. Depth — books & papers (read as needed)

13. **"Designing Evals for Agentic Systems"** (Leanpub book)
    https://leanpub.com/designing-evals-agentic-system
    Full treatment: general vs task-specific judges, critique shadowing, data flywheel,
    production-sampling selector cards, eval maturity assessment. Best single artifact
    when you want the complete mental model, not blog posts.

14. **LangSmith evaluation docs — offline + online flows**
    https://docs.langchain.com/langsmith/evaluation
    The dataset → evaluator → experiment → compare model, plus online evaluators with
    sampling rates on live traces. **Take for us:** the workflow we could adopt directly
    for the LangSmith leg of Phase 3 (they already have this repo's langsmith-tool-
    evaluator integration).

15. **DeepEval — multi-turn end-to-end evaluation docs**
    https://deepeval.com/docs/evaluation-end-to-end-multi-turn
    Synthetic-user multi-turn eval: goldens = {scenario, expected_outcome,
    user_description}, an LLM user plays against the agent, metrics TurnRelevancy /
    KnowledgeRetention / RoleAdherence / ConversationCompleteness. Already mapped onto
    our KCCL work in the skill (references/multiturn-simulation-design.md).

16. **Uber Compass Stage talk — agent eval platform (Aug 2026)** — LOCAL COPY
    ~/AgentWork/lenny-transcripts/Compass Stage - Uber Agent Eval Platform - Aug 2 2026 - LEARNINGS.md
    The maturity benchmark our skill already reviewed: tracing from day 1, versioned
    reruns, no-masking (we do all); auto-push to builders, classification churn metric,
    production eval, failure→fix loop, dataset freshness (we don't — Phase 2/3 work).

## 5. Hands-on tooling (for the tools comparison table, see #5)

- **Promptfoo** (OSS CLI) — golden YAML evals + 157 plugin red-teaming, OWASP-LLM
  presets; closest OSS match to our expected_tool behavioral layer.
- **DeepEval** (OSS Python) — 50+ metrics, synthetic dataset + multi-turn simulator.
- **LangSmith** — the platform we already partly run on (trace eval + online eval).
- **Galileo / Braintrust / Patronus** — paid; failure-mode mining, dataset→CI gating,
  hallucination detectors. Not needed until the online layer grows.

## Reading order if you only have 4 hours

1 → 2 → 3 (orientation) → 5 (eval design rules) → 8 (online sampling). Then 11 for the
numeric gates, 13 when you want the book-length version.