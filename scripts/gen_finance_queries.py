#!/usr/bin/env python3
"""Rebuild accounts/finance/queries.xlsx — Finance agent eval query set (2026-09-18).

PERSONA: CFO / accountant. DOMAIN: ERP ONLY (no WhatsApp facts).
Expected behaviors: ANSWER | CLARIFY | REFUSE | CHAT | MIXED (col E).
Expected tool: TOOL:<catalogue metric> | TOOL:search_threads (chat) | NO_TOOL (col D).
NOTE: the finance agent executes the metric catalogue as backend SQL — its SSE stream shows NO
tool events (observed 2026-09-18 discovery). expected_tool is the INTENT label for human review
and gold matching; the run grades finance on behavior + answer quality, not tool_calls.

REAL-ENTITY RULE: every named customer/product/invoice comes from the hirafoods workspace
(discovery 2026-09-18): 11 customers, 11 products, invoices 12851-12859, GST-0 zero-rate slab
(taxable value Rs.16,01,31,807 at zero rate). Generation HARD-GATES: placeholder-token scan,
entity-token membership, coverage: >=8 customers, >=6 products, >=1 invoice.
"""
import re
from pathlib import Path
import openpyxl
from openpyxl.styles import Font

OUT = Path("/home/sumit/AgentWork/eval-dashboard/accounts/finance/queries.xlsx")
OUT.parent.mkdir(parents=True, exist_ok=True)

CUSTOMERS = {
    "Om Enterprises Traders 421", "Sai Agencies & Co 1051", "Ganesh Wholesalers Pvt Ltd 955",
    "Krishna Traders LLP 125", "Durga Traders Traders 811", "Sri Retail & Co 196",
    "Lakshmi Distributors LLP 20", "Jai Wholesalers & Co 918", "Radha Agencies LLP 552",
    "Shree Retail Pvt Ltd 581", "Radha Agencies Pvt Ltd 787",
}
PRODUCTS = {
    "Silver Body Lotion Classic", "Golden Shampoo Premium",   # live top-products (2026-09-18)
    "Golden Biscuits Lite", "Fresh Shampoo Fresh", "Classic Toothpaste Strong",
    "Sunrise Juice Max", "Diamond Pasta Regular", "Diamond Namkeen Classic",
    "Ultra Biscuits Regular", "Diamond Juice Strong", "Power Soap Strong",
}
INVOICES = {12851, 12852, 12853, 12854, 12855, 12856, 12857, 12858, 12859}
PLACEHOLDER_RE = re.compile(r"\b(ABC|XYZ|TEST|PLACEHOLDER|EXAMPLE|SAMPLE|DUMMY|SOMECUSTOMER)\b", re.I)
CUST_TOKEN_RE = re.compile(r"\b(?:Om Enterprises Traders|Sai Agencies|Ganesh Wholesalers|Krishna Traders|"
                           r"Durga Traders|Sri Retail|Lakshmi Distributors|Jai Wholesalers|Radha Agencies|"
                           r"Shree Retail)\b")
INV_RE = re.compile(r"\b12\d{3}\b")

CFO = "CFO/accountant, ERP only"
# (query, expected_tool, expected_behavior, remark)
SECTIONS = {
    "Receivables & AR Health": [
        ("What is my total outstanding receivables right now?", "TOOL:receivables", "ANSWER",
         "gold = reconciled PAB; crosscheck warning banner has fired on this exact ask (2026-09-18) - flag as finding"),
        ("How many debtors do I have with an outstanding balance?", "TOOL:receivables", "ANSWER", CFO),
        ("Show me the ageing buckets of unpaid invoices.", "TOOL:aging", "ANSWER",
         "upper bound (invoice-status P/PP); never headline over PAB outstanding"),
        ("How much is stuck in invoices more than 90 days past due?", "TOOL:aging", "ANSWER", "upper-bound caveat"),
        ("What is my DSO right now?", "TOOL:dso", "ANSWER", "gold: AR = reconciled PAB / sales run-rate"),
        ("How long does it take me to collect on average?", "TOOL:dso", "ANSWER", "plain-language DSO"),
        ("How concentrated is my revenue on the top 5 customers?", "TOOL:concentration", "ANSWER", "top-5 share"),
        ("What percent of my sales comes from my five biggest customers?", "TOOL:concentration", "ANSWER", "test_form"),
    ],
    "Customer-Anchored": [
        ("Who are my top 5 customers by outstanding balance?", "TOOL:top_outstanding", "ANSWER", CFO),
        ("List the customers who currently have dues.", "TOOL:customers_with_dues", "ANSWER", CFO),
        ("Which debtors above 20 lakh have been outstanding for over 90 days?", "TOOL:big_old_debtors", "ANSWER",
         "threshold lives in the SQL (20L/90d)"),
        ("Compare the sales of Om Enterprises Traders 421, Sai Agencies & Co 1051 and Ganesh Wholesalers Pvt Ltd 955 this quarter.", "TOOL:top_customers", "ANSWER", "real customers, ranking framing"),
        ("Show the opening vs closing dues of Radha Agencies LLP 552 this period.", "TOOL:balance_movement", "ANSWER", "trial-balance style"),
        ("Which customers' dues moved the most this month?", "TOOL:balance_movement", "ANSWER", CFO),
        ("Where does Om Enterprises Traders 421 rank in my top customers by sales?", "TOOL:top_customers", "ANSWER", "real customer"),
        ("Who are the top 5 dormant customers - biggest dues, no order in over 60 days?", "TOOL:dormant", "ANSWER",
         "60d dormant threshold in SQL; customer_summary only for latestOrderDate"),
        ("How much has Krishna Traders LLP 125's dues moved this month?", "TOOL:balance_movement", "ANSWER", "real customer"),
        ("What were the invoiced sales of Durga Traders Traders 811 this quarter?", "TOOL:top_customers", "ANSWER", "real customer"),
        ("What is the closing ledger balance of Sri Retail & Co 196?", "TOOL:balance_movement", "ANSWER", "real customer"),
        ("Show me the balance history of Radha Agencies Pvt Ltd 787.", "TOOL:balance_movement", "ANSWER",
         "real customer (resolvable; also used in AR set as the ambiguity pair)"),
    ],
    "Sales & Trend": [
        ("Show me monthly invoiced sales for the last 6 months.", "TOOL:sales_trend", "ANSWER", CFO),
        ("How did invoiced sales move over the past six months?", "TOOL:sales_trend", "ANSWER", "month-on-month"),
        ("What were my total sales this period?", "TOOL:total_sales", "ANSWER", CFO),
        ("How many invoices did I raise last month?", "TOOL:invoice_count", "ANSWER", CFO),
        ("What is my average invoice value?", "TOOL:avg_invoice", "ANSWER", CFO),
        ("How many invoices are still unpaid?", "TOOL:unpaid_count", "ANSWER", "invoice-status count (not ageing)"),
        ("What are my top 5 products by sales value?", "TOOL:top_products", "ANSWER",
         "live answer 2026-09-18 had an unnamed product entry at top - data-quality finding candidate"),
        ("What were the sales of Silver Body Lotion Classic last quarter?", "TOOL:top_products", "ANSWER",
         "real product (live top-products)"),
        ("What were the sales of Golden Shampoo Premium this month?", "TOOL:top_products", "ANSWER",
         "real product (live top-products)"),
    ],
    "Payments & Collections": [
        ("How much did I collect in total this month?", "TOOL:collected_total", "ANSWER", CFO),
        ("What is my collection efficiency - paid vs invoiced?", "TOOL:collection", "ANSWER", CFO),
        ("Compare this month's collections with last month's.", "TOOL:collected_total", "ANSWER", "period compare"),
        ("Which customers should I call about payments today?", "TOOL:customers_to_call", "ANSWER", "PAB + days-since-last-payment"),
        ("Who should I prioritize for collections this week?", "TOOL:collection_priority", "ANSWER", CFO),
        ("What is my next best collection action?", "TOOL:next_action", "ANSWER", CFO),
        ("How much have I issued in credit notes this quarter?", "TOOL:credit_notes", "ANSWER", CFO),
        ("What is the payment status of invoice 12859?", "TOOL:unpaid_count", "ANSWER",
         "REAL invoice from live discovery (Rs.900); payment status, not ageing"),
    ],
    "Purchases": [
        ("What did I purchase from suppliers this month?", "TOOL:purchases", "ANSWER", CFO),
        ("Show me my purchase trend month by month.", "TOOL:purchase_by_month", "ANSWER", CFO),
        ("Who are my top suppliers by purchase value?", "TOOL:purchases", "ANSWER", CFO),
        ("Which suppliers should I reconcile before making the next payment?", "TOOL:purchases", "ANSWER",
         "supplier payables under-recorded - expect honest coverage caveat"),
    ],
    "Inventory": [
        ("What is my current stock on hand?", "TOOL:stock_on_hand", "ANSWER", CFO),
        ("What is my total stock value at list price?", "TOOL:stock_value_at_list_price", "ANSWER",
         "list price only - never cost"),
        ("Which products are dead stock (no movement in 90 days)?", "TOOL:dead_stock", "ANSWER", "90d threshold in SQL"),
        ("How much Golden Biscuits Lite stock is sitting unsold?", "TOOL:dead_stock", "ANSWER", "real product (GST-0)"),
        ("Which products are slow-moving, with no sales in the last 90 days?", "TOOL:dead_stock", "ANSWER", CFO),
        ("Is Sunrise Juice Max dead stock or still moving?", "TOOL:dead_stock", "ANSWER", "real product"),
        ("What is the stock value of Ultra Biscuits Regular?", "TOOL:stock_on_hand", "ANSWER", "real product"),
        ("What is the stock value of Classic Toothpaste Strong?", "TOOL:stock_on_hand", "ANSWER", "real product"),
    ],
    "GST & Tax": [
        ("How much GST did I collect this quarter?", "TOOL:gst_collected", "ANSWER", CFO),
        ("Show me GST collected by rate slab.", "TOOL:gst_by_rate", "ANSWER",
         "live 2026-09-18: zero-rate slab Rs.0 on taxable Rs.16,01,31,807 - GST-0 catalogue"),
        ("Which invoices have a GST amount that does not match the taxable value?", "TOOL:gst_by_rate", "ANSWER",
         "real user query (sql-pairs)"),
        ("Which sales transactions have missing or inconsistent tax details?", "TOOL:gst_by_rate", "ANSWER",
         "real user query (sql-pairs)"),
        ("How much of my billing is on the zero-rate (GST-0) slab?", "TOOL:gst_by_rate", "ANSWER",
         "grounded in the GST-0 product catalogue"),
    ],
    "Orders & Operations": [
        ("What is my current order pipeline value?", "TOOL:order_pipeline", "ANSWER", CFO),
        ("Where are my orders coming from, channel-wise?", "TOOL:orders_by_source", "ANSWER", CFO),
        ("What fraction of my orders convert to invoices?", "TOOL:order_to_invoice_conversion", "ANSWER", CFO),
        ("Which beats did my field force cover this week?", "TOOL:beat_coverage", "ANSWER", CFO),
        ("How many orders are in the pipeline right now?", "TOOL:order_pipeline", "ANSWER", CFO),
        ("How many customers do I have per segment?", "TOOL:customers_by_segment", "ANSWER", CFO),
    ],
    "Refusals - Data Boundary (NEVER guess)": [
        ("What is my profit margin this quarter?", "NO_TOOL", "REFUSE", "COGS/margin/P&L genuinely absent"),
        ("Show me my profit and loss statement.", "NO_TOOL", "REFUSE", "P&L absent"),
        ("What is my current cash and bank balance?", "NO_TOOL", "REFUSE", "cash & bank absent"),
        ("How much do I owe my suppliers in total?", "NO_TOOL", "REFUSE", "net supplier payables unreliable (under-recorded)"),
        ("What is the value of my inventory at cost?", "NO_TOOL", "REFUSE", "only list price exists"),
        ("What was my total profit last year?", "NO_TOOL", "REFUSE", "P&L absent"),
        ("What is the COGS for Golden Biscuits Lite?", "NO_TOOL", "REFUSE", "product cost absent - refuse, never estimate"),
    ],
    "Clarifying Questions (vague term - must clarify, not guess)": [
        ("Are we financially healthy?", "NO_TOOL", "CLARIFY", "'healthy' = multiple readings - clarify first"),
        ("Forget the standard reports. Tell me what looks unusual in the financial data.", "NO_TOOL", "CLARIFY",
         "REAL trace example (2026-09-17): clarify_q + 4 options observed"),
        ("Who is my best customer?", "NO_TOOL", "CLARIFY", "by sales or by outstanding?"),
        ("Which customers are risky?", "NO_TOOL", "CLARIFY", "'risky' ambiguous"),
        ("Who are my late payers?", "NO_TOOL", "CLARIFY", "'late payer' = which reading?"),
        ("Is my business doing well?", "NO_TOOL", "CLARIFY", "vague - needs scope"),
    ],
    "Chat - customer messages (no ERP grounding)": [
        ("What did customers complain about in the WhatsApp groups last week?", "TOOL:search_threads", "CHAT",
         "OpenSearch k=8; degrades to out_of_scope"),
        ("Which customers asked for a ledger copy in the groups?", "TOOL:search_threads", "CHAT", "message evidence"),
        ("What payment claims have customers made in the groups?", "TOOL:search_threads", "CHAT", "message evidence"),
    ],
    "Mixed - chat WHO + ledger numbers": [
        ("Which customers complained about an invoice AND still have dues?", "TOOL:receivables", "MIXED",
         "mixed branch degrades to ledger-only when chat unavailable"),
        ("Which customers asked for ledger copies and what do they owe?", "TOOL:receivables", "MIXED", "mixed"),
        ("Who queried about their payments in the groups and is still outstanding?", "TOOL:top_outstanding", "MIXED", "mixed"),
        ("Which customers promised payment in messages but still show dues?", "TOOL:receivables", "MIXED", "mixed"),
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
refuse = clarify = chat = mixed = answer = 0
used_customers, used_products, used_invoices = set(), set(), set()
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
        elif beh == "CHAT": chat += 1
        elif beh == "MIXED": mixed += 1
        else: answer += 1
        for cname in CUSTOMERS:
            if cname in q: used_customers.add(cname)
        for p in PRODUCTS:
            if p in q: used_products.add(p)
        for n in INVOICES:
            if str(n) in q: used_invoices.add(n)

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
if len(used_customers) < 8:
    problems.append(f"customer coverage too low: {len(used_customers)}/11 used: {sorted(used_customers)}")
if len(used_products) < 6:
    problems.append(f"product coverage too low: {len(used_products)}/11 used: {sorted(used_products)}")
if not used_invoices:
    problems.append("no real invoice number used in any query")
print(f"WROTE {OUT} | queries={total} | ANSWER={answer} CLARIFY={clarify} REFUSE={refuse} CHAT={chat} MIXED={mixed}")
print(f"customers used={len(used_customers)}/11 | products used={len(used_products)}/11 | invoices used={sorted(used_invoices)}")
if problems:
    print("HARD-GATE FAILURES:")
    for p in problems:
        print("  -", p)
    raise SystemExit(1)
print("HARD GATE PASSED (no placeholders, all entities known, coverage ok)")