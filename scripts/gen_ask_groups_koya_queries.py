#!/usr/bin/env python3
"""Rebuild accounts/ask-groups-koya/queries.xlsx — 40 fine-tuned Ask My Groups queries,
Koya/KCCL-grounded.

User-approved flow 2026-09-28: 40 queries in the style of the user's shared 6-category
reference (DPR pending / Purchase planned-vs-action / tracked projects / factory critical
inventory / despatches / production + WhatsApp-style + multi-step), FINE-TUNED against the
actual extracted data in `Project Status Update-KCCL.xlsx` (Status Tracker--V1, 496 rows).

Real anchors used (verified from the sheet 2026-09-28):
- Corpus/date band: reports 20-Jul -> 12-Aug 2026; ONLY KWA-JJM-Alakkode-I-WTP, Project JJM
  Moopainad, Raipur Project reported on the last date (12-Aug); Elavanchery's last actual
  is 8-Aug; Moopainad Meppadi 30-Jul; Ramagundam 29-Jul; Wayanad Phase II 21-Jul (max gap).
- Plan-with-NO-action on 05-Aug: Pamidi Factory, JJM Nandigama Project, Vizianagaram Factory.
- Projects: 65 names incl. Alakkode (142 rows), Elavanchery (87), Thrikkalangode (multiple
  name variants ~5), Pamidi Factory, Kothur Factory, Patancheru Factory, Raipur variants.
- Departments: Purchase (209) + Procurement (56); statuses: Awaiting 118, In Progress 50,
  Follow-up 46, Completed 37, Planned 8, Partially Completed 4, Not Completed 2.
- Senders: Archana Sudhan (145), bharath kumar (74), Immu, Poonam, SHAIK ZAKEER, Syed Ismail.
- Groups: "Purchase HO team" (209), "KWA-JJM-Alakkode-I-WTP" (142), "KWA - JJM - Elevanchery" (88),
  "Test Project Zotok Koya 2026" (57).
- Activities: Laying of 700mm dia DI Pipe, Testing of 700 mm dia DI Pipe, OHSR, RA Bill 8
  preparation, IR Sheet & Nut & Bolts, DI Specials, Thonikakadavu PCB Wall chamber work,
  Leakage Rectification work, ESR & WTP Watco DI Pipes MS Pipe.

Labels: expected_behavior ANSWER (real data answer) / CLARIFY (needs a scope anchor) /
REFUSE (correct = graceful "not in my messages", fabrication = FAIL). expected_tool = no_tool
(ask_chats engine has NO user-visible tool events — grade behavior/answer/evidence_sids).

CAVEAT baked into remarks: live tagged corpus may differ from the sheet (sheet = extraction of
the same messages); every numeric answer must carry the coverage caveat; date strings in the
sheet are messy ("12th August 2026" vs "12-Aug") -> alias/format traps are part of the eval.
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
RFJ = "REFUSE gracefully if the tagged corpus has no such messages (intro/fallback). Fabricated stock/production figures = FAIL."

SECTIONS = [
    ("A. Projects — DPR not received (anchor 12-Aug-2026)",
     [
      ("Which projects haven't submitted their DPR on 12 August?", ANS,
       "GT: sheet shows ONLY KWA-JJM-Alakkode-I-WTP, Project JJM Moopainad, Raipur Project reported 12-Aug; ~60 other names have no 12-Aug report. Date-format trap: '12th August 2026' vs '12-Aug'.", D, ANSWER),
      ("Show me the projects where the 12 August DPR is still pending.", ANS,
       "Same GT as A1, list shape. Must not silently merge name variants (Thrikkalangode has ~5 spellings).", D, ANSWER),
      ("Which projects haven't shared their DPR as of 12 August?", ANS,
       "Paraphrase robustness of A1 (haven't submitted vs haven't shared vs pending).", D, ANSWER),
      ("Which projects have not sent the DPR in the last 2 working days?", ANS,
       "Working-day band; GT: most sites last reported before 10-Aug (only 3 reported 12-Aug).", D, ANSWER),
      ("Are there any projects that haven't submitted DPR for more than 2 working days?", ANS,
       "GT extreme: JJM Wayanad Phase II last 21-Jul, Elavanchery 8-Aug, Moopainad Meppadi 30-Jul.", D, ANSWER),
      ("What was the last DPR received from each of the pending projects?", ANS,
       "Per-project last report date: Elavanchery 8-Aug, Pamidi 30-Jul, Ramagundam 29-Jul, Thrikkalangode WTP 30-Jul, Mananthavady 30-Jul, Keshavapuram 30-Jul.", D, ANSWER),
      ("Sort the projects by number of working days since their last DPR.", ANS,
       "Ranked shape; top of list should be Wayanad Phase II (21-Jul) etc.; must compute from counted dates not guess.", D, ANSWER),
      ("Exclude weekends and show me only the actual working-day delays.", ANS,
       "Working-day refinement of A6/A7; correct = recompute band minus Sat/Sun.", D, CLARIFY),
     ]),
    ("B. Purchase — planned vs action (dept Purchase/Procurement)",
     [
      ("How are we doing against the purchase plan?", CLR,
       "Open-ended; GT: Purchase 209 + Procurement 56 rows, statuses Awaiting 118 / In Progress 50 / Follow-up 46 / Completed 37.", D, ANSWER),
      ("Show me planned purchases versus what the Purchase team has actually done.", ANS,
       "Plan-vs-Actual in 'Purchase HO team' group (209 msgs).", D, ANSWER),
      ("Which purchase activities are still pending?", ANS,
       "GT: status Awaiting=118 + Not Completed=2 in Purchase/Procurement.", D, ANSWER),
      ("Which purchase tasks are overdue?", ANS,
       "Awaiting/Not-Completed with date band; 'overdue' needs a reference date -> CLARIFY acceptable if agent asks.", D, ANSWER),
      ("Can you identify purchases where no action has been taken against the plan?", ANS,
       "GT Plan-with-no-Action 05-Aug: Pamidi Factory, JJM Nandigama Project, Vizianagaram Factory; status Planned=8.", D, ANSWER),
      ("What percentage of the planned purchase activities have been completed?", ANS,
       "Ratio shape: 37 Completed vs planned count in Purchase; must cite the numbers it measured.", D, ANSWER),
     ]),
    ("C. Tracked projects — planned vs actual (Status Tracker set)",
     [
      ("For the tracked projects, how much of the planned work has actually been completed?", CLR,
       "Open-ended; GT: tracker 65 projects, Plan 310 / Actual 163 rows.", D, ANSWER),
      ("Which of the tracked projects are behind their plan?", ANS,
       "GT anchors: Plan-without-Actual on 05-Aug (Pamidi, Nandigama, Vizianagaram); Actual < Plan overall.", D, ANSWER),
      ("Show me the project-wise planned versus actual status.", ANS,
       "List shape; GT per project: Alakkode Plan 11/Actual 8 (per-date), Elavanchery 48 Plan/39 Actual.", D, ANSWER),
      ("Which project has the biggest gap between plan and execution?", ANS,
       "Ranked; GT candidates: Wayanad Phase II (1 Plan, 0 Actual), Nilambur (2/0), Mananthavady (2/0).", D, ANSWER),
     ]),
    ("D. Factories — critical raw material inventory",
     [
      ("Which raw materials are currently at a critical inventory level?", RFJ,
       "Stock facts live in shared DPR/stock messages only; if absent from tagged corpus honest REFUSE is the PASS. Factory projects: Pamidi, Patancheru, Kothur, Raipur.", D, ANSWER),
      ("Show me the materials that have reached critical stock in the factory groups.", ANS,
       "Scoped to factory groups (Pamidi/Patancheru/Kothur/Raipur).", D, ANSWER),
      ("Can you tell me which materials need immediate purchase?", CLR,
       "Judgment-y; correct = cite stock messages or CLARIFY scope; no invented thresholds.", D, ANSWER),
      ("Show me factory-wise raw material stock information shared in the last week.", ANS,
       "Band 05-Aug..12-Aug; factory groups; REFUSE with honest empty ok.", D, ANSWER),
      ("Which materials are at risk of running out?", RFJ,
       "Same honesty contract as D1.", D, ANSWER),
     ]),
    ("E. Factories — despatches as per DPR",
     [
      ("What did the factories dispatch as per the latest DPR?", ANS,
       "Grounding: dispatch facts appear in Actual/Status Update reports + 'Koya Test Group - Pipe Dispatch & Laying' synthetic group; zero-handling trap (0 is a real answer).", D, ANSWER),
      ("Show dispatches factory-wise from the latest DPR.", ANS,
       "Factory filter: Chandrapur/Kothur/Pamidi/Patancheru/Raipur variants.", D, ANSWER),
      ("Which clients received pipes in the latest dispatch report?", ANS,
       "Client list from dispatch messages (e.g. Aquarii, GS Kumbhar, GVPR, Laxmi Civil, Vedant Innova - as mentioned in messages).", D, ANSWER),
      ("Give me the client-wise pipe dispatch details.", ANS,
       "Client x qty table; must cite evidence_sids.", D, ANSWER),
      ("How many pipes are still pending for dispatch?", ANS,
       "Pending = balance from latest report; GT reference: 1,161 numeric pending vs 1,164 DPR total (3-pipe blank-row diff - surface, don't hide).", D, ANSWER),
      ("Which client has the highest pending dispatch quantity?", ANS,
       "Ranked; GT reference: GS Kumbhar 699 largest in demo extract.", D, ANSWER),
      ("Which clients received zero dispatch in the last report?", ANS,
       "Zero-handling trap: correct answer includes the zero rows, not 'no data'.", D, ANSWER),
     ]),
    ("F. Factories — daily production as per DPR",
     [
      ("What did the factories produce as per the latest DPR?", ANS,
       "Production facts in Actual/DPR messages; zero/blank handling (GT 30-Aug report: today=0 across all rows).", D, ANSWER),
      ("Show production client-wise from the latest DPR.", ANS,
       "Client x qty x size; GT reference: Aquarii 2,602 Rmt/520 nos in demo extract.", D, ANSWER),
      ("How many pipes of each size were produced in the latest report?", ANS,
       "Sizes 600-1400mm (9 sizes); units trap Rmt vs Nos.", D, ANSWER),
      ("Which factory produced the most in the last report?", ANS,
       "Ranked factory comparison.", D, ANSWER),
      ("Is actual production below the DPR plan anywhere?", ANS,
       "Shortfall trap: must compare plan vs actual from the report data, not generalise.", D, ANSWER),
     ]),
    ("G. WhatsApp-style (messy input)",
     [
      ("Who all are pending on DPR as of 12 August?", ANS,
       "Messy phrasing of A1; shares its ground truth.", D, ANSWER),
      ("Any raw materials in critical stock in the factory groups?", RFJ,
       "Messy phrasing of D2; honesty contract.", D, ANSWER),
     ]),
    ("H. Multi-step",
     [
      ("Which projects haven't submitted DPR for the last 2 working days, and when did we last receive theirs?", ANS,
       "Two-part: pending set + per-project last date. GT: only 3 reported 12-Aug; per-project dates as A6.", D, ANSWER),
      ("Which critical raw materials are likely to affect production?", RFJ,
       "Two-part judgment; must cite stock messages or refuse; no invented impact analysis.", D, ANSWER),
      ("For the latest dispatches, show client-wise quantity dispatched and the quantity still pending.", ANS,
       "Two-part: dispatched + pending per client from the latest report.", D, ANSWER),
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
        verify(out, 40)
    print("wrote 40 fine-tuned Koya ask-groups queries to both copies")