#!/usr/bin/env python3
"""Rebuild accounts/finance/queries.xlsx — Finance agent eval query set (2026-09-18, v2).

USER-PROVIDED SET (2026-09-18): 30 CFO-level insight questions, used VERBATIM and in the user's
order. Persona: CFO / accountant. Domain: ERP ONLY.

Labeling follows the CLASSIFY GATE's own decision order (trace-verified):
  1. needs_clarify — vague/judgment term with >1 metric reading or open review scope
     ('healthy', 'risky', 'looks wrong', 'best customer' family) -> CLARIFY, NO_TOOL.
     A clarify turn PARKS with a question and NO tools; grading a parked turn as
     under-delivery would be wrong.
  2. out_of_scope — genuinely absent data: profitability (COGS/margin/P&L), cash & bank,
     expenses (P&L), net supplier payables (under-recorded) -> REFUSE, NO_TOOL.
  3. else -> ANSWER with the gold metric(s). The finance agent executes catalogue SQL on the
     backend and streams NO tool events (observed 2026-09-18) — expected_tool is the INTENT
     label for review, not an observable tool call.

REAL-ENTITY RULE: this set is deliberately entity-free (user-provided). Placeholder tokens still
banned. The AR set (gen_ar_agent_queries.py) carries the real-entity gates (11 customers).

expected_behavior values: ANSWER | CLARIFY | REFUSE.
"""
import re
from pathlib import Path
import openpyxl
from openpyxl.styles import Font

OUT = Path("/home/sumit/AgentWork/eval-dashboard/accounts/finance/queries.xlsx")
OUT.parent.mkdir(parents=True, exist_ok=True)

PLACEHOLDER_RE = re.compile(r"\b(ABC|XYZ|TEST|PLACEHOLDER|EXAMPLE|SAMPLE|DUMMY|SOMECUSTOMER)\b", re.I)

CAT = "CFO Insight Questions (user set, 2026-09-18)"

# (query, expected_tool, expected_behavior, remark)
SECTIONS = {
    CAT: [
        ("Give me a quick sense of how the business is doing financially. Anything that stands out to you?",
         "NO_TOOL", "CLARIFY", "'how is the business doing' + open review -> clarify first (health = multiple readings)"),
        ("Revenue looks okay to me, but are we actually making money? Walk me through the profitability.",
         "NO_TOOL", "REFUSE", "profitability = COGS/margin/P&L -> GENUINELY ABSENT; expect boundary refusal, never a profit estimate"),
        ("Where is our cash getting stuck right now?",
         "NO_TOOL", "CLARIFY", "'cash' ambiguous: cash/bank balance absent vs money stuck in receivables (answerable) -> clarify or scoped answer; lenient"),
        ("I'm concerned about receivables. Who is holding up our cash and how serious is it?",
         "TOOL:top_outstanding", "ANSWER", "who + how serious = top debtors by outstanding + magnitude (receivables total)"),
        ("Do we have a working-capital problem, or is the situation under control?",
         "NO_TOOL", "CLARIFY", "'problem or under control' = judgment; WC spans receivables+inventory-payables, payables unreliable -> clarify"),
        ("Which customers are becoming a cash-flow risk for us?",
         "NO_TOOL", "CLARIFY", "'risk' is the classifier's own clarify-trigger example -> needs scope"),
        ("Show me customers where we're doing good business but collections are poor. I want to understand the pattern.",
         "TOOL:top_customers", "ANSWER", "analysis-style join: strong sales ∩ poor collections (outstanding/aging); clarify acceptable if 'poor' needs scope — lenient"),
        ("Are there customers whose outstanding is growing faster than their business with us?",
         "TOOL:balance_movement", "ANSWER", "analysis: dues movement vs sales growth (balance_movement vs sales_trend)"),
        ("If I had to recover cash aggressively this month, which accounts would you ask me to focus on first?",
         "TOOL:collection_priority", "ANSWER", "collection_priority / next_action family — PAB + days-since-last-payment"),
        ("How much of our receivables is actually overdue, and how much of that looks difficult to recover?",
         "TOOL:aging", "ANSWER", "overdue = aging buckets (upper bound, invoice-status); 'difficult to recover' must be hedged — no recoverability data"),
        ("Are we giving customers too much credit? What does the data suggest?",
         "NO_TOOL", "CLARIFY", "'too much credit' = judgment; credit-limit data absent; may answer concentration as exposure — lenient"),
        ("What is happening with our payables? Are we under pressure from suppliers or do we have some room?",
         "NO_TOOL", "REFUSE", "net supplier payables under-recorded -> unreliable; pressure/room unanswerable"),
        ("Are we paying suppliers before we collect from customers?",
         "NO_TOOL", "REFUSE", "needs supplier-payment timing (absent) vs receivable timing; payables side unreliable -> boundary refusal"),
        ("What's putting pressure on our margins?",
         "NO_TOOL", "REFUSE", "margins = COGS -> absent"),
        ("Our sales may be growing, but are margins improving or deteriorating?",
         "NO_TOOL", "REFUSE", "margin trend needs cost data (absent) — question centers on margins"),
        ("Find me the areas where revenue is growing but profitability isn't keeping up.",
         "NO_TOOL", "REFUSE", "profitability absent"),
        ("Which expenses should I be questioning right now?",
         "NO_TOOL", "REFUSE", "expense ledger / P&L absent (purchases != expenses)"),
        ("Have any expenses increased disproportionately compared with the business?",
         "NO_TOOL", "REFUSE", "expense trend absent"),
        ("If you were reviewing these numbers with me as CFO, what would you challenge?",
         "NO_TOOL", "CLARIFY", "open review, no scope -> clarify (same family as the 'looks wrong' trace)"),
        ("Forget the standard reports. Tell me what looks unusual in the financial data.",
         "NO_TOOL", "CLARIFY", "REAL TRACE EXAMPLE (2026-09-17): clarify_q + 4 options observed verbatim"),
        ("Something doesn't look right in the numbers. Can you find any unusual movements that I should investigate?",
         "NO_TOOL", "CLARIFY", "same family as the trace clarify; anomaly scope needed"),
        ("Where are we taking the biggest financial risks without necessarily seeing them in the P&L?",
         "NO_TOOL", "CLARIFY", "'biggest risks' = classifier's clarify-trigger family; may answer concentration/aging scoped — lenient"),
        ("Are there any customers where the amount of credit we're extending doesn't make sense given their payment history?",
         "NO_TOOL", "CLARIFY", "judgment term; may run customers_to_call-style PAB × payment-recency — lenient"),
        ("Which accounts have become materially different from what we normally see?",
         "TOOL:balance_movement", "ANSWER", "analysis/anomaly: balance_movement + sales anomalies; clarify acceptable for 'materially' — lenient"),
        ("Tell me where management attention is most needed financially.",
         "NO_TOOL", "CLARIFY", "open prioritization across metrics -> needs scope"),
        ("If sales remain at the current level, what could hurt our cash flow over the next few months?",
         "TOOL:aging", "ANSWER", "data-backed risk framing: aging/dormant exposure; the forward-looking cash aspect may be refused — lenient"),
        ("What is the biggest difference between our accounting profit and the cash situation?",
         "NO_TOOL", "REFUSE", "accounting profit (P&L) absent AND cash absent"),
        ("Are there signs that our growth is consuming too much working capital?",
         "TOOL:dso", "ANSWER", "growth vs WC = DSO (reconciled AR / sales run-rate) + receivables growth; 'too much' judgment — lenient"),
        ("Which customers or suppliers have the biggest financial concentration for us?",
         "TOOL:concentration", "ANSWER", "customer side = top-5 concentration (gold); supplier side via purchases amounts only — payables totals unavailable"),
        ("What would worry you if you were looking at these numbers for the first time?",
         "NO_TOOL", "CLARIFY", "open review, first-look -> clarify (same family as the trace)"),
    ],
}

# ---------- generation ----------
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Chat Queries"
ws.append(["Query", "Expected Response", "Remarks", "Expected Tool", "Expected Behavior"])
bold = Font(bold=True)
r = 2
total = 0
answer = clarify = refuse = 0
for cat, qs in SECTIONS.items():
    c = ws.cell(row=r, column=1, value=cat); c.font = bold
    r += 1
    for q, tool, beh, remark in qs:
        ws.cell(row=r, column=1, value=q)
        ws.cell(row=r, column=3, value=remark)
        ws.cell(row=r, column=4, value=tool)
        ws.cell(row=r, column=5, value=beh)
        r += 1
        total += 1
        if beh == "REFUSE": refuse += 1
        elif beh == "CLARIFY": clarify += 1
        else: answer += 1

wb.save(OUT)

# ---------- HARD GATE ----------
problems = []
all_queries = [q for qs in SECTIONS.values() for q, *_ in qs]
if total != 30:
    problems.append(f"expected EXACTLY 30 user queries, got {total}")
for q in all_queries:
    if PLACEHOLDER_RE.search(q):
        problems.append(f"placeholder token: {q[:80]}")
# user-order integrity: exact first/last strings
if all_queries[0].startswith("Give me a quick sense of how the business"):
    pass
else:
    problems.append("first query not the user's Q1")
if all_queries[-1].startswith("What would worry you"):
    pass
else:
    problems.append("last query not the user's Q30")
valid = all(any(q[0] == aq for aq in all_queries) for q, *_ in [e for qs in SECTIONS.values() for e in qs])
print(f"WROTE {OUT} | queries={total} | ANSWER={answer} CLARIFY={clarify} REFUSE={refuse}")
if problems:
    print("HARD-GATE FAILURES:")
    for p in problems:
        print("  -", p)
    raise SystemExit(1)
print("HARD GATE PASSED (30 user queries, verbatim order, no placeholders)")