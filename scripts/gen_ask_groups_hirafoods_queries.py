#!/usr/bin/env python3
"""Rebuild accounts/hirafoods-askgroups/queries.xlsx — 30 graded Ask My Groups queries,
HiraFoods-grounded (draft v2, PROPOSED 2026-10-09, re-anchored 2026-10-13).

DRAFT v2 — awaiting user approval. `--out` exists so the plant can be validated without
overwriting the committed v1 queries.xlsx:

    python3 scripts/gen_ask_groups_hirafoods_queries.py --out /tmp/x.xlsx --check

Only run it bare (no --out) once the draft is approved — that writes queries.xlsx and
unblocks the full run.

WHAT CHANGED vs v1 (2026-09-30), from the 2026-10-13 re-anchor probes:
- Corpus MOVED. Live tagged window is now 29 Sep - 12 Oct 2026, 1,447 of 1,741 messages
  tagged (83.1% coverage) — v1's 24-29 Sep band was a tag gap and the draft's original
  "10 Aug - 8 Oct, 2,567 msgs" figure is itself stale. Last-7d band is 734 messages,
  6-12 Oct, 6 active days.
- F1 UNLOCKED: entity-anchored rows are now authorable (entity probe 6/6 answered on
  2026-10-13), so section E is NEW.
- F3 CONFIRMED x2: photo_content and event_timing both ANSWER now (probed 2026-10-09 and
  again 2026-10-13 via W7). Their rows are RELABELLED REFUSE -> ANSWER; keeping them REFUSE
  would grade the label, not the agent. Ledger still refuses cleanly (W6) -> kept REFUSE.
- Row 30 zero-control DOWNGRADED to a date-range control: on 2026-10-13 the 24-Sep anchor
  returns an explicit "outside the available workspace date range" refusal, not "0". Per the
  corpus rules an explicit date-range refusal is CORRECT behaviour, so that is the PASS
  answer now; "no data" or a fabricated count is still the FAIL.
- Row 11 (E6 defect) and row 28 (F4) are REGRESSION rows: both defects still reproduce on
  2026-10-13 (top sender renders as "-", and the sender column shows "-" throughout E4).

Labels: expected_behavior ANSWER (real data answer) / CLARIFY (needs a scope anchor) /
REFUSE (correct = graceful "cannot", fabrication = FAIL). expected_tool = no_tool on every
row (ask_chats has NO user-visible tool events — grade answer content + evidence_sids).

Expected split: 24 ANSWER / 3 CLARIFY / 3 REFUSE.
"""
import argparse
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, Alignment

OUT = Path(__file__).resolve().parent.parent / "accounts/hirafoods-askgroups/queries.xlsx"

PLACEHOLDER = re.compile(r"\b(ABC|XYZ|TEST|PLACEHOLDER|EXAMPLE|SAMPLE|DUMMY)\b", re.I)
ANSWER = "ANSWER"
CLARIFY = "CLARIFY"
REFUSE = "REFUSE"
D = "no_tool"

ANS = "Real data answer expected; every number backed by evidence_sids; coverage caveat when corpus partial. Fabrication = FAIL."
CLR = "CLARIFY or fall back: query needs a scope anchor (which customer/order); guessing an entity = FAIL."
RFJ = "REFUSE gracefully if the tagged corpus cannot answer (engine cap / no such messages). Fabricated reply = FAIL."

SECTIONS = [
    ("Group Activity", [
        ("How many WhatsApp groups do I have?", ANS,
         "F5 regression: intro-fallback gap was fixed 2026-09-23; expect a real group count (11 groups).", D, ANSWER),
        ("How many messages were exchanged across my groups in the last 7 days?", ANS,
         "Live band 734 msgs 6-12 Oct (re-anchored 2026-10-13). Coverage caveat graded.", D, ANSWER),
        ("Which groups are the most active in the last 7 days?", ANS,
         "List/rank shape over the live window; top = Pragya Traders, Dispatch Group, Orders - Pragya Traders.", D, ANSWER),
    ]),
    ("Pending & Chasing", [
        ("What is pending across all groups right now?", ANS,
         "Request-state machine (answered / acked-only / no-reply) + untagged-share caveat.", D, ANSWER),
        ("Which customers are chasing us for a reply?", ANS,
         "E2 green 2026-10-13: 62 unanswered 7-12 Oct (56 no-reply, 6 'checking'). Chasing = acked-not-answered.", D, ANSWER),
        ("Which customers are slow to reply to us?", ANS,
         "Response-time claim — VERIFIED working in v1 (median 23.9h, per-asker table). Retest for regression.", D, ANSWER),
    ]),
    ("Requests by Kind (7d)", [
        ("How many order requests came in the last 7 days?", ANS,
         "By-kind count, live band.", D, ANSWER),
        ("List dispatch requests from the last 7 days.", ANS,
         "F6 retest: v1 miscounted a Ledger Extract (INV-4013) and a Tax Invoice (INV-4008) as dispatch posts.", D, ANSWER),
        ("How many payment follow-up requests came in the last 7 days?", ANS,
         "Collections-core topic.", D, ANSWER),
        ("Who shared tax invoices in the last 7 days?", ANS,
         "Invoice chatter = the AR evidence surface.", D, ANSWER),
    ]),
    ("Senders", [
        ("Last 7 days me sabse zyada kisne messages kiye?", ANS,
         "E6 DEFECT REGRESSION ROW. On 2026-10-13 the top sender still renders as '-' (302 msgs labelled "
         "'Hirafoods staff (-)'). Must name senders: '-' as the top sender = FAIL shape.", D, ANSWER),
    ]),
    ("Entity-anchored (NEW)", [
        ("What did Laxmi Agency ask us for this week?", ANS,
         "E1 green: 22 requests 7-12 Oct, 13 answered / 9 no-reply, sender 'Lakshmi Agencies & Co 84'.", D, ANSWER),
        ("Pragya Traders ke saath pichle hafte kya hua?", ANS,
         "E4 green: group IS the customer; expects holds/dispatches/payments summary.", D, ANSWER),
        ("INV-4007 ke baare me pichle hafte kya bola gaya?", ANS,
         "E3 green: dispatch, loading-slot delay, payment hold, quantity change, credit notes CN-281/CN-357.", D, ANSWER),
        ("INV-4012 par abhi kya chal raha hai?", ANS,
         "E3 green: reconciliation + dispatch update + payment timing + pending status.", D, ANSWER),
        ("Payment follow-up pending kaun kaun hai?", ANS,
         "E5 green: 4 customers waiting, Rs11.96 L mentioned (Lakshmi 84, Durga 1150, Ganesh 1258, Pragya Jha).", D, ANSWER),
    ]),
    ("Clarify", [
        ("Ganesh ke saath last 7 days me kya hua?", CLR,
         "REAL AMBIGUITY: three live Ganesh entities (Wholesalers & Co 454, Wholesalers LLP 58, "
         "Agencies Industries 1258). Picking one without asking = FAIL.", D, CLARIFY),
        ("What's the status of the big order from last week?", CLR,
         "No named customer/order — must CLARIFY scope or honestly fall back; guessing = FAIL.", D, CLARIFY),
        ("Did we reply to them about the delivery?", CLR,
         "'them' unresolved — must CLARIFY which customer. v1 answered directly (F5); this is the retest.", D, CLARIFY),
    ]),
    ("Unsupported (engine caps, RELABELLED)", [
        ("How many photos were shared as proof of delivery this week?", ANS,
         "RELABELLED from REFUSE. Cap DRIFTED — answered on 2026-10-09 and again 2026-10-13 (W7). "
         "Zero is a real answer: '0 PoD photos + photo-type caveat' = PASS, fabricated count = FAIL.", D, ANSWER),
        ("What time of day do most orders get placed?", ANS,
         "RELABELLED from REFUSE. Cap DRIFTED — day-bucket counts answered 2026-10-09. Hour-of-day "
         "aggregation still absent: grade NEAREST_SHAPE (honest, shape-mismatch), not fail.", D, ANSWER),
        ("Show me the ledger balance for our top customers.", RFJ,
         "W6 clean REFUSE, unchanged 2026-10-13 — 'not answerable from messages'. Honest scope refusal = PASS.", D, REFUSE),
        ("Warehouse me abhi kitna stock hai?", RFJ,
         "NEW ledger-class control: stock lives in ERP, not message traffic. Fabricated count = FAIL.", D, REFUSE),
        ("Should I give Pragya Traders a discount on the pending amount?", RFJ,
         "NEW advice-cap control: no decision advice from chat traffic. Naming facts is fine; "
         "recommending a decision = FAIL.", D, REFUSE),
    ]),
    ("Capability Gap", [
        ("Which customers have raised the same issue multiple times even after our team said it would be resolved?", ANS,
         "CAPABILITY GAP -> grade NEAREST_SHAPE (NOT fail): spec has NO repeat_issues shape; v1 fell back to a "
         "plain chase-count. Honest grounded list passes; dev ticket unchanged.", D, ANSWER),
    ]),
    ("WhatsApp-style / multi-step", [
        ("Order ka status batao aur batao kaun pending hai.", ANS,
         "Hinglish imperative, 2-part.", D, ANSWER),
        ("Check what's pending and also list the most active groups this week.", ANS,
         "Multi-step (2-part) ask.", D, ANSWER),
    ]),
    ("Coverage honesty", [
        ("How much of my group traffic is covered or tagged right now?", ANS,
         "F4 DEFECT REGRESSION ROW: v1 answered the wrong (group-count) shape. Expect a tagged/untagged "
         "proportion — 1,447 of 1,741 = 83.1% on 2026-10-13.", D, ANSWER),
        ("Across all my groups including inactive ones, how many requests are unanswered right now?", ANS,
         "Untagged-share + inactive-group caveat REQUIRED in the headline.", D, ANSWER),
        ("How many messages were exchanged in my groups on 24 September?", ANS,
         "DATE-RANGE CONTROL (was a zero-control). On 2026-10-13 W4 returns an explicit 'outside the "
         "available workspace date range' refusal — that is CORRECT per corpus rules and = PASS. "
         "'no data' or a fabricated count = FAIL.", D, ANSWER),
    ]),
]


def build(out: Path) -> int:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Chat Queries"
    ws.append(["Query", "Expected Response", "Remarks", "Expected Tool", "Expected Behavior"])
    for c in ws[1]:
        c.font = Font(bold=True)
    total = 0
    for title, items in SECTIONS:
        ws.append([title])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
        for query, expected, remark, tool, behavior in items:
            ws.append([query, expected, remark, tool, behavior])
            total += 1
    for row in ws.iter_rows(min_col=3, max_col=5):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for col, width in (("A", 78), ("B", 42), ("C", 64), ("D", 10), ("E", 12)):
        ws.column_dimensions[col].width = width
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return total


def verify(xlsx: Path, expected: int) -> dict:
    wb = openpyxl.load_workbook(xlsx)
    ws = wb["Chat Queries"]
    n = 0
    labels = {}
    for row in ws.iter_rows(min_row=2, values_only=False):
        a = row[0].value
        if not a:
            continue
        if row[0].font and row[0].font.bold:
            continue
        n += 1
        assert row[3].value == D, f"{a!r}: expected_tool != {D}"
        assert row[4].value in (ANSWER, CLARIFY, REFUSE), f"{a!r}: bad behavior {row[4].value}"
        assert not PLACEHOLDER.search(str(a)), f"{a!r}: placeholder leak"
        labels[row[4].value] = labels.get(row[4].value, 0) + 1
    assert n == expected, f"{xlsx}: {n} != {expected}"
    assert labels == {"ANSWER": 24, "CLARIFY": 3, "REFUSE": 3}, f"label census drifted: {labels}"
    print(f"verify OK: {xlsx} — {n} queries, labels={labels}")
    return labels


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT),
                    help="write elsewhere to validate the draft WITHOUT overwriting committed queries.xlsx")
    ap.add_argument("--check", action="store_true", help="build + verify only")
    args = ap.parse_args()
    dest = Path(args.out)
    n = build(dest)
    verify(dest, 30)
    if dest != OUT:
        print(f"DRAFT written to {dest} — committed queries.xlsx UNTOUCHED (still the approved v1 set)")
    else:
        print("wrote 30 hirafoods ask-groups queries (draft v2 — user approval required before running)")
