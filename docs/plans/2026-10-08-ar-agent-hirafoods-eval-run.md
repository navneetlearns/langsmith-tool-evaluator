# AR Agent (collection_and_account_receivables) — HiraFoods Eval Run Plan

> **Status: EXECUTED 2026-10-09 (approved by the user same day).** Result: 32/32 rows, 0 errors,
> 19/32 pass-class, 0 fabrication — readout `accounts/hirafoods-ar/EVAL_READOUT_v1.md`, dashboard
> `docs/hirafoods-ar/index.html`. Two plan assumptions were corrected by live evidence:
> **D6** (the expected_tool family) — NOT one query_ar-family tool fired; the surface is the ERP
> 5-tool contract + ar_promises/ar_payments_reported + product/dispatch tools (13 tools), so strict
> tool accuracy is a label artifact again; and **D5/B2** — the invoice × WA-signal JOIN refuses on
> Zainab but ANSWERS on HiraFoods, so the REFUSE-with-offer expectation for row 18 was graded
> ANSWER-with-hedge. Gate G4 (identity) came back PARTIAL: the WhatsApp display name does not
> resolve against the customer master. Original plan text follows unchanged for the record.
>
> **Original status: PROPOSED 2026-10-08 — awaiting approval. Do not run until G1–G5 are green.**
> Prepared after: the query-design page (`seller-copilot/ar-agent/ar-agent-query-design.md`),
> the 32-row draft (`accounts/hirafoods-ar/QUERY_SET_DRAFT_v1.md`), the AR v1 readout
> (`accounts/ar-agent/EVAL_READOUT_v1.md`), and the live B2 boundary observation
> (2026-10-08, user's copilot stream trace).

**Goal:** Run the AR agent eval (`collection_and_account_receivables`) on the **HiraFoods**
workspace using a generator-owned query set, and produce a judged readout + dashboard —
the same evidence bar as AR v1 (Zainab), finance v1/v2 and ask-groups HiraFoods v1.

**Architecture:** Gate the workspace first (both data legs must return rows, else the eval is
a no-op), harvest real entities from the workspace, generate the query set from the two-root
grid as a Format-A xlsx, probe 3 rows for quota/init/parser, then run the full set through the
two-turn runner, judge `no_data` + `marginal` in-session, and render the AR readout.

**Repo:** work in `~/AgentWork/eval-dashboard` (active eval repo; `langsmith-tool-evaluator/`
is the mirror + Pages source). Account dir: `accounts/hirafoods-ar/`.

---

## Safety rules (non-negotiable)

1. **HiraFoods `c331ac11` is a LIVE client workspace** (AU Bank / HiraFoods, phone 4040505050).
   Every probe is **READ-ONLY**. No writes, no sends, no config changes on the workspace.
2. The AR agent's own contract applies and is also a test assertion: **drafting never sends**.
   Nothing in this plan causes a message to be sent to a real customer.
3. **Metered API**: agent templates return `402 topup_required` once the Zops meter drains.
   Check quota on the probe run (P4) before spending on the full run (P5).
4. No prod business data is exported outside the workspace: entities are harvested *from
   this workspace*; numbers may appear in the readout only as eval evidence, same as v1.
5. `eval-dashboard` is a git repo — **commit locally, never push without asking** (user rule).

---

## Locked decisions (settle now so no task re-decides)

| # | Decision | Value | Why |
|---|---|---|---|
| D1 | Workspace | **HiraFoods `c331ac11-c3e8-4d42-a8d6-b8b04127354c`**, phone `4040505050` | User instruction: "test ar agent in hirafoods". Closes query-design §8 Option A. |
| D2 | Query-set source | The 32-row `QUERY_SET_DRAFT_v1.md` → generator-owned xlsx | Unless the user swaps in their own set, in which case theirs is kept verbatim, in their order (skill rule: user-provided sets are never padded with a generated draft). |
| D3 | `wa_config_id` | The **AR app's** binding on this workspace (B2 trace: `c331ac11-…_917893797892_COP`) | NOT the ask-groups binding (`…_914040505050`). Verify live in P0.2 — do not copy ask-groups'. |
| D4 | Grading vocabulary | `ANSWER · CLARIFY · REFUSE · CHAT · MIXED`; capability-gap rows grade `NEAREST_SHAPE` (marginal, not fail) | Consistent with AR v1 / ask-groups. |
| D5 | Invoice × WA-signal JOIN | Graded **REFUSE-with-offer = PASS-class** | B2 observed 2026-10-08: the analytical path refuses "overdue bills where the customer promised payment" and offers the two supported roots. |
| D6 | `expected_tool` labels | Taken from the **wire** tool surface (`query_ar`, `get_ar_evidence`, `query_ar_financials`, `resolve_ar_customer`, `get_ar_schema`) | AR v1 got strict tool accuracy 0/54 because labels came from the harvest `ar_*` family that never fired. Do not repeat. |

---

## Gates (must be green before P3 generates a set or P5 runs it)

| Gate | Question | Where it is answered | If it fails |
|---|---|---|---|
| **G1** | Does the user approve the 32-row draft (or supply their own set)? | Human | Stop. Blocked, not guessed. |
| **G2 LEDGER GATE** | Does `query_ar_financials` (`customer_balances`, `invoices`) return rows on `c331ac11`? | P1.1 probe | Rows 1,2,9,19,20,21,24,25 drop to REFUSE / honest-fallback; set becomes WA-signal-only. |
| **G3 SIGNAL GATE** | Does the AR object store (`objects` / `activity` / `worklist`) return rows on `c331ac11`? | P1.1 probe | If BOTH legs are empty → **no-op eval, STOP and report** (the v1 lesson: this is why v1 went to Zainab). |
| **G4 IDENTITY** | How does "Laxmi Agency" resolve vs "Lakshmi Agencies & Co 84"? | P1.2 probe | Alias rows re-labelled; bare-"Laxmi" rows stay CLARIFY controls. |
| **G5 QUOTA** | Does a cheap 3-row probe return 200s (no 402/422)? | P4 | Wait for top-up; do not spend the full run. |

---

## Phase 0 — Preflight (workspace, lane, auth)

**Files:** Create `accounts/hirafoods-ar/config.yaml`

- [ ] **P0.1 — Confirm the AR lane is deployed on this workspace.**
  Run: `python scripts/enumerate_templates.py --account hirafoods`
  Expected: a template with `chatTemplateCode: collection_and_account_receivables` present and
  active on `c331ac11`. If absent, STOP — the lane is not deployed here.

- [ ] **P0.2 — Write `accounts/hirafoods-ar/config.yaml`** with the AR app's own binding.
  Run first to read the live value (do not guess): `python scripts/diag_chatcode.py --account hirafoods-ar`
  Expected file content:
  ```yaml
  account_name: "HiraFoodsAR"
  phone: "4040505050"
  workspace_id: "c331ac11-c3e8-4d42-a8d6-b8b04127354c"
  seller_details:
    firstName: "HiraFoods"
    mobile: "917893797892"          # the AR app's WA binding phone — CONFIRM live in P0.2, do not copy ask-groups
  wa_config_id: "c331ac11-c3e8-4d42-a8d6-b8b04127354c_917893797892_COP"   # CONFIRM live
  llm_provider: "gpt-6-luna"        # informational — B2 trace showed gpt-6-luna on this lane
  base_url: "https://api.zotok.ai"
  sse_timeout: 300
  sse_read_timeout: 120
  chatTemplateCode: "collection_and_account_receivables"   # REAL code — never ""
  ```
  Verify: `python scripts/verify_account_config.py --account hirafoods-ar` → config parses, lane code set.

- [ ] **P0.3 — Auth preflight.**
  Run: `python scripts/preflight_otp.py --account hirafoods-ar`
  Expected: login for 4040505050 succeeds (OTP flow / session), thread-init 200.

---

## Phase 1 — Data gate, READ-ONLY (the go/no-go)

**Files:** Create `scripts/probe_ar_hirafoods_gate.py` (parameterized copy of `probe_ar_harvest.py`,
which is hardcoded to Zainab `d53279c2`).

- [ ] **P1.1 — Run the two-leg gate probe.**
  Run: `python scripts/probe_ar_hirafoods_gate.py --account hirafoods-ar`
  Four queries, one per gate leg:

  | # | Query | Leg it tests | G2/G3 evidence |
  |---|---|---|---|
  | 1 | "total outstanding kitna hai?" | ledger | `query_ar_financials` → `customer_balances` rows |
  | 2 | "konsi invoices abhi pending hain?" | ledger | `query_ar_financials` → `invoices` rows |
  | 3 | "kis-kis ne bola paid, par system me abhi pending hai?" | WA signal | `objects` (payment_claim, reported) rows |
  | 4 | "Lakshmi Agencies ka outstanding kya hai?" | identity | `resolve_ar_customer` behaviour on a typed alias |

  Record for each: response, `tool_calls`, `status_sequence`, whether any data rows came back.
  Expected output file: `accounts/hirafoods-ar/runs/gate_probe_v1.jsonl`.

- [ ] **P1.2 — Record the verdict and ripple it into the draft.**
  Write the outcome into `QUERY_SET_DRAFT_v1.md` §C (annotate "G2 = PASS/EMPTY", "G3 = PASS/EMPTY",
  "G4 = resolved/clarify/not-found") — the draft's labels depend on it.
  If G2 AND G3 are both EMPTY: STOP, block for input (no-op eval).

---

## Phase 2 — Entity harvest → `entities.json`

**Files:** Create `accounts/hirafoods-ar/entities.json`

- [ ] **P2.1 — Harvest real entities from the workspace** (probe output from P1 + the user-shared
  chats payload, group "Laxmi Agency + Hirafoods", 2026-10-05 window). Write `entities.json` with
  the fields the generator reads: customers (master form + seen alias forms), invoices, groups,
  money anchors.
  Expected minimum: `Lakshmi Agencies & Co 84` (master) ↔ `Laxmi Agency` (alias), `INV-4007`,
  `INV-4009`, `INV-4011`, `INV-4012`, `INV-4013`, `₹7,60,000`, `₹1,460.88`.

- [ ] **P2.2 — Probe resolution on the typed forms** before alias rows are written:
  run the "Lakshmi Agencies ka outstanding kya hai?" / "Laxmi wale ka kya status hai?" pair and
  record whether the agent resolves, clarifies, or guesses. Never let an alias row be graded
  ANSWER unless a probe shows it resolves.

---

## Phase 3 — Query-set generation (generator-owned xlsx)

**Files:** Create `scripts/gen_ar_hirafoods_queries.py`; output `accounts/hirafoods-ar/queries.xlsx`

- [ ] **P3.1 — Write the generator** mirroring `scripts/gen_ar_user_queries.py`:
  Format A sheet named `Chat Queries`; bold col A = category header; col A query, col D
  `expected_tool` (wire surface only — D6), col E `expected_behavior`. Source rows = the 32-row
  draft grid (`QUERY_SET_DRAFT_v1.md` §B/§B2/controls), with G2/G3/G4 adjustments applied.
  The generator **owns** the xlsx; no hand-edits after generation.

- [ ] **P3.2 — Generate and verify.**
  Run: `python scripts/gen_ar_hirafoods_queries.py`
  Expected: `accounts/hirafoods-ar/queries.xlsx` with exactly 32 data rows.
  Verify: `python -c "import openpyxl;ws=openpyxl.load_workbook('accounts/hirafoods-ar/queries.xlsx')['Chat Queries'];print(sum(1 for i in range(2,ws.max_row+1) if ws.cell(i,1).value and not (ws.cell(i,1).font and ws.cell(i,1).font.bold)))"`
  Expected: `32`.

- [ ] **P3.3 — Show the set for approval before running** (standing rule). Paste the 32-row table
  (query + expected_behavior) and stop. Do not proceed to P4 on a silent approval.

---

## Phase 4 — Probe run (quota / init / parser gate)

- [ ] **P4.1 — Run 3 representative rows.**
  Run: `python scripts/run_agent_evals.py --account hirafoods-ar --only 1,11,27`
  (1 = ledger LOOKUP, 11 = invoice LOOKUP, 27 = CLARIFY control)
  Expected: three 200s, non-empty responses where the gate says data exists, no `402`/`422`,
  the parser captures the full ui-markdown answer (not a truncated block).

- [ ] **P4.2 — Inspect the three rows** in `accounts/hirafoods-ar/runs/query_results_v1.jsonl`
  before the full run: response non-empty, `status_sequence` recorded, no unexpected park.

---

## Phase 5 — Full run (metered; requires explicit green-light)

- [ ] **P5.1 — Run the full set.**
  Run: `python scripts/run_agent_evals.py --account hirafoods-ar`
  Expected: `manifest.json` created; 32/32 rows; 0 errors. If a mid-run failure occurs, resume
  with `--resume 1` (never re-run from scratch; never overwrite).

- [ ] **P5.2 — Verify completeness.**
  Run: `wc -l accounts/hirafoods-ar/runs/query_results_v1.jsonl` → `32`
  Run: `python scripts/eval_cli.py summary hirafoods-ar v1 --json` → outcomes tally, error count 0.

---

## Phase 6 — Judged pass (the classifier cannot be trusted for AR)

**Files:** Modify `scripts/analyze_ar_run.py` (+ `--account`, default unchanged = `ar-agent`)

- [ ] **P6.1 — Generalize the analyzer.**
  Run: `python scripts/analyze_ar_run.py --account hirafoods-ar --version 1`
  Expected: bucket counts + behavior matrix + tool accuracy (strict/lenient) + format bans +
  latency, written to `accounts/hirafoods-ar/runs/analysis_v1.json`.

- [ ] **P6.2 — In-session judged pass over `no_data` + `marginal`.**
  Read every `no_data`/`marginal` row and the empty-section-block answers, and override the
  bucket by hand (v1 lesson: the AR answer format trips the `no_data` regex while the headline
  carries the real answer). Write `accounts/hirafoods-ar/runs/judgments_v1.jsonl`, one verdict
  per inspected row, with the quoted evidence.

---

## Phase 7 — Readout + dashboard

**Files:** Create `accounts/hirafoods-ar/EVAL_READOUT_v1.md`;
Modify `scripts/render_ar_dashboard.py` (+ `--account`, currently hardcodes `accounts/ar-agent/`)

- [ ] **P7.1 — Write `EVAL_READOUT_v1.md`** mirroring the AR v1 readout structure: headline,
  raw-vs-judged table, behavior matrix, tool-surface drift status, the gates (G2/G3/G4 outcomes),
  B2 boundary confirmation, findings with owners, limits.
- [ ] **P7.2 — Render the dashboard.**
  Run: `python scripts/render_ar_dashboard.py --account hirafoods-ar`
  Expected: `docs/hirafoods-ar/index.html` (two-tab: plain-language Overview + For-developers),
  quotes pulled from the run file at build time.
- [ ] **P7.3 — Visual QA** (memory rule: never declare done on file size). Open the page in
  Playwright/Chromium, screenshot, confirm the overview renders, scorecard tiles show real
  numbers, and every quoted answer matches the run file.

---

## Phase 8 — Docs + commit

- [ ] **P8.1 — README index + PROJECTS.md** updated in the same commit group: the plan, the
  readout, the new account dir, and the newly parameterized scripts.
- [ ] **P8.2 — Commit locally** (`git add` / `git commit`) in `eval-dashboard`. **Do not push**
  without asking.

---

## Out of scope (explicitly)

- Any write/send to the HiraFoods workspace or its customers.
- Pushing to GitHub.
- Re-anchoring the Zainab v1 set (that is a separate v3 on a different workspace).
- Fixing the underlying defects the eval finds — this plan measures; fixes become their own cards.

---

## Verification Checklist

1. `python scripts/enumerate_templates.py --account hirafoods` lists
   `collection_and_account_receivables` for `c331ac11` (P0.1).
2. `accounts/hirafoods-ar/config.yaml` exists and carries the **AR app's** `wa_config_id`
   (…_917893797892_COP), not the ask-groups one (…_914040505050) (P0.2).
3. `accounts/hirafoods-ar/runs/gate_probe_v1.jsonl` exists and answers G2 + G3 explicitly (P1.1).
4. `accounts/hirafoods-ar/entities.json` contains the Lakshmi/Laxmi alias pair and the invoice set (P2.1).
5. `accounts/hirafoods-ar/queries.xlsx` has exactly 32 data rows and `expected_tool` values only
   from the wire surface (P3.2).
6. Probe run (`--only 1,11,27`) → 3 rows, no 402/422 (P4.1).
7. Full run → `wc -l query_results_v1.jsonl` = 32, error count 0 (P5.2).
8. `analysis_v1.json` + `judgments_v1.jsonl` exist; every `no_data`/`marginal` row has a hand verdict (P6.2).
9. `accounts/hirafoods-ar/EVAL_READOUT_v1.md` exists and states the G2/G3 verdicts (P7.1).
10. `docs/hirafoods-ar/index.html` renders with real numbers and quotes matching the run file (P7.3).
11. `git log --oneline -1` shows the local commit; `git status --short` clean; nothing pushed (P8.2).

---

## Risks

| Risk | Mitigation |
|---|---|
| Live client workspace touched by a write | All probes read-only (Safety 1); no send path anywhere in the plan. |
| No-op eval (both legs empty) | G2+G3 gate before generation; STOP if both empty. |
| Zops meter drains mid-run (402) | P4 probe before P5; `--resume` instead of re-running. |
| Tool-accuracy repeat of v1's 0/54 | D6: labels from the wire surface, not the harvest family. |
| Classifier mis-buckets AR answers | P6.2 mandatory judged pass over `no_data` + `marginal`. |
| Entity set drifts from what the workspace actually has | P1/P2 harvest from the workspace itself; alias rows only after a resolution probe. |
