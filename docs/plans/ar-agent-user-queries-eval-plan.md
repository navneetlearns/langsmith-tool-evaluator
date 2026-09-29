# AR Agent Eval — User-Provided Query Set — Plan

> **Status: EXECUTED 2026-09-24 — labels OK'd by user; probe gate passed; full v2 run
> complete (56/56, 0 errors); analysis + EVAL_READOUT_v1.md + two-tab dashboard built;
> PUSHED to origin/main 2026-09-24 (4a1b262 → 804006d + scorecard-tile fix). Details:
> EVAL_READOUT_v1.md + references/ar-agent-v1-run.md (skill). Remaining: optional v3 with
> re-mapped expected_tool labels (see readout action item 4), order-to-dispatch plan (shelved).**
> Prepared 2026-09-23. Supersedes the AR half of `ar-finance-agent-eval-plan.md` for the
> query-set source: the user's own queries REPLACE the generated 70-query draft
> (skill rule: user-provided sets are kept verbatim, in the user's order — never padded with
> or replaced by a generated draft). The generated draft stays on disk as reference only.
>
> **WORKSPACE (2026-09-23): Zainab Enterprises — d53279c2-0f92-42ea-876d-1c57770f5184,
> login 9029012960 (user-provided eval creds; the 2026-09-22 trace workspace).** hirafoods
> (c331ac11) is OUT — it has NO WhatsApp group data, and the AR agent's value surface is
> WhatsApp-grounded (claims, commitments, acknowledgements, disputes, evidence).
> **Ask-groups recon EXECUTED 2026-09-23 on Zainab (12 probes, 12/12, ~14s avg) — VERDICT:
> workspace VIABLE.** See accounts/ask-groups/RECON_DATA_INVENTORY.md (257 active groups/7d,
> tagged corpus ~10k msgs/week, 61% untagged + 3 low-volume days disclosed, payment chatter
> sparse: 9 payment requests/7d, real evidence anchors found: invoice B NO 15293, 02-Sep
> cheque-not-deposited, Al Anwar outstanding). Consequences that ripple through this plan:
> - ALL hirafoods entities (11 customers, products, invoices 12851-12859) are INVALID for the
>   new workspace → Phase 1 gains a MANDATORY entity harvest (live discovery probes on the new
>   workspace → new `entities.json`). The hirafoods entities.json stays on disk as reference
>   but is NOT the eval entity set.
> - `config.yaml` in Phase 2 is parameterized from the NEW credentials, not the hirafoods
>   values (those are shown only as a shape example).
> - Phase 3 gains a hard data-presence gate: if the new workspace also has no AR signal data,
>   STOP and report — an AR eval against an empty object store is a no-op, not a run.

**Goal:** Run the first AR agent (`collection_and_account_receivables`) eval on the NEW AR workspace (credentials pending)
using the USER-PROVIDED query set: completion, 4-bucket quality (+ judged pass),
tool-accuracy vs expected_tool, clarify-correctness (identity shortlist), refusal-correctness,
answer-format compliance, latency → `EVAL_READOUT_v1.md` + dashboard, same as collections
v1/v2 and finance v1.

**Architecture:** Feed the user's verbatim queries through the existing two-turn runner
(`scripts/run_agent_evals.py --account ar-agent`, Format A xlsx + col E `expected_behavior`),
labeled per the AR agent's own decision order. Stream live to the new AR workspace
(prod api.zotok.ai), record tool calls + timing + status_sequence per query, version every run,
grade against expected labels, report to owners.

**Tech stack:** eval-dashboard repo (`~/AgentWork/eval-dashboard/`), `run_agent_evals.py` +
`build_dashboard.py` + `CopilotClient` (SSE agentic protocol), openpyxl (xlsx), Playwright
(dashboard visual verify).

---

## Knowledge gathered (ground truth for this plan)

**What the AR agent is** (`~/AgentWork/seller-copilot/agent-design-notes.md` + agent-profiles):
- `chatTemplateCode: "collection_and_account_receivables"` → supervisor intent
  `collections_search` → `ar_agent` subgraph: `load_context` → ReAct loop (gpt-5.6-luna) →
  `format`. Agentic SSE protocol — tool events DO surface (`status.phase tool_start/tool_done`),
  unlike finance (so tool grading applies here).
- Sources: **ERP + WhatsApp groups**. User: anyone in **upper management**, plain business
  language. Answers "who owes what and what they said about it".
- Tool family (design-notes era): `query_ar` / `query_ar_financials` / `get_ar_evidence` /
  `resolve_ar_identity` / `get_paid_collections` / `get_ar_conversation_snapshot`.
  **2026-09-23 live discovery on Zainab — the DEPLOYED surface differs:** `get_receivables`
  (mode customers|invoice), `list_invoices` (start/end date, doc_number, page),
  `ar_position`, `ar_worklist` (limit/include_held), `ar_promises` (payment
  commitments/acknowledgements), `ar_payments_reported` (WhatsApp-reported payments NOT in
  ERP — the reconciliation core; live answer: 10 claims, ₹7,41,130), `search_threads`
  (WhatsApp conversations), `search_customers_master` (identity resolution). The `query_ar*`
  family and `resolve_ar_identity` were NOT observed. Resolver inconsistency: named lookups
  sometimes fall back to windowed `get_receivables` instead of `search_customers_master`
  (Casa Walls/Palette/Whistling Wood/Mohanlal failed this way; Interworld Furnishings
  resolved via search_customers_master).
- Presentation contract: ONE short plain-language sentence per result (the APP renders the
  table/cards); NEVER tool names/dataset names/SQL/run IDs/source metadata in response text;
  max 5 rows; empty = what was searched + useful next step; stale snapshot → "the latest list
  is from <date>" (never the word "stale"); hedged wording for unconfirmed claims
  (reported ≠ bank-verified, kept/entered ≠ settled, unknown amount ≠ zero); no forecasts
  (DSO, credit limits, bank matching, cash).
- identity CLARIFY (design-notes era): `resolve_ar_identity` shortlist required selection.
  **2026-09-23 on Zainab: NO shortlist tool observed** — referent-less/ambiguous rows get an
  ask-back or an honest not-found ANSWER; user set labels CLARIFY only for the 2 truly
  referent-less rows (expected_tool ASK_BACK), everything named → ANSWER with resolution via
  search_customers_master when the name is close to master.
**Real entities: hirafoods INVALID for this eval.** The committed entities.json (harvested
  2026-09-18 from hirafoods: 11 customers incl. the two-Radha pair, 11 products, invoices
  12851–12859, GST-0) is workspace-specific and must NOT seed this eval. Phase 1 harvests the
  NEW workspace's own entities; no hirafoods customer/product/invoice may appear in labels
  until re-harvested there.
- Known style observations from the 09-17 trace thread: objects filters are LITERAL
  (`status=eq("open")` ≠ open-states; agent recovered); follow-up activity per customer is
  UNCONFIRMABLE by design (activity = last_inbound/outbound only).

**Eval-harness facts:**
- Runner exists and reads col E: `run_agent_evals.py` parses Format A + col E
  `expected_behavior`, streams via the fixed parser (09-18: full `ui`-markdown answers +
  SSE `error` capture landed), incremental JSONL, `--resume N`, `--only q1,q7`, carries
  untouched rows on subset re-runs, flags empty+clean+fast turns as `possible_clarify`.
- **accounts/ar-agent/ is HALF-SCAFFOLDED**: `entities.json` + `queries.xlsx` (generated 70)
  exist and are committed; **`config.yaml` is MISSING** and **no `runs/` exist yet** — no AR
  run has ever executed. Phase 3 below is the missing scaffold.
- Collections v1/v2 (Sep 5–9) ran the OLD `get_receivables`-era surface — those numbers are
  STALE baselines vs the query_ar-era agent (prompt changed in place 09-17). This run
  establishes the NEW baseline; churn vs v1/v2 is a capability shift, not a regression.
- Quota: agent-template paths run on metered Zops — `402 topup_required` kills runs mid-way.
  ALWAYS probe one cheap query before a full run (Phase 3).
- Latency: simple lookups 7–15s, data/evidence-heavy 40–300s; SSE pauses between tool events.
- `chatTemplateCode` init is intermittently flaky for the real code (retry 3× absorbed);
  `""` is the stable-200 but routes to `general` — MUST use the real code here.
- AR quality nuance: the one-sentence contract makes many correct answers look
  no_data/marginal to the regex classifier — report raw classifier AND a judged pass.

---

## §0 Decision gates (need user answers before execution)

1. **Workspace credentials — RESOLVED 2026-09-23.** Zainab Enterprises
   d53279c2-0f92-42ea-876d-1c57770f5184 / 9029012960; config.yaml written for BOTH
   accounts/ar-agent and accounts/ask-groups (both verify OK via the pipeline loader).
2. **The query list** — user provides it (paste in chat / file / sheet is all fine). Keep
   VERBATIM, in the user's order, one category row for the whole set (or user's own groups).
3. **Replace the generated 70?** Recommended: YES — user set is THE eval set (draft kept at
   `accounts/ar-agent/queries.generated-70.xlsx` as reference, not merged). Alternative:
   run both (adds ~1-2h).
4. **Two-turn clarify runs** — include (recommended; it is the only way to test the identity
   shortlist behavior — and AR's is guaranteed by design) vs single-turn-only with CLARIFY
   recorded as "parked, not resumed".
5. **Push** — commit locally as we go; nothing pushed without explicit go (standing rule).
6. **Surana untouched; collections dir untouched** (standing rules).

---

## Phase 0.5 — Ask-groups recon (EXECUTED 2026-09-23)

Purpose per user decision ("ask my groups first, then AR/collections"): know what exists in
WhatsApp groups before building AR/collections query sets, since both agents' WhatsApp leg is
driven by the same group conversations.

- Ran: `python3 scripts/run_agent_evals.py --account ask-groups` → 12/12 ok, avg 14.2s, no
  errors, no clarify; results `accounts/ask-groups/runs/query_results_v1.jsonl`.
- Config `accounts/ask-groups/config.yaml` (lane `ask_chats`, Zainab creds) + generator
  `scripts/gen_ask_groups_recon.py` → recon xlsx (expected_tool/expected_behavior = RECON =
  NOT graded; chat engine has no user-visible tools).
- Output: `accounts/ask-groups/RECON_DATA_INVENTORY.md` — full numbers + implications.
- Key feeds into AR: group aliases for identity-CLARIFY queries, real payment anchors
  (B NO 15293, 02-Sep cheque, Al Anwar), coverage caveat carry-over (AR hedges on the
  WhatsApp leg = correct, not fail), and the verdict that Zainab is viable.
- Known gap reproduced: "how many groups i have" still intro-fallbacks (scope gap) — an
  ask-groups eval finding; does not block AR.

## Phase 1 — Ingest & label the user query set (EXECUTED 2026-09-23, awaiting label review)

Round-1 + round-2 harvest probes (probe_ar_harvest.py, probe_ar_harvest2.py →
harvest_results_v1.json + v2.json) run on Zainab: **data-presence gate PASSED**
(ar_position ₹233.22Cr across 545 customers, ₹228.95Cr overdue, worklist 10 ranked / 32
held; list_invoices 2,716 in window; ar_payments_reported 10 claims ₹7,41,130).
`entities.json` REBUILT for Zainab (anchored set: worklist top accounts, reported-claim
customers, ONCE & AGAIN promise, invoices 17369/17371/17353/17348/17346, mismatch anchor
B NO 15293; hirafoods values gone). User's 55 queries ENRICHED per instruction (Palette →
TRENDS FURNISHING; Bill 12798 → B NO 15293; pronouns anchored on real invoices/customers;
2 rows kept referent-less as CLARIFY/ask-back tests) + 1 identity-resolution gate row =
**56 queries** in `scripts/gen_ar_user_queries.py` (gates: placeholder, anchor↔entities,
≥1 CLARIFY, ≥1 invoice-anchored) → queries.xlsx; generated-70 draft backed up as
queries.generated-70.xlsx. **BLOCKED on user label review before the live run** (plan rule).

**Files:**
- Input: user's query list (verbatim).
- Create: `scripts/gen_ar_user_queries.py` (generator owns the dataset — collections pattern,
  never hand-edit the xlsx).
- Output: `accounts/ar-agent/queries.xlsx` (replaces the generated 70).

- [ ] **Step 0: Harvest the NEW workspace's real entities (MANDATORY — hirafoods entities are
  invalid here).** Live discovery probes, one thread per probe (5-30s each): top customers by
  outstanding (query_ar position/worklist or query_ar_financials customer_balances),
  signal-objects inventory (claims / commitments / acknowledgements / disputes / cheques),
  evidence rows, recent invoices (query_ar_financials invoices), paid-collections totals.
  Parse entity names + tool names out of the response text; REPLACE
  `accounts/ar-agent/entities.json` with the new workspace's customers[], products[] (with
  rates if the workspace has them), invoices[], gst{}, harvest timestamp + source notes
  (reference §2 of agent-query-set-generation). The ask-groups recon (Phase 0.5) already
  supplies the conversational aliases (accounts/ask-groups/RECON_DATA_INVENTORY.md) — this
  step adds the ERP side. Probe one named entity before committing to a full run: a
  resolvable-but-untagged entity yields no-data answers.
- [ ] **Step 1: Take the user list verbatim + in order.** One category row ("User Queries"
  unless the user grouped them) then rows A=query, B=Expected Response (BLANK at generation —
  goldens added at review), C=remarks, D=`expected_tool`, E=`expected_behavior`.
- [ ] **Step 2: Label each query by applying the AR agent's OWN decision order** (not our
  opinion of the ideal answer):
  - **CLARIFY** (`TOOL:resolve_ar_identity`) — named customer with ambiguous/truncated/absent
    account number ("Radha", "Sai Agencies", "the big distributor"), firm-only names, any
    question whose entity needs the shortlist-selection turn. Two-Radha phrasing = guaranteed
    CLARIFY.
  - **REFUSE** (`NO_TOOL`) — genuinely-absent or read-only-guard classes: bank verification /
    cleared-cheque confirmation, forecasts (collections/DSO/credit/cash), send-a-message on
    WhatsApp (drafts only), mark-settled / any write, "which claims hit the bank", employee-
    level chasing history. NOTE: AR hedges more than it refuses — if the query is business-
    data-answerable WITH a limitation, label ANSWER, not REFUSE (trace: "payments stuck
    despite repeated follow-ups" → ANSWER with honest hedge).
  - **ANSWER** (`TOOL:<tool>`) — everything else, with the tool-routing map:
    status/rank/signals → `query_ar`; invoices/balances → `query_ar_financials`; exact wording
    → `get_ar_evidence`; workspace paid totals → `get_paid_collections`; recent group window →
    `get_ar_conversation_snapshot`; named-but-unresolved customer in an answerable question →
    `resolve_ar_identity` → then the data tool (label the primary).
  - Mark genuinely ambiguous rows 'lenient' in remarks (a scoped answer or a partial hedge
    scores fine, not a miss).
- [ ] **Step 3: Hard gates in the generator (raise SystemExit(1) on failure):**
  - Placeholder-token regex over ALL query texts: `(ABC|XYZ|TEST|PLACEHOLDER|EXAMPLE|SAMPLE|DUMMY)`.
  - If user queries NAMED entities: customer/product tokens must token-match `entities.json`;
    invoice numbers only from THIS workspace's live harvest. User entity-free questions
    legitimately DROP the entity-coverage gates (reference §5) — placeholder scan + count/order
    assertions still hold.
  - Count/order: printed `queries=N` == parsed data-row count == number of user queries, in
    the user's order (verify with the pipeline's OWN parser:
    `python3 -c "from scripts.run_agent_evals import parse_xlsx; print(len(parse_xlsx('ar-agent')))"`,
    expected N).
  - ≥1 CLARIFY (identity ambiguity) present in the set; ≥1 invoice-anchored query if any
    invoice exists in the set.
- [ ] **Step 4 (replaces the two-Radha item in the earlier draft):** the hirafoods two-Radha
  ambiguity case does NOT transfer. Required: ≥1 identity-ambiguity CLARIFY built from
  whatever the harvest reveals (a name collision, or a truncated firm-only name like
  "Sai Agencies" that forces the shortlist). **Step 5: Back up the draft** — `cp accounts/ar-agent/queries.xlsx accounts/ar-agent/queries.generated-70.xlsx` BEFORE the generator runs (draft preserved for reference).
- [ ] **Step 6: Commit** — generator + xlsx committed locally; xlsx handed to the USER for
  label review BEFORE any live run (review checks: persona fit, CLARIFY/REFUSE phrasings,
  entity realism). Edits go through the GENERATOR, never the xlsx.

## Phase 2 — Scaffold the missing account config

**File:** Create `accounts/ar-agent/config.yaml` (currently MISSING — blocker for any run).
Fill from the NEW credentials (gate 1) — the values below are the hirafoods SHAPE only,
NOT the eval values:

```yaml
account_name: "ar-agent"
phone: "<NEW phone>"            # from user's credentials drop
workspace_id: "<NEW workspace UUID>"
seller_details:
  firstName: "<seller firstName>"
  mobile: "91<NEW phone>"
wa_config_id: "<NEW workspace UUID>_91<NEW phone>"   # default derivation unless told otherwise
llm_provider: "gpt-5.6-luna"   # informational — AR loop runs luna
base_url: "https://api.zotok.ai"
sse_timeout: 300
sse_read_timeout: 120
chatTemplateCode: "collection_and_account_receivables"   # REAL code, not ""
```

- [ ] **Step 1:** Verify with the pipeline's own loader:
  `python3 -c "from copilot_query_pipeline import load_account_config; c=load_account_config('ar-agent'); print(c['chatTemplateCode'], c['workspace_id'])"`
  Expected: the code + workspace UUID printed; `chatTemplateCode` is the STRING
  `collection_and_account_receivables` (if it prints `{}` the empty-value loader guard
  regressed — re-apply the `key != "chatTemplateCode"` fix).
- [ ] **Step 2:** `python3 scripts/verify_account_config.py ar-agent 4040505050` — exit 0.
- [ ] **Step 3:** OTP preflight: `python3 scripts/preflight_otp.py 4040505050` — 201 + OTP
  echoed = flow alive (does NOT prove registration; the run's auth step is the real gate).

## Phase 3 — Probe gate (interface-changed rule; BEFORE the run)

- [x] **Step 0 (HARD data-presence gate): PASSED 2026-09-23 via the Phase-1 harvest** —
  ar_position/ar_worklist returned rows (₹233.22Cr / 545 customers / 10 ranked), ar_promises
  found commitments, ar_payments_reported found the 10-claim mismatch set, search_threads
  pulled WhatsApp conversations. Zainab has AR signal data; no 402 quota errors on 13 live
  queries.
- [ ] **Step 1:** ONE cheap live query via the runner (`--only <1 cheap index>`) and dump the
  RAW SSE (event:+data: split) for `collection_and_account_receivables`. Verify and RECORD:
  - init 200; agentic events present (`status.phase tool_start/tool_done`); response now
    arrives via the `ui`-markdown unwrap (the 09-18 parser patch — empty-response-with-tools
    should be GONE; if it reappears, it's a wire-format gap to diff, never a no-data answer).
  - **Quota check: any `402 topup_required` → STOP, tell the user to top up Zops, re-probe
    after.** (Agent-template paths burn the meter fast; a full run confirms at its own cost.)
  - `search_customers_master`/legacy `get_receivables` in tool_calls? — records whether the
    old surface still ships (known unknown #4) but does NOT change grading (lenient).
  - Response = one plain sentence, no tool/dataset names in the text.
- [ ] **Step 2:** If init flakes, `scripts/evid_init_flaky.py ar-agent 10` — log EVERY status,
  compute the real rate before calling anything flaky (evidence-before-claims rule).
- [ ] **Step 3:** If the set contains identity-CLARIFY queries, probe ONE: does the interrupt /
  shortlist surface on the wire (event + payload)? The runner flags `possible_clarify` on
  empty+clean+fast turns and records interrupt if carried; if the shortlist text is NOT on the
  wire, the two-turn resume still works (resume with a chosen option on the same thread_id) —
  but document the wire shape as a known gap for owners (mirrors finance P1).
- [ ] **Step 4:** Record findings in `references/ar-agent-protocols.md` (commit).

## Phase 4 — Run

- [ ] **Step 1:** `cd ~/AgentWork/eval-dashboard && python3 scripts/run_agent_evals.py --account ar-agent`
  — backgrounded, output teed to `ar-agent_run.log`, notify_on_complete. Budget:
  N queries × (7–15s simple, 40–300s data-heavy), CLARIFY rows take 2 turns → plan
  ~0.5–1.5h for 20–40 queries; heartbeat if >1h. SSE pauses between tool events are normal.
- [ ] **Step 2:** Watch the incremental JSONL mid-run
  (`tail -f accounts/ar-agent/runs/query_results_v1.jsonl`); `--resume N` on any partial
  failure, never re-run completed rows, never retry a failed stream (HEART).
- [ ] **Step 3:** Runs are versioned — the first run is v1; manifest row written per version.

## Phase 5 — Analysis

- [ ] **Step 1: Quality.** `build_dashboard.classify_quality(record)` (FULL record dict, not
  the response string) → success/no_data/marginal/fail buckets. THEN a judged pass on
  non-success records (AR's one-sentence contract under-buckets correct answers) — report
  BOTH raw and judged counts. `possible_clarify` / interrupt records classify as `clarify`,
  NOT fail.
- [ ] **Step 2: Behavior matrix.** expected vs observed per query (ANSWER | CLARIFY | REFUSE):
  CLARIFY queries → shortlist surfaced, no data tool ran, resume produced an answer;
  ANSWER queries → answered WITHOUT spurious clarify; REFUSE queries → boundary-named answer,
  no tool call, no estimate. Report the mismatch list by query index (mirrors finance v1:
  mismatches are either mapping errors — fix the labels — or agent drift — flag owners).
- [ ] **Step 3: Tool-accuracy vs expected_tool.** Strict (exact tool) AND lenient (any genuine
  `query_ar*`/`resolve_ar_identity`/`get_*` data call satisfies a TOOL-marked intent —
  collections v2 lesson) + a tool-surface inventory flagging ANY tool outside the declared
  set (drift = owner action item, not eval bug).
- [ ] **Step 4: Format compliance** (AR-specific, deterministic): regex response text for
  tool names / dataset names / `run-`/`query_`/run IDs / words "stale", "partial", "sql",
  "offset", "page" — the presentation contract bans them; any hit = finding. Also verify
  "₹-sanity" (major-unit INR, not paise) and one-sentence shape for short answers.
- [ ] **Step 5: Value read** (user's standing criterion — value to the end user, not fetch
  success): answers must reach L3+ (named item + magnitude/comparison). With the one-sentence
  contract, boilerplate/padding shows as cross-answer repetition (same sentence shape recycled)
  and thin density — reuse `scripts/analyze_finance_value.py`'s deterministic checks adapted
  to AR if the set is 15+ queries. Refusals scored separately — signal-free is CORRECT.
- [ ] **Step 6: Latency** — avg + P95, reported BY OUTCOME (answered vs clarify-park vs
  refusal vs error), never one blended average (finance v1 lesson).
- [ ] **Step 7: Write `accounts/ar-agent/EVAL_READOUT_v1.md`** — the owner artifact FIRST
  (dashboard is presentation): completion/fail counts, buckets (raw + judged), tool-accuracy
  strict+lenient, behavior matrix results, what the agent got RIGHT (hedged claims, safe
  refusals, honest limitations), and an action list (clarify noise, tool drift, wire gaps,
  entity-resolution failures). ≥1 action item or explicit "no drift".

## Phase 6 — Dashboard + close-out

- [ ] **Step 1:** `python3 build_dashboard.py --account ar-agent` → builds the CLARIFY-aware
  page (behavior matrix + possible_clarify card auto-render when records carry
  `expected_behavior`; light theme rules apply).
- [ ] **Step 2:** Add the landing card in `langsmith-tool-evaluator/docs/index.html` (mirror
  surana/unifoods cards; HARDCODED, manual edit).
- [ ] **Step 3:** Playwright visual verify the built page (stat-card counts match the JSONL,
  clarify card present, zero console errors, no legacy dark hexes).
- [ ] **Step 4:** Commit locally (runner jsonl, readout, dashboard, config, entities, skill
  notes, PROJECTS.md seller-copilot/eval line + repo README account table). **Push only on
  explicit user go** (dashboard data loads from GitHub RAW — page shows live counts only
  after push; say so, don't push).
- [ ] **Step 5:** Update the zotok-copilot-eval skill: run results, whether the old
  get_receivables surface still ships, verified clarify wire shape, resolved design-notes
  known unknowns #4/#5.

---

## Verification checklist

1. Generator prints `queries=N`; xlsx data-row count == N; user order preserved; zero
   placeholder tokens; named entities token-match entities.json (where the user named any).
1b. `entities.json` harvested from the NEW workspace (no hirafoods values); data-presence
   gate passed (objects/worklist probes returned rows). Ask-groups recon v1 (12/12) executed
   and its inventory written to accounts/ask-groups/RECON_DATA_INVENTORY.md.
2. `verify_account_config ar-agent` exits 0; loader prints the string code, not `{}`.
3. Probe gate: init 200, tool events captured, response text present (parser patch held),
   no 402 — or the run was halted at the quota gate with the user informed.
4. v1 jsonl has N records, manifest v1 present; CLARIFY rows have turn1 + turn2 where
   resumed; no retried failures.
5. Both raw and judged bucket counts reported; clarify/possible_clarify never counted as fail.
6. Behavior matrix, tool-accuracy (strict+lenient), format-compliance, latency-by-outcome all
   computed; tool-surface inventory answers known unknown #4.
7. EVAL_READOUT_v1.md exists with ≥1 action item or explicit "no drift".
8. Dashboard renders real counts (Playwright); landing card links; light-theme tokens only.
9. `git status --short` clean after commit (pre-existing leftovers excepted); nothing pushed
   without the user's go.

## Notes / open items

- If the user's queries turn out to be almost all judgment/vague ("who should we worry
  about", "is anyone taking too long") expect a large CLARIFY share — that is normal for
  upper-management sets, not a weak eval (mirror: finance insight set = 9 ANSWER /
  12 CLARIFY / 9 REFUSE).
- The hirafoods two-Radha pair does NOT transfer to the new workspace. The guaranteed
  identity-ambiguity case becomes whatever the new-workspace harvest reveals (name collision
  or truncated firm-only name) — include one unless the user's set forbids customer names.
- Keep `queries.generated-70.xlsx` untouched as the reference draft — do not merge, do not
  delete.