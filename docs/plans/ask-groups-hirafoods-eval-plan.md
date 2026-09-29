# Ask My Groups Agent — Eval Plan on HiraFoods Account

**Status: Proposed — NOT executed. Individual gates (Step 0 + the questions in §5) decide each phase.**
**Date:** 2026-09-28 · **By:** eval harness worker
**Relation to strategy:** executes the Ask My Groups pillar (agent-eval-strategy.md Task 1.4),
with one scope deviation: **workspace = hirafoods (c331ac11…) instead of Zainab (d53279c2…).**

---

## 0. What we're running and what's known

**Agent:** Ask My Groups = message-traffic copilot (Q&A over WhatsApp-group traffic, tagged
MessageFacts table, prompt_version v5). Lane: `chatTemplateCode = ask_chats` →
supervisor `threads_search` → `chats_agent` (parse → engine_answer → layout).

**Grading rules that apply (from skill refs/ask-groups-agent.md):**
- NO tool events on the wire (backend chat engine) — grade behavior/evidence like finance;
  `expected_tool` = intent only, never a hard assertion.
- Request-state machine is the agent's own `method` disclosure (one request = sender asks
  within 5 min incl. photos; Answered = quoted reply else next msg within 24h; "checking"
  alone = acknowledged-not-answered).
- Honesty caveats in headline (untagged %, low-volume days) are a FEATURE — grade their
  presence; counts move across re-processes.
- **CAPABILITY GAP class** (2026-09-28 trace): repeat-issue/reason queries execute as plain
  request-lists — grade NEAREST_SHAPE (no_data/marginal, NOT fail). Add one as an
  unsupported-class row.
- Evidence contract: cited_sids / evidence_sids + per-row sid — grade on it.

**Target account (hirafoods, existing demo creds — user explicitly asked for this account):**
- phone 4040505050 · workspace c331ac11-c3e8-4d42-a8d6-b8b04127354c
  · wa_config_id c331ac11-c3e8-4d42-a8d6-b8b04127354c_914040505050 · base api.zotok.ai
- Existing `accounts/hirafoods/` config uses `chatTemplateCode: ""` (general lane) — do NOT
  touch it; this run gets its OWN account dir (below).
- **UNVERIFIED on hirafoods:** (a) whether `ask_chats` is a deployed template on this
  workspace (observed workspaces so far: Zainab d53279c2, ZoTok-internal 05f67562), and
  (b) whether hirafoods has any WhatsApp-group data — as of 2026-09-23 it was
  "unusable — no WhatsApp data" (AR-prep finding, user-confirmed). Both are Step-0 gates.

---

## 1. Step 0 — Viability gate (run FIRST; everything below depends on it)

Nothing else runs if this fails. Use the pipeline's own auth (load_account_config +
CopilotAuth/CopilotClient), never a reimplementation.

1. **Enumerate deployed templates on c331ac11:**
   `GET /hub/copilot/api/agent-platform/deployed-chat-templates?sellerWorkspaceId=c331ac11-c3e8-4d42-a8d6-b8b04127354c`
   (Bearer copilot JWT). Capture `code`, `id`, `workspace_id` for EVERY template; dump each
   `system_prompt` to /tmp — the prompt is the eval ground truth (tool allow-list, status
   vocabulary, UNSUPPORTED section = REFUSE/CLARIFY query classes) before writing a query.
   - `ask_chats` present → proceed.
   - `ask_chats` ABSENT → **STOP**. Do NOT fall back to `""` (routes to the general lane —
     that's the search_threads Seller Copilot, a different agent). Report to user with the
     enumeration result; blocked for a decision (deploy ask_chats on a demo ws, or run on
     Zainab instead).
2. **Data-presence probes (RECON-class, not graded, ~5 queries, ~14s each):** group count,
   7d message volume, active groups, pending/chasing, one by-kind count. These are the same
   12 recon shapes already run on Zainab (accounts/ask-groups/queries.xlsx).
   - **GATE:** ≥1 probe returns real rows (NOT "no data"/intro-fallback) AND the headline
     carries the coverage/untagged caveat. Empty corpus (the 09-23 expectation) → **STOP,
     report, no run** (burning 60+ queries into an empty MessageFacts table is a no-op eval).
3. **Quota probe:** one REFUSE-class ask_chats query (minimal Zops burn); fail hard on
   `402 topup_required` / thread-init failure / empty-response-with-no-error. Pattern:
   `scripts/preflight_agent_probe.py` adapted for the ask_chats lane.
4. Config sanity via `scripts/verify_account_config.py` against the NEW account dir (§2.1)
   — asserts with the pipeline's loader (catches the chatTemplateCode ""→{} regression).

## 2. Query-set build (only after Step 0 passes)

1. **New account dir** `accounts/hirafoods-askgroups/` (never touch `accounts/hirafoods/`):
   config.yaml = phone 4040505050, workspace c331ac11…, `chatTemplateCode: ask_chats`
   (the trace-verified real lane — a code present in the deployed list is the most stable
   init value), sse_timeout 300 / read 120. `queries.xlsx` + `runs/` per account layout.
2. **Query set (per strategy Task 1.4, grounded in RECON_DATA_INVENTORY.md):**
   - Reuse the entity-free recon shapes as-is: group count, 7d throughput, pending,
     chasing, unanswered-window, response-time claims, most-active groups, by-kind lists
     (Stock/Dispatch/Order/Price/Invoice/Payment/Ledger), topic day-band, invoice sharing,
     slow customers, sender list.
   - DROP the Zainab-anchored rows (invoice B NO 15293, 02-Sep cheque-not-deposited,
     Al Anwar outstanding, fabric aliases) — replace with real hirafoods entities harvested
     from the Step-0.2 probe output (customer names AS TYPED in groups) or rephrase
     entity-free. **REAL-ENTITY RULE: no ABC/XYZ placeholders, ever.**
   - REFUSE/CLARIFY rows from the ask_chats prompt's UNSUPPORTED section (dumped in Step 0.1).
   - ONE CAPABILITY-GAP row (repeat-issue shape) labeled NEAREST_SHAPE.
   - Cols: query / expected response / remarks / expected_tool (intent only) /
     `expected_behavior` (ANSWER|CLARIFY|REFUSE) — Format-A parser reads A–D, col E is
     additive and safe. Verify count with `run_agent_evals.parse_xlsx` (header row is NOT a
     query), assert placeholder scan = 0.
   - **Size:** full ~60–80 rows per Task 1.4 if quota allows; otherwise a 30-row starter —
     user decision §5.3.
3. **Also run `ask_chats` on Zainab?** Only if the user wants the strategy's original
   Task 1.4 baseline as well (Zainab recon already exists). Default: hirafoods only.

## 3. Run

1. Preflight single-query probe through the ask_chats lane (quota + init + parser sanity).
2. `python3 scripts/run_agent_evals.py --account hirafoods-askgroups --run 1`
   (incremental JSONL; `--resume N`; suspected clarify parks flagged `possible_clarify`).
3. Budget: ~14 s/query avg → 60–80 rows ≈ 15–25 min wall + SSE overhead. Nothing runs
   concurrently against the same workspace. If mid-run `402` → stop, report, `--resume`
   after topup (HEART: version all runs, never overwrite).
4. Expect NO tool events (chat engine) — `tools=[]` is faithful capture here, not a parser
   regression (only suspect the parser if Zainab reruns flip too).

## 4. Analyze + deliver

1. **EVAL_READOUT_v1.md** (build BEFORE the dashboard — it's the decision artifact for
   owners): completion/fail counts, quality buckets (answered / no_data / marginal /
   clarify-park / error + raw-vs-judged), **honesty-caveat pass rate** (coverage-untagged %
   surviving into answers), CAPABILITY-GAP findings, safe/hedged answer notes, action list.
2. **Dashboard** `python3 build_dashboard.py --account hirafoods-askgroups` — light theme
   (page design rules: bg #f8fafc, ink #0f172a, zero legacy dark hexes asserted),
   clarify-aware, no relative `../../` data links (absolute raw.githubusercontent.com),
   Playwright QA (stat counts == summary, zero console errors, light-hex sweep).
3. **Push** to navneetlearns/langsmith-tool-evaluator ONLY with the user's explicit go
   (GitHub rule). Before push: single-copy discipline (`git pull --rebase origin main`
   first — two-copy divergence known issue), commit accounts/hirafoods-askgroups/** +
   docs/hirafoods-askgroups/index.html, then curl -sI the Pages URL (200 + real counts).
4. Update `accounts/ask-groups/` recon doc? No — keep per-account; instead add
   `hirafoods-askgroups` row to the skill's account table + note ask_chats deployment state
   on c331ac11 (observed or absent) in the skill ref. Update agent-eval-strategy.md §0.1
   workspace line only if the user confirms the scope deviation (§5.5).

## 5. Decisions needed before execution

1. **Confirm target = hirafoods demo workspace c331ac11 / phone 4040505050** (user
   requested; read-only Q&A only — the harness never sends WhatsApp messages, and ask_chats
   is Q&A by construction). OTP for this phone fires during auth — OK?
2. **Data expectation:** do you believe hirafoods NOW has WhatsApp-group traffic? If Step 0
   finds the 09-23 state (no group data) still true, the run stops at the gate — acceptable,
   or should the plan fall back to the Zainab eval workspace?
3. **Run size:** full 60–80 graded set (Task 1.4) or 30-row starter?
4. **Push:** OK to push run files + dashboard to navneetlearns/langsmith-tool-evaluator
   (Pages public) once the run exists — same as prior agent runs?
5. **Scope deviation:** update agent-eval-strategy.md so Task 1.4 targets hirafoods (+ any
   new ask_chats deployment finding), or keep this plan standalone?