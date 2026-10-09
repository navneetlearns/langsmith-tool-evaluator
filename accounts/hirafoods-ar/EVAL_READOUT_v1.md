# AR Agent Eval — HiraFoods EVAL_READOUT_v1

- **Date:** 2026-10-09 · **Agent:** `collection_and_account_receivables` (ZoChief seller-copilot, AR / collections)
- **Workspace:** HiraFoods c331ac11-c3e8-4d42-a8d6-b8b04127354c / 4040505050 (live AU Bank client workspace — every probe READ-ONLY)
- **Lane check:** the AR template IS deployed and enumerable here now: `code=collection_and_account_receivables`, id `26fc7c56-f2f6-4fe6-823c-91d0dfbbc1fe`, system_prompt 11,984 chars (5-tool read-only ERP contract). The 2026-09-24 note that this endpoint never lists AR codes is stale.
- **Set:** approved verbatim by the user 2026-10-09 (`accounts/hirafoods-ar/QUERY_SET_DRAFT_v1.md` → `queries.xlsx`, generator-owned, 32 rows: 24 ANSWER / 3 CLARIFY / 4 REFUSE / 1 NEAREST_SHAPE)
- **Runs:** `runs/gate_probe_v1.jsonl` (6 read-only gate probes) · `runs/query_results_v1.jsonl` (3-row quota probe) · `runs/query_results_v2.jsonl` (32 rows, the eval)
- **Artifacts:** `runs/analysis_v2.json` (deterministic) · `runs/judgments_v1.jsonl` (hand verdicts) · dashboard `langsmith-tool-evaluator/docs/hirafoods-ar/index.html`

## Headline

The AR agent **works on this workspace when the question is workspace-level or WhatsApp-anchored** —
total outstanding, pending invoices, collections, claims and promises all came back with real
numbers — and it produced **zero format violations and zero fabrications**. It fails on **two
lookup paths that matter to a collections user**, and one of them is the same defect class AR v1
found on Zainab:

1. **The master resolver cannot resolve the customer name the business actually uses.** Every
   Lakshmi row that starts from the name (`Lakshmi Agencies`, `Laxmi Agency`) returns *"koi match
   nahi mila"*. The WhatsApp-signal leg resolves the same customer instantly as **Lakshmi Agencies
   & Co 84**. The resolver gap *touches* 5 rows (q1, q2, q4, q5, q32) — three of them (q1, q4, q5)
   return no answer at all, while q2 and q32 still ask honestly for a mobile number.
2. **Invoice numbers the message store knows are not findable in the ledger.** `INV-4007`,
   `INV-4009`, `INV-4013` → *"invoice record nahi mila"*, while the same invoices are quoted in the
   WhatsApp claims (q3, q17) and 14,592 pending invoices exist (q15). 6 rows are affected
   (q11–q14, q19, q20); 5 lose the answer, and only q11's refusal is correct-by-contract.

Also: **2 silent empty responses** (q13, q28) on determinate questions, and **2 over-reaches** —
non-AR questions (product stock, product rate) were *answered* rather than refused because product
tools are wired into the lane (q29, q31).

Raw vs judged (the classifier cannot be trusted for this answer format — the v1 lesson repeats;
it scored 30/32 "success" while 6 rows in fact returned nothing usable):

| Bucket | Raw (script) | Judged (hand) |
|---|---|---|
| Solid answers | 30 success | 7 |
| Good but hedged / limited | — | 6 |
| Correct clarify | 0 parks* | 3 |
| Correct refusal | — | 3 |
| Under-delivered (supported thing refused/not fetched) | — | 2 |
| Tool failure surfaced as "try later" | — | 1 |
| Lookup failure — resolver / invoice | — | 6 |
| Silently empty | 2 fail | 2 |
| Answered out of scope | — | 2 |

\* `parks=[]` in the raw pass: q13/q28 come back **empty with no `interrupt` event**, so the runner
cannot even flag them as clarify parks — they are indistinguishable from failure.

**Pass-class = 19/32 (59%).** The 13 non-pass rows partition disjointly into: **6 on the two lookup
paths** (q1, q4, q5 name-resolution; q12, q14, q20 invoice-lookup), **2 silent empty responses**
(q13, q28), **3 scope errors** (q19 over-refused a supported capability; q29 and q31 answered out of
scope), and **2 reliability singletons** (q9 took the failing tool path for a question class q24
answers cleanly; q16 surfaced a transient failure as "try again later"). Note the difference between
*affected* and *lost*: the resolver defect touched 5 rows and the invoice defect 6, but q2/q32/q11
still behaved acceptably — which is why the affected counts exceed the 13 rows actually lost.

## Behaviour matrix (expected → observed, 32)

| Expected | Observed | Count | Rows |
|---|---|---|---|
| ANSWER | data answer | 23 | (of which 7 are solid, the rest narrowed/hedged) |
| ANSWER | empty | 1 | q13 |
| ANSWER | lookup failure phrased as "not found" | 6 | q1, q4, q5, q12, q14, q20 (q9/q19 = tool-refusal/under-delivery) |
| CLARIFY | asked a proper question | 2 | q2, q27 |
| CLARIFY | answered something adjacent | 1 | q8 (group disambiguation — partial) |
| CLARIFY | empty | 1 | q28 |
| REFUSE | correct refusal | 2 | q11, q30 |
| REFUSE | answered anyway (out of scope) | 2 | q29, q31 |
| REFUSE | over-refused a supported thing | — | (q19 sits in the ANSWER→under-delivery row) |
| NEAREST_SHAPE | honest, no fabricated cause | 1 | q32 |

## Tool surface — a THIRD mix, neither the plan's nor the prompt's

D6 (from the 2026-10-08 plan) assumed the wire family would be the Zainab AR family
(`query_ar`, `get_ar_evidence`, `query_ar_financials`, `resolve_ar_customer`, `get_ar_schema`).
**Not one of those fired.** The deployed template's 5-tool ERP contract
(`search_customers_master`, `getCustomerAccountData`, `getCustomerAnalytics`, `get_receivables`,
`get_collections`) fired, **alongside** the WhatsApp-signal family and adjacent-domain tools:

`search_customers_master` 5 · `get_receivables` 5 · `list_invoices` 3 · `search_messages` 2 ·
`ar_promises` 2 · `getCustomerAccountData` 2 · `search_product_master` 2 · `spawn_filter_agent` 1 ·
`ar_payments_reported` 1 · `get_channel_data` 1 · `search_threads` 1 · `list_dispatch_notes` 1 ·
`get_collections` 1 — **13 distinct tools, 0 from the query_ar family.**

- Strict tool accuracy **9/27 (28%)**, lenient **21/27 (66%)** — but strict is a *label-surface*
  artifact again, not agent error: the labels were written from the 6-probe gate surface, and the
  full run deployed more tools (invoice lookups went to `list_invoices`, claims to `search_messages`).
- `search_product_master` (2 calls) and `list_dispatch_notes` / `list_orders` are **wired into the
  AR lane** and are what produced the over-reach rows. This is the actionable tool-surface finding:
  the AR lane is not tool-scoped to receivables.
- Observe the split that causes finding #2: invoice questions route to **`list_invoices`** (ledger
  series, which does not hold INV-4xxx), while WhatsApp invoice mentions come back through
  **`search_messages`**. Two stores, two invoice namespaces, no reconciliation.

## Gates (live, read-only) — all green, one assumption overturned

| Gate | Verdict | Evidence |
|---|---|---|
| G1 approval | GREEN | user approved the 32-row draft verbatim |
| G2 LEDGER | GREEN | `get_receivables`: total outstanding **₹57,77,21,622.19**; **14,592** pending invoices |
| G3 WA-SIGNAL | GREEN | `ar_payments_reported`: 1 unresolved claim — **Lakshmi Agencies & Co 84 / INV-4007** (reported 05/10/2026) |
| G4 IDENTITY | **PARTIAL** | `Lakshmi Agencies` does not resolve; `Laxmi wale ka kya status hai?` resolves the customer but answered **order** status (probe) / clarified (**run q27**) — **behaviour differs between the probe and the run** |
| G5 QUOTA | GREEN | 3-row probe 3/3, 0 errors, no 402/422 |
| B2 JOIN BOUNDARY | **INVERTED vs Zainab** | the invoice × WA-signal JOIN **answers** here (1 customer, 12 overdue bills, overdue ₹1,78,611.84) with a names-don't-match hedge — Zainab's plan-level D5 "REFUSE-with-offer = PASS" does not apply to this workspace |

**Model-of-the-stack correction (user's own question, 2026-10-08):** you said the AR agent calls the
finance agent for ledger queries. On this workspace the ledger answers arrived directly from
`get_receivables` inside the AR lane (₹57.77Cr, 14,592 invoices, collections total) — the finance
hand-off is not the only path, and `finance` is a separate deployed template (201-char prompt) here.

## Numbers returned (all live, 2026-10-09)

| Metric | Value | Source |
|---|---|---|
| Workspace total outstanding | ₹57,77,21,622.19 (₹57.77 Cr) | q21 = gate probe, identical |
| Pending invoices | 14,592+ | q15, gate probe |
| Collections 01–09 Oct 2026 | ₹36,255.75 across 4 payments | q22 (server-calculated total) |
| Highest customer balance | ₹20.48L | q24 (top-5 list) |
| Lakshmi overdue position | 12 overdue bills · ₹1,78,611.84 overdue | gate probe |
| Lakshmi acknowledgement | INV-4011 **₹5,48,000**; INV-4008/4009/4010/4012 acknowledged, amount unspecified | q6 |
| Lakshmi commitments | by 10-Oct; ₹1,460.88 by 20-Oct | q23 (matches the draft anchors) |
| INV-4007 | claim "All settled from our side", unresolved | q3, q7 |

**No 10×/100× scaling inconsistency was found** (unlike Zainab v1's Interworld 40-lakh-vs-72-crore
pair). The one thing a human should eyeball: q24's highest party ₹20.48L against a ₹57.77Cr workspace
total is a wide spread — verify on the AR dashboard that ₹20.48L is a genuine top-customer balance
and not a truncated page.

## Findings (with owners)

1. **Resolver cannot match the WhatsApp display name to the master record** — *owner: AR agent /
   data team.* `Lakshmi Agencies` (the name the business types, and the name in the customer's own
   messages) returns no match while the signal leg resolves `Lakshmi Agencies & Co 84` fine. Fix =
   alias matching on the master search, or resolve from the signal side's customer identity. Cost
   today: 5 rows no user value.
2. **Invoice-number lookup gap across two namespaces** — *owner: AR agent / data team.* `INV-4xxx`
   invoices exist in the message store and in the receivables summary but `list_invoices` /
   `getCustomerAccountData` return "not found" for INV-4007/4009/4013. Same class as v1's invoice
   17346. Decide: are the WA invoice numbers a different series than the ledger's, or is the lookup
   broken? Either way the agent must say *which* series it searched.
3. **Silent empty responses on determinate questions (q13 "invoice 4008 ka kya hua?", q28 "aur
   INV-4011?")** — *owner: agent platform.* Empty body, no tool call, no `interrupt` event, so the
   runner cannot even flag a park. This is the v1 "clarify question never reaches the wire" defect,
   now also appearing with **no** event at all.
4. **The AR lane answers non-AR questions** — *owner: agent platform.* Product stock (q29) and
   product rate (q31) were answered with real product data (`search_product_master`). Either the
   lane should refuse these or the REFUSE contract in the deployed prompt is not being followed.
5. **Tool choice for one question class is not deterministic** — *owner: agent platform.* q9
   ("sabse zyada kis party ka payment baaki") failed to fetch via `getCustomerAccountData`; q24 (top-5
   by outstanding) answered cleanly via `get_receivables`. Same intent, different path, one works.
6. **Over-refusal on a supported capability** — *owner: agent platform.* q19 refused "unpaid status"
   although q15/q21/q25 read receivables/overdue fine.
7. **Register inconsistency** — *owner: product.* Answers alternate Hinglish / Devanagari (q14) /
   English (q24) within one run on Hinglish queries.
8. **Expected-tool labels are a surface artifact** (28% strict) — *owner: eval.* Re-map labels to the
   13-tool observed surface before v3 (this is precisely what v1's action 4 asked for, and the
   surface changed again since).

## Limits

- One workspace, one run, 32 rows; labels are hand-set, so "tool accuracy" is a *label* metric.
- Judged pass is a human verdict with quoted evidence per row (`judgments_v1.jsonl`); no ground-truth
  baseline exists for these answers.
- Live client workspace: everything was read-only. The AR contract "drafting never sends" was never
  exercised — no send path exists in the harness.
- Hedging rate 18/30 (56%) is measured with a Hinglish-aware regex added during this run; the
  English-only version scored 2/30 and is wrong for this workspace.

## Files

- `accounts/hirafoods-ar/{config.yaml, entities.json, QUERY_SET_DRAFT_v1.md, queries.xlsx}`
- `accounts/hirafoods-ar/runs/{gate_probe_v1.jsonl, query_results_v1.jsonl, query_results_v2.jsonl, manifest.json, analysis_v2.json, judgments_v1.jsonl}`
- `scripts/{probe_ar_hirafoods_gate.py, gen_ar_hirafoods_queries.py}` (new) ·
  `scripts/{analyze_ar_run.py, render_ar_dashboard.py}` (generalized to `--account`)
- Dashboard: `langsmith-tool-evaluator/docs/hirafoods-ar/index.html`
