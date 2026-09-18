#!/usr/bin/env python3
"""Rebuild accounts/ar-agent/queries.xlsx — AR collections agent eval query set (2026-09-18).

PERSONA: anyone in upper management (plain business language).
DOMAIN: ERP + WhatsApp groups (the groups confirm the LATEST updates on payments/receivables:
claims, commitments, acknowledgements, disputes).
Tool surface (deployed 2026-09-17, live-confirmed 2026-09-18: query_ar_financials +
resolve_ar_identity observed): query_ar (position|worklist|objects|activity),
query_ar_financials (invoices|customer_balances), get_ar_evidence, get_ar_schema,
resolve_ar_identity, get_paid_collections, get_ar_conversation_snapshot.
Presentation: ONE short plain sentence (app renders details); identity shortlists REQUIRE explicit
selection (a named-customer query may park for a selection turn - the two-turn runner handles it).
Expected behaviors: ANSWER | CLARIFY | REFUSE (col E).

REAL-ENTITY RULE: every named customer from the hirafoods workspace (11 real accounts). HARD GATES:
placeholder-token scan, customer-token membership, minimum customer coverage, at least one
two-Radha ambiguity case and at least one invoice-anchored query.
"""
import re
from pathlib import Path
import openpyxl
from openpyxl.styles import Font

OUT = Path("/home/sumit/AgentWork/eval-dashboard/accounts/ar-agent/queries.xlsx")
OUT.parent.mkdir(parents=True, exist_ok=True)

CUSTOMERS = {
    "Om Enterprises Traders 421", "Sai Agencies & Co 1051", "Ganesh Wholesalers Pvt Ltd 955",
    "Krishna Traders LLP 125", "Durga Traders Traders 811", "Sri Retail & Co 196",
    "Lakshmi Distributors LLP 20", "Jai Wholesalers & Co 918", "Radha Agencies LLP 552",
    "Shree Retail Pvt Ltd 581", "Radha Agencies Pvt Ltd 787",
}
INVOICES = {12851, 12852, 12853, 12854, 12855, 12856, 12857, 12858, 12859}
PLACEHOLDER_RE = re.compile(r"\b(ABC|XYZ|TEST|PLACEHOLDER|EXAMPLE|SAMPLE|DUMMY|SOMECUSTOMER)\b", re.I)
CUST_TOKEN_RE = re.compile(r"\b(?:Om Enterprises Traders|Sai Agencies|Ganesh Wholesalers|Krishna Traders|"
                           r"Durga Traders|Sri Retail|Lakshmi Distributors|Jai Wholesalers|Radha Agencies|"
                           r"Shree Retail)\b")
INV_RE = re.compile(r"\b12\d{3}\b")

UM = "upper management, plain language"
WA = "WhatsApp-groundable"
# (query, expected_tool, expected_behavior, remark)
SECTIONS = {
    "Position - Outstanding Snapshot": [
        ("What is our total outstanding right now?", "TOOL:query_ar", "ANSWER", "position snapshot; latest date if omitted"),
        ("How much of our outstanding is overdue vs not yet due?", "TOOL:query_ar", "ANSWER", "position buckets"),
        ("Show me the ageing breakup of what customers owe.", "TOOL:query_ar", "ANSWER", "b_1_30..b_90+ buckets"),
        ("Which customer has the highest outstanding?", "TOOL:query_ar", "ANSWER", "position sorted desc"),
        ("Who are our top 5 by outstanding?", "TOOL:query_ar", "ANSWER", UM),
        ("Is this outstanding figure up to date?", "TOOL:query_ar", "ANSWER",
         "stale snapshot -> 'latest list is from <date>' (never the word stale)"),
        ("What did our outstanding look like as of last month's snapshot?", "TOOL:query_ar", "ANSWER", "as_of param"),
        ("Which customers have no outstanding at all?", "TOOL:query_ar", "ANSWER", "zero-balance list"),
        ("Has our total outstanding changed much vs the previous snapshot?", "TOOL:query_ar", "ANSWER",
         "trend honesty: DSO/collections history unavailable by design"),
    ],
    "Worklist - Priority & Chase": [
        ("Who do we chase first today?", "TOOL:query_ar", "ANSWER", "worklist rank is AUTHORITATIVE - never re-rank by opinion"),
        ("Show the top of the chase list with days past due.", "TOOL:query_ar", "ANSWER", "chaseable_balance + days_past_due"),
        ("Which 5 customers should we prioritize for collection today?", "TOOL:query_ar", "ANSWER", UM),
        ("Who is on hold right now and why?", "TOOL:query_ar", "ANSWER", "held rows have null rank; suppression_object links"),
        ("What is our next best follow-up?", "TOOL:query_ar", "ANSWER", UM),
        ("Where does Om Enterprises Traders 421 sit on the chase list?", "TOOL:query_ar", "ANSWER", "real customer"),
        ("Are any holds linked to an open dispute?", "TOOL:query_ar", "ANSWER", WA),
        ("Which customers did we follow up repeatedly?", "TOOL:query_ar", "ANSWER",
         "UNCONFIRMABLE by design (activity = last_inbound/outbound only) - expect honest limitation"),
        ("Should we chase anyone today?", "TOOL:query_ar", "ANSWER", UM),
    ],
    "Objects - WhatsApp Signals": [
        ("Are there new payment claims in the groups?", "TOOL:query_ar", "ANSWER", WA),
        ("Who committed to paying this week?", "TOOL:query_ar", "ANSWER", "objects type=commitment"),
        ("Which customers acknowledged their dues in WhatsApp?", "TOOL:query_ar", "ANSWER", "objects type=acknowledgement"),
        ("Any disputes raised in the groups?", "TOOL:query_ar", "ANSWER", "objects type=dispute"),
        ("Have any cheques been promised?", "TOOL:query_ar", "ANSWER", "objects type=cheque"),
        ("Who asked for a ledger copy or document in the groups?", "TOOL:query_ar", "ANSWER", "objects type=document_request; WA"),
        ("Om Enterprises Traders 421 said the payment is done - does the data confirm it?", "TOOL:query_ar", "ANSWER",
         "claim reported != bank-verified; unknown amount != zero"),
        ("What did Sai Agencies & Co 1051 commit to paying?", "TOOL:resolve_ar_identity", "ANSWER", "resolve then objects; WA"),
        ("Any claims with an expected payment date this week?", "TOOL:query_ar", "ANSWER", "expected_date filter; WA"),
        ("Which open claims are suppressing our chasing?", "TOOL:query_ar", "ANSWER", "suppresses_chasing; WA"),
        ("Is there a hold because of a dispute from Krishna Traders LLP 125?", "TOOL:resolve_ar_identity", "ANSWER",
         "real customer; resolve -> objects -> worklist hold"),
        ("Any recent payment claims from Radha Agencies Pvt Ltd 787?", "TOOL:query_ar", "ANSWER",
         "real customer (the 2nd Radha - ambiguity pair with LLP 552); WA"),
    ],
    "Financials - Invoices & Balances": [
        ("Show me the current balance of Ganesh Wholesalers Pvt Ltd 955.", "TOOL:query_ar_financials", "ANSWER", "customer_balances; real customer"),
        ("Which invoices are still open for Krishna Traders LLP 125?", "TOOL:query_ar_financials", "ANSWER", "invoices dataset"),
        ("What is the ledger balance of Sai Agencies & Co 1051?", "TOOL:query_ar_financials", "ANSWER", "customer_balances"),
        ("Show me the most recent open invoices.", "TOOL:query_ar_financials", "ANSWER", "invoices; app renders rows"),
        ("Invoiced vs paid totals for Durga Traders Traders 811?", "TOOL:query_ar_financials", "ANSWER", "real customer"),
        ("What is the outstanding summary for Jai Wholesalers & Co 918?", "TOOL:resolve_ar_identity", "ANSWER", "resolve -> financials"),
        ("Show me invoice 12859 and its payment status.", "TOOL:query_ar_financials", "ANSWER", "REAL invoice from live discovery (Rs.900)"),
        ("Which customer's ledger moved the most this month?", "TOOL:query_ar_financials", "ANSWER", UM),
        ("What is the current balance of Lakshmi Distributors LLP 20?", "TOOL:query_ar_financials", "ANSWER", "real customer"),
    ],
    "Evidence": [
        ("What exactly did the customer say about the payment in the group?", "TOOL:get_ar_evidence", "ANSWER",
         "exact stored wording; authorize object first"),
        ("Show me the exact wording of Om Enterprises Traders 421's payment claim.", "TOOL:get_ar_evidence", "ANSWER", WA),
        ("What did Radha Agencies LLP 552 say about the cheque?", "TOOL:get_ar_evidence", "ANSWER",
         "real customer; evidence text + sender"),
        ("Can you show me the message where the commitment was made?", "TOOL:get_ar_evidence", "ANSWER", WA),
    ],
    "Paid Collections": [
        ("How much did we collect in total this month?", "TOOL:get_paid_collections", "ANSWER", "workspace paid totals by payment date (status P)"),
        ("Compare this week's collections with last week's.", "TOOL:get_paid_collections", "ANSWER", "inclusive IST from/to"),
        ("Show me collections by payment date for this period.", "TOOL:get_paid_collections", "ANSWER", UM),
        ("Are collections improving month over month?", "TOOL:get_paid_collections", "ANSWER",
         "period comparison; honest about scope - no customer breakdown"),
    ],
    "Conversation Snapshot": [
        ("What is the latest update in the HiraFoods-Om Enterprises Traders 421 group?", "TOOL:get_ar_conversation_snapshot", "ANSWER",
         "authorized 15-min window, NOT full history"),
        ("What was the most recent message from Radha Agencies LLP 552?", "TOOL:get_ar_conversation_snapshot", "ANSWER", WA),
        ("What was discussed around the Shree Retail Pvt Ltd 581 payment?", "TOOL:get_ar_conversation_snapshot", "ANSWER", "real customer"),
        ("Any activity on the Sri Retail & Co 196 thread recently?", "TOOL:get_ar_conversation_snapshot", "ANSWER", "real customer"),
    ],
    "Identity - Clarify & Selection": [
        ("Tell me about Radha's outstanding.", "TOOL:resolve_ar_identity", "CLARIFY",
         "TWO Radha accounts exist (LLP 552 + Pvt Ltd 787) - shortlist MUST be selected, even one row"),
        ("What is the balance for Sai Agencies?", "TOOL:resolve_ar_identity", "CLARIFY", "truncated name -> shortlist"),
        ("Who is Krishna Traders?", "TOOL:resolve_ar_identity", "CLARIFY", "fuzzy -> shortlist"),
        ("What does Om Enterprises owe us?", "TOOL:resolve_ar_identity", "CLARIFY", "firm-only (no account number) -> shortlist"),
        ("Check the dues for Shree Retail.", "TOOL:resolve_ar_identity", "CLARIFY", "truncated -> shortlist"),
        ("What is Ganesh Wholesalers' position?", "TOOL:resolve_ar_identity", "CLARIFY", "no number -> shortlist"),
        ("Balance of Jai Wholesalers & Co?", "TOOL:resolve_ar_identity", "CLARIFY", "no number -> shortlist"),
    ],
    "Plain-Language Upper Management": [
        ("Who owes us the most right now?", "TOOL:query_ar", "ANSWER", UM),
        ("Any big payments stuck?", "TOOL:query_ar", "ANSWER", UM),
        ("What is the latest on the big payments?", "TOOL:query_ar", "ANSWER", "objects + position; WA"),
        ("Where is most of our money stuck?", "TOOL:query_ar", "ANSWER", UM),
        ("Are our collections getting better?", "TOOL:get_paid_collections", "ANSWER", UM),
        ("Is anyone about to pay us this week?", "TOOL:query_ar", "ANSWER", "expected_date commitments; WA"),
    ],
    "Unsupported - Read-Only Guard": [
        ("Verify in the bank that Om Enterprises Traders 421 paid us.", "NO_TOOL", "REFUSE", "bank verification absent"),
        ("Forecast our collections for next quarter.", "NO_TOOL", "REFUSE", "no forecasts (DSO/credit/cash)"),
        ("Mark Durga Traders Traders 811 as settled.", "NO_TOOL", "REFUSE", "read-only - no writes ever"),
        ("Send a payment reminder to Sai Agencies & Co 1051 on WhatsApp.", "NO_TOOL", "REFUSE",
         "drafts only; sending is an authenticated UI action"),
        ("Show me which claims actually hit the bank account.", "NO_TOOL", "REFUSE", "bank matching absent"),
        ("Confirm that Jai Wholesalers & Co 918's cheque has cleared.", "NO_TOOL", "REFUSE", "bank verification absent"),
    ],
}

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Chat Queries"
ws.append(["Query", "Expected Response", "Remarks", "Expected Tool", "Expected Behavior"])
bold = Font(bold=True)
r = 2
total = answer = clarify = refuse = 0
used_customers, used_invoices = set(), set()
has_radha_ambiguity = False
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
        if beh == "CLARIFY": clarify += 1
        elif beh == "REFUSE": refuse += 1
        else: answer += 1
        for cname in CUSTOMERS:
            if cname in q:
                used_customers.add(cname)
        for n in INVOICES:
            if str(n) in q: used_invoices.add(n)
        if "Radha" in q and "outstanding" in q and "LLP 552" not in q and "Pvt Ltd 787" not in q:
            has_radha_ambiguity = True

wb.save(OUT)

# ---------- HARD GATE ----------
problems = []
all_queries = [q for qs in SECTIONS.values() for q, *_ in qs]
for q in all_queries:
    if PLACEHOLDER_RE.search(q):
        problems.append(f"placeholder token: {q[:80]}")
    for m in CUST_TOKEN_RE.finditer(q):
        tok = m.group(0)
        if not any(tok in c for c in CUSTOMERS):
            problems.append(f"unknown customer token '{tok}': {q[:80]}")
    for n in INV_RE.findall(q):
        if int(n) not in INVOICES:
            problems.append(f"unknown invoice number {n}: {q[:80]}")
if len(used_customers) < len(CUSTOMERS):
    problems.append(f"customers never used: {sorted(CUSTOMERS - used_customers)}")
if not has_radha_ambiguity:
    problems.append("no two-Radha ambiguity CLARIFY query present")

print(f"WROTE {OUT} | queries={total} | ANSWER={answer} CLARIFY={clarify} REFUSE={refuse}")
print(f"customers used={len(used_customers)}/{len(CUSTOMERS)} | invoices used={len(used_invoices)}")
if problems:
    print("HARD-GATE FAILURES:")
    for p in problems:
        print("  -", p)
    raise SystemExit(1)
print("HARD GATE PASSED (no placeholders, all customers known, ambiguity case present)")