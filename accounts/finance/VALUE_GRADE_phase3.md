# Finance Agent — Value Analysis Phase 3 (shadow-answer skeletons + per-query grade)

**Run:** v1 (2026-09-18) · 30 CFO queries (20 answered, 9 clarify-parks, 1 tech fail)
**Method:** for each query family, the ideal CFO/accountant answer skeleton was written FIRST
(a competent accountant handing the owner a memo), then every actual response was graded
element-by-element against it (present / partial / missing). No LLM judge involved — this is
direct reading of all 20 response texts.
**Value ladder:** L1 fetch · L2 paraphrase/padding · L3 structured finding · L4 insight + decision
support · L5 proactive CFO partner.

---

## 1. The 5 family skeletons (competent-accountant baseline)

**Family A — Cash / chase / collections (q3 q4 q9 q10 q26 q30)**
A1 Size the problem: total outstanding + debtor count + DSO/collection rate (only if valid)
A2 Name the accounts with ₹ + payment recency (days since last payment)
A3 Prioritize with reasoning: amount × staleness, escalation tiers
A4 Flag fastest-deteriorating accounts (balance delta, not just level)
A5 Actions: who to call today, what to demand (dated commitments), when to escalate
A6 Honest gaps: what cannot be quantified + why (overdue/recoverability)

**Family B — Credit discipline (q11 q8 q23 q7)**
B1 Exposure size (outstanding, DSO, collection rate)
B2 Per-customer credit-vs-payment pattern → outliers (balance × history)
B3 Verdict: credit too loose? (with honest "no external benchmark" caveat)
B4 Actions: review limits/terms/order-release, tighten cadence, monitor KPIs

**Family C — Profitability / margins (q2 q14 q15 q16 q27)**
C1 What CAN be computed (sales, collection, concentration)
C2 Boundary, stated once and precisely: margin/profit not tracked
C3 Best proxy + its limits (purchases ≠ COGS; volatility ≠ growth)
C4 Cross-metric insight (per-customer sales vs receivables tie-up)
C5 Actions: what data to start recording, what to review commercially

**Family D — Expenses / payables (q12 q13 q17 q18)** — refusal family
D1 Named boundary: what's absent (expense GL, payables, COGS)
D2 What CAN be worked instead (sales/payments/ledger)
D3 One-line actionable offer

**Family E — Anomaly / strategic review (q1 q19 q20 q21 q22 q24 q25 q28 q29 q30)**
E1 Ranked top risks/movements by materiality (₹ + why it matters)
E2 Cross-check views for inconsistencies (movement vs ranking vs cut-off)
E3 Hypothesis per anomaly (billing lag, duplicate postings, cut-off timing)
E4 Verification path: which reconciliations to run next
E5 Decision link: what this changes (credit, chase, planning, replenishment)

---

## 2. Per-query grade (20 answered)

Legend: ✓ present · ◐ partial · ✗ missing · REF = correct refusal (separate lens)
Parks (q3 q5 q6 q7 q8 q14 q23 q24 q29) and fail (q20) have no response to grade — see §4.

| q | tier | family | level | skeleton coverage | strongest element | main defect |
|---|---|---|---|---|---|---|
| q1 | T1 | E | L4 | A1◐ A2✓ A3✓ A5✓ E1✓ | actions + honest gaps | literal "[unverified]" text ×2 (grounding guard left placeholders); no portfolio outstanding (says "not in supplied rows") |
| q2 | T3 | C | L4 | C1✓ C2✓ C3✓ C4◐ C5✓ | boundary phrased precisely, purchases≠COGS explained | receivables block copied from other answers; no per-customer sales-vs-outstanding |
| q4 | T2 | A | **L5** | A1✓ A2✓ A3✓ A4✓ A5✓ A6✓ | fastest-worsening tracked separately (Radha +₹9,66,376, Ganesh, Jai) + "hold credit for fastest risers" | "days days" |
| q9 | T2 | A | **L5** | A1◐ A2✓ A3✓ A4✓ A5✓ | first-wave/second-wave/escalation operating plan — the closest thing to a CFO call sheet | boilerplate + same top-5 block as q4/q11/q22/q25/q26/q28/q30 |
| q10 | T1 | A | L3 | A1✓ A6✓ A2◐ | honest "overdue/recoverability cannot be quantified" + why, then actionable substitute | answer is essentially a quantified refusal — correct, but thin (1 figure in 1,777 chars) |
| q11 | T2 | B | L4 | B1✓ B2◐ B3✓ B4✓ | verdict + honest "no external benchmark" caveat; unpaid-invoice count (14,556) | no per-customer credit-vs-payment outlier table (just the top-5 again) |
| q12 | T1 | D | REF ✓ | D1✓ D2✓ D3✓ | boundary precise (payables under-recorded) | "…ledger data.. I can work" double-period glitch |
| q13 | T1 | D | REF ✓ | D1✓ D2✓ D3✓ | names exactly which pieces are missing (payables, cash/bank, payment timing) | ".." glitch |
| q15 | T3 | C | L4 | C1✓ C2✓ C3✓ C4◐ C5✓ | the volume reveal: invoices 5,642→117, ₹1,59,48,487→₹11,97,739 — real comparative insight | margin verdict correctly refused; stock/segment reasoning thin |
| q16 | T3 | C | L4 | C1✓ C2✓ C3✓ C4✓ C5✓ | cross-metric: Ganesh sales ₹3,62,161 vs outstanding ₹4,94,550 (revenue tying up cash); concentrations 50.3% / 49.6% | no boilerplate (good); unnamed-product attribution limits |
| q17 | T1 | D | REF ✓ | D1✓ D2◐ D3◐ | structured refusal with sections | "0 figures verified" footer reads odd for a refusal |
| q18 | T1 | D | REF ✓ | D1✓ D2✓ D3✓ | clean + fast | ".." glitch |
| q19 | T3 | E | **L5** | E1✓ E2✓ E3✓ E4✓ E5✓ | the strongest answer in the set: challenges period-matching of collections/invoicing, concentration review, forecasting caution (invoice counts 1,640→5,642→117) | boilerplate; asks "would challenge" but answer borrows standard top-5 block |
| q21 | T3 | E | **L5** | E1✓ E2✓ E3✓ E4✓ E5✓ | the standout: caught cross-view inconsistency (Ganesh ₹8,01,148 movement vs ₹4,94,550 ranking; negative starting balances) + hypotheses (cut-off, duplicates) + verification path | boilerplate |
| q22 | T3 | E | L4 | E1✓ E2◐ E3◐ E5✓ | off-P&L framing + payment-to-sales ratio (0.02 for Ganesh — genuinely new metric) | "days days"; ratio not explained to lay reader |
| q25 | T3 | E | L4 | E1✓ E2◐ E4✓ E5✓ | multi-area: receivables + inventory sell-through gate (no last-sale-date → pause replenishment) | boilerplate; inventory insight appears only here, so cross-query consistency of facts is uneven (fresh vs cached) |
| q26 | T2 | A | L3/L4 | A1✓ A2✓ A5✓ A6✓ | honest scope: "indicates receivables-driven pressure, not a complete liquidity forecast" | the forward-look element is one line; rest is the standard top-5 chase block |
| q27 | T3 | C | REF ✓ | D1✓ D2✓ D3✓ | precise on what a real answer needs (P&L, COGS, cash/bank) | ".." glitch |
| q28 | T2 | E | L4 | E1✓ E2◐ E5✓ | DSO vs measured period: 120.8d of a 167d window = 72% of the period parked in receivables — the sharpest ratio insight in the set | boilerplate; "growth consuming working capital" answered via receivables only |
| q30 | T3 | E | L4 | E1✓ E2◐ E4✓ E5✓ | surfaced a 6th entity (Jai Enterprises 151 days) beyond the standard top-5 | boilerplate; first-worry answer = chase list re-run |

## 3. The headline finding: no data-dump answers, but TEMPLATE REUSE across the conversation

- Every single answer is well-structured, grounded, ends in actions — **zero pure L1/L2 data-dumps in the set**. The user's worst-case hypothesis did not materialize at the individual-answer level.
- The repetition problem is CROSS-ANSWER, not inner-answer:
  - same reconcile boilerplate ×14 (Phase 1),
  - the same top-5 customer block reappears in most answers (measured: Ganesh Retail Traders in 12 answers, Jai Wholesalers / Om Enterprises in 10, Krishna Traders LLP / Om Wholesalers in 9 of 20),
  - the KPI trio is recycled as the "insight" across answers (measured: ₹17,48,30,219 in 6 answers, DSO 120.8 in 4, 33.8% collection in 7).
  A CFO asking 8 different questions gets 8 answers that lean on the same evidence block — each is fine in isolation; as a conversation it reads repetitive and, worse, signals the agent isn't finding query-specific evidence for queries where specific evidence exists (only q21/q30/q28 found genuinely different facts).
- Non-obvious per-answer defects: literal "[unverified]" placeholders (q1, grounding-guard artifact — must never reach a user), "days days" duplicate-unit in 6 data answers (q1 q4 q9 q11 q22 q26 — 30 occurrences total), ".." double-period before "I can work" in 4 refusals (q12 q13 q18 q27), q17's "0 figures verified" footer.

## 4. Parks and the fail (no response graded)

- CLARIFY parks (9): q3 q5 q6 q7 q8 q14 q23 q24 q29. Parked, not failed — but 4 of them were ANSWER-labeled (q7 q8 q24 q29) and q14 (margin pressure) is answerable per the q2/q15 pattern → **gate noise cost = at least 5 lost answers** worth recouping via classify-gate tuning (temperature / force-clarify terms).
- q20: technical fail (IncompleteRead at 244.7s) — the anomaly-type query the agent CAN answer (q21 proved it), so this is a latency/robustness loss, not a capability verdict.
- Value realized from the 30 asks: 13 L4/L5 answers (43%), 1 L3, 5 correct refusals (17%), 9 parks, 1 fail — the productive number for owners is **13 of 30 queries got CFO-grade decision support; 5+ more were lost to gate noise + 1 to a backend drop.**

## 5. Owner action list (Phase 3 lens)

1. **P1 — Kill cross-answer template reuse (the real repetition):** the same top-5/KPI block must not be re-emitted as the "insight" for 8 different questions. Per-family evidence selection: chase-family questions may share exposure data, but credit/margin/anomaly questions must get query-specific evidence (q21/q28/q30 proved it exists). This is a prompt-format change (evidence selection per intent), not a model change.
2. **P1 — "days days" duplicate unit** in ~9/15 answers (format-node regression, one-line fix).
3. **P1 — Grounding guard must never emit literal "[unverified]"** (q1): either re-probe, reason from adjacent data, or drop the sentence entirely.
4. **P2 — Reconcile warning placement:** emit once per conversation/thread, not per answer (14× today). Needs thread-state awareness or a position rule (only in the first answer of a thread).
5. **P2 — Refusal grammar glitch** "dataset.. I can work" (double period, 4 refusals).
6. **P2 — Classify gate noise cost:** 5+ answerable queries parked (q7 q8 q14 q24 q29) — tie to the EVAL_READOUT P1 clarify-gate item with the count as the business impact.
7. **P3 — q17 "0 figures verified" footer** on a refusal is confusing; strip the process footer for refusal outputs.

## 6. Method notes / what NOT to trust

- Grades are my direct reading against the skeletons — no judge involved, but also no second reader; Phase 2 (calibrated judge) exists to catch what I missed, and the user can re-grade any row.
- Skeleton "coverage" is element presence, not quality of the element; a ✓ on A5 ('actions') doesn't measure whether the actions are right for THIS business.
- Tier tags (T1/T2/T3) approved by user (2026-09-18 review); refusal bucket = q12 q13 q17 q18 q27.

Data: responses read from runs/query_results_v1.jsonl · Phase 1 metrics: runs/value_phase1_v1.json · script: scripts/analyze_finance_value.py