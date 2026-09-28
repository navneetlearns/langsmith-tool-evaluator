# Agent Eval Strategy — AR, Finance, Order-to-Dispatch, Ask My Groups (2026-09-28)

**Status: Proposed — NOT approved. Executes only after the user confirms the decision gates in §0.**
Prepared from web research (2026-09-28) + the eval harness's existing state. Replaces the
ad-hoc per-agent flow (each agent has its own query set, own run, own readout, no shared
contract) with one operating model applied to all FOUR agents, plus an online layer the
harness has never had. (v2: added Ask My Groups as a first-class agent 2026-09-28.)

## §0 Decision gates (approve before execution)

1. **Scope = exactly four agents:**
   - **Finance** (hirafoods ws, `chatTemplateCode: finance`, 30 CFO queries, v1/v2 done)
   - **AR** (Zainab ws, 56 user queries, v1/v2 done, label remap pending)
   - **Order-to-Dispatch** (hirafoods ws, plan exists, NEVER run)
   - **Ask My Groups** (Zainab ws, `chatTemplateCode: ask_chats` → threads_search →
     chats_agent lane, recon v1 done 12/12 — NEVER graded)
   If the agent list is anything else (e.g. deployed templates incl. `general` /
   collections), say so — the plan changes only in which golden sets get built.
2. **Baseline re-verification:** AR v3, Finance v3, O2D first run AND Ask Groups first
   graded run all consume Zops quota (finance ~45–140s/query, metered provider — 402
   topup_required is a real gate). Confirm quota is topped up or accept pausing mid-run.
3. **Online layer (Phase 3) is optional scope** — no API change (replays LangSmith traces
   the copilot already writes), but it is new build work. Offline parts (Phases 0–2)
   proceed regardless.

## The core strategy (from research, one paragraph)

Split testing into **behavioral** (deterministic assertions: did it call the right tool,
did the answer contain the expected element — cheap, belongs everywhere) and **evaluative**
(LLM-judge quality — expensive, belongs in experiment workflows, needs calibration). Run
both against a **versioned, stratified golden set per agent**; **gate releases on the delta
vs the previous version on the same set** (significance test + churn metric), never on
absolute numbers; calibrate every judge (cross-family, binary criteria, ~80% human
agreement) and let new metrics sit in observation mode before becoming hard gates. Then add
the layer that catches what lab evals structurally cannot: **sampled evaluation of real
traffic** (stratified, oversample failure-rich cells), fold failures back into the golden
sets, and measure the **lab-vs-prod (Goodhart) gap** instead of believing lab scores.

Sources: Red Hat behavioral-vs-agent-eval (redhat.com 2026-07-30), LangChain eval lifecycle
(langchain.com/resources/llm-evals), Octomind evals-design playbook (octomind.run), 2026
agent CI/CD gate guide (baeseokjae.github.io), Agents Honestly online-evals (agentshonestly.com),
Armalo production-sampling (trust.armalo.ai), arXiv 2503.22458 multi-turn survey,
arXiv 2503.16416 agent-eval survey. Annotated list in `agent-eval-learning-resources.md`.

## What research says we ALREADY do right (don't rebuild)

- Versioned runs, no-retry, timing per query (HEART) — matches 2026 best practice.
- Behavioral layer exists: `expected_tool` / `expected_behavior` labels + deterministic
  4-bucket quality classifier — this is exactly the Red Hat golden-query pattern.
- Value ladder (L1–L5) + FinGAIA tiers — ahead of most published guidance for finance agents.
- Judge discipline for finance: cross-family, anchored criteria, evidence-quoted verdicts.
- Preflight probes + quota awareness (402 gate) — cost gate, partially built.
- Zepto quality-gate recommendation is on file but never implemented as a blocking gate.

## The four gaps research exposes (the "better strategy")

**G1 — No shared eval contract / no baseline-relative gate.** Every version is judged ad hoc.
Fix: per-agent pillar contract (numeric gates) + version-pair delta gate with significance.
**G2 — Golden sets are small and unmanaged.** Finance 30, AR 56, O2D 0, Ask Groups 0-graded.
Research floor for agent evals is 50–200+ with stratification + versioning + owner + refresh.
Quota caps us at ~60–80/run/agent — acceptable IF stratified and honestly labeled as to
resolution, and IF targeted subset reruns exist for regressions.
**G3 — No classification churn metric.** Uber gap since Aug; implement per version pair.
**G4 — No online layer.** Lab-only evals miss distribution shift and the eval→prod gap
(reported 16-point lab-vs-prod gap is the norm, not an outlier). We already capture live
copilot traces in LangSmith (seller-copilot-agent) — replay-scoring them is cheap.
**G5 — No closed loop.** Reported failures never promote back into query sets, so the suite
stops improving (MLflow/LangChain pattern: grow the suite from real failures).

## Phase 0 — Eval contract + golden-set governance (no API cost)

- **Task 0.1** — `EVAL_CONTRACT.md` at repo root: per agent, the pillar table
  (Correctness success-rate, Tool-selection strict/lenient, zero-fabrication, clarify-park
  rate, P95 latency, ₹/query). Start values from existing run baselines:
  Finance v2 (runs/v2 summary.json), AR v2 lenient 46/54, Collections v2 reference,
  Ask Groups recon (12/12 ok, avg 14.2s — behavior/evidence grading, no tool events).
- **Task 0.2** — Golden-set manifest per agent: version, size, category splits, label
  counts, last_updated, source (generator script owns it — collections rule applies to ALL
  agents: edit the generator, re-run it, never hand-edit xlsx), baseline version it was
  built against, owner. Add `last_updated` + `owns_queries` to each account's config.yaml
  or a `golden-set.json` next to queries.xlsx.
- **Task 0.3** — Stratification audit of the four sets against 50/30/20 (routine / edge /
  safety-or-refusal). Finance: refusal class = 9/30 (good); AR: 2 CLARIFY of 56 (thin edge
  coverage); Ask Groups: build refusal/coverage-caveat class from its prompt's unsupported
  list + undisclosed-coverage cases.

## Phase 1 — Bring all four agents to a comparable baseline run

- **Task 1.1 — Finance v3** (after dev fixes; rerun-after-fix map from the skill):
  subset rerun first, then full; `eval diff v2 v3`; check the F16 "[unverified]" 2→48
  regression specifically, clarify-park rate, boilerplate repetition.
  Gate: pass-rate non-worse than v2 (McNemar), churn ≤ 30%.
- **Task 1.2 — AR v3** (re-mapped expected_tool labels — strict-vs-ar_* split from the v2
  readout; ASK_BACK rows q46/q51; resolver-inconsistency + invoice-17346 gap as owner
  flags). Gate: strict score rises vs v2's 0/54; lenient holds ≥ 46/54.
- **Task 1.3 — Order-to-Dispatch first run** (unblocks the shelved plan): query set built
  from the deployed prompt's TOOL ROUTING section (never another account's categories),
  expected_tool + expected_behavior labels, production from the prompt's status vocabulary
  (Notified ≠ order status; Accepted vs Approved), NO_TOOL classes as refusals. Probe gate
  (`scripts/preflight_agent_probe.py`) → full run → EVAL_READOUT + two-tab dashboard →
  contract baseline numbers.
- **Task 1.4 — Ask My Groups first graded run** (unblocks recon → graded): the agent is a
  WhatsApp-group Q&A (ask_chats lane, threads_search chat engine — NO tool events on the
  wire; grade behavior/evidence like finance, never invent expected_tool beyond intent).
  Query set built from the RECON inventory (`accounts/ask-groups/RECON_DATA_INVENTORY.md`):
  request-by-kind (Stock/Dispatch/Order/Price/Invoice/Payment/Ledger), pending/chasing
  ("what is pending", "who chased us"), response-time, group inventory, evidence anchors
  (invoice B NO 15293, 02-Sep cheque-not-deposited, Al Anwar outstanding), plus
  coverage-caveat honesty checks (61%-untagged disclosure must survive in answers).
  REFUSE/CLARIFY classes from the deployed ask_chats prompt (enumerate
  deployed-chat-templates first — skill rule). expected_behavior labels ANSWER/CLARIFY/
  REFUSE per row; run via run_agent_evals.py; probe gate before the full run.
  Gate: quality buckets + honesty-caveat pass rate vs recon baseline.
- **Task 1.5 — Uniform readout shape** for all four: same EVAL_READOUT_v<N> structure
  (completion, tool-accuracy, quality buckets, refusals, action list) + two-tab dashboard.

## Phase 2 — Cross-agent rigor tooling (the measurement upgrades)

- **Task 2.1 — churn metric** (Uber gap #2): queries_changed_quality_class(vN, vN+1)/total
  per agent; render in dashboard + EVAL_READOUT header. Threshold >30% = low trust signal.
- **Task 2.2 — significance in `eval_cli.py gate`:** augment the point-estimate pass rate
  with a paired test vs previous version (McNemar on verdict changes; warn when n is too
  small to resolve 5pt effects — currently true at 30–56 queries: report CI not just delta).
  Gate semantics: block if candidate is statistically worse on any pillar.
- **Task 2.3 — multi-turn suite per agent** (arXiv 2503.22458 taxonomy): finance
  clarify-resume contract (2-turn, resume payload), AR multi-turn claim→status verification
  (Zainab groups), O2D multi-step status progression, Ask Groups follow-up entity
  resolution (topic search → resolved group/channel, freshness re-fetch — the KCCL
  two-turn probe pattern). Reuse the two-turn runner + scenario files.
- **Task 2.4 — robustness & stochasticity:** clarify-boundary rows (finance classify gate
  is stochastic ~30% park): run pass@3, report park RATE not per-query verdict;
  typo/alias/paraphrase perturbation subset for AR + Ask Groups (WhatsApp-grounded =
  messy inputs ARE the real distribution; Zainab alias list in the recon inventory).

## Phase 3 — Online layer (optional, needs go in §0.3)

- **Task 3.1 — replay-scoring of real traces:** pull recent live copilot runs from
  LangSmith (seller-copilot-agent project), group by session, judge each turn with a
  calibrated judge (groundedness + answered-the-question only — two rubrics, binary),
  report lab-vs-prod score delta per agent. No API change; this is the Goodhart gap
  (Armalo: 87 eval vs 71 prod is the typical first reading).
- **Task 3.2 — stratified sampling plan** (Agents Honestly): baseline % of everything +
  100% of escalations/retries/errors/long-tail/cost outliers; only score what you sample —
  shadow without scoring is duplicate spend.
- **Task 3.3 — closed loop:** failing production traces promote into the per-agent golden
  sets (label once, regenerate xlsx via generator), quarterly coverage audit.
- **Task 3.4 — auto-push summaries** (Uber gap #1): post run result (EVAL_READOUT tldr +
  gate verdict) to Telegram via cron deliver='telegram' after each run. Cheap, high
  visibility.

## Sequencing & effort

Phase 0 + 1.3/1.4 (O2D + Ask Groups first runs) are the immediate value: every agent has a
baseline + contract. Phase 2 is a few days of tooling. Phase 3 is a small replay script +
cron, gated by §0.3. Quota is the hard external dependency for all live runs (Phase 1).
One worker: single-profile repo operation; run subagents per task only for parallel
O2D query-gen and churn-metric build.

## Verification checklist (after implementation)

1. `python3 scripts/eval_cli.py diff finance v2 v3` runs and shows per-query verdict changes
   + churn figure.
2. `eval_cli.py gate --min-match <baseline>` exits nonzero when candidate is statistically
   worse (mock a 2-query flip to test).
3. Order-to-Dispatch: `scripts/preflight_agent_probe.py` passes, full run completes,
   EVAL_READOUT_v1.md + two-tab dashboard render, page verified with Playwright
   (light theme, zero console errors, no `../../` relative links).
4. Ask My Groups: probe gate passes (quota + lane ask_chats init), full run completes,
   EVAL_READOUT_v1.md with quality buckets + honesty-caveat pass rate, unreported in
   recon: ~60-80 queries.
5. EVAL_CONTRACT.md exists with 4 pillar tables, all numbers recomputed from run JSONLs
   (never from memory/older readouts).
6. All four accounts' golden sets carry a manifest (version/size/owner/last_updated),
   regenerated from generator scripts, `git status` clean of hand-edited xlsx drift.
7. Online replay (Phase 3): one script invocation scores ≥100 real traces, outputs
   lab-vs-prod delta per agent; failing traces land in a promote/ queue visible in the
   readout.