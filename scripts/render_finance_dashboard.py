#!/usr/bin/env python3
"""Render the Finance-agent eval page (docs/finance/index.html) — two-tab, plain-language
Overview + For-developers. Same pattern as scripts/render_ar_dashboard.py.

Reads accounts/finance/runs/query_results_v2.jsonl + derived v2/ (summary, findings,
judgments, leaks). Quotes are pulled from the run file at build time. Scorecard numbers are
the run's judged verdicts (summary.json vs_expected + outcomes), footnoted as judgment with
no ground-truth baseline.

Run: python3 scripts/render_finance_dashboard.py
The previous technical page stays reproducible via scripts/render_finance_static.py.
"""
import html as H
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "accounts/finance/runs"
OUT = ROOT / "langsmith-tool-evaluator/docs/finance/index.html"
sys.path.insert(0, str(ROOT))
import build_dashboard as bd

RUN = 2
recs = [json.loads(l) for l in (RUNS / f"query_results_v{RUN}.jsonl").read_text().splitlines()]
by = {r["query_index"]: r for r in recs}
N = len(recs)
DER = RUNS / f"v{RUN}"
summ = json.loads((DER / "summary.json").read_text())
findings = json.loads((DER / "findings.json").read_text())
judgments = {j["query_index"]: j for j in (json.loads(l) for l in (DER / "judgments.jsonl").read_text().splitlines())}
leaks = [json.loads(l) for l in (DER / "leaks.jsonl").read_text().splitlines()]

# ---------------- markdown-lite (same as AR renderer) ----------------
def clean(s):
    s = re.sub(r"\\([^\da-zA-Z])", r"\1", s)
    return H.unescape(s)

def inline(t):
    t = clean(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\*+", "", t)
    return t

def md_to_html(s):
    if not s:
        return "<p class=empty>No answer.</p>"
    s = re.sub(r"<!--table:\d+-->", "", s)          # app table placeholders, not captured
    lines = s.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("### "):
            out.append(f"<h4>{inline(ln[4:])}</h4>")
        elif ln.startswith("> "):
            out.append(f"<p class=quote>{inline(ln[2:])}</p>")
        elif ln.strip().startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{inline(lines[i].strip()[2:])}</li>"); i += 1
            out.append("<ul>" + "".join(items) + "</ul>"); continue
        elif ln.startswith("|"):
            rows, i2 = [], i
            while i2 < len(lines) and lines[i2].startswith("|"):
                rows.append(lines[i2]); i2 += 1
            rows = [r for r in rows if not re.match(r"^\|[\s:|-]+\|$", r)]
            if rows:
                tbl = ["<table>"]
                for ri, row in enumerate(rows):
                    cells = [c.strip() for c in row.strip().strip("|").split("|")]
                    tag = "th" if ri == 0 else "td"
                    tbl.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
                tbl.append("</table>")
                out.append("".join(tbl)); i = i2; continue
        elif ln.strip():
            out.append(f"<p>{inline(ln.strip())}</p>")
        i += 1
    return "\n".join(out)

def snippet(qi, limit=420):
    s = clean(by[qi].get("response") or "")
    if len(s) > limit:
        cut = s.rfind(".", 0, limit)
        s = s[: cut if cut > 200 else limit] + " …"
    return md_to_html(s)

# ---------------- outcomes (machine) + expected labels ----------------
OUT_LABEL = {"success": "Answered", "marginal": "Partial", "no_data": "No data",
             "clarify": "No answer", "fail": "No answer"}
EXP_LABEL = {"ANSWER": "Data answer", "CLARIFY": "Follow-up expected", "REFUSE": "Should decline"}
def outcome(r):
    return bd.classify_quality(r)

parks = sorted(i for i, r in by.items() if "interrupt" in (r.get("status_sequence") or []))
by_outcome = Counter(outcome(r) for r in recs)

lat = defaultdict(list)
for r in recs:
    lat[outcome(r)].append(r.get("response_time_seconds") or 0)
def lats(k):
    v = sorted(lat[k]); return len(v), (round(sum(v) / len(v), 1) if v else 0), (round(median(v), 1) if v else 0)

# verdict levels from judgments
LVL_PLAIN = {"L5": "Decision-grade", "L4": "Decision-grade", "L3": "Useful", "L2": "Thin", "REF": "Refusal", "": "Not judged"}

# ---------------- hand-graded / judged constants (finance v2 readout, 2026-09-24) ----------------
SCORECARD = [
    ("Solid answers", summ["vs_expected"]["match"], "ok", "✓", "Per-query verdict matched expectations"),
    ("Partially right", summ["vs_expected"]["partial"], "partial", "◐", "Right direction, missing pieces"),
    ("Off-target", summ["vs_expected"]["mismatch"], "bad", "✗", "Gate drift — answered/parked/refused unexpectedly"),
    ("Honest “can’t do”", summ["outcomes"]["hard_refusal"], "ok", "?", "Clean refusal naming the missing data"),
    ("No answer (parked)", summ["outcomes"]["parked"], "none", "–", "Stopped to ask, question not captured"),
    ("Technical errors", summ["vs_expected"]["error"], "ok", "✓", "Stream/backend failures"),
]

GORES_WRONG = [
    {
        "title": "Placeholder tokens leak into answers",
        "q": 9,
        "note": "Literal “[unverified]” appears 48 times across 15 of 25 answers (v1 had 2). It eats the decision-critical figures — q9's whole recovery plan names no numbers. The footer says “N unverified figures removed by the grounding guard” while the tokens still ship.",
    },
    {
        "title": "Follow-up questions can return nothing",
        "q": 24,
        "note": "5 of 30 questions (q5, q6, q7, q23, q24) stopped in ~1.6 s with no question and no answer on the wire. Two of them (q7, q24) were expected to be answered outright.",
    },
    {
        "title": "Asking the same thing twice gives different behaviour",
        "q": 1,
        "note": "The classify gate is ~30% stochastic: 9 questions expected to pause for a follow-up instead got full answers (q1 answered above, though the label said “follow-up expected”), while 2 expected to be answered outright (q7, q24) parked.",
    },
    {
        "title": "Numbers contradict inside one answer",
        "q": 16,
        "note": "“Sales surged in ₹9,71,68,124 to ₹9,71,68,124” — a broken range — and the answer's headline sales figure (₹24,20,47,712) disagrees with its own bullets. A reader can't tell which number is real.",
    },
    {
        "title": "Answers reuse the same skeleton",
        "q": 4,
        "note": "~15 of 20 answers recycle the same top-5 chase block (Ganesh ₹4,94,550 · Jai ₹4,50,426 · Krishna ₹4,33,051 · Om ₹4,43,121 · Om ₹4,19,575) and the same KPI trio (₹17,50,35,089 outstanding / DSO 126.6 days / 33.8% collected). These numbers are correct but the repetition hides what's new in each answer.",
    },
]

WE_GOOD = ("Solid economy of language and a clear money story: **₹17,50,35,089 outstanding across "
           "1,551 debtors**, the five largest balances named, and the highest-exposure accounts "
           "called out for the chase.")

IDEAL = ("“Cash is stuck in a handful of big overdue accounts: ₹17,50,35,089 is outstanding "
         "across 1,551 debtors, and the five largest balances — led by Ganesh Retail Traders — "
         "are the place to start the chase today.”")

# popularity check for the good-answer section (q4)
GOODQ = 4

# ---------------- dev-tab constants (from readout/summary) ----------------
mis = summ["vs_expected"].get("mismatch_details", {})
CKEY, AKEY, RKEY = "CLARIFY\u2192", "ANSWER\u2192", "REFUSE\u2192"
DEV_FAILMAP = [
    ("Grounding-placeholder leak (P0)", [
        "Literal [unverified] in answers: 2 (v1) → 48 across 15 of 25 answers (v2).",
        "Strikes decision-critical figures: q9's whole recommendation is hollow (12 figures stripped); q8/q10/q19/q22 counts, amounts, comparisons eaten.",
        "Footer claims “N unverified figures removed” while 40+ tokens ship in prose (q1: footer says 2 removed, 2 tokens in text).",
        "Root cause (F16): free-form semantic keys ({total_outstanding}-style) never resolve from the emitted figures array; v1's positional {fN} always had a match.",
    ]),
    ("Clarify gate drift (~30% stochastic)", [
        f"12 verdict mismatches: {mis.get(CKEY + 'answered', 0)} CLARIFY→answered, {mis.get(AKEY + 'parked', 0)} ANSWER→parked (q7, q24), {mis.get(RKEY + 'answered', 1)} REFUSE→answered.",
        "Interrupt payload (the clarifying question + options) is still NOT captured on the wire — parks are empty responses.",
        "Parked turns are fast (median 1.6 s) — the gate bails early, the runner cannot resume.",
    ]),
    ("Cross-answer template reuse (P1 value)", [
        "Same top-5 chase block in ~15 of 20 answers (₹4,94,550 / ₹4,50,426 / ₹4,43,121 / ₹4,33,051 / ₹4,19,575).",
        "KPI trio recycled everywhere: outstanding ≈₹17,50,35,089 · DSO 126.6 · collections 33.8%.",
        "0 L5 answers in v2 (v1 had 4) — the rigid What/Why/Watch/Actions template suppresses organic proactive items.",
    ]),
    ("Craft nits", [
        "q16 renders a broken range (“surged in ₹9,71,68,124 to ₹9,71,68,124”) and its headline sales figure contradicts its bullets.",
        "Double periods (“.. I can work”) in q17/q18/q27; q17's “0 figures verified” footer on a refusal.",
        "Data recency: answers cite a latest-month drop (9.77 crore → 11.98 lakh) that contradicts the max invoice date (F-001, low).",
    ]),
]

DEV_BUGS = [
    ("P0", "Grounding-placeholder leak — [unverified] tokens ship in prose; footer tally doesn't match (F-002 → 15 queries)", "q1, q2, q8, q9, q10, q11, q13, q15, q19, q20, q21, q22, q25, q26, q29"),
    ("P1", "Clarify gate drift — ~30% stochastic park rate; ALIGN answer/expected label", "q1, q3, q7, q11, q19, q20, q21, q22, q24, q25, q30"),
    ("P1", "Template reuse — same top-5 block + KPI trio in ~15 of 20 answers", "~15 of 20 answered"),
    ("P2", "Broken range rendering", "q16"),
    ("P2", "Headline/bullet contradiction (sales figure)", "q16"),
    ("P2", "Double-period craft nits", "q17, q18, q27"),
    ("P2", "“0 figures verified” footer on a refusal", "q17"),
    ("P3", "Data recency — cited drop contradicts max invoice date", "F-001"),
]

DEV_NUMBERS = [
    ("[unverified] tokens", "v1 → v2 regression", "2 (q1) → 48 across 15 answers"),
    ("Answered latency median", "v1 → v2", "47.2 s → 21.4 s (p95 30.7 s, max 30.7 s)"),
    ("q16 sales range", "inside one answer", "₹9,71,68,124 → ₹9,71,68,124 (identical endpoints)"),
    ("q16 headline vs bullets", "inside one answer", "₹24,20,47,712 headline vs bullet-level figures"),
    ("Top-5 chase block", "reused across answers", "₹4,94,550 / ₹4,50,426 / ₹4,43,121 / ₹4,33,051 / ₹4,19,575 (consistent, recycled)"),
    ("KPI trio", "reused across answers", "₹17,50,35,089 · DSO 126.6 days · 33.8% collected"),
]

DEV_HARNESS = [
    "Finance streams NO tool events (metric answers are backend SQL) — expected_tool is the review intent label only; grade behavior + answer quality, never tool_calls.",
    "Interrupts recorded as empty responses — the clarifying question + options are not on the wire; the runner flags possible_clarify but cannot resume.",
    "Classify gate is stochastic (~30% park rate): same query can park in one run and answer in the next (q3 parked in v1, answered in v2).",
    "Judge (judgments.jsonl) is an in-session model, same family as the grader, no external call; a 10-answer human calibration spot-check is the open item.",
    "Reconcile guard banner leaks a workspace reference on 1 answer (q2, workspace_ref rule).",
    "“Ask next:” suggestion footers are app UI — stripped before leak detection (see AR run lesson).",
]

DEV_FIX_ORDER = [
    "Placeholder fix (P0): on key ref-miss drop the sentence fragment, or reuse only keys from the emitted figures array, or render “—” and suppress the clause.",
    "Capture the interrupt payload on the wire so parks carry the clarifying question (eval harness + client).",
    "Per-intent evidence selection to break template reuse; keep the What/Why/Watch/Actions template but let evidence vary the content.",
    "Craft nits: range rendering, headline-consistency check, double periods, footer on refusals.",
    "Re-investigate the L5 regression once reuse is fixed (v1's 4 L5 answers were the organic compositions).",
]

# ---------------- explorer data ----------------
def level_plain(i):
    j = judgments.get(i)
    if not j:
        return "Not judged"
    lv = j.get("level")
    return LVL_PLAIN.get(lv, lv or "Not judged")

expl = []
for r in recs:
    i = r["query_index"]
    t = re.sub(r"<[^>]+>", " ", md_to_html(clean(r.get("response") or "")))
    t = re.sub(r"\s+", " ", t).strip()
    lv = level_plain(i)
    out = "Honest refusal" if lv == "Refusal" else OUT_LABEL[outcome(r)]
    expl.append({
        "i": i, "exp": EXP_LABEL.get(r.get("expected_behavior"), r.get("expected_behavior", "?")),
        "out": out, "lvl": lv,
        "q": clean(r.get("query") or ""),
        "a": (t[:420] + " …") if len(t) > 420 else t,
        "s": round(r.get("response_time_seconds") or 0),
    })

# ---------------- page ----------------
Q = lambda s: H.escape(s)

score = "".join(f'<div class="tile tile-{c}" title="{_d}"><div class="tile-icon">{ic}</div><div class="tile-n">{n}</div><div class="tile-l">{lab}</div></div>'
                for lab, n, c, ic, _d in SCORECARD)

def card_goes(g):
    qq = Q(clean(by[g["q"]]["query"]))
    return f"""<div class="card"><h3>{g['title']}</h3>
  <p class="qq"><span class="qmark">Q</span> “{qq}” <span class="qi">q{g['q']}</span></p>
  <div class="ans">{snippet(g['q'], 420)}</div>
  <p class="note">{g['note']}</p></div>"""
gores = "\n".join(card_goes(g) for g in GORES_WRONG)

fm = "".join(f'<div class="fm"><h3>{t}</h3>' + "".join(f"<p>{i}</p>" for i in it) + "</div>" for t, it in DEV_FAILMAP)
bugs = "".join(f"<tr><td>{Q(a)}</td><td>{Q(b)}</td><td>{Q(c)}</td></tr>" for a, b, c in DEV_BUGS)
nums = "".join(f"<tr><td>{Q(a)}</td><td>{Q(b)}</td><td>{Q(c)}</td></tr>" for a, b, c in DEV_NUMBERS)
harness = "".join(f"<li>{Q(h)}</li>" for h in DEV_HARNESS)
fix = "".join(f"<li>{Q(f)}</li>" for f in DEV_FIX_ORDER)
lat_rows = "".join(f"<tr><td>{k}</td><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>"
                   for k, v in [("Answered", lats("success")), ("Partial", lats("marginal")),
                                ("No data", lats("no_data")), ("No answer (parked)", lats("clarify"))])
# findings from file (automatic)
find_rows = ""
for f in findings[:14]:
    if isinstance(f, dict):
        fid = f.get("id", "?")
        sev = f.get("severity", "")
        ev = str(f.get("evidence", ""))[:180].replace("\n", " ")
        find_rows += f'<tr><td>{Q(fid)}</td><td><span class="chip sev-{Q(sev)}">{Q(sev)}</span> {Q(ev)}</td></tr>'

exp_opts = "".join(f'<option>{Q(v)}</option>' for v in sorted(set(e["exp"] for e in expl)))
out_opts = "".join(f'<option>{Q(v)}</option>' for v in sorted(set(e["out"] for e in expl)))
exp_rows = "".join(
    f'<tr data-exp="{Q(e["exp"])}" data-out="{Q(e["out"])}"><td class="qi">q{e["i"]}</td>'
    f'<td class="qcol">{Q(e["q"][:110])}</td>'
    f'<td><span class="chip chip-exp">{e["exp"]}</span></td>'
    f'<td><span class="chip chip-{e["out"].lower().replace(" ","-")}">{e["out"]}</span></td>'
    f'<td><span class="chip chip-lvl">{e["lvl"]}</span></td>'
    f'<td class="s">{e["s"]}s</td><td class="acol">{Q(e["a"])}</td></tr>' for e in expl)

q1 = by[1]
FQ_BAD = re.sub(r"<[^>]+>", " ", md_to_html(clean(q1["response"])))
m_footer = re.search(r"_How I worked this out.*?_", q1["response"])

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Finance agent — CFO answers, 30-question test</title>
<style>
:root{ --bg:#f8fafc; --card:#ffffff; --ink:#0f172a; --mut:#475569; --line:#e2e8f0;
 --acc:#2563eb; --ok:#15803d; --bad:#b91c1c; --warn:#b45309; --none:#64748b; --soft:#f1f5f9; }
@media (prefers-color-scheme: dark){ :root{ --bg:#0b1220; --card:#111a2e; --ink:#e2e8f0;
 --mut:#94a3b8; --line:#1e293b; --acc:#60a5fa; --ok:#4ade80; --bad:#f87171; --warn:#fbbf24;
 --none:#94a3b8; --soft:#172033; } }
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 18px 60px}
header h1{font-size:24px;margin:0 0 4px} header p{color:var(--mut);margin:2px 0}
.tabs{display:flex;gap:8px;margin:22px 0 4px;border-bottom:2px solid var(--line)}
.tabs button{background:none;border:none;padding:10px 16px;font-size:15px;cursor:pointer;
 color:var(--mut);border-bottom:3px solid transparent;margin-bottom:-2px}
.tabs button.on{color:var(--acc);border-color:var(--acc);font-weight:600}
.pane{display:none} .pane.on{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
.verdict{font-size:17px;background:var(--card);border:1px solid var(--line);
 border-left:4px solid var(--acc);border-radius:10px;padding:16px 18px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 12px;text-align:center}
.tile-icon{font-size:20px} .tile-n{font-size:30px;font-weight:700;margin:2px 0}
.tile-l{font-size:12px;color:var(--mut);line-height:1.3}
.tile-ok .tile-icon{color:var(--ok)} .tile-bad .tile-icon{color:var(--bad)}
.tile-partial .tile-icon{color:var(--warn)} .tile-none .tile-icon{color:var(--none)}
h2{font-size:20px;margin:34px 0 10px} h3{font-size:16px;margin:0 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.qq{color:var(--mut);font-style:italic;margin:2px 0 10px} .qi{font-style:normal;font-size:12px;color:var(--mut)}
.qmark{display:inline-block;background:var(--soft);border-radius:6px;padding:0 7px;font-weight:700;color:var(--acc)}
.ans{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:13.5px;overflow-x:auto}
.ans table{border-collapse:collapse;margin:6px 0;font-size:13px}
.ans th,.ans td{border:1px solid var(--line);padding:4px 9px;text-align:left}
.ans th{background:var(--card)} .note{color:var(--mut);font-size:13.5px;margin:10px 0 0}
ul{margin:6px 0;padding-left:22px} .quote{color:var(--mut)}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:760px){.compare{grid-template-columns:1fr} .grid{grid-template-columns:repeat(2,1fr)}}
.filters{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0;align-items:center}
.filters select{background:var(--card);color:var(--ink);border:1px solid var(--line);
 border-radius:8px;padding:7px 10px;font-size:14px}
.tblwrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}
table.tbl{border-collapse:collapse;width:100%;font-size:13.5px;min-width:760px}
.tbl th{text-align:left;background:var(--soft);padding:9px 12px;border-bottom:1px solid var(--line)}
.tbl td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.qcol{font-weight:600;max-width:240px} .acol{color:var(--mut);max-width:340px}
.s{white-space:nowrap;color:var(--mut)}
.chip{display:inline-block;border-radius:99px;padding:2px 10px;font-size:12px;border:1px solid}
.chip-answered{color:var(--ok);border-color:var(--ok)}
.chip-partial{color:var(--warn);border-color:var(--warn)}
.chip-no-data{color:var(--none);border-color:var(--none)}
.chip-no-answer{color:var(--bad);border-color:var(--bad)}
.chip-exp{color:var(--acc);border-color:var(--acc)}
.chip-honest-refusal{color:var(--none);border-color:var(--none);background:var(--soft)}
.chip-lvl{color:var(--mut);border-color:var(--line)}
.sev-low{color:var(--none)} .sev-medium{color:var(--warn)} .sev-high{color:var(--bad)}
.rowcount{color:var(--mut);font-size:13px}
.fn{color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);margin-top:34px;padding-top:12px}
ol{margin:6px 0;padding-left:24px} ol li{margin:4px 0}
.fm{margin:10px 0} .fm h3{margin-bottom:4px} .fm p{margin:3px 0;color:var(--mut);font-size:14px}
table.numt{border-collapse:collapse;width:100%;margin:8px 0 4px;font-size:14px}
.numt th,.numt td{border:1px solid var(--line);padding:7px 11px;text-align:left}
.numt th{background:var(--soft)} .flag{color:var(--bad);font-weight:600}
.p0{color:var(--bad);font-weight:700}
</style></head><body><div class="wrap">

<header>
  <h1>Finance agent — 30 CFO questions test</h1>
  <p>Metric answers about receivables, cash and collections · hirafoods workspace · 2026-09-24 (v2, post PR #20789)</p>
</header>

<div class="tabs">
  <button class="on" data-tab="ov">Overview</button>
  <button data-tab="dev">For developers</button>
</div>

<section class="pane on" id="pane-ov">
  <div class="verdict">Answers come back fast and most are clean — but a grounding bug prints
  literal “[unverified]” in place of the decision-critical figures in 15 of 25 answers, and
  the same “who to chase” list is recycled across most replies.</div>

  <h2>Scorecard</h2>
  <div class="grid">__SCORECARD__</div>

  <h2>What works</h2>
  <div class="card"><ul>
    <li><strong>Clean refusals.</strong> “Revenue is strong, but this view cannot prove profit because cost data is missing” — profitability questions are refused with the boundary named, no invented numbers.</li>
    <li><strong>Answers open with the finding.</strong> Post-fix, answers start with the conclusion (“Cash blockage is concentrated in a few overdue accounts…”) instead of boilerplate.</li>
    <li><strong>Fast, and no technical failures.</strong> Median 21.4 s (was 47.2 s), p95 30.7 s, 0 errors — the query that failed at 244.7 s in v1 now answers in 20.6 s.</li>
    <li><strong>Figures are grounded with disclosure.</strong> The footer states how many figures were verified and how many unverified were removed by the guard.</li>
    <li><strong>Actionable detail.</strong> Answers name accounts and amounts (Ganesh ₹4,94,550, Jai ₹4,50,426…) with a next step attached.</li>
  </ul></div>

  <h2>What goes wrong</h2>
  __GORES__

  <h2>What a good answer looks like</h2>
  <div class="compare">
    <div class="card"><h3>What the assistant gave</h3>
      <p class="qq"><span class="qmark">Q</span> “__GOODQ__” <span class="qi">q4</span></p>
      <div class="ans">__GOODACT__</div>
      <p class="note">Good: the money story upfront, accounts named with amounts. Held back by the recycled KPI trio that appears in most answers.</p>
    </div>
    <div class="card"><h3>Ideal answer</h3>
      <div class="ans" style="background:transparent;border:2px solid var(--ok)">
        <p>__IDEAL__</p>
      </div>
      <p class="note">One number, one conclusion, one place to start — decision-grade in a single breath.</p>
    </div>
  </div>

  <h2>All 30 questions</h2>
  <div class="filters">
    <select id="f-exp"><option value="">All expectations</option>__EXPOPTS__</select>
    <select id="f-out"><option value="">All outcomes</option>__OUTOPTS__</select>
    <span class="rowcount" id="rc">Showing all 30 questions</span>
  </div>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>#</th><th>Question</th><th>Expected</th><th>Outcome</th><th>Level</th><th>Time</th><th>Answer (trimmed)</th></tr></thead>
    <tbody id="tbody">__ROWS__</tbody>
  </table></div>
</section>

<section class="pane" id="pane-dev">
  <h2>Failure map, ordered by impact</h2>
  __FAILMAP__
  <h2>Bug list</h2>
  <table class="numt"><thead><tr><th>Severity</th><th>Issue</th><th>Queries</th></tr></thead><tbody>__BUGS__</tbody></table>
  <h2>Numbers of note</h2>
  <table class="numt"><thead><tr><th>Item</th><th>Where</th><th>Value</th></tr></thead><tbody>__NUMS__</tbody></table>
  <h2>Findings (from the run pipeline)</h2>
  <table class="numt"><thead><tr><th>ID</th><th>Evidence</th></tr></thead><tbody>__FINDS__</tbody></table>
  <h2>Harness notes</h2>
  <ul>__HARNESS__</ul>
  <h2>Latency</h2>
  <table class="tbl" style="min-width:0"><thead><tr><th>Outcome</th><th>Count</th><th>Mean (s)</th><th>Median (s)</th></tr></thead><tbody>__LAT__</tbody></table>
  <p class="note">Separate: hard refusals median 1.4 s; parked turns median 1.6 s; overall 30 queries. Full interactive technical page remains reproducible via <code>scripts/render_finance_static.py</code>.</p>
  <h2>Suggested fix order</h2>
  <ol>__FIX__</ol>
  <p class="fn">Judgment, not ground truth: verdicts/levels are the run's own per-query judge (in-session model, no external call; human calibration still open), quality buckets are the classifier's, quotes are verbatim from the run file. Hand-grading a subset remains the open item.</p>
</section>

<p class="fn">Scoring: solid answers 15 · partially right 3 · off-target 12 · honest “can’t do” 5 · no answer (parked) 5 · technical errors 0. These are the run's judged verdicts — no ground-truth baseline exists; quotes on this page are verbatim from the run file (accounts/finance/runs/query_results_v2.jsonl).</p>
</div>
<script>
var tabs=document.querySelectorAll('.tabs button');tabs.forEach(function(b){b.onclick=function(){
 tabs.forEach(function(x){x.classList.remove('on')});b.classList.add('on');
 document.querySelectorAll('.pane').forEach(function(p){p.classList.remove('on')});
 document.getElementById('pane-'+b.dataset.tab).classList.add('on');window.scrollTo(0,0);}});
function rep(){var e=document.getElementById('f-exp').value,o=document.getElementById('f-out').value,n=0;
 document.querySelectorAll('#tbody tr').forEach(function(tr){
  var ok=(!e||tr.dataset.exp===e)&&(!o||tr.dataset.out===o);tr.style.display=ok?'':'none';if(ok)n++;});
 document.getElementById('rc').textContent='Showing '+n+' of 30 questions';}
document.getElementById('f-exp').onchange=rep;document.getElementById('f-out').onchange=rep;
</script>
</body></html>"""

goodq = clean(by[GOODQ]["query"])
goodact = snippet(GOODQ, 480)

page = (HTML.replace("__SCORECARD__", score).replace("__GORES__", gores)
        .replace("__GOODQ__", Q(goodq)).replace("__GOODACT__", goodact).replace("__IDEAL__", IDEAL.replace("₹", "₹"))
        .replace("__EXPOPTS__", exp_opts).replace("__OUTOPTS__", out_opts).replace("__ROWS__", exp_rows)
        .replace("__FAILMAP__", fm).replace("__BUGS__", bugs).replace("__NUMS__", nums)
        .replace("__FINDS__", find_rows).replace("__HARNESS__", harness)
        .replace("__LAT__", lat_rows).replace("__FIX__", fix))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page)
print(f"WROTE {OUT} ({len(page)} bytes, {N} records) outcomes=" + " ".join(f"{k}={v}" for k, v in sorted(by_outcome.items()))
      + f" verdicts={summ['vs_expected']}")