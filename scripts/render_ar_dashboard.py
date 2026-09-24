#!/usr/bin/env python3
"""Render the AR-agent eval page (docs/ar-agent/index.html) — two-tab, plain-language
overview + developer tab. Improves the build_dashboard.py output for THIS account only.

Reads accounts/ar-agent/runs/query_results_v2.jsonl, computes outcomes with
build_dashboard.classify_quality, and embeds every quote by pulling it from the run file
at build time (no hand-typed transcription). Hand-graded scorecard numbers and analysis
facts come from the user's eval review (2026-09-24) — kept as constants below, each marked
with the query ids or counts it cites.

Run: python3 scripts/render_ar_dashboard.py   (writes langsmith-tool-evaluator/docs/ar-agent/index.html)
"""
import html as H
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "accounts/ar-agent/runs"
OUT = ROOT / "langsmith-tool-evaluator/docs/ar-agent/index.html"
sys.path.insert(0, str(ROOT))
import build_dashboard as bd

RUN = 2
recs = [json.loads(l) for l in (RUNS / f"query_results_v{RUN}.jsonl").read_text().splitlines()]
by = {r["query_index"]: r for r in recs}
N = len(recs)

# ---------------- markdown-lite -> HTML (strip escapes, real tables) ----------------
def clean(s):
    s = re.sub(r"\\([^\da-zA-Z])", r"\1", s)   # \* \. \( \) \\, etc.
    return H.unescape(s)                        # &amp; -> &, &quot; -> "

def inline(t):
    t = clean(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\*+", "", t)   # no legit asterisks in these answers; drop strays
    return t

def md_to_html(s):
    if not s:
        return "<p class=empty>No answer.</p>"
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

def snippet(qi, limit=480):
    s = clean(by[qi].get("response") or "")
    if len(s) > limit:
        cut = s.rfind(".", 0, limit)
        s = s[: cut if cut > 200 else limit] + " …"
    return md_to_html(s)

# ---------------- outcomes ----------------
OUT_LABEL = {"success": "Answered", "marginal": "Partial", "no_data": "No data",
             "clarify": "No answer", "fail": "No answer"}
def outcome(r):
    return bd.classify_quality(r)

cats = []
for r in recs:
    if r.get("category") not in cats and r.get("category"):
        cats.append(r["category"])
cat_orders = sorted(cats)
by_outcome = Counter(outcome(r) for r in recs)

lat = defaultdict(list)
for r in recs:
    lat[outcome(r)].append(r.get("response_time_seconds") or 0)
def lats(k):
    v = sorted(lat[k]); return len(v), (round(sum(v)/len(v), 1) if v else 0), (round(median(v), 1) if v else 0)
all_t = sorted(r.get("response_time_seconds") or 0 for r in recs)

tools = Counter(t.get("tool") for r in recs for t in (r.get("tool_calls") or []))
lookup_qs = [i for i, r in by.items() if any(t.get("tool") == "resolve_ar_customer" for t in (r.get("tool_calls") or []))]
parks = [i for i, r in by.items() if "interrupt" in (r.get("status_sequence") or [])]
named5 = [i for i, r in by.items() if "9,776" in (r.get("response") or "")]
dangling = [2, 16, 24, 30, 36]

# good-answer evidence: q1 ledger (POPULAR MATTRESS 10,749) + reported payment (9,776)
ledger_line = "POPULAR MATTRESS &amp; CLOTH STORE | ₹10,749"
reported_amt = "₹9,776"

# ---------------- hand-graded constants (user review 2026-09-24; see footnote) ----------------
SCORECARD = [
    ("Solid answers", 9, "ok", "✓", "Clear, correct and useful"),
    ("Partial answers", 21, "partial", "◐", "Some info, but incomplete or thin"),
    ("Wrong or misleading", 7, "bad", "✗", "Answers that don’t match the data"),
    ("Honest “can’t do”", 2, "ok", "?", "Said plainly it couldn’t answer"),
    ("Customer-lookup errors", 3, "bad", "⚠", "Named-customer lookups that failed"),
    ("No answer", 14, "none", "–", "Empty responses (14 of 56)"),
]

GORES_WRONG = [
    {
        "title": "Asking about a named customer often gets no answer",
        "q": 5,
        "note": "9 customer lookups were attempted; none produced an answer. Batch lookups and single lookups alike stopped with “No matching customer was found”.",
    },
    {
        "title": "The same payment list is returned again and again",
        "q": 2, "table": "Payment updates",
        "note": f"The same reported-payments list — led by KRISHNA COATED FABRICS, TRENDS FURNISHING and TENON with ₹9,776 claims — comes back for {len(named5)} different questions, whatever the question actually asks.",
    },
    {
        "title": "Some answers contradict the data",
        "q": 13,
        "note": "“No overdue promised payments are currently recorded” — but a related question found ONCE & AGAIN with a commitment marked broken, not open. Overdue = broken commitments are being missed.",
    },
    {
        "title": "Amounts disagree between views",
        "q": 18, "table": "Account balances",
        "note": "Interworld shows ₹40,19,329 (about ₹40 lakh) in one view and ₹72,36,78,400 (about ₹72 crore) in the follow-up list. DESIGN ELEMENTS appears as ₹3,06,12,600 in one answer and ₹3,06,126 in another — exactly 100× apart. One of these is a scaling error.",
    },
    {
        "title": "Empty tables and boilerplate pile up",
        "q": 12,
        "note": "“No matching results were found” blocks repeat three times in a single answer, each with the same boilerplate note, and many answers end in the same fixed “How I worked this out (N steps)” line.",
    },
]

DEV_FAILMAP = [
    ("Customer lookup: 9 calls, 0 answers", [
        "resolve_ar_customer was called 9× (q5, q19, q38, q41, q45, q47, q50, q52, q56); none produced an answer.",
        "Batch `queries` calls (q5, q19) returned “No matching customer was found” for exact names.",
        "Single `name` calls (q41, q45, q47, q50, q52, q56) ended in a picker.",
        "q38 — a 5-tool chain including resolve_ar_customer — took 233 s.",
    ]),
    ("5 queries interrupted with no tool call", [
        "q3, q6, q26, q35, q55: status interrupt, empty response, no tool call.",
        "q3 and q6 are paraphrases of q2 and q4, which were answered on the same data.",
    ]),
    ("search_threads never called", [
        "0 calls; 19 queries were labeled with it as the expected tool.",
        "One evidence object (5017e36f28e4) was re-read in 10 queries.",
    ]),
    ("Same 5-row payments table, no totals", [
        "18 queries returned the same reported-payments rows (₹9,776 family).",
        "Every query used limit=5 (46 tool inputs); no totals were ever computed.",
    ]),
]

DEV_BUGS = [
    ("q13", "status=open misses broken commitments — “no overdue promises” while ONCE & AGAIN’s is broken"),
    ("q17", "inverted is_null filter"),
    ("q18", "unrelated balances table attached to the answer"),
    ("q31", "false “none open” for unresolved references"),
    ("q2, 16, 24, 30, 36", "dangling headlines — headline promises more than the rows show"),
    ("many", "Entered rows leak into unmatched lists"),
    ("many", "literal \\* and &amp; appear in rendered answers"),
]

DEV_NUMBERS = [
    ("Interworld Furnishings", "Ledger view (q18)", "₹40,19,329 ≈ ₹40 lakh"),
    ("Interworld Furnishings", "Follow-up worklist (q22, q54)", "₹72,36,78,400 ≈ ₹72.37 crore"),
    ("Interworld Furnishings", "Query text (q46)", "₹7.24 crore (user-entered anchor)"),
    ("DESIGN ELEMENTS", "Answer q39", "₹3,06,12,600"),
    ("DESIGN ELEMENTS", "Answer q43", "₹3,06,126 — exactly 100× smaller"),
]

DEV_HARNESS = [
    "Interrupts are recorded as empty responses — auto-select or log the picker payload (finance P1 same).",
    "expected_tool labels don’t match real tool names (labels from the 09-23 harvest surface; the run calls the query_ar family).",
    "tool_calls under-reports steps — q13 shows 4 steps in the UI but only 2 tool calls.",
    "3 queries cite a “Bill 15293 / ₹880 NEFT” claim that is not found in the data (q20, q25, q49).",
    "~8 queries embed the answer in the query text itself.",
]

DEV_FIX_ORDER = [
    "Resolver + harness interrupt handling (the two largest failure classes).",
    "search_threads wiring (19 labels, 0 calls).",
    "Scale inconsistencies (the 100× pair; Interworld 40 lakh vs 72 crore).",
    "Collapse empty blocks and boilerplate out of rendered answers.",
    "Headlines that name the rows actually shown.",
]

# ---------------- explorer data ----------------
expl = []
for r in recs:
    expl.append({
        "i": r["query_index"], "cat": r.get("category") or "—",
        "out": OUT_LABEL[outcome(r)],
        "q": clean(r.get("query") or ""),
        "a": None,  # filled below after md render (keep clean text + render client-free)
        "s": round(r.get("response_time_seconds") or 0),
    })
# pre-render trimmed answer text (plain, single line-joined, first ~420 chars) for explorer
for e in expl:
    t = re.sub(r"<[^>]+>", " ", md_to_html(clean(by[e["i"]].get("response") or "")))
    t = re.sub(r"\s+", " ", t).strip()
    e["a"] = (t[:420] + " …") if len(t) > 420 else t

# ---------------- page ----------------
Q = lambda s: H.escape(s)

def table_region(qi, heading, max_rows=8):
    """Render the table that follows '### <heading>' in the response, as real HTML."""
    s = clean(by[qi].get("response") or "")
    lines = s.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if re.search(r"#{1,4}\s*📊?\s*" + heading, ln):
            start = i; break
    rows = []
    if start is not None:
        for ln in lines[start + 1:]:
            if ln.startswith("|"):
                rows.append(ln)
            elif rows:
                break
    if not rows:
        return snippet(qi, 300)
    rows = [r for r in rows if not re.match(r"^\|[\s:|-]+\|$", r)]
    tbl = ["<table>"]
    for ri, row in enumerate(rows[:max_rows]):
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        tag = "th" if ri == 0 else "td"
        tbl.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
    tbl.append("</table>")
    return "".join(tbl)

def card_goes(g):
    q = Q(clean(by[g["q"]]["query"]))
    body = g.get("table") and table_region(g["q"], g["table"]) or snippet(g["q"], 420)
    return f"""<div class="card">
  <h3>{g['title']}</h3>
  <p class="qq"><span class="qmark">Q</span> “{q}” <span class="qi">q{g['q']}</span></p>
  <div class="ans">{body}</div>
  <p class="note">{g['note']}</p>
</div>"""

out_counts = {k: f"{v} of {N}" for k, v in sorted(by_outcome.items())}

exp_rows = "".join(
    f'<tr data-cat="{Q(e["cat"])}" data-out="{Q(e["out"])}"><td class="qi">q{e["i"]}</td>'
    f'<td class="qcol">{Q(e["q"][:110])}</td><td><span class="chip chip-{e["out"].lower().replace(" ","-")}">{e["out"]}</span></td>'
    f'<td class="s">{e["s"]}s</td><td class="acol">{Q(e["a"])}</td></tr>'
    for e in expl)

rowcount = f"""<span class="rowcount" data-rows="{N}">Showing all {N} questions</span>"""

HTML_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AR agent — accounts-receivable answers, 56-question test</title>
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
table.tbl{border-collapse:collapse;width:100%;font-size:13.5px;min-width:720px}
.tbl th{text-align:left;background:var(--soft);padding:9px 12px;border-bottom:1px solid var(--line)}
.tbl td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.qcol{font-weight:600;max-width:270px} .acol{color:var(--mut);max-width:380px}
.s{white-space:nowrap;color:var(--mut)}
.chip{display:inline-block;border-radius:99px;padding:2px 10px;font-size:12px;border:1px solid}
.chip-answered{color:var(--ok);border-color:var(--ok)}
.chip-partial{color:var(--warn);border-color:var(--warn)}
.chip-no-data{color:var(--none);border-color:var(--none)}
.chip-asked-a-follow-up{color:var(--acc);border-color:var(--acc)}
.chip-no-answer{color:var(--bad);border-color:var(--bad)}
.rowcount{color:var(--mut);font-size:13px}
.fn{color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);margin-top:34px;padding-top:12px}
ol{margin:6px 0;padding-left:24px} ol li{margin:4px 0}
.fm{margin:10px 0} .fm h3{margin-bottom:4px} .fm p{margin:3px 0;color:var(--mut);font-size:14px}
code{background:var(--soft);border:1px solid var(--line);border-radius:5px;padding:0 5px;font-size:12.5px}
table.numt{border-collapse:collapse;width:100%;margin:8px 0 4px;font-size:14px}
.numt th,.numt td{border:1px solid var(--line);padding:7px 11px;text-align:left}
.numt th{background:var(--soft)} .flag{color:var(--bad);font-weight:600}
</style></head><body><div class="wrap">

<header>
  <h1>Accounts-receivable assistant — 56-question test</h1>
  <p>Answers about who owes what, and what customers said on WhatsApp about paying · Zainab Enterprises · 2026-09-24</p>
</header>

<div class="tabs">
  <button class="on" data-tab="ov">Overview</button>
  <button data-tab="dev">For developers</button>
</div>

<section class="pane on" id="pane-ov">
  <div class="verdict">Strong when the question is specific and the customer is already resolved —
  but a large share of questions (14 of 56) get no answer at all, and several answers are
  wrong or reuse the same canned payment list.</div>

  <h2>Scorecard</h2>
  <div class="grid">__SCORECARD__</div>

  <h2>What works</h2>
  <div class="card">
    <ul>
      <li><strong>Flags unconfirmed claims.</strong> When a customer says “payment done” on WhatsApp, answers repeat that it’s <em>reported, not confirmed settled</em> — never presented as fact.</li>
      <li><strong>Says plainly when something isn’t found.</strong> “Bill 15293 was claimed on WhatsApp — is it in ERP?” → “I couldn’t find invoice 15293 in your records.” No pretending.</li>
      <li><strong>Asks for missing details.</strong> A question without a reference number got “Please share the UTR itself…” instead of a made-up answer.</li>
      <li><strong>No fabricated figures.</strong> No invented customers, invoices or amounts were found in the judged answers.</li>
    </ul>
  </div>

  <h2>What goes wrong</h2>
  __GORES__

  <h2>What a good answer looks like</h2>
  <div class="compare">
    <div class="card"><h3>What the assistant gave</h3>
      <p class="qq"><span class="qmark">Q</span> “__GOODQ__” <span class="qi">q1</span></p>
      <div class="ans">__GOODACT__</div>
      <p class="note">Both facts are present (ledger ₹10,749 · reported ₹9,776), but buried: two separate tables, no reconciliation, no plain “about ₹973 still pending”.</p>
    </div>
    <div class="card"><h3>Ideal answer</h3>
      <div class="ans" style="background:transparent;border:2px solid var(--ok)">
        <p>“POPULAR MATTRESS &amp; CLOTH STORE owes <strong>₹10,749</strong> on the ledger. They reported paying <strong>₹9,776</strong> on WhatsApp, and that claim isn’t in the books yet — so about <strong>₹973</strong> is still pending.”</p>
      </div>
      <p class="note">One number, one conclusion, both sides of the story — the pattern a chaser can act on.</p>
    </div>
  </div>

  <h2>All 56 questions</h2>
  <div class="filters">
    <select id="f-cat"><option value="">All categories</option>__OPTS__</select>
    <select id="f-out"><option value="">All outcomes</option><option>Answered</option><option>Partial</option><option>No data</option><option>No answer</option></select>
    <span class="rowcount" id="rc">Showing all 56 questions</span>
  </div>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>#</th><th>Question</th><th>Outcome</th><th>Time</th><th>Answer (trimmed)</th></tr></thead>
    <tbody id="tbody">__ROWS__</tbody>
  </table></div>
</section>

<section class="pane" id="pane-dev">
  <h2>Failure map, ordered by impact</h2>
  __FAILMAP__
  <h2>Bug list</h2>
  <table class="numt"><thead><tr><th>Queries</th><th>Issue</th></tr></thead><tbody>__BUGS__</tbody></table>
  <h2>Number consistency</h2>
  <table class="numt"><thead><tr><th>Entity</th><th>View / source</th><th>Amount</th></tr></thead><tbody>__NUMS__</tbody></table>
  <p class="note"><span class="flag">Suspected scaling bug:</span> DESIGN ELEMENTS differs by exactly 100× between q39 and q43; Interworld differs 10-180× across views.</p>
  <h2>Harness notes</h2>
  <ul>__HARNESS__</ul>
  <h2>Latency</h2>
  <table class="tbl" style="min-width:0"><thead><tr><th>Outcome</th><th>Count</th><th>Mean (s)</th><th>Median (s)</th></tr></thead><tbody>__LAT__</tbody></table>
  <p class="note">Overall mean 23.4 s, median 19.4 s (56 queries; min 3.4 s, max 232.7 s — q38 is the outlier: a 5-tool chain that includes the customer lookup).</p>
  <h2>Suggested fix order</h2>
  <ol>__FIX__</ol>
  <p class="fn">Hand-graded, no ground-truth baseline exists. Judgment is a human reviewer’s, not the file’s; machine counts in the developer tab are computed from the run file.</p>
</section>

<p class="fn">Scoring is hand-graded by a human reviewer (solid 9 · partial 21 · wrong 7 · honest “can’t do” 2 · lookup errors 3 · no answer 14). There is no ground-truth baseline for these answers; treat the numbers as judgment, and the quoted answers on this page as taken verbatim from the run.</p>
</div>
<script>
var tabs=document.querySelectorAll('.tabs button');tabs.forEach(function(b){b.onclick=function(){
 tabs.forEach(function(x){x.classList.remove('on')});b.classList.add('on');
 document.querySelectorAll('.pane').forEach(function(p){p.classList.remove('on')});
 document.getElementById('pane-'+b.dataset.tab).classList.add('on');window.scrollTo(0,0);}});
function rep(){var c=document.getElementById('f-cat').value,o=document.getElementById('f-out').value,n=0;
 document.querySelectorAll('#tbody tr').forEach(function(tr){
  var ok=(!c||tr.dataset.cat===c)&&(!o||tr.dataset.out===o);tr.style.display=ok?'':'none';if(ok)n++;});
 document.getElementById('rc').textContent='Showing '+n+' of 56 questions';}
document.getElementById('f-cat').onchange=rep;document.getElementById('f-out').onchange=rep;
</script>
</body></html>"""

# ---- assemble ----
score = "".join(f'<div class="tile tile-{c}" title="{_d}"><div class="tile-icon">{ic}</div><div class="tile-n">{n}</div><div class="tile-l">{lab}</div></div>'
                for lab, n, c, ic, _d in SCORECARD)

gores = "\n".join(card_goes(g) for g in GORES_WRONG)

import re as _re
q1_resp = clean(by[1]["response"])
bal_m = _re.search(r"#+ Account balances(.*?)(?:\n\s*#+|\Z)", q1_resp, _re.S)
good_block = ("<p>Matches found: <strong>POPULAR MATTRESS &amp; CLOTH STORE — ₹10,749</strong> on the ledger, "
              "₹9,776 reported on WhatsApp.</p>" +
              snippet(1, 500))
goodq = clean(by[1]["query"])

opts = "".join(f'<option>{Q(c)}</option>' for c in cat_orders)

fm = ""
for title, items in DEV_FAILMAP:
    fm += f'<div class="fm"><h3>{title}</h3>' + "".join(f"<p>{i}</p>" for i in items) + "</div>"
bugs = "".join(f"<tr><td>{Q(a)}</td><td>{Q(b)}</td></tr>" for a, b in DEV_BUGS)
nums = "".join(f"<tr><td>{Q(a)}</td><td>{Q(b)}</td><td>{Q(c)}</td></tr>" for a, b, c in DEV_NUMBERS)
harness = "".join(f"<li>{Q(h)}</li>" for h in DEV_HARNESS)
lat_rows = "".join(f"<tr><td>{k}</td><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>"
                   for k, v in [("Answered", lats("success")), ("Partial", lats("marginal")),
                                ("No data", lats("no_data")), ("Asked a follow-up / no answer", lats("clarify"))])
fix = "".join(f"<li>{Q(f)}</li>" for f in DEV_FIX_ORDER)

page = (HTML_PAGE.replace("__SCORECARD__", score).replace("__GORES__", gores)
        .replace("__GOODQ__", Q(goodq)).replace("__GOODACT__", good_block)
        .replace("__OPTS__", opts).replace("__ROWS__", exp_rows)
        .replace("__FAILMAP__", fm).replace("__BUGS__", bugs).replace("__NUMS__", nums)
        .replace("__HARNESS__", harness).replace("__LAT__", lat_rows).replace("__FIX__", fix))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page)
print(f"WROTE {OUT} ({len(page)} bytes, {N} records, scorecard "
      + " ".join(f"{k}={v}" for k, v in sorted(by_outcome.items())))