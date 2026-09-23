#!/usr/bin/env python3
"""Rebuild accounts/ar-agent/queries.xlsx — the USER-PROVIDED AR eval set, enriched.

Source of the set: the user's query list (2026-09-23, 8 sections, 55 queries), kept in the
USER's order and section structure. Per the user's instruction ("update relevant info in these
queries so that output has some value") generic or placeholder phrasing was anchored on REAL
Zainab entities harvested 2026-09-23:
  - harvest_results_v1.json (round 1: balances/position/worklist, alias resolution)
  - harvest_results_v2.json (round 2: invoice numbers, chat claims, promises,
    reported-not-in-ERP claims)
  - accounts/ask-groups/RECON_DATA_INVENTORY.md (group-side aliases + evidence anchors)
Obsolete anchors replaced: the user's "Palette" (unresolvable in Zainab balances) -> TRENDS
FURNISHING (real WhatsApp-reported claim); the example "Bill 12798" -> B NO 15293 (real
claimed-on-WhatsApp / NOT-found-in-ERP mismatch).

Labeling uses the REAL deployed tool surface on Zainab (no query_ar family; no
resolve_ar_identity shortlist observed):
  get_receivables | list_invoices | ar_position | ar_worklist | ar_promises |
  ar_payments_reported | search_threads | search_customers_master
expected_behavior: ANSWER (with expected_tool = the primary tool; chaining allowed),
CLARIFY (ASK_BACK — referent-less rows; the agent must ask for the missing name/invoice).
[lenient] in a remark = judgment beyond hard facts (amount-match, dedupe, credit-note status,
promise-overdue) — a scoped/hedged answer scores fine.
"""
import json
import re
import sys

import openpyxl
from openpyxl.styles import Font
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "accounts/ar-agent/queries.xlsx"
ENTITIES = json.loads((ROOT / "accounts/ar-agent/entities.json").read_text())

PLACEHOLDER = re.compile(r"\b(ABC|XYZ|TEST|PLACEHOLDER|EXAMPLE|DUMMY)\b|Bill 12798|Palette", re.I)

# (category, [(query, expected_tool, expected_behavior, remark), ...]) — user's order.
SECTIONS = {
    "WhatsApp vs ERP Reconciliation": [
        ("Which customers said payment is done on WhatsApp but it is still outstanding in ERP?",
         "ar_payments_reported", "ANSWER", "core; reported claims vs ledger"),
        ("Which payments were claimed on WhatsApp but I can't find in ERP?",
         "ar_payments_reported", "ANSWER", "core"),
        ("Check the payment claims in WhatsApp against the ERP receipts.",
         "ar_payments_reported", "ANSWER", "hedge: both sides presented, no auto-reconcile claim"),
        ("Who says they paid, but we haven't received it in our books?",
         "ar_payments_reported", "ANSWER", "core"),
        ("Find payment claims with no matching ERP receipt — like KRISHNA COATED FABRICS, POPULAR MATTRESS & CLOTH STORE, TRENDS FURNISHING.",
         "ar_payments_reported", "ANSWER", "anchored: the 10-claim ₹7,41,130 set"),
        ("Which WhatsApp payments are still unreconciled?",
         "ar_payments_reported", "ANSWER", "[lenient] unreconciled = judgment"),
        ("Show me payments where the WhatsApp amount doesn't match the ERP amount.",
         "ar_payments_reported", "ANSWER", "[lenient] amount-compare judgment"),
        ("Who paid partially in ERP even though they said full payment on WhatsApp?",
         "ar_payments_reported", "ANSWER", "[lenient] partial-vs-full judgment; chain get_receivables"),
        ("Which customers shared a UTR on WhatsApp but there is no matching receipt in ERP?",
         "search_threads", "ANSWER", "[lenient] UTR-matching judgment; chain get_receivables"),
        ("Any payment claims from WhatsApp that need verification?",
         "ar_payments_reported", "ANSWER", "core"),
    ],
    "Payment Commitment Follow-up": [
        ("Who promised to pay this week but still has an outstanding balance?",
         "ar_promises", "ANSWER", "core"),
        ("Who said on WhatsApp they'll pay tomorrow?",
         "ar_promises", "ANSWER", "chain search_threads"),
        ("Which promised payments are overdue now — like the ONCE & AGAIN commitment?",
         "ar_promises", "ANSWER", "anchored; [lenient] promise-overdue judgment; chain ar_position"),
        ("Show me customers whose committed payment date has passed.",
         "ar_promises", "ANSWER", "core"),
        ("Who keeps promising payment but hasn't cleared the dues?",
         "ar_promises", "ANSWER", "[lenient] 'keeps' = repeated commitments; chain get_receivables"),
        ("Which WhatsApp payment commitments are still pending in ERP?",
         "ar_promises", "ANSWER", "core"),
        ("Who gave a payment date on WhatsApp but no payment has been posted in ERP yet?",
         "ar_promises", "ANSWER", "chain ar_payments_reported"),
        ("Show me customers who said payment is scheduled but ERP still shows outstanding.",
         "ar_promises", "ANSWER", "chain get_receivables"),
    ],
    "Invoice / Bill Level": [
        ("Which invoices were mentioned as paid on WhatsApp but are still open in ERP?",
         "ar_payments_reported", "ANSWER", "chain list_invoices"),
        ("Bill 15293 was claimed as paid on WhatsApp (NEFT ₹880) — is it in ERP?",
         "list_invoices", "ANSWER", "anchored: REAL mismatch — ERP says NOT FOUND (doc_number filter)"),
        ("Which bills have payment claims but no receipt entry?",
         "ar_payments_reported", "ANSWER", "core"),
        ("Show me the overdue bills where the customer has already promised payment — e.g. the 91-day worklist accounts.",
         "ar_worklist", "ANSWER", "anchored: RICH DECOR/EMBELLISH 91d class; chain ar_promises; [lenient] overdue = position"),
        ("Which invoice payments are pending despite customer confirmation on WhatsApp?",
         "ar_payments_reported", "ANSWER", "core"),
        ("Find bills where the WhatsApp amount and the ERP receipt don't match.",
         "ar_payments_reported", "ANSWER", "[lenient] amount-compare judgment"),
        ("Which customers mentioned specific invoice numbers while discussing payment — like 15293 or the ₹880 NEFT claim?",
         "search_threads", "ANSWER", "anchored: invoice-number mentions in chat"),
    ],
    "UTR / Reference Matching": [
        ("Check the UTRs shared on WhatsApp against the ERP receipts.",
         "search_threads", "ANSWER", "hedge: both sides presented"),
        ("Which UTRs don't have a matching entry in ERP?",
         "search_threads", "ANSWER", "[lenient] matching judgment; chain get_receivables"),
        ("Show me payment claims where the reference number matches an ERP receipt.",
         "search_threads", "ANSWER", "[lenient] matching judgment"),
        ("Are there any duplicate payment claims in WhatsApp?",
         "ar_payments_reported", "ANSWER", "[lenient] dedupe judgment"),
        ("Find payments where the UTR exists in WhatsApp but the receipt is missing in ERP.",
         "search_threads", "ANSWER", "[lenient] matching judgment; chain get_receivables"),
        ("Which payment references are still unresolved?",
         "ar_payments_reported", "ANSWER", "[lenient] unresolved = judgment"),
    ],
    "Credit Note Scenarios": [
        ("Who is waiting for a credit note before making payment?",
         "search_threads", "ANSWER", "[lenient] CN surface UNVERIFIED on Zainab — expect hedge"),
        ("Which payments are stuck because of pending credit notes?",
         "search_threads", "ANSWER", "[lenient] CN surface unverified"),
        ("Find customers who said they'll pay after a credit note adjustment.",
         "search_threads", "ANSWER", "[lenient] CN surface unverified"),
        ("How much is pending after the credit note mentioned on WhatsApp?",
         "search_threads", "ANSWER", "[lenient] CN surface unverified; chain get_receivables"),
        ("Which credit notes discussed in WhatsApp are still not reflected in ERP?",
         "search_threads", "ANSWER", "[lenient] CN surface unverified; chain get_receivables"),
        ("Who asked for a credit note and still has an outstanding balance?",
         "search_threads", "ANSWER", "[lenient] CN surface unverified; chain get_receivables"),
        ("Find cases where the customer says the credit note is pending but ERP already shows one.",
         "search_threads", "ANSWER", "[lenient] both-sides CN compare"),
    ],
    "Repeated Follow-ups": [
        ("Who have we chased multiple times but still haven't paid?",
         "ar_worklist", "ANSWER", "chain search_threads"),
        ("Which customers have repeated payment reminders in WhatsApp?",
         "search_threads", "ANSWER", "core"),
        ("Show me the large outstanding customers with recent payment follow-ups — like Interworld Furnishings (₹7.24Cr).",
         "ar_worklist", "ANSWER", "anchored: Interworld ₹7.24Cr 91d"),
        ("Who hasn't responded to our payment reminders?",
         "search_threads", "ANSWER", "[lenient] response-status judgment"),
        ("Which customers have acknowledged the dues but haven't paid?",
         "ar_promises", "ANSWER", "acknowledged = commitment; chain get_receivables"),
        ("Find customers where payment follow-up repeats without any payment.",
         "ar_worklist", "ANSWER", "[lenient] repeat+touch judgment; chain ar_payments_reported"),
    ],
    "Natural Accountant-style Queries": [
        ("What's the latest update on TRENDS FURNISHING's payment?",
         "ar_payments_reported", "ANSWER", "anchored (user's 'Palette' swapped — Palette unresolvable in Zainab balances; TRENDS FURNISHING has a real reported claim); chain search_threads"),
        ("Did they actually pay this one?",
         "ASK_BACK", "CLARIFY", "referent-less; tests the ask-back path"),
        ("What did Interworld Furnishings say about their pending ₹7.24Cr in the chats?",
         "search_threads", "ANSWER", "anchored: Interworld ₹7.24Cr 91d; chain get_receivables"),
        ("Has the payment for invoice 17346 been posted?",
         "list_invoices", "ANSWER", "anchored: real ERP invoice 17346 (₹27.73)"),
        ("They sent a UTR — can you check it? (the NEFT ₹880 claim against B NO 15293)",
         "search_threads", "ANSWER", "anchored: hiteshvthakkar ₹880 / B NO 15293 mismatch case; chain list_invoices"),
        ("Check what KRISHNA COATED FABRICS said about their payment in the group and compare it with ERP.",
         "search_threads", "ANSWER", "anchored: real reported claim; chain ar_payments_reported"),
        ("Why is this still showing outstanding when they said paid?",
         "ASK_BACK", "CLARIFY", "referent-less; tests the ask-back path"),
        ("How much is really pending for POPULAR MATTRESS & CLOTH STORE after their WhatsApp-reported payment?",
         "get_receivables", "ANSWER", "anchored: real reported claim; chain ar_payments_reported"),
        ("For the customers who reported payments on WhatsApp, what are they waiting for from us?",
         "search_threads", "ANSWER", "[lenient] reason-extraction judgment"),
        ("Who should I follow up with today based on the chats and ERP?",
         "ar_worklist", "ANSWER", "core — the worklist case"),
        ("Give me the cases where WhatsApp and ERP don't agree.",
         "ar_payments_reported", "ANSWER", "core — mismatch summary"),
        ("What's the current outstanding of Interworld Furnishings?",
         "search_customers_master", "ANSWER", "identity-resolution gate: truncated-name vs ERP master 'Interworld Furnishings (I) Pvt. Ltd.' — expect resolve+answer, no fabricated amount"),
    ],
}

# ---- anchors used in queries, asserted against entities.json ----
ANCHOR_CUSTOMERS = ["Interworld Furnishings", "PURPLE PATCH STUDIO", "HOMZ COUTURE",
                    "EMBELLISH", "RICH DECOR", "ONCE & AGAIN", "KRISHNA COATED FABRICS",
                    "POPULAR MATTRESS & CLOTH STORE", "TRENDS FURNISHING", "TENON",
                    "R DECOR SPACE", "HARI OM FURNISHING HOUSE"]
ANCHOR_INVOICES = ["15293", "17346", "17369"]
ANCHOR_AMOUNTS = ["₹7.24Cr", "₹880", "₹7,41,130", "₹5,192"]

ent_names = {c["name"].lower() for c in ENTITIES["customers"]}
for c in ENTITIES["customers"]:
    ent_names.update(a.lower() for a in (c.get("aliases") or []))
ent_inv = {i["number"] for i in ENTITIES["invoices"]}
ent_mismatch = ENTITIES["invoice_notes"]["mismatch_anchor"]["number"]

total = 0
for cat, qs in SECTIONS.items():
    for q, *_ in qs:
        if PLACEHOLDER.search(q):
            print(f"PLACEHOLDER TOKEN in query: {q!r}")
            sys.exit(1)
        for a in ANCHOR_CUSTOMERS:
            if a.lower() in q.lower() and a.lower() not in ent_names:
                print(f"ANCHOR MISSING FROM entities.json: {a!r} (in {q!r})")
                sys.exit(1)
        for inv in ANCHOR_INVOICES:
            if inv in q:
                if inv == ent_mismatch:
                    continue  # mismatch anchor lives in invoice_notes, not invoices[]
                if inv not in ent_inv:
                    print(f"INVOICE ANCHOR MISSING: {inv} (in {q!r})")
                    sys.exit(1)
        total += 1

n_clarify = sum(1 for qs in SECTIONS.values() for q, t, b, _ in qs if b == "CLARIFY")
n_inv_anchored = sum(1 for qs in SECTIONS.values() for q, *_ in qs
                     if any(i in q for i in ANCHOR_INVOICES))
assert n_clarify >= 1, "need >=1 CLARIFY (identity/ask-back) query"
assert n_inv_anchored >= 1, "need >=1 invoice-anchored query"

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Chat Queries"
ws.append(["Query", "Expected Response", "Remarks", "Expected Tool", "Expected Behavior"])
bold = Font(bold=True)
r = 2
for cat, qs in SECTIONS.items():
    c = ws.cell(row=r, column=1, value=cat)
    c.font = bold
    r += 1
    for q, tool, beh, remark in qs:
        ws.cell(row=r, column=1, value=q)
        ws.cell(row=r, column=3, value=remark)
        ws.cell(row=r, column=4, value=tool)
        ws.cell(row=r, column=5, value=beh)
        r += 1
wb.save(OUT)
print(f"WROTE {OUT} | queries={total} | CLARIFY={n_clarify} | ANSWER={total - n_clarify} | "
      f"invoice_anchored={n_inv_anchored}")