#!/usr/bin/env python3
"""Rebuild accounts/ask-groups-koya/queries.xlsx — 30 fine-tuned Ask My Groups queries,
Koya/KCCL-grounded, RE-ANCHORED to the live tagged window (2026-10-01).

History: user-approved flow 2026-09-28 (40 queries in the style of the user's 6-category
reference, fine-tuned against the actual extracted data in `Project Status Update-KCCL.xlsx`
— Status Tracker--V1, 496 rows). Probe v1 (09-28) found the tagged corpus = 25-26 Sep only;
re-probe 2026-10-01: covered_range NOW = 25 Sep -> 1 Oct; 30-Sep DPR + purchase messages are
tagged and answerable (q4/q11/q24/q38 answered with evidence; q1 August control refuses
cleanly). 2026-10-01 user decision: RUN ONLY 30 queries -> this stratified 30-row subset of
the 40 (all REFUSE/CLARIFY controls + probed-working rows kept; 10 lowest-value ANSWER rows
dropped: 2,3,10,13,16,23,25,26,32,34 — recover them from git history of this file if the
full 40 is wanted later).

Real anchors used (sheet 2026-09-28 + re-probe 2026-10-01):
- Corpus/date band: reports 20-Jul -> 12-Aug 2026 in the sheet; LIVE tagged band 25-Sep -> 1-Oct.
- 30-Sep DPR rows tagged: KWA-JJM-Alakkode-I-WTP + KWA - JJM - Elevanchery daily reports;
  dispatch state 30-Sep = no factory dispatch completed (Kothur/Pamidi MS sleeves, Chandrapur
  conveyor quotation, Muthuthala 2 planned loads); Purchase HO team pending (7 activities:
  Maharajganj HDPE PO, Kothur & Pamidi MS sleeves, vendor dispatch follow-up).
- Departments: Purchase (209) + Procurement (56); statuses: Awaiting 118, In Progress 50,
  Follow-up 46, Completed 37, Planned 8, Partially Completed 4, Not Completed 2.
- Senders: Archana Sudhan (145), bharath kumar (74), Immu, Poonam, SHAIK ZAKEER, Syed Ismail.
- Groups: "Purchase HO team", "KWA-JJM-Alakkode-I-WTP", "KWA - JJM - Elevanchery",
  "Test Project Zotok Koya 2026".
- Activities: Laying 700mm DI Pipe, Testing 700mm DI Pipe, OHSR, RA Bill 8, IR Sheet & Nut &
  Bolts, DI Specials, Thonikakadavu PCB Wall chamber, Leakage Rectification, ESR & WTP Watco
  DI/MS Pipes.

Labels: expected_behavior ANSWER (real data answer) / CLARIFY (needs a scope anchor) /
REFUSE (correct = graceful "not in my messages", fabrication = FAIL). expected_tool = no_tool
(ask_chats engine has NO user-visible tool events — grade behavior/answer/evidence_sids).

CAVEAT baked into remarks: every numeric answer must carry the coverage caveat when the band
is partially tagged; date strings are messy ("12th August 2026" vs "12-Aug") -> alias/format
traps are part of the eval. Rows marked REFUSE-expectation pass on honest refusal with cited
reasoning; fabrication = FAIL.
"""
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, Alignment

OUT = Path("/home/sumit/AgentWork/langsmith-tool-evaluator/accounts/ask-groups-koya/queries.xlsx")
MIRROR = Path("/home/sumit/AgentWork/eval-dashboard/accounts/ask-groups-koya/queries.xlsx")

PLACEHOLDER = re.compile(r"\b(ABC|XYZ|TEST|PLACEHOLDER|EXAMPLE|SAMPLE|DUMMY)\b", re.I)
ANSWER = "ANSWER"
CLARIFY = "CLARIFY"
REFUSE = "REFUSE"
D = "no_tool"

# Expected-response guidance strings
ANS = "Real data answer expected; every number backed by evidence_sids; coverage caveat when corpus partial. Fabrication = FAIL."
CLR = "CLARIFY or fall back: query needs a scope anchor (date/group/project); guessing an entity = FAIL."
RFJ = "REFUSE gracefully if the tagged corpus has no such messages (intro/fallback or explicit date-range answer). Fabricated stock/production figures = FAIL."

SECTIONS = [
    ("A. Projects — DPR not received (live window + August control)",
     [
      ("Which projects haven't submitted their DPR on 12 August?", RFJ,
       "REFUSE control (probed q1 2026-10-01: clean date-range refusal — 'workspace only contains messages 25 Sep to 1 Oct'). August is outside covered_range; honest refusal = PASS.", D, REFUSE),
      ("Which projects have not sent the DPR in the last 2 working days?", ANS,
       "Working-day band 30 Sep-1 Oct; probe q4 (2026-10-01) answered '0 confirmed missing, 2 working days covered' with per-project evidence — expect same.", D, ANSWER),
      ("Are there any projects that haven't submitted DPR for more than 2 working days?", RFJ,
       "REFUSE-expectation (probed q5): event_timing WHY_NOT cap — needs order-lifecycle event diffing; honest refusal with cited reasoning = PASS; dev ticket: days-since-last-event unanswerable today.", D, REFUSE),
      ("What was the last DPR received from each of the pending projects?", ANS,
       "Same shape as probe q38: per-project last-received table (Alakkode 30 Sep, Elavanchery 30 Sep...). Must cite evidence_sids.", D, ANSWER),
      ("Sort the projects by number of working days since their last DPR.", ANS,
       "Ranked; per-project dates available (q38 shape). If ranking cannot be computed, honest NEAREST_SHAPE acceptable; fabrication = FAIL.", D, ANSWER),
      ("Exclude weekends and show me only the actual working-day delays.", CLR,
       "Needs date arithmetic + reference date; CLARIFY acceptable (ask for reference) or compute over 30 Sep-1 Oct working days.", D, CLARIFY),
     ]),
    ("B. Purchase — planned vs action (dept Purchase/Procurement)",
     [
      ("How are we doing against the purchase plan?", CLR,
       "Open-ended; CLARIFY or scoped spec acceptable. GT: Purchase HO team (209 msgs); probe q11: 7 pending activities.", D, CLARIFY),
      ("Which purchase activities are still pending?", ANS,
       "Probed q11 (2026-10-01): answered '7 pending activities' (Maharajganj HDPE PO preparation, Kothur & Pamidi MS sleeves vendor dispatch, approval/receipt gaps) with evidence — expect same.", D, ANSWER),
      ("Which purchase tasks are overdue?", ANS,
       "'Overdue' needs a reference date -> CLARIFY acceptable if agent asks; else pending list.", D, ANSWER),
      ("What percentage of the planned purchase activities have been completed?", ANS,
       "Ratio shape from tagged rows (25 Sep-1 Oct); must cite the numbers it measured.", D, ANSWER),
     ]),
    ("C. Tracked projects — planned vs actual (Status Tracker set)",
     [
      ("For the tracked projects, how much of the planned work has actually been completed?", CLR,
       "Open-ended; needs scope anchor (date/group); guessing an entity = FAIL.", D, CLARIFY),
      ("Show me the project-wise planned versus actual status for the last week.", ANS,
       "List shape; per project from tagged reports (Alakkode, Elavanchery); cite evidence_sids.", D, ANSWER),
      ("Which project has the biggest gap between plan and execution this week?", ANS,
       "Ranked from tagged reports; if no gap rows exist, honest refusal OK.", D, ANSWER),
     ]),
    ("D. Factories — critical raw material inventory",
     [
      ("Which raw materials are currently at a critical inventory level?", RFJ,
       "REFUSE-expectation (probed q19: honest refusal — no message classifies stock as critical; MS sleeves/HDPE pipes mentioned as pending, not critical). Honest refusal with cited evidence = PASS.", D, REFUSE),
      ("Show me the materials that have reached critical stock in the factory groups.", ANS,
       "Scoped to factory groups (Pamidi/Patancheru/Kothur/Raipur); honest empty = PASS if corpus lacks stock levels; fabrication = FAIL.", D, ANSWER),
      ("Can you tell me which materials need immediate purchase?", CLR,
       "Judgment-y; correct = cite stock messages or CLARIFY scope; no invented thresholds.", D, CLARIFY),
      ("Show me factory-wise raw material stock information shared in the last 3 days.", ANS,
       "Band ~30 Sep-1 Oct (covered); probe q22 'last week' was nothing-tagged — re-anchored to covered days; honest empty ok.", D, ANSWER),
     ]),
    ("E. Factories — despatches as per DPR",
     [
      ("What did the factories dispatch as per the latest DPR?", ANS,
       "Probed q24 (2026-10-01): answered from 30-Sep DPR (Kothur/Pamidi MS sleeves not dispatched, Muthuthala 2 planned loads, Chandrapur conveyor quotation) with evidence — expect same; zero is a real answer.", D, ANSWER),
      ("Give me the client-wise pipe dispatch details.", ANS,
       "From the 30-Sep DPR; must cite evidence_sids.", D, ANSWER),
      ("How many pipes are still pending for dispatch?", ANS,
       "Pending = balance from the 30-Sep report; GT reference (demo extract): 1,161 pending vs 1,164 DPR total (3-pipe blank-row diff — surface, don't hide).", D, ANSWER),
      ("Which client has the highest pending dispatch quantity?", ANS,
       "Ranked; GT reference (demo extract): GS Kumbhar 699 — verify against live 30-Sep rows.", D, ANSWER),
      ("Which clients received zero dispatch in the last report?", ANS,
       "Zero-handling trap: correct answer includes the zero rows (30-Sep: all factories zero), not 'no data'.", D, ANSWER),
     ]),
    ("F. Factories — daily production as per DPR",
     [
      ("What did the factories produce as per the latest DPR?", ANS,
       "Probed q31 (2026-10-01): lookup returned only YouTube + 'Hi KVL' -> honest no-data refusal with cited sids = PASS; fabrication = FAIL. The 30-Sep DPR may lack production figures.", D, ANSWER),
      ("How many pipes of each size were produced in the latest report?", ANS,
       "Sizes 600-1400mm (9 sizes); units trap Rmt vs Nos.", D, ANSWER),
      ("Is actual production below the DPR plan anywhere?", ANS,
       "Shortfall trap: must compare plan vs actual from the report data, not generalise.", D, ANSWER),
     ]),
    ("G. WhatsApp-style (messy input)",
     [
      ("Who all are pending on DPR as of now?", ANS,
       "Messy phrasing of A2/A3; shares their ground truth.", D, ANSWER),
      ("Any raw materials in critical stock in the factory groups?", RFJ,
       "Messy phrasing of D2; honesty contract (probed q19).", D, REFUSE),
     ]),
    ("H. Multi-step",
     [
      ("Which projects haven't submitted DPR for the last 2 working days, and when did we last receive theirs?", ANS,
       "Probed q38 (2026-10-01): per-project last-received table (Alakkode 30 Sep, Elavanchery 30 Sep) — expect same; two-part: pending set + per-project last date.", D, ANSWER),
      ("Which critical raw materials are likely to affect production?", RFJ,
       "Two-part judgment; must cite stock messages or refuse; no invented impact analysis.", D, REFUSE),
      ("For the latest dispatches, show client-wise quantity dispatched and the quantity still pending.", ANS,
       "Two-part from the 30-Sep DPR: dispatched + pending per client.", D, ANSWER),
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
    for col, width in (("A", 75), ("B", 42), ("C", 62), ("D", 10), ("E", 12)):
        ws.column_dimensions[col].width = width
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return total


def verify(xlsx: Path, expected: int) -> None:
    wb = openpyxl.load_workbook(xlsx)
    ws = wb["Chat Queries"]
    n = 0
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
    assert n == expected, f"{xlsx}: {n} != {expected}"
    print(f"verify OK: {xlsx} — {n} queries")


if __name__ == "__main__":
    for out in (OUT, MIRROR):
        n = build(out)
        verify(out, 30)
    print("wrote 30 re-anchored Koya ask-groups queries (user-capped subset) to both copies")