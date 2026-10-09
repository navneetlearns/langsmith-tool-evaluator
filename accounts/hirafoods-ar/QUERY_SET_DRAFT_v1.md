# AR Agent (collection_and_account_receivables) — HiraFoods Query Set Draft v1

**Account:** `accounts/hirafoods-ar/` (proposed) · workspace `c331ac11-c3e8-4d42-a8d6-b8b04127354c`
(phone 4040505050) · lane `collection_and_account_receivables`
**Draft date:** 2026-10-08 · **Status:** DRAFT — for user approval before any generator/xlsx write or run.
**Entities source:** user-shared chats/context payload (2026-10-05 window, group "Laxmi Agency + Hirafoods").

Grading vocabulary: **ANSWER** · **CLARIFY** · **REFUSE** · **CHAT** · **MIXED**; capability-gap rows
grade NEAREST_SHAPE (marginal, not fail). Every ANSWER must carry the AR honesty contract
(hedged unconfirmed claims, verbatim quoted text + sid, graceful empties, identity never guessed,
money in major-unit INR).

---

## A. Real entity inventory (from the user's sample — the only entities allowed in this set)

| Entity | Forms seen | Notes |
|---|---|---|
| Customer | "Lakshmi Agencies & Co 84" (sender) · "Laxmi Agency" (group title) · "Lakshmi" | Live alias mismatch — resolution must be probed; bare "Laxmi" rows are CLARIFY controls |
| Group | "Laxmi Agency + Hirafoods" · channel `49cc94d3-9d51-4f2c-be92-9f8313c8bc89` | |
| INV-4007 | dispatched 5-Oct, delivery expected 7-Oct; customer: "All settled from our side" | claim vs ledger state |
| INV-4008 | customer checking; team: "checking with the godown… will confirm shortly" | open thread |
| INV-4009 | payment link/UPI sent ₹7,60,000; customer: "let me check with accounts and revert by 8 PM" | unconfirmed claim + same-day report-back |
| INV-4011 | customer: "collections are slow, INV-4011 by 10-Oct" | dated promise |
| INV-4012 | team: "has now been reconciled" | team-side claim |
| INV-4013 | customer: change qty to 30 cases Diamond Juice Strong before dispatch; team: noted | change request (dispute-adjacent) |
| Money | ₹7,60,000 (INV-4009) · ₹1,460.88 credit terms due 20-Oct (order 12 cases Ultra Biscuits Regular 100g) | major-unit strings expected |
| Non-AR noise | Ultra Biscuits Regular stock/reserve · Classic Toothpaste Strong 24 cases · MH34 GH 7357 dispatch · rates | REFUSE control fodder |

---

## B. Query matrix (draft)

### R1 — customer-anchored

| # | Cell | Query (register) | Exp. | Answered from | Note — what the agent should say |
|---|---|---|---|---|---|
| 1 | R1×LOOKUP | "Lakshmi Agencies ka kitna baaki hai?" | ANSWER | customer_balances | **LEDGER GATE** — hedge if only WA signals available |
| 2 | R1×LOOKUP-alias | "Laxmi Agency ka outstanding kya hai?" | CLARIFY/ANSWER | resolve_ar_customer + balances | alias vs master; clean resolve OR honest ask, never guess |
| 3 | R1×LOOKUP-Q2 | "Lakshmi ne bola tha INV-4007 ka paid kar diya — confirm hua?" | ANSWER | objects(payment_claim, reported) + evidence | hedge: "customer said settled; ERP/bank status X"; quote the message + sid |
| 4 | R1×LOOKUP-Q4 | "Lakshmi ne payment ka kya promise kiya tha?" | ANSWER | objects(commitment) + evidence | quote "INV-4011 by 10-Oct" and "revert by 8 PM" rows |
| 5 | R1×LOOKUP-Q6 | "Lakshmi Agencies ke saath kya stuck hai?" | ANSWER | worklist/objects + evidence | INV-4008 godown-confirm open thread; evidence rows |
| 6 | R1×LIST-Q3 | "kaunsi party ne outstanding acknowledge kiya?" | ANSWER | objects(acknowledged) | list + cited sids |
| 7 | R1×LIST-Q2 | "kis-kis ne bola paid, par system me abhi pending hai?" | ANSWER | objects(reported, unconfirmed) + financials | hedged list; evidence per row |
| 8 | R1×LIST | "Lakshmi ke group me pichle hafte kya hua?" | ANSWER | activity | request-state summary + evidence |
| 9 | R1×RANK | "sabse zyada kis party ka payment baaki hai?" | ANSWER | customer_balances | **LEDGER GATE** |
| 10 | R1×RANK-Q7 | "kis party se last 3 din me koi baat nahi hui?" | ANSWER | activity recency | |

### R2 — invoice-anchored

| # | Cell | Query (register) | Exp. | Answered from | Note — what the agent should say |
|---|---|---|---|---|---|
| 11 | R2×LOOKUP | "INV-4009 ka payment aaya?" | ANSWER | invoices + objects | link sent ₹7,60,000 5-Oct, customer said revert by 8 PM — "sent, awaiting confirmation", hedged |
| 12 | R2×LOOKUP | "INV-4007 settle hua?" | ANSWER | invoices + objects | customer claimed settled; state the ledger truth |
| 13 | R2×LOOKUP | "invoice 4008 ka kya hua?" | ANSWER | invoices + threads | godown confirm pending; evidence rows |
| 14 | R2×LOOKUP | "INV-4013 ka status?" | ANSWER | invoices | qty-change request noted (30 cases Diamond Juice Strong) |
| 15 | R2×LIST | "konsi invoices abhi pending hain?" | ANSWER | invoices | list with amounts; ledger gate if amounts need balances |
| 16 | R2×LIST | "is hafte dispatch hue invoices?" | ANSWER | invoices + dispatch msgs | INV-4007 window evidence |
| 17 | R2×LIST-Q2 | "kis invoice ke liye party ne bola paid?" | ANSWER | objects(payment_claim) + invoices | INV-4007 row; hedge unconfirmed |
| 18 | R2×LIST-Q4 | "kis invoice ka payment kab tak aayega?" | REFUSE (observed) | objects(commitment) + invoices | **SEE B2** — live-tested 2026-10-08: this cell refuses with an offer; grade the refusal as PASS |
| 19 | R2×RANK | "sabse purani unpaid invoice konsi hai?" | ANSWER | invoices | **LEDGER GATE** |
| 20 | R2×SUM | "INV-4009 tak kitna payment aana hai?" | ANSWER | invoices aggregate | **LEDGER GATE** |

### D — derivations

| # | Cell | Query (register) | Exp. | Answered from | Note |
|---|---|---|---|---|---|
| 21 | D×SUM | "total outstanding kitna hai?" | ANSWER | customer_balances | **LEDGER GATE** |
| 22 | D×SUM | "is mahine kitna payment aaya?" | ANSWER | resolved payments | |
| 23 | D×LIST-Q4 | "aaj kis-kis ne payment ka promise kiya?" | ANSWER | worklist/commitment | |
| 24 | D×RANK | "top 5 party by outstanding" | ANSWER | customer_balances | **LEDGER GATE** |
| 25 | D×TREND | "outstanding pichle hafte se badha ya ghata?" | ANSWER | position snapshots | gate: snapshots exist? |
| 26 | D×LIST | "kis invoice par credit terms hain?" | ANSWER | invoices | ₹1,460.88 due 20-Oct anchor |

### Controls (must exist, must be graded)

| # | Cell | Query | Exp. | Why |
|---|---|---|---|---|
| 27 | C-CTX | "Laxmi wale ka kya status hai?" | CLARIFY | alias vs master — a *correct* clarify is a pass |
| 28 | C-CTX | "aur INV-4011?" (referent-less follow-up) | CLARIFY | multi-turn referent handling |
| 29 | C-OOS | "Ultra Biscuits Regular ka stock kitna bacha?" | REFUSE | inventory ≠ AR; honest out-of-scope, no fabrication |
| 30 | C-OOS | "X ko supply band kar du?" | REFUSE | credit decision ≠ AR |
| 31 | C-OOS | "Diamond Juice Strong ka rate kya hai?" | REFUSE | pricing ≠ AR |
| 32 | C-GAP | "Lakshmi ke payment delay kyun hote hain?" | NEAREST_SHAPE | reasons-shape capability gap — graded marginal, not fail |

---

## B2. Live-observed boundary (2026-10-08 — user's copilot stream trace)

**Tested query:** "Show me overdue bills where the customer has already promised payment."

**Observed response (UI card, metadata `finance`, classification `analytical`, agent `ar`):**
> "Exact invoice follow-ups aren't supported in this analytical path yet. I can check the
> customers from that list, or you can ask for a fresh invoice search."
Run facts: 14.3s, 15,150 tokens, assistant `seller_copilot`, llm_provider `gpt-6-luna`.

**Reading:** the unsupported cell is the **invoice × WA-signal JOIN** (overdue bills → promises).
The agent explicitly offers the two supported paths around it: **customer-anchored** checks ("the
customers from that list") and a **fresh invoice search**. That matches the two-root grammar: the
roots work, the cross-product join is the gap. First documented account of this boundary on
c331ac11's AR analytical path.

**Grading consequence:** refusal-with-offer = **PASS-class** (honest boundary + actionable next
step), not a failure. Rows joining invoice × commitment/promise (18, and by extension 7, 16, 17
where the join is implied) carry **REFUSE-with-offer** as the expected behaviour until a probe
shows the fresh-invoice-search path actually answers them. Rows 4 and 23 (customer-side
promises) stay ANSWER-expectation — the offer explicitly keeps the customer path — pending probe.

**Config facts to mirror in `accounts/hirafoods-ar/config.yaml`:**
- wa_config_id used by the app on this workspace: `c331ac11-…_917893797892_COP` — **different**
  from the ask-groups config's `…_914040505050`; the eval account must use the AR app's exact
  wa_config_id, not copy ask-groups'.
- llm_provider: `gpt-6-luna` (luna family, as in AR design notes).

---

## C0. LIVE GATE VERDICTS — 2026-10-09 (read-only gate probe, `runs/gate_probe_v1.jsonl`)

Approved by the user 2026-10-09 ("the draft 32 queries you prepared yesterday is fine — those were
customer and invoice anchored … yes, approve"). Gates then answered live, all READ-ONLY:

| Gate | Verdict | Live evidence |
|---|---|---|
| G1 approval | **GREEN** | user approved the 32-row set verbatim, same day |
| G2 LEDGER | **GREEN** | `get_receivables` returned rows: total outstanding **₹57,77,21,622.19**; **14,592** pending invoices |
| G3 WA-SIGNAL | **GREEN** | `ar_payments_reported` returned 1 unresolved claim: **Lakshmi Agencies & Co 84 / INV-4007**, reported 05/10/2026 |
| G4 IDENTITY | **PARTIAL** | `Lakshmi Agencies` does **not** resolve (agent asks for mobile/code — honest); `Laxmi wale ka kya status hai?` resolves the customer but answers **order** status (`search_customers_master`+`list_orders`) instead of clarifying |
| G5 QUOTA | **GREEN** | 3-row probe (`--only 1,11,27`) 3/3 200s, 0 errors, no 402/422, avg 14.5s |
| B2 JOIN BOUNDARY | **DIFFERS FROM ZAINAB** | the invoice × WA-signal JOIN **answers** here (1 customer, 12 overdue bills, overdue balance ₹1,78,611.84) with a hedge that promise refs (INV-4008–INV-4012, INV-4011) don't match the receivables bill numbers |

Note for the user's model of the stack: the AR lane on this workspace mixes tool families on the
wire — the deployed 5-tool ERP contract (`get_receivables`, `search_customers_master`, …) **and**
the WhatsApp-signal family (`ar_payments_reported`, `ar_promises`), plus `list_invoices` /
`list_orders`. Ledger answers here come back from `get_receivables` directly; the finance hand-off
you described is therefore not the only path the eval will observe.

## C. Open gates (resolve before running)

1. **LEDGER GATE (rows 1, 2, 9, 19, 20, 21, 24, 25):** does `query_ar_financials` (`customer_balances`, `invoices`) return rows on c331ac11? WA data in OpenSearch feeds objects/activity; the outstanding/ledger cells need the ERP side. If empty → those rows drop to REFUSE/honest-fallback and the set becomes WA-signal-only (approved-once confirmed).
2. **Identity:** probe how "Laxmi Agency" vs "Lakshmi Agencies & Co 84" resolves before the alias rows.
3. **More user samples** — their own test queries + agent responses calibrate the labels above (every row's default here is the honesty contract from the AR profile).

## D. Status

- [x] User approves draft (or edits) — approved verbatim 2026-10-09
- [x] Generator script `scripts/gen_ar_hirafoods_queries.py` owns `accounts/hirafoods-ar/queries.xlsx` (no hand-edits) — 32 rows written
- [x] Probe 1–3 rows (`--only`) — quota/init/parser gate GREEN (3/3, avg 14.5s, no 402/422)
- [x] Full run — v2 DONE 32/32 rows, 0 errors, avg 16.3s, 0 format violations, 0 fabrication
- [x] Judged pass over no_data + marginal → `runs/judgments_v1.jsonl` (32 verdicts) + `EVAL_READOUT_v1.md` + dashboard `docs/hirafoods-ar/index.html` (Playwright QA PASS)

Result: **19/32 pass-class**; the 13 non-pass rows partition disjointly as 6 lookup-path
(name-resolution q1/q4/q5 · invoice-lookup q12/q14/q20) · 2 silent empty responses (q13, q28) ·
3 scope errors (1 over-refusal + 2 out-of-scope answers) · 2 reliability singletons (q9 tool-path,
q16 transient). Note *affected* ≠ *lost*: the name defect touched 5 rows and the invoice defect 6,
but q2/q32/q11 still behaved acceptably.
See `EVAL_READOUT_v1.md` for the findings and owners.