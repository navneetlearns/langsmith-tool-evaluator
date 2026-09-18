# AR + Finance Agent Evals — Plan (2026-09-18)

**Status:** Proposed — NOT approved. Executes only after the user confirms the decision gates in §0.
Deferred: the order_to_dispatch plan (order-to-dispatch-agent-eval-plan.md) stays shelved until this
is done — user scoped this session to AR + Finance on the **hirafoods account**
(phone 4040505050, workspace c331ac11-c3e8-4d42-a8d6-b8b04127354c).

## Goal

First full harness evals of the two deployed "agent" templates — the AR collections agent
(`collection_and_account_receivables`) and the Finance agent (`finance`) — on the hirafoods
workspace, counting their **clarifying-question behavior** as a first-class dimension, per agent:
completion, 4-bucket quality, tool-accuracy vs expected_tool, clarify-correctness, refusal-correctness,
latency → EVAL_READOUT + dashboard, like collections v1/v2.

## Knowledge gathered (trace-grounded, 2026-09-17/18)

Source of truth: `~/AgentWork/seller-copilot/agent-design-notes.md` + the raw traces
(`Finance Agent/trace-01a0ae11-…json` clarify turn, `ar-agent/trace-01a0aeaa-…json` 4-turn thread,
`run-01a0ae51-…json` AR system-prompt/catalog export). One langgraph graph (`seller_copilot`);
chatTemplateCode picks the workflow (deterministic router, no LLM).

**Finance agent** (`chatTemplateCode: "finance"`, intent financial_search, metadata-verified):
- classify gate runs FIRST on every turn (gpt-5.4-mini): `needs_clarify` > `out_of_scope` > else run.
- CLARIFY: vague terms that map to >1 metric ("looks wrong", "healthy", "best customer", "risky")
  → GraphInterrupt `finance_clarification`: clarify_q + 2-4 options. **Turn parks — no tools, no
  answer; client resumes the SAME thread with the chosen option.** Real trace example: "Forget the
  standard reports. Tell me what looks unusual in the financial data." → "What do you mean by 'looks
  wrong' — overdue receivables/payment issues, invoice or ledger disputes, unusual sales or stock
  patterns, or customer complaints/messages?" (4 options). On clarify, the classifier dumps ALL 34
  metric keys — treat metrics as meaningful only when needs_clarify=false.
- OUT_OF_SCOPE: refusal naming the data boundary, never a guess. GENUINELY ABSENT: COGS/margin/P&L,
  cash & bank, reliable net supplier payables, inventory at cost.
- ANSWER path: 34-metric gold-SQL catalogue (Finance Agent/standard metrics.txt; money raw paise
  /100 at render; `customer_summary` PROHIBITED for receivables/dso/top_outstanding/customers_with_dues;
  aging = upper bound; who-to-chase = PAB + days-since-last-payment). Answer = narrative + verified
  markdown table(s) + optional warning banners + confidence. Also `chat` (OpenSearch thread search)
  and `mixed` (chat WHO + ledger numbers) branches.
- Seed queries: Finance Agent/finance-agent-sql-pairs.json (9 real user queries).

**AR agent** (`chatTemplateCode: "collection_and_account_receivables"`, intent collections_search):
- load_context (system prompt + semantic catalog + snapshot context) → agent/tools ReAct loop
  (gpt-5.6-luna) → format. NEW tool family (deployed 2026-09-17; whether the old Sep-9 tools
  get_receivables/get_collections still ship = KNOWN UNKNOWN #4, resolved by this run's tool
  inventory): `query_ar` (datasets position | worklist | objects | activity), `query_ar_financials`
  (invoices | customer_balances), `get_ar_evidence` (exact object wording), `get_ar_schema`,
  `resolve_ar_identity` (channel-index shortlist), `get_paid_collections` (workspace paid totals by
  payment date, status P), `get_ar_conversation_snapshot` (authorized 15-min window), whatsapp
  resolve/prepare (drafts never send).
- IDENTITY CLARIFY: resolve_ar_identity shortlist ALWAYS requires explicit user selection (even one
  row); never guess identities → ambiguous named-customer queries park for selection (second turn).
- Presentation contract: ONE short plain sentence (app renders verified result details); never tool
  names/dataset names/SQL/run IDs in the response; max 5 rows; empty = what was searched + next step;
  stale snapshot → "the latest list is from <date>" (never the word "stale"); promises-without-dates
  → acknowledgement; kept/entered ≠ bank-verified; no forecasts (DSO, credit limits, bank matching).
- Tool routing (for expected_tool labels): status/rank/signals → query_ar; invoices/balances →
  query_ar_financials; exact wording → get_ar_evidence; named (unresolved) customer →
  resolve_ar_identity; paid totals → get_paid_collections; unknown/ambiguous name → resolve_ar_identity
  → CLARIFY turn.

**Cross-cutting:** AR prompt/answer format changed IN PLACE 2026-09-17 — collections v1/v2 numbers
(Sep 5-9, get_receivables surface) are STALE vs the new surface; churn vs them is expected, not a
regression. Latency: ledger/data-heavy 40-300s in evals; simple lookups 7-15s; SSE pauses between
tool events. Interrupts show in LangSmith as error=True with a stack trace — normal control flow.

**AGENT DIFFERENTIATION (user-confirmed 2026-09-18 — the two agents are NOT the same thing):**

| | AR agent (collections) | Finance agent |
|---|---|---|
| Data sources | **ERP + WhatsApp groups** (the groups are an ADDED source — user confirms latest payment/receivables updates from conversations: claims, commitments, acknowledgements, disputes) | **ERP only** (ledger, invoices, stock, GST, orders) |
| Core user | **Anyone in upper management** (owner/GM/ops head — not necessarily accounting-literate) — plain business language, "what's the latest on X", "who said what" | **CFO and accountants** — metric-accurate report language (DSO, ageing buckets, reconciled ledger, GST by rate) |
| Shared theme | Both answer receivables/outstanding — but AR = position snapshot + WhatsApp-confirmable facts; Finance = reconciled-PAB ledger numbers | same, other side |
| Refusal style | hedges on confirmability ("evidence doesn't confirm"), never claims settlement/bank-verification | names the data boundary (COGS/cash/supplier payables absent), never guesses |

Eval consequence: a query like "what's the latest on Om Enterprises' payment?" belongs to the AR
account (WhatsApp-groundable), while "what is my DSO?" belongs to finance (ERP metric). The same
customer names appear in both sets, but framing, expected tools, and expected answers differ.

**REAL-ENTITY RULE (user-confirmed 2026-09-18):** every named entity in the query sets MUST be a
real HiraFoods entity — no ABC/XYZ/test placeholders. Known real material: the 10 customer accounts
(Om Enterprises Traders 421 · Sai Agencies & Co 1051 · Ganesh Wholesalers Pvt Ltd 955 · Krishna
Traders LLP 125 · Durga Traders Traders 811 · Sri Retail & Co 196 · Lakshmi Distributors LLP 20 ·
Jai Wholesalers & Co 918 · Radha Agencies LLP 552 · Shree Retail Pvt Ltd 581 — plus
"Radha Agencies Pvt Ltd 787" already proven resolvable in collections v2) and the 9 real products
(Golden Biscuits Lite 500ml ₹460.58 · Fresh Shampoo Fresh 100ml ₹95.98 · Classic Toothpaste Strong
1Kg ₹296.31 · Sunrise Juice Max 200ml ₹247.29 · Diamond Pasta Regular 500g ₹32.53 · Diamond Namkeen
Classic 200g ₹47.08 · Ultra Biscuits Regular 100g ₹121.74 · Diamond Juice Strong 1L ₹156.19 · Power
Soap Strong 1Kg ₹24.49). Real invoice numbers + GST rates must be harvested live (Phase 1 discovery)
before any invoice-numbered query is written.

## §0 Decision gates (need user answers before execution)

1. **Query counts:** finance = **30 (user-provided CFO insight set, 2026-09-18, verbatim + ordered)**;
   AR = 70 (datasets + identity-clarify + unsupported). Ten-question query sets replace the
   generated 72/80 drafts — the user's 30 ARE the finance eval set.
2. **Two-turn clarify runs:** include (recommended — it is the only way to test the clarifying
   behavior) vs first pass single-turn-only, clarify queries recorded as "clarified, not resumed".
3. **Account dirs:** new `accounts/finance/` + `accounts/ar-agent/` (collections dir untouched —
   its v1/v2 history stays as the OLD-surface baseline).
4. **Push:** commit locally as we go; nothing pushed without explicit go (standing rule).
5. **Surana untouched** (standing rule); the 2 untracked probe leftovers stay as-is.

## Phase 1 — Probe gate (interface-changed rule; BEFORE any query set)

Raw-SSE probe script /tmp/hermes-verify-agent-probes.py using CopilotClient (same login):
- finance, code `finance`: (a) "total outstanding receivables" (direct-answer path),
  (b) "what looks unusual in the financial data" (expect clarify),
  (c) "what is my profit margin" (expect out_of_scope refusal). Init + stream, dump event:+data:.
- AR, code `collection_and_account_receivables`: (a) "who are my top overdue customers" (query_ar),
  (b) named-customer question with an ambiguous name (expect identity shortlist),
  (c) "did customer X pay" style evidence question (get_ar_evidence / financials).

Verify and RECORD (block on any unknown; evidence before claims):
- [ ] init 200 for BOTH codes on the hirafoods workspace; N=10 evidence probe if either flakes
      (scripts/evid_init_flaky.py pattern — log EVERY status before calling anything flaky).
- [ ] Event vocabulary vs the parser (agentic status.phase tool_start/tool_done?) — diff against
      references/stream-protocols.md.
- [ ] **Wire shape of a clarify/interrupt** — what SSE events carry the finance_clarification
      (question + options) and the AR identity shortlist? Does the parser capture it, or does it
      look like an error/empty turn? This decides the two-turn runner's clarify DETECTION.
- [ ] **Resume mechanics** — after a clarify turn, POST /stream on the SAME thread_id with the
      option text: does it produce the final answer? What exactly must the resume message be
      (option text verbatim? prefixed?)?
- [ ] tool_calls captured on answer turns; empty on clarify/refusal turns; response text shape
      (AR: one sentence; finance: narrative/tables; ₹ not paise).
- [ ] Data presence: do direct finance metric queries return rows on this workspace, or no_data?
      (No-data = workspace finding, not eval failure; flag for owners.)
- [ ] **ENTITY DISCOVERY (mandatory — real-entity rule):** harvest the workspace's real entities
      into `accounts/<name>/entities.json`: confirm the 10 customer accounts + 9 products resolve
      (AR: query_ar customer_balances / worklist rows; finance: gold-SQL list queries via the
      copilot, e.g. top customers by outstanding, top products by sales), harvest REAL invoice /
      document numbers (AR query_ar_financials invoices; finance list_invoices path), and GST rates
      (finance gst_by_rate metric). Every entity used in a query MUST appear in this file.

Deliverable: probe report (protocols + clarify wire shape + resume contract), committed as
references/ar-finance-protocols.md once verified.

## Phase 2 — Query-set generators (source of truth = the SCRIPT, collections pattern)

- Create `scripts/gen_finance_queries.py` — SECTIONS dict; writes
  `accounts/finance/queries.xlsx`. Columns: query | reference | remarks | expected_tool
  (`TOOL:<metric>` | `NO_TOOL`) | **expected_behavior** (`ANSWER | CLARIFY | REFUSE | CHAT | MIXED`).
  **Persona: CFO / accountant. Domain: ERP ONLY** (no WhatsApp facts). Query set = the
  USER-PROVIDED 30 CFO insight questions (2026-09-18), VERBATIM and in the user's order; labeled per
  the classify-gate rules (9 ANSWER / 12 CLARIFY / 9 REFUSE — profitability/cash/payables/expenses =
  REFUSE; vague/open-review = CLARIFY). The earlier ~72 metric-set draft was replaced by the user's
  set. Generator owns the labels (scripts/gen_finance_queries.py prints 30; hard-gates order +
  placeholders). NOTE: finance metric answers have no observable SSE tool events (backend SQL) —
  expected_tool is the review intent label; grade finance on behavior + answer quality.
- Create `scripts/gen_ar_agent_queries.py` — ~64. **Persona: upper management. Domain: ERP +
  WhatsApp groups (the groups confirm the LATEST updates on payments/receivables).** Categories:
  position (outstanding, ageing snapshots, stale-snapshot honesty — "the latest list is from <date>"),
  worklist (priority, chase list, holds — "who do we chase first today"), objects (payment claims,
  commitments, acknowledgements, disputes, cheque, document requests — WhatsApp-grounded:
  "Om Enterprises Traders 421 said the payment is done — does the group confirm it?",
  "who acknowledged their dues in the group recently?"), financials (invoices, customer balances —
  "balance for Radha Agencies LLP 552"), evidence (exact wording of a claim from the group),
  paid collections (period totals), conversation snapshot ("what's the latest update in the
  HiraFoods–Om Enterprises Traders 421 group?"), identity CLARIFY (ambiguous named customer —
  resolve → select), UNSUPPORTED refusals (settlement proof from unconfirmed claims, bank
  verification, forecasts, "repeated follow-up" confirmation). `expected_tool` = query_ar |
  query_ar_financials | get_ar_evidence | get_paid_collections | resolve_ar_identity | NO_TOOL;
  every named customer from entities.json (the 10 accounts + Radha Agencies Pvt Ltd 787 — proven
  resolvable in collections v2).
- Both: print `queries=N TOOL-expected=X CLARIFY=Y REFUSE=Z` on run; verify xlsx row counts
  excluding header + category rows (assert exact N). **HARD GATE on generation: every named entity
  in a query text must token-match entities.json; zero placeholder tokens (ABC|XYZ|TEST|PLACEHOLDER|
  EXAMPLE); invoice numbers must come from the live harvest.**

## Phase 3 — Two-turn runner (new capability, no changes to the sacred single-turn pipeline)

Create `scripts/run_agent_evals.py` (reuses CopilotClient / load_account_config):
- For each query: init thread (code per account) → stream turn 1 → classify the turn per the
  probe-gate detection (clarify vs answer vs refusal) → if CLARIFY-expected or clarify detected:
  resume SAME thread_id with the chosen option (option text per probe contract) → stream turn 2.
- JSONL schema per query (`accounts/<name>/runs/query_results_v1.jsonl`):
  {query_index, query, category, expected_behavior, expected_tool, turn1: {response, tool_calls,
  clarify: {question, options}|null, error}, turn2: {response, tool_calls, error}|null,
  resumed, total_seconds}. Incremental append per query (resume-safe via --resume N).
- No retries on failures (HEART). Versioned runs, never overwrite.

## Phase 4 — Scaffold accounts

- `accounts/finance/config.yaml`: phone 4040505050, workspace_id c331ac11-…, chatTemplateCode
  `finance`, llm_provider gpt-5.4-mini (matches the classifier pin; NOTE the AR loop runs
  gpt-5.6-luna — config value is informational), base_url https://api.zotok.ai,
  sse_timeout 300, sse_read_timeout 120.
- `accounts/ar-agent/config.yaml`: same but chatTemplateCode `collection_and_account_receivables`.
- Verify both with the pipeline's own loader:
  `python3 scripts/verify_account_config.py finance 4040505050` (exit 0) + same for ar-agent.

## Phase 5 — Runs

- `python3 scripts/run_agent_evals.py --account finance` + `--account ar-agent` — background,
  tee to `<name>_pipeline_run.log`, notify on complete. Budget: 60-80 queries × (7-15s simple,
  40-300s data-heavy) ≈ 1.5-3h per agent; run sequentially, heartbeat if >1h.
- Watch incremental jsonl mid-run; resume partial failures with `--resume N`, never re-run
  completed rows. No retries (HEART).

## Phase 6 — Analysis

- 4-bucket quality via `build_dashboard.classify_quality()` (pass the FULL record dict) — with a
  stated CAVEAT: AR's one-sentence contract will bucket many correct answers as marginal/no_data;
  run a judgment pass on non-success buckets and report both (raw classifier + judged).
- Tool-accuracy vs expected_tool: strict + lenient (any genuine data call satisfies a TOOL-marked
  intent — collections v2 lesson). Tool-surface inventory: flag ANY tool outside the declared set
  (resolve KNOWN UNKNOWN #4: do get_receivables/get_collections still ship?).
- Clarify-correctness (the new dimension): CLARIFY queries → clarify surfaced + options + no tools +
  resume produced an answer (record the resume-answer tool chain). ANSWER queries → answered WITHOUT
  spurious clarify. REFUSE queries → refusal naming the boundary + no estimate, no tools.
- Finance: ₹-sanity spot-check (no raw paise), refusal text names data boundary.
- Latency: avg + P95, clarify-turn latency reported separately (parks, no tools).
- Churn vs collections v1/v2 (AR): expected — surface changed in place 2026-09-17; report as
  capability shift, not trust loss.

## Phase 7 — Deliverables

- `accounts/finance/EVAL_READOUT_v1.md` + `accounts/ar-agent/EVAL_READOUT_v1.md` (owner artifacts:
  completion, buckets, tool-accuracy, clarify-correctness, refusals-right, action list).
- `python3 build_dashboard.py --account finance` + `--account ar-agent`; landing cards in
  langsmith-tool-evaluator/docs/index.html. Playwright visual verify (stat-card counts, zero JS
  console errors). Commit locally; push only on explicit go.
- Update zotok-copilot-eval skill with: run results, the two-turn runner, the verified clarify/
  resume protocol, and resolutions of known unknowns #1/#4 (design-notes cross-ref).
- Update PROJECTS.md seller-copilot/eval lines + repo README account table.

## Verification checklist

1. Probe report: both init codes 200; clarify wire shape + resume contract documented with raw
   event samples; parser compatibility verdict per agent.
2. Generators print expected counts; xlsx data-row counts == N; every named customer/product/
   invoice token-matches entities.json (zero ABC/XYZ/test tokens); invoice numbers from the live
   harvest; finance has no WhatsApp-grounded queries, AR has no metric-jargon-only queries.
3. verify_account_config exits 0 for both accounts.
4. Each run completes: N records in jsonl, manifest v1 row (success/failed/avg), clarify queries
   have turn1 + turn2 where resumed, no retried failures.
5. classify_quality parses; bucket counts + judged-pass counts both reported.
6. Tool-accuracy strict+lenient, clarify-correctness, refusal-correctness computed; tool-surface
   inventory answers unknown #4.
7. Both EVAL_READOUTs exist with ≥1 action item or explicit "no drift".
8. Dashboards render real counts (Playwright), landing cards link.
9. `git status --short` clean after commit (except pre-existing leftovers if user kept them).