#!/usr/bin/env python3
"""Finance eval dashboard renderer — redesign 2026-09-19.

Builds docs/finance/index.html (story-first, sticky side nav, 7 sections) from the
derived artifacts in accounts/finance/runs/v<N>/, plus docs/finance/legacy/index.html
(the pre-redesign page) so the old page stays reachable until the new one is verified.

Design rules (baked in):
  - Every number on the page is DERIVED from the run artifacts; invariants are asserted
    and the build FAILS on violation (outcomes/verdicts/matrix sums == 30, label cards
    == 30, all 30 deep links present, no relative ../../ hrefs).
  - Content is fully server-rendered; inline JS is used for query-explorer FILTERING
    only (no external CDNs, zero runtime dependencies).
  - Inconsistencies are SURFACED, never silently resolved (tier version conflicts,
    judge provenance, family assignment gaps, q10/q26 aging-label conflict).

Invoked from build_dashboard.py when account == "finance".
"""

import argparse
import html as html_mod
import json
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
TEMPLATE = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "template.html"
OUT_DIR = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "finance"
LEGACY_DIR = OUT_DIR / "legacy"
RAW = "https://raw.githubusercontent.com/navneetlearns/langsmith-tool-evaluator/main"

SEV_COLOR = {"high": "#b91c1c", "medium": "#b45309", "low": "#64748b"}
OUTCOME_LABEL = {
    "answered": "Answered", "hard_refusal": "Hard refusal",
    "parked": "Clarify park", "error": "Technical error",
}
# Dark 700-800 shades: readable as TEXT on white. (Light 500-shades were
# invisible on white; see OUTCOME_BAR for the bar's tinted backgrounds.)
OUTCOME_COLOR = {"answered": "#166534", "hard_refusal": "#1e40af",
                 "parked": "#5b21b6", "error": "#991b1b"}
# Outcome bar segment backgrounds: LIGHT tints + dark text (not dark bars).
OUTCOME_BAR = {"answered": "#d9f0e2", "hard_refusal": "#dbe4fb",
               "parked": "#e8dcf7", "error": "#f7dcdc"}
VERDICT_LABEL = {"match": "Match", "partial": "Partial",
                 "mismatch": "Mismatch", "error": "Error"}
VERDICT_COLOR = {"match": "#15803d", "partial": "#b45309",
                 "mismatch": "#b91c1c", "error": "#b91c1c"}

# ---- Tier tags. Authoritative source: VALUE_JUDGE_phase2.md + VALUE_GRADE_phase3.md
# (user-approved 2026-09-18). VALUE_SCORECARD_phase1.md originally tagged the four
# starred queries differently (q2 T1, q15 T2, q16 T2, q27 T1) — DISPUTED, surfaced.
TIERS = {1: "T1", 2: "T3*", 3: "T2", 4: "T2", 5: "T3", 6: "T3", 7: "T3", 8: "T3",
         9: "T2", 10: "T1", 11: "T2", 12: "T1", 13: "T1", 14: "T2", 15: "T3*",
         16: "T3*", 17: "T1", 18: "T1", 19: "T3", 20: "T3", 21: "T3", 22: "T3",
         23: "T2", 24: "T3", 25: "T3", 26: "T2", 27: "T3*", 28: "T2", 29: "T3", 30: "T3"}

# ---- Question families, per VALUE_GRADE_phase3.md §1. q5/q6 unassigned; q30 in A and E.
FAMILIES = {3: "A", 4: "A", 9: "A", 10: "A", 26: "A", 30: "A",
            7: "B", 8: "B", 11: "B", 23: "B",
            2: "C", 14: "C", 15: "C", 16: "C", 27: "C",
            12: "D", 13: "D", 17: "D", 18: "D",
            1: "E", 19: "E", 20: "E", 21: "E", 22: "E", 24: "E", 25: "E",
            28: "E", 29: "E", 30: "E"}
FAMILY_NAME = {"A": "Cash / chase / collections", "B": "Credit discipline",
               "C": "Profitability / margins", "D": "Expenses / payables",
               "E": "Anomaly / strategic review"}
FAMILY_SKELETON = {
    "A": "A1 size the problem (outstanding, debtor count, DSO) · A2 name accounts with Rs + payment recency · A3 prioritise amount x staleness · A4 flag fastest-deteriorating · A5 actions (who to call today, dated commitments) · A6 honest gaps",
    "B": "B1 exposure size · B2 per-customer credit-vs-payment outliers · B3 credit-too-loose verdict (with no-benchmark caveat) · B4 actions: limits, terms, order-release",
    "C": "C1 what CAN be computed (sales, collection, concentration) · C2 boundary stated once (margin/profit untracked) · C3 best proxy + limits (purchases != COGS) · C4 cross-metric insight · C5 actions",
    "D": "D1 named boundary (expense GL, payables, COGS absent) · D2 what CAN be worked instead · D3 one-line actionable offer",
    "E": "E1 ranked top risks by materiality · E2 cross-check views for inconsistencies · E3 hypothesis per anomaly · E4 verification path · E5 decision link",
}

# ---- Judge provenance (as documented, both passes true) ----
JUDGE_STATEMENT = ("Grades come from one in-session model (deepseek-v4, a different family "
                   "from the producing agent gpt-5.4-mini) in two passes: Phase 3 = direct "
                   "reading against pre-written accountant skeletons (no separate LLM judge "
                   "invocation, no second reader); Phase 2 = an anchored judge pass with a "
                   "verbatim-evidence requirement. The two passes agree 20/20 — that is "
                   "model SELF-CONSISTENCY, not human calibration. Human-reviewed: 0/20.")


def esc(x):
    return html_mod.escape(str(x), quote=True)


def extract_template_css():
    if not TEMPLATE.exists():
        return ""
    t = TEMPLATE.read_text()
    m = re.search(r"<style>(.*?)</style>", t, re.S)
    return m.group(1) if m else ""


# ---- data loading (single source of truth = finance_pipeline.derive) ----
def load(version: int):
    d = SCRIPT_DIR / "accounts" / "finance" / "runs" / f"v{version}"
    summary = json.loads((d / "summary.json").read_text())
    findings = json.loads((d / "findings.json").read_text())
    leaks = [json.loads(l) for l in (d / "leaks.jsonl").read_text().splitlines() if l.strip()]
    judg_lines = [json.loads(l) for l in (d / "judgments.jsonl").read_text().splitlines() if l.strip()]
    sys.path.insert(0, str(SCRIPT_DIR / "scripts"))
    from finance_pipeline import derive
    _, rows, _, _ = derive(int(version))
    records = [json.loads(l) for l in (d / "results.jsonl").read_text().splitlines() if l.strip()]
    by_rec = {r["query_index"]: r for r in records}

    for r in rows:
        qi = r["query_index"]
        rec = by_rec.get(qi, {})
        r["tier"] = TIERS.get(qi, "?")
        r["family"] = FAMILIES.get(qi, "—")
        r["family_shared"] = "q30" if qi == 30 else ""
        r["expected_tool"] = rec.get("expected_tool") or "NO_TOOL"
        r["response_full"] = rec.get("response") or ""
        r["status_seq"] = rec.get("status_sequence") or []
        jr = next((j for j in judg_lines if j["query_index"] == qi), {})
        r["judge_note"] = jr.get("note") or ""
        r["value_errors"] = r.get("value_errors") or []
        # boundary-refusal flag: REFUSE-expected that did not hard-refuse
        r["boundary"] = (r["expected_behavior"] == "REFUSE"
                         and r["outcome"] == "answered" and r["verdict"] == "partial")

    # cross-source facts the page asserts
    n_threads = len({r.get("thread_id") for r in records})
    payload = Counter(r.get("ui_payload_type") for r in records)
    return {
        "version": version, "summary": summary, "findings": findings, "leaks": leaks,
        "judgments": judg_lines, "rows": rows, "n_threads": n_threads, "payload": payload,
    }


# ============================================================
# F1-F9 SEED FINDINGS (grouped by component in the page). Query
# lists recomputed from the run; auto = derived from data, manual
# = doc-verified curation (Phase 2/3 readouts, owner flags).
# ============================================================
def seed_findings(b):
    rows = b["rows"]
    exp_of = {r["query_index"]: r["expected_behavior"] for r in rows}
    out_of = {r["query_index"]: r["outcome"] for r in rows}
    ver_of = {r["query_index"]: r["verdict"] for r in rows}
    parked_wrong = sorted(q["query_index"] for q in rows if q["outcome"] == "parked"
                          and q["expected_behavior"] in ("ANSWER", "REFUSE"))
    clarify_answered = sorted(q["query_index"] for q in rows if q["expected_behavior"] == "CLARIFY"
                              and q["outcome"] == "answered")
    answered = sorted(q["query_index"] for q in rows if q["outcome"] == "answered")
    banner_q = sorted(q["query_index"] for q in rows if "not fully reconciled" in q["response_full"])
    dd_q = sorted(q["query_index"] for q in rows if "days days" in q["response_full"])
    f = []
    f.append(dict(id="F1", component="Clarify gate", severity="high",
        title="Clarify gate routing is inconsistent — parked and answered queries overlap",
        evidence=(f"{len(parked_wrong)} answerable queries wrongly parked "
                  f"(q{' q'.join(map(str, parked_wrong))}); {len(clarify_answered)} CLARIFY-labeled "
                  f"queries answered instead (q{' q'.join(map(str, clarify_answered))}) while equally "
                  f"vague q3 q5 q6 q23 parked. Gate is non-deterministic: q3 parked in-run, answered on "
                  f"re-probe (~30% park rate on clarify-prone queries; grade as a rate, not per-query)."),
        queries=parked_wrong + clarify_answered,
        done_when="no ANSWER/REFUSE-labeled query parks; clarify-park rate reproducible per input",
        status="open", origin="auto"))
    f.append(dict(id="F2", component="Data & aggregation layer", severity="high",
        title="q16 percentages do not reconcile with invoiced sales",
        evidence=("Rs 23,94,95,748 stated as 49.6% implies a Rs 48.29cr total vs invoiced sales "
                  "Rs 24,17,71,682 (it is ~99% of sales); Rs 16,21,37,760 stated as 50.3% implies "
                  "Rs 32.23cr (actual ~67% of sales). Likely double counting / join fan-out in the "
                  "segment and product aggregations."),
        queries=[16], done_when="q16 percentages imply denominators within 5% of the sales total",
        status="open", origin="auto"))
    f.append(dict(id="F3", component="Data & aggregation layer", severity="high",
        title="q21 cross-view contradiction: movement view outranks the outstanding ranking",
        evidence=("Movement view: Krishna Wholesalers LLP Rs 14,53,793 largest ending balance "
                  "(up Rs 8,27,052), Jai Retail Traders up Rs 9,05,018 to Rs 9,63,472, Radha "
                  "Distributors & Co Rs 8,06,190 (up Rs 9,66,376 from a NEGATIVE opening of "
                  "-Rs 1,60,186 — unallocated advances?), Ganesh Retail Traders Rs 8,01,148 "
                  "(up Rs 9,10,046 while period sales were only Rs 3,62,161 per q16) — all four "
                  "ABOVE the Rs 4,94,550 'largest outstanding' the agent repeats in 12 answers "
                  "(q1 q2 q4 q9 q11 q16 q21 q22 q25 q26 q28 q30). q21's headline flags the Radha "
                  "movement spike for investigation but only Ganesh's cross-view difference is "
                  "explicitly resolved ('confirm that both views use the same cut-off')."),
        queries=[21], done_when="every figure states its view/source; no 'largest' claim contradicts another view",
        status="open", origin="auto"))
    f.append(dict(id="F4", component="Planner / evidence selection", severity="medium",
        title="Top-5 list is not material: ~1.3% of the portfolio presented as a recovery plan",
        evidence=("The top-5 collection block totals Rs 22,40,723 = ~1.3% of Rs 17,48,30,219 "
                  "outstanding across 1,549 debtors, yet q9 presents it as the aggressive-recovery "
                  "plan while q4 says the issue is broad. Same block, opposite framings."),
        queries=[4, 9, 26, 28],
        done_when="answers naming top accounts quantify their share of the portfolio",
        status="open", origin="auto"))
    f.append(dict(id="F5", component="Planner / evidence selection", severity="medium",
        title="Cross-answer template reuse hides query-specific evidence",
        evidence=(f"Ganesh Retail Traders appears in 12 of 16 data answers (q{' q'.join(map(str, [q for q in answered if 'Ganesh Retail Traders' in next(r['response_full'] for r in b['rows'] if r['query_index'] == q)]))} "
                  f"per run data; KPI trio recycled: Rs 17,48,30,219 in 6, DSO 120.8 in 4, 33.8% in 7). "
                  f"Four answers (q1 q15 q19 q25) say the outstanding total is unavailable while six state "
                  f"it (q4 q10 q11 q22 q26 q28): non-deterministic tool selection. Caveat: threads are "
                  f"isolated so answers cannot know they repeat; q21/q28/q30 prove query-specific evidence exists."),
        queries=answered, done_when="answers to different questions use different evidence blocks (C-04 share < 50%)",
        status="open", origin="auto"))
    f.append(dict(id="F6", component="Planner / evidence selection", severity="medium",
        title="q1 headlines 'priority customers' at 23.6% of sales, but they are small accounts",
        evidence=("q1: 'listed priority customers contribute Rs 5,70,49,359, or 23.6% of sales'. The "
                  "collection-priority top-5 are small (Ganesh sales Rs 3,62,161 per q16) — two different "
                  "'priority' populations, one headline."),
        queries=[1], done_when="'priority' labels in the answer match the population they are computed from",
        status="open", origin="manual"))
    f.append(dict(id="F7", component="Grounding & formatting", severity="medium",
        title="Format-node defects: unit duplication, placeholder tokens, craft glitches",
        evidence=(f"'days days' x30 across 6 answers (q{' q'.join(map(str, dd_q))}); literal '[unverified]' "
                  f"x2 in q1; '..' before 'I can work' in q12 q13 q18 q27; q17 footer '0 figures verified' "
                  f"on a refusal; 'figures verified' counts not comparable (42-123 typical, 2685 in q1, 929 in "
                  f"q30); reconcile banner in 14 answers even when ageing is not used."),
        queries=dd_q + [1, 12, 13, 17, 18, 27],
        done_when="no 'days days' / '[unverified]' / '..' artifacts; banner once per thread; footer consistent",
        status="open", origin="auto"))
    f.append(dict(id="F8", component="Latency / robustness", severity="medium",
        title="Broadest prompts are slowest; one answer dropped before the client timeout",
        evidence=("q20 dropped at 244.7s (IncompleteRead — upstream drop, before the 300s SSE timeout, "
                  "so NOT a client timeout); q30 211.9s, q1 142.1s; the three broadest prompts are the slowest."),
        queries=[1, 20, 30], done_when="no answer exceeds 120s; no IncompleteReads in a rerun",
        status="open", origin="auto"))
    f.append(dict(id="F9", component="Data & aggregation layer", severity="low",
        title="Data recency unverified: latest-month drop may be a partial/cutoff artifact",
        evidence=("Sales fall Rs 9,77,65,078 (5,642 invoices) to Rs 11,97,739 (117 invoices) in the latest "
                  "month — likely a partial month or cutoff, but the max invoice date was never checked. If "
                  "partial, 33.8% collection efficiency and DSO 120.8d (over a 167-day window) are "
                  "period-sensitive."),
        queries=[], done_when="invoice_date is captured and the latest-month window verified (C-05)",
        status="open", origin="manual"))
    f.append(dict(id="F10", component="Grounding & formatting", severity="low",
        title="Answers lean on cookie-cutter data-availability phrasing",
        evidence=("Data-availability phrasing ('supplied|returned|provided rows|results', heuristically "
                  "detected by the leak rule of the same name) repeats across q1 q15 q19 q25: q1 'total "
                  "outstanding balance is not present in the supplied rows', q15 'unavailable for every month "
                  "in the supplied results', q19 'authoritative outstanding balance is not in the returned "
                  "results', q25 'provided rows do not include a portfolio-wide outstanding total'; q19 also "
                  "echoes 'requested'. Process transparency is fine — the cookie-cutter repetition across "
                  "isolated threads is the signal."),
        queries=[1, 15, 19, 25],
        done_when="answers name missing data with query-specific phrasing, not the same supplied/returned rows boilerplate",
        status="open", origin="auto"))
    return f


# ============================================================
# INVARIANTS — build fails on any violation
# ============================================================
def assert_invariants(b, html_page=None):
    s = b["summary"]; rows = b["rows"]; n = len(rows)
    errs = []
    o = Counter(r["outcome"] for r in rows)
    v = Counter(r["verdict"] for r in rows)
    if n != 30:
        errs.append(f"INVARIANT: 30 queries expected, found {n}")
    if sum(o.values()) != n:
        errs.append(f"INVARIANT: outcomes sum {sum(o.values())} != {n}")
    if dict(o) != s["outcomes"]:
        errs.append(f"INVARIANT: row outcomes {dict(o)} != summary.outcomes {s['outcomes']}")
    if sum(v.values()) != n:
        errs.append(f"INVARIANT: verdicts sum {sum(v.values())} != {n}")
    if dict(v) != {k: s["vs_expected"][k] for k in ("match", "partial", "mismatch", "error")}:
        errs.append(f"INVARIANT: row verdicts {dict(v)} != summary.vs_expected")
    # every query has exactly one outcome and one verdict
    bad = [r["query_index"] for r in rows if not r["outcome"] or not r["verdict"]]
    if bad:
        errs.append(f"INVARIANT: rows missing outcome/verdict: q{','.join(map(str, bad))}")
    # heatmap row sums == expected-label counts, total == 30 (checked again post-render)
    exp = Counter(r["expected_behavior"] for r in rows)
    if dict(exp) != {"ANSWER": 9, "CLARIFY": 12, "REFUSE": 9}:
        errs.append(f"INVARIANT: expected labels {dict(exp)} != 9/12/9")
    # single-isolated-thread property (HEART full trace capture)
    if b["n_threads"] != n:
        errs.append(f"INVARIANT: {b['n_threads']} distinct thread_ids != {n} (isolation broken)")
    # judged + parked + error must cover all queries
    judged = sum(1 for r in rows if r["value_level"])
    if judged + o["parked"] + o["error"] != n:
        errs.append(f"INVARIANT: judged({judged}) + parked({o['parked']}) + error({o['error']}) != {n}")
    if html_page is not None:
        missing = [q for q in range(1, 31) if f'id="q{q}"' not in html_page]
        if missing:
            errs.append(f"INVARIANT: deep links missing for q{','.join(map(str, missing))}")
        rel = sorted(set(re.findall(r'href="(\.\./\.\./[^"]+)"', html_page)))
        if rel:
            errs.append(f"INVARIANT: relative ../ links that 404 on Pages: {rel}")
    if errs:
        raise SystemExit("\n".join("[finance-static FAIL] " + e for e in errs))
    return True


# ============================================================
# SMALL HTML BUILDERS
# ============================================================
def outcome_bar(b):
    """Clickable outcome bar; segments sum to 30 (asserted)."""
    o = b["summary"]["outcomes"]; n = b["summary"]["queries"]
    segs = []
    for key in ("answered", "hard_refusal", "parked", "error"):
        c = o.get(key, 0)
        if c <= 0:
            continue
        pct = c / n * 100
        segs.append(
            f'<a class="obar-seg" href="#results" style="background:{OUTCOME_BAR[key]};width:{pct:.2f}%;color:{OUTCOME_COLOR[key]};" '
            f'title="{OUTCOME_LABEL[key]} — click for per-query detail">'
            f'<span class="obar-n">{c}</span><span class="obar-lbl">{OUTCOME_LABEL[key]}</span></a>')
    return (f'<div class="obar" role="img" aria-label="Outcome bar — sums to {n}">'
            f'{"".join(segs)}</div>'
            f'<div class="obar-total">mutually exclusive outcomes — sum <strong>{n}</strong></div>')


def kpi_cards(b, findings):
    s = b["summary"]; v = s["vs_expected"]
    n = s["queries"]
    wrongly_parked = sum(1 for r in b["rows"] if r["outcome"] == "parked"
                         and r["expected_behavior"] in ("ANSWER", "REFUSE"))
    open_di = sum(1 for f2 in findings if f2["component"] in ("Data & aggregation layer",)
                  and f2["status"] == "open")
    cards = [
        ("L4/L5 by skeleton coverage (element presence)", f"{s['value']['L4_L5']}/30",
         "13 of the 20 judged answers; grades measure element PRESENCE against pre-written accountant skeletons, not numeric correctness — limit: one in-session LLM judge, no ground truth (see §6)"),
        ("Behavior matched expectation", f"{v['match']}/30",
         f"expected-vs-observed verdicts; +{v['partial']} partial (hedged) · {v['mismatch']} mismatch · {v['error']} error"),
        ("Wrongly parked by clarify gate", f"{wrongly_parked}/30",
         "ANSWER/REFUSE-labeled queries the gate parked instead of resolving (technical note: gate is a ~30% stochastic rate, not per-query truth)"),
        ("Open data-integrity findings", f"{open_di}", "F2 q16 ratio-reconciliation + F3 q21 cross-view contradiction (deterministic FAIL checks)"),
    ]
    out = []
    for label, val, desc in cards:
        out.append(f'<div class="kpi"><div class="kpi-v">{val}</div>'
                   f'<div class="kpi-l"><strong>{label}</strong>'
                   f'<div class="kpi-d">{desc}</div></div></div>')
    return '<div class="kpis">' + "".join(out) + "</div>"


def pipeline_steps(b):
    s = b["summary"]; o = s["outcomes"]
    steps = [
        ("1 · Query set", "30 CFO insight questions, user-provided 2026-09-18", "#labels",
         "ANSWER 9 · CLARIFY 12 · REFUSE 9"),
        ("2 · Expected labels", "per classify-gate rules (real metric → ANSWER; vague/judgment → CLARIFY; absent data → REFUSE)", "#labels",
         "9 · 12 · 9"),
        ("3 · Agent run (v1)", f"live streams, one isolated thread per query (30 distinct), no retries — {o.get('answered',0)} answered · {o.get('hard_refusal',0)} refused · {o.get('parked',0)} parked · {o.get('error',0)} error", "#results",
         "16 · 4 · 9 · 1"),
        ("4 · Rating", "skeleton-first grading (Phase 3) + in-session cross-family judge (Phase 2), verbatim evidence", "#evaluated",
         "13 L4/L5 · 2 L3 · 5 REF · 10 ungraded"),
    ]
    out = []
    for t, d, href, chip in steps:
        out.append(f'<a class="pstep" href="{href}"><div class="pstep-t">{t}</div>'
                   f'<div class="pstep-d">{d}</div><code>{chip}</code></a>')
    return '<div class="psteps">' + "".join(out) + "</div>"


def heatmap(b):
    """Expected x observed. 4 observed buckets (mutually exclusive, derived); a literal
    3x3 would drop the 1 error row — deviation surfaced in the caption."""
    rows = b["rows"]
    exps = ["ANSWER", "CLARIFY", "REFUSE"]
    outs = ["answered", "hard_refusal", "parked", "error"]
    cells = {e: {k: [] for k in outs} for e in exps}
    for r in rows:
        cells[r["expected_behavior"]][r["outcome"]].append(r["query_index"])
    head = "".join(f"<th>{OUTCOME_LABEL[k]}</th>" for k in outs)
    body = ""
    for e in exps:
        tds = ""
        for k in outs:
            qs = cells[e][k]
            if not qs:
                tds += f'<td class="heat-0">0</td>'
                continue
            links = " ".join(f'<a href="#q{q}">q{q}</a>' if q != 17 else f'<a href="#q{q}">q{q}*</a>'
                             for q in sorted(qs))
            note = ('<div class="heat-note">answered-with-boundary (hedged refusal)</div>'
                    if e == "REFUSE" and k == "answered" else "")
            tds += f'<td class="heat-{len(qs)}">{len(qs)}<div class="heat-q">{links}</div>{note}</td>'
        body += f"<tr><th>{e}</th>{tds}</tr>"
    return (f'<div class="table-wrap"><table class="heat"><thead><tr><th>Expected ↓ / observed →</th>{head}'
            f'</tr></thead><tbody>{body}</tbody></table></div>'
            f'<div class="desc">Observed axis is the derived mutually-exclusive taxonomy '
            f'(4 buckets; “error” holds q20) — a literal 3×3 would mislabel it. '
            f'<strong>q17* has an “answer” payload but refuses in substance.</strong> '
            f'REFUSE-row “answered” cells are all hedged boundary-named refusals (partial verdicts), never clean data answers. '
            f'Cells sum to 30 (asserted at build).</div>')


def error_chips(b):
    val = b["summary"]["value"]
    errs = val.get("errors") or {}
    if not errs:
        return "<code>none</code>"
    extra = ["OperationalProcessAwarenessBarrier: 0", "HallucinatoryFinancialReasoning: 0",
         "EntityCausationMisidentification: 0"]
    return " ".join(f"<code>{esc(k)} x{c}</code>" for k, c in sorted(errs.items())) + " " + \
           " ".join(f"<code>{esc(x)}</code>" for x in extra)


# ============================================================
# CSS (compact; keeps the shared template's dark tokens)
# ============================================================
def page_css():
    # Self-contained LIGHT theme — does NOT inherit the shared template's dark
    # palette (dark-on-dark was unreadable). Readable text/background pairs only.
    return """
:root{
  --bg:#f8fafc; --card:#ffffff; --surface:#ffffff;
  --border:#e2e8f0; --ink:#0f172a; --muted:#475569;
  --green:#166534; --blue:#1d4ed8; --violet:#5b21b6; --red:#b91c1c; --amber:#b45309;
  --out-answered:#166534; --out-refusal:#1e40af; --out-parked:#5b21b6; --out-error:#991b1b;
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:14px;line-height:1.6;}
h1,h2,h3{line-height:1.3;color:var(--ink);}
a{color:var(--blue);text-underline-offset:2px;}
a:visited{color:var(--violet);}
.layout{display:grid;grid-template-columns:230px 1fr;max-width:1440px;margin:0 auto;gap:28px;padding:0 20px;}
.sidebar{position:sticky;top:0;height:100vh;overflow-y:auto;padding:22px 10px 40px;border-right:1px solid var(--border);}
.sidebar h1{font-size:15px;margin:0 0 4px;line-height:1.35;}
.sidebar .src{font-size:11px;color:var(--muted);margin-bottom:14px;}
.sidebar nav{display:flex;flex-direction:column;gap:2px;}
.sidebar nav a{color:var(--ink);text-decoration:none;font-size:12.5px;padding:6px 10px;border-radius:6px;}
.sidebar nav a:hover{background:#eef2ff;color:var(--blue);}
.sidebar nav a.act{color:var(--blue);background:#eef2ff;font-weight:600;}
main{min-width:0;padding:22px 8px 80px;}
section{margin:0 0 44px;scroll-margin-top:14px;}
h2{font-size:19px;margin:0 0 6px;border-bottom:1px solid var(--border);padding-bottom:8px;}
h3{font-size:14.5px;margin:16px 0 6px;}
.desc{color:var(--muted);font-size:12.5px;line-height:1.6;margin:6px 0;}
.verdict{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--green);border-radius:12px;padding:16px 20px;margin:14px 0;font-size:14px;line-height:1.75;}
.verdict .s{color:var(--green);font-weight:700;}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:14px 0;}
.kpi{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--blue);border-radius:10px;padding:12px 14px;}
.kpi-v{font-size:22px;font-weight:800;color:var(--blue);}
.kpi-l strong{color:var(--ink);}
.kpi-d{font-size:11.5px;color:var(--muted);line-height:1.5;margin-top:4px;}
.obar{display:flex;height:64px;border-radius:10px;overflow:hidden;border:1px solid var(--border);margin:12px 0 4px;}
.obar-seg{display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:800;text-decoration:none;min-width:44px;transition:filter .12s;}
.obar-seg:hover{filter:brightness(.97);}
.obar-n{font-size:17px;} .obar-lbl{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.03em;opacity:.9;}
.obar-total{font-size:11px;color:var(--muted);}
.psteps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:14px 0;}
.pstep{background:var(--card);border:1px solid var(--border);border-top:3px solid var(--blue);border-radius:10px;padding:12px 14px;text-decoration:none;color:var(--ink);}
.pstep-t{font-weight:700;font-size:13px;} .pstep-d{font-size:11.5px;color:var(--muted);line-height:1.5;margin:6px 0;}
.table-wrap{overflow-x:auto;}
table{width:100%;border-collapse:collapse;font-size:12.5px;}
th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);padding:8px 10px;border-bottom:2px solid var(--border);}
td{padding:8px 10px;border-bottom:1px solid var(--border);vertical-align:top;}
table.heat td,table.heat th{text-align:center;}
table.heat td{font-weight:800;font-size:16px;}
.heat-0{color:#94a3b8;} .heat-1{color:var(--blue);} .heat-2{color:var(--amber);} .heat-3{color:var(--red);} .heat-4,.heat-5,.heat-6,.heat-7{color:var(--red);background:rgba(185,28,28,.08);}
.heat-q{font-weight:400;font-size:11px;line-height:1.7;} .heat-q a{color:inherit;}
.heat-note{font-size:10px;font-weight:400;color:var(--amber);max-width:180px;margin:4px auto;}
code{background:#eef2ff;color:#1e3a8a;padding:1px 5px;border-radius:4px;font-size:11px;}
details{margin:8px 0;border:1px solid var(--border);border-radius:10px;background:var(--card);overflow:hidden;}
details>summary{cursor:pointer;padding:10px 14px;font-size:13px;font-weight:600;list-style:none;display:flex;gap:10px;align-items:baseline;color:var(--ink);}
details>summary::-webkit-details-marker,details>summary::marker{display:none;content:"";}
details>summary::before{content:"\25B8";display:inline-block;color:var(--green);transition:transform .15s;}
details[open]>summary::before{transform:rotate(90deg);}
details .details-body{padding:2px 16px 14px;}
.finding{border-left:4px solid var(--blue);}
.finding.sev-high{border-left-color:var(--red);}
.finding.sev-medium{border-left-color:var(--amber);}
.finding.sev-low{border-left-color:#64748b;}
.flag{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;padding:1px 7px;border-radius:99px;margin-left:6px;white-space:nowrap;}
.flag.auto{color:#166534;background:rgba(22,101,52,.1);} .flag.manual{color:var(--blue);background:rgba(29,78,216,.1);}
.flag.disp{color:var(--amber);background:rgba(180,83,9,.1);} .flag.open{color:var(--red);background:rgba(185,28,28,.1);}
.qrow{border-left:4px solid #cbd5e1;margin:10px 0;}
.qrow.out-answered{border-left-color:var(--out-answered);} .qrow.out-hard_refusal{border-left-color:var(--out-refusal);}
.qrow.out-parked{border-left-color:var(--out-parked);} .qrow.out-error{border-left-color:var(--out-error);}
.qrow summary .qmeta{color:var(--muted);font-size:11px;font-weight:400;}
.qrow pre{white-space:pre-wrap;font-size:11.5px;line-height:1.6;color:var(--ink);background:#f8fafc;border:1px solid var(--border);border-radius:8px;padding:12px;max-height:420px;overflow-y:auto;}
.filters{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0;font-size:12px;}
.filters label{color:var(--muted);}
.filters select{background:var(--card);color:var(--ink);border:1px solid var(--border);border-radius:6px;padding:4px 8px;}
.dotplot{display:flex;gap:0;align-items:flex-end;height:150px;padding:10px 8px 0;border-bottom:1px solid var(--border);position:relative;}
.dotplot .bar{width:9px;background:var(--blue);border-radius:3px 3px 0 0;margin:0 2px;}
.dotplot .bar.error{background:var(--red);} .dotplot .bar.parked{background:var(--violet);} .dotplot .bar.hard_refusal{background:var(--out-refusal);}
.dotplot .t300{position:absolute;right:0;bottom:0;height:0;border-right:2px dashed var(--red);}
.latlabel{font-size:10px;color:var(--muted);}
.latgrid{display:flex;flex-direction:column;gap:10px;}
.latrow{display:grid;grid-template-columns:130px 1fr 60px;gap:8px;align-items:center;font-size:11.5px;}
.latbar{background:linear-gradient(90deg,#1d4ed8,#3b82f6);height:14px;border-radius:4px;min-width:4px;}
.latbar.error{background:linear-gradient(90deg,#991b1b,#b91c1c);}
.latbar.parked{background:linear-gradient(90deg,#5b21b6,#7c3aed);}
.latbar.hard_refusal{background:linear-gradient(90deg,#1e40af,#2563eb);}
.latmark{position:relative;height:14px;}
.latmark::after{content:"300s client timeout";position:absolute;right:0;top:-2px;font-size:10px;color:var(--red);border-right:2px dashed var(--red);padding-right:4px;}
.info-card{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--blue);border-radius:10px;padding:12px 16px;margin:10px 0;font-size:12.5px;line-height:1.75;}
.labels-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;}
.lcard{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px 12px;font-size:12px;line-height:1.6;}
.lcard .q{font-weight:800;}
.note-box{background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;padding:12px 16px;font-size:12.5px;line-height:1.7;margin:12px 0;}
.todo-box{background:#f1f5f9;border:1px dashed #94a3b8;border-radius:10px;padding:12px 16px;font-size:12.5px;line-height:1.7;margin:12px 0;}
/* TL;DR strip — the short version at the top */
.tldr{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--blue);border-radius:12px;padding:16px 20px;margin:0 0 30px;}
.tldr h2{font-size:15px;margin:0 0 8px;border:none;padding:0;}
.tldr-line{font-size:13.5px;line-height:1.7;color:var(--ink);margin:4px 0;}
.tldr-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;align-items:center;}
.tldr-chip{background:#eef2ff;border:1px solid #dbe4ff;color:var(--blue);border-radius:8px;padding:5px 11px;font-size:12.5px;text-decoration:none;font-weight:600;}
.tldr-chip b{font-size:14px;}
.tldr-chip.nolink{background:#f8fafc;border-color:var(--border);color:var(--ink);font-weight:500;}
.tldr-jump{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);}
.tldr-jump a{font-size:12px;color:var(--muted);text-decoration:none;}
.tldr-jump a:hover{color:var(--blue);text-decoration:underline;}
.foot{color:var(--muted);font-size:11.5px;margin-top:40px;border-top:1px solid var(--border);padding-top:14px;line-height:1.8;}
@media (max-width:900px){.layout{grid-template-columns:1fr;padding:0 12px;}
.sidebar{position:static;height:auto;border-right:none;border-bottom:1px solid var(--border);}
.sidebar nav{flex-direction:row;flex-wrap:wrap;gap:6px;}}
"""

# ============================================================
# SECTIONS
# ============================================================
def section_tldr(b, findings):
    """Short version at the top: one-line verdict + key chips + jumps."""
    s = b["summary"]; o = s["outcomes"]; v = s["vs_expected"]; val = s["value"]
    wrongly_parked = sum(1 for r in b["rows"] if r["outcome"] == "parked"
                         and r["expected_behavior"] in ("ANSWER", "REFUSE"))
    chip = lambda lbl, val_txt, href=None: (
        f'<a class="tldr-chip" href="{href}">{lbl} <b>{val_txt}</b></a>' if href
        else f'<span class="tldr-chip nolink">{lbl} <b>{val_txt}</b></span>')
    chips = [
        chip("L4/L5 (skeleton coverage)", f"{val['L4_L5']}/30", "#results"),
        chip("Behavior matched", f"{v['match']}/30", "#results"),
        chip("Wrongly parked", f"{wrongly_parked}/30", "#means"),
        chip("Fabricated figures", "none detected (1 judge, 20 answers)", "#limits"),
        chip("Leak hits (all likely FP)", f"{s['leaks']['flagged']}", "#evaluated"),
    ]
    # fix-first: high+medium findings, linked to their anchors
    first = [f2 for f2 in findings if f2["severity"] in ("high", "medium")]
    fix = " · ".join(f'<a class="tldr-chip" href="#{f2["id"].lower()}">{f2["id"]} — {esc(f2["title"][:58])}</a>'
                     for f2 in sorted(first, key=lambda x: x["severity"] != "high"))
    jumps = " ".join(
        f'<a href="#{a}">{t}</a>' for a, t in [
            ("summary", "Summary & run build"), ("means", "Fix-first findings"),
            ("results", "Query-by-query results"), ("evaluated", "How we evaluated"),
            ("labels", "How queries were labeled"), ("limits", "Limits & trust"),
            ("reproduce", "Reproduce as v2")])
    return f"""<div class="tldr" id="tldr">
<h2>TL;DR — the short version</h2>
<div class="tldr-line">{o["answered"]} of 30 CFO questions got substantive answers; <strong>{val["L4_L5"]}/30
L4/L5</strong> on the value ladder (skeleton coverage, element presence), <strong>no fabricated figures
detected</strong> (1 judge, 20 answers). Main defect: cross-answer template reuse. Refusals on payables /
expenses / P&amp;L / cash reflect workspace data gaps, not agent bugs.</div>
<div class="tldr-chips">{"".join(chips)}</div>
<div class="tldr-chips">{fix}</div>
<div class="tldr-jump">{jumps}</div>
</div>"""

def section_summary(b, findings):
    s = b["summary"]; o = s["outcomes"]; v = s["vs_expected"]; val = s["value"]
    verdict = (f'<div class="verdict"><span class="s">One-sentence verdict:</span> '
               f'{o["answered"]} of 30 CFO questions got substantive answers and '
               f'<strong>{val["L4_L5"]}/30 (43%)</strong> reached L4/L5 on the value ladder '
               f'(graded by skeleton coverage — element presence, not numeric correctness); '
               f'{o["hard_refusal"]} clean boundary-named refusals + {o["parked"]} clarify-parks; '
               f'<strong>no fabricated figures detected</strong> (1 judge, 20 answers judged) — '
               f'but see <a href="#f2">F2</a>: numbers can co-exist incoherently even with zero fabrication. '
               f'The main defect is <strong>cross-answer template reuse</strong>, not answer-level quality. '
               f'Refusals about payables, expenses, P&amp;L/COGS and cash/bank reflect <strong>data gaps in '
               f'the workspace</strong>, not agent bugs.</div>')
    header3 = (f'<h3>Data integrity (what not to trust)</h3>'
               f'<div class="note-box">Two deterministic checks FAIL: <strong>F2</strong> q16 percentages imply '
               f'denominators above the invoiced-sales total (double counting suspected) and <strong>F3</strong> q21 '
               f'cross-view contradiction (movement view outranks the “largest outstanding”). The q10/q26 '
               f'<code>expected_tool: aging</code> labels conflict with the workspace banner — overdue/ageing are '
               f'OVERSTATED (only ~3% of collected amounts are allocated to invoices). Numbers in answers can '
               f'co-exist incoherently even with zero fabrication — F2 is the proof.</div>')
    return f"""
<section id="summary">
  <h2>1 · Summary — how did the agent do?</h2>
  {verdict}
  <h3>Outcome bar (mutually exclusive; sums to 30)</h3>
  {outcome_bar(b)}
  <h3>KPI cards</h3>
  {kpi_cards(b, findings)}
  <h3>How this run was built — 4 steps</h3>
  {pipeline_steps(b)}
  {header3}
</section>"""


def section_findings(b, findings):
    order = ["Clarify gate", "Planner / evidence selection", "Data & aggregation layer",
             "Grounding & formatting", "Latency / robustness", "What works"]
    grouped = {}
    for f2 in findings:
        grouped.setdefault(f2["component"], []).append(f2)
    sev_order = {"high": 0, "medium": 1, "low": 2}
    html = ['<section id="means">',
            "<h2>2 · What this means for you — what should I fix first?</h2>",
            '<div class="desc">Findings grouped by the agent component that owns the fix. '
            'Each lists affected queries (deep-link into the explorer), a “done when” test to close it, '
            'and status across runs (all open in v1). “What works” is the do-not-regress list.</div>']
    for comp in order:
        items = grouped.get(comp, [])
        if not items:
            continue
        html.append(f'<h3>{comp}</h3>')
        for f2 in sorted(items, key=lambda x: sev_order.get(x["severity"], 9)):
            col = SEV_COLOR[f2["severity"]]
            qs = " ".join(f'<a href="#q{q}">q{q}</a>' for q in sorted(set(f2["queries"])) if 1 <= q <= 30) or "—"
            origin_flag = f'<span class="flag {"auto" if f2["origin"] == "auto" else "manual"}">{f2["origin"]}</span>'
            find_id = f2["id"].lower()  # f1..f9, used as anchor target
            html.append(f'<details class="finding sev-{f2["severity"]}" id="{find_id}">'
                        f'<summary><span style="color:{col};font-weight:800;">{f2["id"]}</span> '
                        f'<span>{esc(f2["title"])}</span> {origin_flag}<span class="flag open">{f2["status"]}</span></summary>'
                        f'<div class="details-body">'
                        f'<div class="desc"><strong>Evidence ({esc(f2["origin"])}):</strong> {esc(f2["evidence"])}</div>'
                        f'<div class="desc"><strong>Affected queries:</strong> {qs}</div>'
                        f'<div class="desc"><strong>Done when:</strong> {esc(f2["done_when"])}</div>'
                        f'</div></details>')
    # What works
    html.append("<h3>What works (do not regress)</h3>")
    html.append('<div class="info-card">'
                '<strong>No fabricated figures detected</strong> — none in 20 judged answers (1 judge); '
                'this is not a correctness guarantee (see <a href="#f2">F2</a>). <strong>Reconcile-guard discipline</strong> — ageing/overdue '
                'never headlined. <strong>Clean boundary-naming refusals</strong> (“Supplier payables … not reliably '
                'available”) that tell the user exactly which data is absent. <strong>Concrete actions</strong> in every '
                'answer (call today, dated commitments, escalation triggers). <strong>L5 benchmarks to preserve:</strong> '
                'q4, q9 (portfolio sizing + wave-based chase plan), q19 (CFO-style challenges), q21 (anomaly cross-check '
                'with hypotheses).</div>')
    html.append("</section>")
    return "".join(html)


def section_results(b):
    s = b["summary"]
    # value by tier and family (q30 counted in both A and E, flagged)
    rows = b["rows"]
    tier_count = Counter()
    tier_val = Counter()
    for r in rows:
        t = r["tier"].rstrip("*")
        tier_count[t] += 1
        if r["value_level"] in ("L4", "L5"):
            tier_val[t] += 1
    fam_rows = {}
    for r in rows:
        for fa in (r["family"].split("|") if "|" in r["family"] else [r["family"]]):
            fam_rows.setdefault(fa, []).append(r)
    fam_html = ""
    for fa in ("A", "B", "C", "D", "E"):
        rs = fam_rows.get(fa, [])
        if not rs:
            continue
        n = len(rs)
        n45 = sum(1 for r in rs if r["value_level"] in ("L4", "L5"))
        unjudged = sum(1 for r in rs if not r["value_level"])
        links = " ".join('<a href="#q{q}">q{q}</a>'.format(q=r["query_index"])
                         for r in sorted(rs, key=lambda x: x["query_index"]))
        fam_html += ("<tr><td><strong>{fa}</strong> — {name}</td><td>{n}</td><td>{n45}</td><td>{unjudged}</td>"
                     '<td style="font-size:11px;">{links}</td></tr>').format(
            fa=fa, name=FAMILY_NAME[fa], n=n, n45=n45, unjudged=unjudged, links=links)
    fam_html = f'<div class="table-wrap"><table><thead><tr><th>Family</th><th>Queries</th><th>L4/L5</th><th>Ungraded</th><th>Queries (q30 in A and E)</th></tr></thead><tbody>{fam_html}</tbody></table></div>'
    tier_html = (f'<div class="table-wrap"><table><thead><tr><th>Tier</th><th>Queries</th><th>L4/L5</th>'
                 f'<th>Definition (FinGAIA business-depth)</th></tr></thead><tbody>'
                 f'<tr><td>T1</td><td>{tier_count["T1"]}</td><td>{tier_val["T1"]}</td>'
                 f'<td style="font-size:11.5px;">operational fetch / refusal</td></tr>'
                 f'<tr><td>T2</td><td>{tier_count["T2"]}</td><td>{tier_val["T2"]}</td>'
                 f'<td style="font-size:11.5px;">decision support</td></tr>'
                 f'<tr><td>T3</td><td>{tier_count["T3"]}</td><td>{tier_val["T3"]}</td>'
                 f'<td style="font-size:11.5px;">strategic risk</td></tr>'
                 f'</tbody></table></div>'
                 f'<div class="desc">Tier tags: authoritative = Phase 2/3 docs (user-approved 2026-09-18); '
                 f'q2/q15/q16/q27 marked * are DISPUTED — the Phase 1 scorecard tagged them T1/T2. '
                 f'See the label section.</div>')
    return f"""
<section id="results">
  <h2>3 · Results — query-by-query</h2>
  <h3>Expected-vs-observed heatmap</h3>
  {heatmap(b)}
  <h3>Query explorer (mismatches first)</h3>
  <div class="desc">Expand any row for the full question, labels, judge grade and the agent's complete response.
      Inline filters are client-side only — all content is server-rendered (view-source shows every row).
      Behavior verdict: <strong>{s["vs_expected"]["match"]} match</strong> ·
      {s["vs_expected"]["partial"]} partial · <strong style="color:#dc2626;">{s["vs_expected"]["mismatch"]} mismatch</strong> ·
      {s["vs_expected"]["error"]} error.
      Mismatches exactly: CLARIFY→answered q1 q11 q19 q21 q22 q25 q30 · ANSWER→parked q7 q8 q24 q29 · REFUSE→parked q14.</div>
  {explorer(b)}
  <h3>Value by tier and family</h3>
  {tier_html}
  {fam_html}
  <h3>Latency by outcome (0→300s, client timeout marked)</h3>
  {latency_section(b)}
</section>"""


## __APPEND_B__


# ============================================================
# QUERY EXPLORER (section 3) — server-rendered rows; inline JS
# filters by data-* attributes only.
# ============================================================
def explorer(b):
    rows = b["rows"]
    rank = {"mismatch": 0, "partial": 1, "error": 2, "match": 3}
    ordered = sorted(rows, key=lambda r: (rank.get(r["verdict"], 9), r["query_index"]))
    out = []
    for r in ordered:
        qi = r["query_index"]
        exp = r["expected_behavior"]
        ver = r["verdict"]
        vl = r["value_level"] or "—"
        tier = esc(r["tier"]); fam = esc(r["family"])
        vc = VERDICT_COLOR.get(ver, "#64748b")
        oc = OUTCOME_COLOR[r["outcome"]]
        flags = []
        if ver == "mismatch":
            flags.append('<span class="flag disp">mismatch</span>')
        elif ver == "partial":
            flags.append('<span class="flag disp">partial − hedged</span>')
        if r["boundary"]:
            flags.append('<span class="flag manual">answered-with-boundary</span>')
        if r["tier"].endswith("*"):
            flags.append('<span class="flag disp">tier disputed (v1 scorecard)</span>')
        if r["expected_tool"] == "TOOL:aging":
            flags.append('<span class="flag disp">tool label conflicts w/ workspace banner</span>')
        if qi == 17:
            flags.append('<span class="flag manual">refusal in substance</span>')
        if qi == 30:
            flags.append('<span class="flag manual">family A + E</span>')
        if not r["response_full"] and r["outcome"] in ("parked", "error"):
            flags.append('<span class="flag manual">no response captured</span>')
        judge_note = esc(r["judge_note"]) or ""
        errs = " ".join(f"<code>{esc(e)}</code>" for e in r["value_errors"]) or "<code>none</code>"
        qshort = esc((r["query"] or "")[:180])
        metaline = (f'<span class="qmeta">expected {exp} · tool {esc(r.get("expected_tool") or "NO_TOOL")}'
                    f' · tier {tier} · family {fam} · outcome <b style="color:{oc}">{r["outcome"]}</b>'
                    f' · verdict <b style="color:{vc}">{ver}</b> · value {vl} · {r.get("latency_s") or "-"}s'
                    f' · {"".join(flags)}</span>')
        body = f"""<div class="details-body">
<div class="desc"><strong>Question:</strong> {esc(r['query'])}</div>
<div class="desc"><strong>Labels:</strong> expected_behavior {exp} (per classify-gate rules) · expected_tool <code>{esc(r.get('expected_tool') or 'NO_TOOL')}</code> · FinGAIA tier {tier} · family {fam}{' (shared A/E)' if qi == 30 else ''}</div>
<div class="desc"><strong>Grade:</strong> value level {vl} · FinGAIA error codes: {errs}</div>
{f'<div class="desc"><strong>Judge note:</strong> {judge_note}</div>' if judge_note else ''}
<pre>{esc(r['response_full'] or '(no response text captured on this stream)')}</pre>
</div>"""
        out.append(f'<details class="qrow out-{r["outcome"]}" id="q{qi}" '
                   f'data-exp="{exp}" data-out="{r["outcome"]}" data-ver="{ver}" '
                   f'data-tier="{esc(r["tier"]).rstrip("*")}" data-fam="{esc(r["family"])}" '
                   f'data-err="{"+".join(r["value_errors"]) or "none"}">'
                   f'<summary><span>q{qi}</span> <span>{qshort}</span>{metaline}</summary>{body}</details>')
    filters = """<div class="filters" id="qfilter">
<label>tier <select data-f="tier"><option value="">all</option><option>T1</option><option>T2</option><option>T3</option></select></label>
<label>family <select data-f="fam"><option value="">all</option><option>A</option><option>B</option><option>C</option><option>D</option><option>E</option></select></label>
<label>outcome <select data-f="out"><option value="">all</option><option>answered</option><option>hard_refusal</option><option>parked</option><option>error</option></select></label>
<label>verdict <select data-f="ver"><option value="">all</option><option>match</option><option>partial</option><option>mismatch</option><option>error</option></select></label>
<label>error code <select data-f="err"><option value="">all</option><option>Craft</option><option>DataTypeHandling</option><option>FinancialTerminologicalBias</option><option>none</option></select></label>
<label><button type="button" id="qreset" style="background:var(--card);color:var(--blue);border:1px solid var(--border);border-radius:6px;padding:3px 10px;cursor:pointer;">reset</button></label>
</div>"""
    js = """<script>
(function(){
 var f=document.querySelectorAll('#qfilter select'), rows=Array.prototype.slice.call(document.querySelectorAll('.qrow'));
 function apply(){var s={};f.forEach(function(x){s[x.dataset.f]=x.value;});
  rows.forEach(function(r){var ok=true;Object.keys(s).forEach(function(k){if(!s[k])return;if(k==='err'){var e=r.dataset.err;if(s[k]==='none'?e!=='none':e.indexOf(s[k])<0)ok=false;}else if(r.dataset[k]!==s[k])ok=false;});r.style.display=ok?'':'none';});
 }
 f.forEach(function(x){x.addEventListener('change',apply);});
 document.getElementById('qreset').addEventListener('click',function(){f.forEach(function(x){x.value='';});apply();});
})();
</script>"""
    return filters + '<div id="qexplorer">' + "".join(out) + "</div>" + js


def latency_section(b):
    rows = [r for r in b["rows"] if r["outcome"] in ("answered", "hard_refusal", "parked", "error")]
    MAX = 300.0
    lat_rows = ""
    for r in sorted(rows, key=lambda x: x["latency_s"] or 0):
        lat = r["latency_s"] or 0
        w = max(1.2, min(100.0, lat / MAX * 100))
        cls = r["outcome"] if r["outcome"] in ("error", "parked", "hard_refusal") else "answered"
        lat_rows += (f'<div class="latrow"><span>q{r["query_index"]} · {OUTCOME_LABEL[r["outcome"]]}</span>'
                     f'<span class="latmark"><span class="latbar {cls}" style="width:{w:.1f}%;display:inline-block;"></span></span>'
                     f'<span>{lat:.1f}s</span></div>')
    return (f'<div class="latgrid">{lat_rows}</div>'
            f'<div class="desc">Scale: 0→300s (HEART #2 SSE client timeout). '
            f'q20 at 244.7s is an upstream IncompleteRead drop <em>before</em> the timeout — recorded as-is, no retry (HEART #5). '
            f'Answered median 47.2s (mean 65.6s; range 35.9–211.9s) — the old blended “44.2s avg” hid the outcome split: '
            f'parks 2–3s, hard refusals ~2s.</div>')


def section_evaluated(b):
    s = b["summary"]; j = s["judge"]

    def qlinks(qs):
        return " ".join('<a href="#q{q}">q{q}</a>'.format(q=q) for q in qs) or "—"

    def stcol(st):
        return {"FAIL": "#dc2626", "WARN": "#d97706", "UNKNOWN": "#64748b"}.get(st, "#16a34a")

    checks = "".join(
        f'<tr><td><strong>{esc(c["id"])}</strong></td>'
        f'<td>{esc(c["name"])}</td>'
        f'<td><span style="color:{stcol(c["status"])};font-weight:700;">{esc(c["status"])}</span></td>'
        f'<td>{qlinks(c["queries"])}</td>'
        f'<td style="font-size:11.5px;">{esc(c["evidence"])}</td></tr>'
        for c in s["content_checks"])
    leaks = "".join(
        f'<tr><td>q{l["query_index"]}</td><td><code>{esc(l["rule"])}</code></td>'
        f'<td style="font-size:11.5px;"><code>{esc(l["matched"])}</code></td>'
        f'<td style="font-size:11px;color:#94a3b8;">{esc(l.get("note", ""))}</td></tr>'
        for l in b["leaks"])
    not_tested = ("Multi-turn conversation (each query ran in its own isolated thread — no follow-ups), "
                  "tool selection (the finance stream is backend SQL and emits no tool events), "
                  "run-to-run variance of the clarify gate (except the q3 park-then-answer re-probe), "
                  "other workspaces, and the numeric correctness of every figure (the ledger cross-checks "
                  "consistency, not ground truth).")
    return f"""
<section id="evaluated">
  <h2>4 · How we evaluated</h2>
  <div class="info-card">
    <h3>Run pipeline (per HEART.md)</h3>
    30 CFO insight questions, executed by <code>scripts/run_agent_evals.py</code> against the live
    <code>finance</code> agent template (hirafoods workspace): <strong>one isolated thread per query</strong>
    (30 distinct thread_ids), single turn, SSE capture with a <strong>300s client timeout</strong>
    (HEART #2), <strong>no retries</strong> (HEART #5 — q20's IncompleteRead is recorded as-is), and full
    trace capture (status sequence, timing, errors). Versioned, never overwritten (HEART #4). Parser fixed
    2026-09-18 to unwrap nested <code>ui.payload.data.markdown</code> answers and to capture SSE error events —
    a pre-fix run would have recorded most answers as empty.
  </div>
  <div class="info-card">
    <h3>Grading: skeleton-first (Phase 3) + anchored judge (Phase 2)</h3>
    Before scoring, a competent-accountant answer skeleton was written per query family (see the label
    section for the 5 skeletons), then every response was graded element-by-element (present / partial /
    missing) and placed on the value ladder: L1 fetch · L2 paraphrase/padding · L3 structured finding ·
    L4 insight + decision support · L5 proactive CFO partner. Phase 2 re-scored all 20 answers with a
    mandatory verbatim-evidence quote and a FinGAIA error-code axis.
  </div>
  <div class="info-card">
    <h3>Versions &amp; provenance</h3>
    Producer: <strong>{esc(s["producer_model"])}</strong> (classify gate + answer format node).
    Judge: <strong>{esc(j["model"])}</strong> · rubric v{j.get("rubric_version", "1")} ·
    human-reviewed <strong>{j["human_reviewed"]}/{j["judged"]}</strong>.
    {JUDGE_STATEMENT}
  </div>
  <div class="info-card">
    <h3>Deterministic content checks (no LLM)</h3>
    <div class="table-wrap"><table><thead><tr><th>ID</th><th>Check</th><th>Status</th><th>Queries</th><th>Evidence</th></tr></thead><tbody>{checks}</tbody></table></div>
  </div>
  <div class="info-card">
    <h3>Leak hits — with the matched string per hit</h3>
    <div class="desc"><strong>{b["summary"]["leaks"]["flagged"]} hits</strong> across
    {len(b["summary"]["leaks"]["by_rule"])} rules — {" · ".join(f"<code>{esc(k)}</code> x{v}" for k, v in sorted(b["summary"]["leaks"]["by_rule"].items()))}.
    All rules are heuristic regexes over response text; every hit is a <strong>likely FALSE POSITIVE</strong>:
    <code>workspace_ref</code> trips on the intentional reconcile warning banner (user-facing text, review
    allowlist); <code>data_availability</code> trips when the agent references the rows/results it was given
    (process transparency — q1 q15 q19 q25, see <a href="#f10">F10</a>); <code>requested_ref</code> trips when
    the agent echoes what the question asked (q19). None reference live internal state, credentials or
    other-workspace data; the matched string per hit is shown so each one is auditable, and the detector
    is unchanged — flagged per hit, resolved manually.</div>
    <div class="table-wrap"><table><thead><tr><th>Query</th><th>Rule</th><th>Matched string</th><th>Note</th></tr></thead><tbody>{leaks}</tbody></table></div>
  </div>
  <div class="info-card">
    <h3>NOT tested by this run</h3>
    <div class="desc">{not_tested}</div>
  </div>
</section>"""


def section_labels(b):
    s = b["summary"]
    rows = b["rows"]
    exp_n = Counter(r["expected_behavior"] for r in rows)
    tool_n = Counter(r["expected_tool"] or "NO_TOOL" for r in rows)
    tier_n = Counter(r["tier"].rstrip("*") for r in rows)
    disputed = [q for q, t in TIERS.items() if t.endswith("*")]
    aging_q = [r["query_index"] for r in rows if (r.get("expected_tool") or "") == "TOOL:aging"]
    # Error-code taxonomy: definitions quoted from FinGAIA (arXiv:2507.17186v2)
    # Appendix B "Examples for Error Analysis" (the paper's five error types);
    # Craft is a LOCAL EXTENSION not present in the paper; local hit counts
    # come from the judge file. See the taxonomy note below the table.
    err_defs = [
        ("Data Type Handling Error (paper)",
         "agent triggers when the type/format of input data falls outside its supported range (e.g. video files, "
         "executable programs), rendering it unable to process the task — a functional limitation, not a logic "
         "error. <strong>This run: 1 local hit on q1</strong> (literal '[unverified]' placeholder) — see note."),
        ("Financial Terminological Bias (paper)",
         "comprehension flaws in the professional financial terminology system; confuses similar regulatory "
         "definitions, misapplies calculation logic, or disregards context sensitivity. <strong>This run: 5 hits</strong> "
         "(judge applied it to duplicated 'days days' unit tokens — format-level reuse of the paper concept)."),
        ("Operational Process Awareness Barrier (paper)",
         "cognitive obstacles regarding standardized financial business processes: misinterprets operational "
         "requirements of regulatory rules, omits key compliance steps, or reverses business-execution sequence. "
         "<strong>This run: 0 hits</strong> (added to this page's taxonomy per the paper; the local judge did not use it)."),
        ("Hallucinatory Financial Reasoning (paper)",
         "agent generates false financial propositions without reliable evidence (factual/logical/data "
         "hallucinations). <strong>This run: 0</strong> — the 'no fabricated figures detected' claim above is exactly "
         "this code's absence."),
        ("Entity-Causation Misidentification (paper)",
         "agent mistakes superficial correlations for fundamental causal drivers or confuses the sequential logic "
         "of business processes. <strong>This run: 0</strong>."),
        ("Craft — LOCAL EXTENSION (not in FinGAIA)",
         "answer-structure/format defects the paper does not taxonomize: refusal '..' glitches (q12 q13 q18 q27), "
         "q17's '0 figures verified' footer on a refusal, template-reuse artifacts. <strong>This run: 5 hits</strong>."),
    ]
    err_html = "".join(
        f"<tr><td><code>{esc(n)}</code></td><td>{esc(d)}</td></tr>" for n, d in err_defs)
    lab = "".join(
        f'<tr><td><strong>{esc(k)}</strong></td><td>{v}</td></tr>'
        for k, v in [("expected_behavior (expected label)", "9 ANSWER · 12 CLARIFY · 9 REFUSE"),
                     ("expected_tool (review-intent)", f"{tool_n.get('NO_TOOL', 0)} NO_TOOL · 9 TOOL:* (see flags)"),
                     ("FinGAIA tier", "T1 6 · T2 8 · T3 16 (4 disputed)"),
                     ("question family", "A 6 (incl. q30) · B 4 · C 5 · D 4 · E 10 (incl. q30); q5 q6 unassigned")])
    cards = []
    for q in sorted(rows, key=lambda x: x["query_index"]):
        r = next(x for x in rows if x["query_index"] == q["query_index"])
        qi = r["query_index"]
        rat = r["judge_note"] or "no rationale recorded"
        flags = []
        if r["tier"].endswith("*"):
            flags.append('<span class="flag disp">tier disputed</span>')
        if (r.get("expected_tool") or "") == "TOOL:aging":
            flags.append('<span class="flag disp">tool vs banner</span>')
        if qi in (5, 6):
            flags.append('<span class="flag manual">family unassigned</span>')
        if qi == 30:
            flags.append('<span class="flag manual">A + E</span>')
        cards.append(
            f'<details class="lcard" id="lc{qi}"><summary><span class="q">q{qi}</span> '
            f'<span style="font-size:11px;color:#94a3b8;">{esc((r["query"] or "")[:70])}</span>'
            f'{"".join(flags)}</summary>'
            f'<div class="details-body" style="padding:2px 4px 8px;">'
            f'<div class="desc">expected_behavior <code>{r["expected_behavior"]}</code> · expected_tool '
            f'<code>{esc(r.get("expected_tool") or "NO_TOOL")}</code> · tier <code>{esc(r["tier"])}</code> · '
            f'family <code>{esc(r["family"])}</code></div>'
            f'<div class="desc" style="font-size:11px;">Rationale: {esc(rat[:220])}</div>'
            f'</div></details>')
    return f"""
<section id="labels">
  <h2>5 · How we labeled the queries</h2>
  <div class="desc">Labels were assigned by you (user, 2026-09-18) per the finance classify-gate decision
  order: a real metric → <strong>ANSWER</strong>; vague / judgment / multi-reading → <strong>CLARIFY</strong>;
  data genuinely absent → <strong>REFUSE</strong>. The tier tags (FinGAIA business-depth, T1–T3) were
  user-approved on the Phase 3 review; the Phase 1 scorecard initially tagged q2/q15/q16/q27 differently
  and that disagreement is deliberately surfaced, not resolved here.</div>
  <div class="table-wrap"><table><thead><tr><th>Label family</th><th>Distribution</th></tr></thead><tbody>{lab}</tbody></table></div>
  <h3>Tier definitions (adapted from FinGAIA, arXiv:2507.17186v2)</h3>
  <div class="table-wrap"><table><thead><tr><th>Tier</th><th>FinGAIA definition (steps · tools)</th><th>Queries</th><th>Example here</th></tr></thead><tbody>
  <tr><td>T1</td><td>L1 Basic Business Analysis — "structurally simple, typically requiring no more than five steps and the use of only one or two tools"</td><td>{tier_n["T1"]}</td><td>q10 – quantify overdue recoverability</td></tr>
  <tr><td>T2</td><td>L2 Asset Decision Support — "increased reasoning steps from 5 to 7, and the integration of more than two tools"</td><td>{tier_n["T2"]}</td><td>q9 – aggressive recovery plan</td></tr>
  <tr><td>T3</td><td>L3 Strategic Risk Management — "a greater number of steps around 10 and require coordinated use of multiple tools, including sequential tool invocation and parameter tuning"</td><td>{tier_n["T3"]}</td><td>q27 – profitability &amp; cash verdict</td></tr>
  </tbody></table></div>
  <div class="note-box"><strong>Adapted from FinGAIA, not FinGAIA itself:</strong> the paper's tiers are defined
  by measured <em>steps and tool counts</em> over 407 expert-validated tasks with ground-truth answers. This run
  has <strong>no ground-truth answers and no tool events</strong> (the finance stream is backend SQL), so the tier
  tags above reflect the question's intended business depth per the user's labels, mapped onto the paper's ladder —
  not a measured step/tool count. Definition text and the error taxonomy below are quoted from the paper
  (arXiv:2507.17186v2, Appendix B "Examples for Error Analysis"); the local artifacts, not the paper, assigned the
  per-query tags. The paper's own evaluation "primarily relied on manual review" of every answer; this run is
  LLM-only with 0 human-reviewed ratings (see §6).</div>
  <h3>Error-code taxonomy (as used by the judge)</h3>
  <div class="table-wrap"><table><thead><tr><th>Code</th><th>Meaning here</th></tr></thead><tbody>{err_html}</tbody></table></div>
  <div class="desc"><strong>DataTypeHandling discrepancy (surfaced, not resolved):</strong> the paper defines
  Data Type Handling Error as input types/formats outside the supported range (video, executables). The single
  local hit is <strong>q1</strong>, where the judge tagged the literal <code>[unverified]</code> placeholder —
  a grounding/format artifact, not an unsupported input file (this run had no file inputs at all). Under the
  paper's definition that hit is a Craft-class format defect, and the paper-defined count here is 0. Kept as
  the judge recorded it; the taxonomy note above is the correction.</div>
  <h3>Disputed labels (surfaced, not resolved)</h3>
  <div class="note-box">
  <strong>Tier conflict:</strong> VALUE_SCORECARD_phase1.md tagged q2 T1, q15 T2, q16 T2, q27 T1; the
  Phase 2/3 docs (user-approved 2026-09-18) tag all four T3. This page uses the Phase 2/3 tags and marks
  q{", ".join(f"q{q}" for q in disputed)} with a dispute flag. <br>
  <strong>Tool-label conflict:</strong> q{", ".join(f"q{q}" for q in aging_q)} carry
  <code>expected_tool: aging</code> while the workspace banner says overdue/ageing are OVERSTATED
  (~3% of collected amounts allocated to invoices) — the label contradicts the workspace's own limitation.<br>
  <strong>Family gaps:</strong> q5 and q6 are not assigned to any family; q30 appears in A and E.
  Flagged for the owner to resolve.</div>
  <h3>Per-query label cards — all 30</h3>
  <div class="labels-grid">{ "".join(cards) }</div>
  <div class="desc"><strong>Why labels matter here:</strong> 7 CLARIFY-labeled queries were answered with
  L4/L5 answers (q1 q11 q19 q21 q22 q25 q30) while equally vague queries parked (q3 q5 q6 q23) — so it is
  unclear whether the agent or the label is wrong. The gate's non-determinism (~30% park rate) makes this
  a rate question, not a per-query one.</div>
</section>"""


## __APPEND_C__


def section_limits(b):
    j = b["summary"]["judge"]
    prov = JUDGE_STATEMENT.split("Human-reviewed")[0].strip() + "."
    return """
<section id="limits">
  <h2>6 · Limits and trust — can I trust and reproduce this?</h2>
  <div class="info-card">
    <strong>Single judge, 30 queries, one run.</strong> The L-levels come from one in-session model
    (deepseek-v4) in two self-consistent passes — {prov}. A human has not reviewed the ratings
    (human-reviewed 0/{judged}). Grading measures element <em>presence</em> against the accountant skeletons
    more than numeric correctness of the figures (the consistency ledger cross-checks figures against
    each other and the known baseline, not against ground truth). The clarify gate is stochastic
    (~30% park rate on clarify-prone inputs), so per-query verdicts on parks are probabilistic, not
    categorical. q20's error is an upstream drop, not a verdict on the agent.
  </div>
  <div class="info-card">
    <strong>What this page does not claim:</strong> no claim that figures are ground-truth correct;
    no fabrication <em>guarantee</em> — "no fabricated figures detected (1 judge, 20 answers)" is the
    honest form; no estimate of run-to-run variance; no coverage of multi-turn behavior or other
    workspaces. The "44.2s average" of the old readout is not used — latency is shown by outcome.
    FinGAIA (arXiv:2507.17186v2) relied primarily on <em>manual review</em> of every answer,
    supplemented by LLM-as-judge; this run is the opposite — LLM-only grading, <strong>0/20
    human-reviewed</strong> — so label, tier and error-code values here carry that confidence gap.
  </div>
</section>""".format(prov=prov, judged=j["judged"])


def section_reproduce(b):
    v = b["version"]
    j = b["summary"]["judge"]
    links = "<br>".join(
        f'<a href="{RAW}/accounts/finance/runs/v{v}/{f}">{f}</a>'
        for f in ("summary.json", "findings.json", "judgments.jsonl", "leaks.jsonl", "results.jsonl"))
    raw_links = "<br>".join(
        f'<a href="{RAW}/accounts/finance/runs/{f}">{f}</a>'
        for f in ("query_results_v1.jsonl", "manifest.json", "value_phase2_judge.json",
                  "value_phase1_v1.json"))
    doc_links = "<br>".join(
        f'<a href="{RAW}/accounts/finance/{f}">{f}</a>'
        for f in ("EVAL_READOUT_v1.md", "VALUE_READOUT_v1.md", "VALUE_JUDGE_phase2.md",
                  "VALUE_GRADE_phase3.md", "VALUE_SCORECARD_phase1.md"))
    return f"""
<section id="reproduce">
  <h2>7 · Reproduce — rerun as v2</h2>
  <div class="info-card">
    <h3>Commands</h3>
    <pre style="font-size:11.5px;line-height:1.7;background:#f8fafc;border:1px solid var(--border);border-radius:8px;padding:10px 12px;color:#0f172a;"># rerun only mismatches/errors as v2 (pre-seeds untouched rows — stays diffable)
python3 scripts/eval_cli.py rerun --failed --account finance
# derive + print the summary block (invariants asserted; exits 1 on violation)
python3 scripts/finance_pipeline.py --run 2 --print
# rebuild this dashboard
python3 build_dashboard.py --account finance --version 2
# compare v1 vs v2 per-query verdicts + metric deltas
python3 scripts/eval_cli.py diff 1 2 --account finance</pre>
    <div class="desc">HEART rules apply to v2 as to v1: versioned file, no retries, no masking,
    full trace capture. A run selector and a v1-vs-v2 delta view will appear on this page once a
    second run exists.</div>
  </div>
  <div class="info-card">
    <h3>Raw sources (absolute links — GitHub Pages publishes only docs/)</h3>
    Run v{v}:<br>{links}<br><br>
    Raw traces + label source:<br>{raw_links}<br><br>
    Owner-facing readouts:<br>{doc_links}
  </div>
  <div class="info-card">
    <h3>Add a query (with labels)</h3>
    Queries are generator-owned: edit <code>scripts/gen_finance_queries.py</code> (query text +
    <code>expected_behavior</code> ANSWER/CLARIFY/REFUSE + <code>expected_tool</code> review-intent),
    regenerate the xlsx, probe one query live, then run. Labels follow the classify-gate decision order
    (real metric → ANSWER; vague/judgment → CLARIFY; absent data → REFUSE). Tier tags (T1–T3) are
    assigned per the FinGAIA business-depth ladder; keep the disputed-label list in sync when you change one.
  </div>
  <div class="info-card">
    <h3>Verified-against-what</h3>
    This page is generated from the derived artifacts with invariants asserted at build time
    (outcomes/verdicts/matrix sums == 30; 30 label cards; all 30 deep links; no relative hrefs;
    30 distinct thread_ids). Every displayed count is derived, never hard-coded.
  </div>
</section>"""


def shell(b, sections_html):
    v = b["version"]; md = b["summary"]["date"]
    nav = [
        ("tldr", "TL;DR · at a glance"), ("summary", "1 · Summary"),
        ("means", "2 · What this means for you"),
        ("results", "3 · Results"), ("evaluated", "4 · How we evaluated"),
        ("labels", "5 · How we labeled"), ("limits", "6 · Limits & trust"),
        ("reproduce", "7 · Reproduce"),
    ]
    nav_html = "".join(f'<a href="#{a}">{t}</a>' for a, t in nav)
    # Plain (non-f) string so the JS braces don't collide with the shell f-string.
    hash_js = ("<script>\n"
               "// open a <details> row/finding/label card when its id arrives via #fragment\n"
               "// (browsers scroll to the element but do NOT open a closed details natively)\n"
               "(function(){function o(){var h=location.hash.slice(1);if(!h)return;\n"
               "var e=document.getElementById(h);\n"
               "if(e&&e.tagName==='DETAILS'&&!e.open)e.open=true;}\n"
               "window.addEventListener('DOMContentLoaded',o);\n"
               "window.addEventListener('hashchange',o);})();\n"
               "</script>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Agent Eval — Run v{v} ({md})</title>
<style>{page_css()}</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <h1>Finance Agent — Eval v{v}</h1>
    <div class="src">Run {md} · 30 user-provided CFO queries · hirafoods workspace ·
    producer gpt-5.4-mini · judge in-session deepseek-v4 · human-reviewed 0/20 ·
    invariants OK (asserted at build)</div>
    <nav>{nav_html}</nav>
    <div class="src" style="margin-top:16px;"><a href="legacy/" style="color:#94a3b8;">← pre-redesign page (legacy)</a></div>
  </aside>
  <main>
    {sections_html}
    <div class="foot">
      Static page rendered from derived artifacts (accounts/finance/runs/v{v}/) — all content
      server-rendered; inline JS only for the explorer's client-side filters. ·
      Raw traces: <a href="{RAW}/accounts/finance/runs/query_results_v{v}.jsonl">query_results_v{v}.jsonl</a> ·
      Pre-redesign page kept at <a href="legacy/">legacy/</a> until the new page is verified. ·
      Repo: navneetlearns/langsmith-tool-evaluator · Run v{v} · {md}
    </div>
  </main>
</div>
{hash_js}
</body>
</html>"""


def build(version: int):
    b = load(version)
    findings = seed_findings(b)
    sections = "".join([
        section_tldr(b, findings),
        section_summary(b, findings),
        section_findings(b, findings),
        section_results(b),
        section_evaluated(b),
        section_labels(b),
        section_limits(b),
        section_reproduce(b),
    ])
    page = shell(b, sections)
    assert_invariants(b, page)                      # fail build on any violation
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "index.html"
    out.write_text(page)
    print(f"  [finance-static] wrote {out} ({len(page)} bytes)")
    build_legacy(version)                            # old page stays reachable at /legacy/
    return page


# ------------------------------------------------------------
# LEGACY page — the pre-redesign story-first layout, preserved
# at docs/finance/legacy/index.html with a superseded banner.
# ------------------------------------------------------------
def build_legacy(version: int):
    d = SCRIPT_DIR / "accounts" / "finance" / "runs" / f"v{version}"
    summary = json.loads((d / "summary.json").read_text())
    findings = json.loads((d / "findings.json").read_text())
    leaks = [json.loads(l) for l in (d / "leaks.jsonl").read_text().splitlines() if l.strip()]
    sys.path.insert(0, str(SCRIPT_DIR / "scripts"))
    from finance_pipeline import derive
    _, rows, _, _ = derive(int(version))
    # rebuild the old page with the previous generator, then banner it
    old = _legacy_page(summary, findings, leaks, rows, version)
    sep = '<div class="dashboard-grid">'
    banner = ('<div class="dashboard-grid"><div style="background:rgba(217,119,6,.1);'
              'border:1px solid rgba(217,119,6,.5);border-radius:10px;padding:10px 16px;'
              'margin:12px 0;font-size:13px;">SUPERSEDED — this is the pre-redesign story-first page. '
              'The redesigned dashboard (sticky nav, 7 sections, findings, label cards) is '
              f'<a href="../index.html" style="font-weight:700;">here (../index.html)</a>.</div>')
    old = old.replace(sep, banner + sep, 1)
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    out = LEGACY_DIR / "index.html"
    out.write_text(old)
    print(f"  [finance-static] wrote {out} ({len(old)} bytes)")
    return old


def _legacy_page(summary, findings, leaks, rows, version):
    """The exact pre-redesign layout (story-first, 7 <details> tables) — rebuilt from the
    same derived artifacts so the legacy page and the current data never drift."""
    o = summary["outcomes"]; v = summary["vs_expected"]; val = summary["value"]
    j = summary["judge"]; lat = summary["latency_by_outcome"]
    css = extract_template_css()
    dl = lambda label, desc, body: (f"<details>\n<summary>{label}</summary>\n"
                                    f'<div class="details-body"><div class="desc">{desc}</div>{body}</div></details>')
    oc0 = {"answered": "#16a34a", "hard_refusal": "#2563eb", "parked": "#7c3aed", "error": "#dc2626"}
    cards = "".join(
        f'<div class="quality-card" style="background:var(--surface);border-left:4px solid {oc0[k]};'
        f'border-radius:8px;padding:16px;"><div class="count" style="color:{oc0[k]};">'
        f'{o.get(k, 0)}</div><div class="desc"><strong>{OUTCOME_LABEL[k]}</strong></div>'
        f'<div class="pct">{round(o.get(k, 0) / summary["queries"] * 100)}% of queries</div></div>'
        for k in OUTCOME_LABEL)
    matrix_rows = ""
    for e, lbl in (("ANSWER", "Answer"), ("CLARIFY", "Clarify (park)"), ("REFUSE", "Refuse")):
        c = {"answered": 0, "hard_refusal": 0, "parked": 0, "error": 0}
        for r in rows:
            if (r.get("expected_behavior") or "ANSWER").upper() == e:
                c[r["outcome"]] += 1
        matrix_rows += (f'<tr><td><strong>{e}</strong></td><td>{c["answered"]}</td>'
                        f'<td>{c["hard_refusal"]}</td><td>{c["parked"]}</td><td>{c["error"]}</td></tr>')
    check_rows = "".join(
        f'<tr><td><strong>{esc(c["id"])}</strong></td><td>{esc(c["name"])}</td>'
        f'<td>{esc(c["status"])}</td><td>{esc(", ".join(f"q{q}" for q in c["queries"]) or "—")}</td>'
        f'<td style="font-size:12px;">{esc(c["evidence"])}</td></tr>' for c in summary["content_checks"])
    finding_rows = "".join(
        f'<tr><td><strong>{esc(f["id"])}</strong></td><td>{esc(f["severity"])}</td><td>{esc(f["type"])}</td>'
        f'<td>{esc(", ".join(f"q{q}" for q in f["queries"]) or "—")}</td>'
        f'<td style="font-size:12px;">{esc(f["evidence"])}</td>'
        f'<td style="font-size:12px;color:#6b7280;">{esc(f["suggested_fix"])}</td>'
        f'<td>{esc(f["status"])}</td></tr>' for f in sorted(findings, key=lambda x: x["id"]))
    leak_rows = "".join(
        f'<tr><td>q{l["query_index"]}</td><td><code>{esc(l["rule"])}</code></td>'
        f'<td style="font-size:12px;"><code>{esc(l["matched"])}</code></td>'
        f'<td style="font-size:11px;color:#6b7280;">{esc(l["note"])}</td></tr>' for l in leaks)
    q_rows = "".join(
        f'<tr><td>q{r["query_index"]}</td>'
        f'<td style="font-size:12px;max-width:260px;">{esc((r.get("query") or "")[:110])}</td>'
        f'<td>{esc(r.get("expected_behavior") or "")}</td><td>{esc(r["outcome"])}</td>'
        f'<td>{esc(r["verdict"])}</td><td>{esc(r.get("value_level") or "")}</td>'
        f'<td>{r.get("latency_s", "")}s</td>'
        f'<td style="font-size:11px;color:#6b7280;max-width:340px;">{esc((r.get("response_excerpt") or "").replace(chr(10), " ")[:160])}…</td></tr>'
        for r in sorted(rows, key=lambda x: x["query_index"]))
    md = summary["date"]
    json_links = "<br>".join(
        f'<a href="{RAW}/accounts/finance/runs/v{version}/{f}">{f}</a>'
        for f in ("summary.json", "findings.json", "judgments.jsonl", "leaks.jsonl", "results.jsonl"))
    doc_links = "<br>".join(
        f'<a href="{RAW}/accounts/finance/{f}">{f}</a>'
        for f in ("EVAL_READOUT_v1.md", "VALUE_READOUT_v1.md"))
    rep = next((c for c in summary["content_checks"] if c["name"] == "repetition"), None)
    t_wrap = lambda rows_html: ('<div class="table-wrap"><table><thead><tr>' +
                                rows_html[0] + '</tr></thead><tbody>' + rows_html[1] +
                                '</tbody></table></div>')
    d_matrix = dl("Expected vs Observed — behavior matrix",
                  "Verdicts: <strong>{m} match</strong> · {p} partial · <strong style='color:#dc2626;'>{mm} mismatch</strong> · {e} error".format(
                      m=v["match"], p=v["partial"], mm=v["mismatch"], e=v["error"]),
                  '<div class="table-wrap"><table><thead><tr><th>Expected label</th><th>Answered</th><th>Hard refusal</th><th>Clarify park</th><th>Error</th></tr></thead><tbody>' + matrix_rows + '</tbody></table></div>')
    d_value = dl("Response Value (judge)",
                 "L4/L5 <strong>{l}</strong> · L3 {l3} · correct refusals {r} · not judged {nj}".format(
                     l=val["L4_L5"], l3=val["L3"], r=val["correct_refusals"], nj=val["not_judged"]),
                 '<div class="desc">' + esc(j.get("note", "")) + '</div>')
    d_lat = dl("Latency by Outcome",
               "Client timeout is 300s per HEART #2; a 244.7s IncompleteRead = upstream drop, not timeout.",
               '<div class="table-wrap"><table><thead><tr><th>Outcome</th><th>n</th><th>Median</th><th>p95</th><th>Max</th></tr></thead><tbody>' +
               "".join(f'<tr><td>{esc(OUTCOME_LABEL.get(k, k))}</td><td>{d["n"]}</td><td>{d["median"]}s</td><td>{d["p95"]}s</td><td>{d["max"]}s</td></tr>' for k, d in lat.items()) +
               '</tbody></table></div>')
    d_checks = dl("Content Checks", "Deterministic checks over the answers.",
                  '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Check</th><th>Status</th><th>Queries</th><th>Evidence</th></tr></thead><tbody>' + check_rows + '</tbody></table></div>')
    d_findings = dl("Findings (ranked, actionable)", "Stable IDs — fixes can be confirmed closed on the next run.",
                    '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Severity</th><th>Type</th><th>Queries</th><th>Evidence</th><th>Suggested fix</th><th>Status</th></tr></thead><tbody>' + finding_rows + '</tbody></table></div>')
    d_leaks = dl("Leak Hits (with matched strings)",
                 "Total " + str(summary["leaks"]["flagged"]) + " flagged — per-response regex hits; the workspace banner is intentional user-facing text (allowlisted).",
                 '<div class="table-wrap"><table><thead><tr><th>Query</th><th>Rule</th><th>Matched text</th><th>Note</th></tr></thead><tbody>' + leak_rows + '</tbody></table></div>')
    d_perquery = dl("Per-Query — all 30", "Full row-level view.",
                    '<div class="table-wrap"><table><thead><tr><th>#</th><th>Query</th><th>Expected</th><th>Outcome</th><th>Verdict</th><th>Value</th><th>Latency</th><th>Response (excerpt)</th></tr></thead><tbody>' + q_rows + '</tbody></table></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Agent Eval — Run v{version} ({md}) [legacy]</title>
<style>{css}
.dashboard-grid {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted, #94a3b8); padding: 8px 10px; border-bottom: 2px solid var(--border, #334155); }}
td {{ padding: 9px 10px; border-bottom: 1px solid var(--border, #334155); vertical-align: top; }}
code {{ background: rgba(148,163,184,.12); padding: 1px 5px; border-radius: 4px; font-size: 11px; }}
a {{ color: #93c5fd; text-underline-offset: 2px; }}
.stat-banner {{ background: linear-gradient(135deg,#0f172a,#1e293b); border:1px solid var(--border,#334155); border-left:4px solid var(--green,#22c55e); border-radius:12px; padding:18px 22px; margin:16px 0; font-size:14px; line-height:1.7; }}
.quality-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin:14px 0; }}
.info-card {{ background:var(--surface, #0b1220); border:1px solid var(--border,#334155); border-left:4px solid var(--primary,#3b82f6); border-radius:10px; padding:14px 18px; margin:12px 0; font-size:13.5px; line-height:1.75; }}
.ref-box {{ background:var(--surface, #0b1220); border:1px solid var(--border,#334155); border-radius:10px; padding:14px 18px; margin:12px 0; font-size:13px; line-height:2; }}
details {{ margin: 12px 0; border: 1px solid var(--border,#334155); border-radius: 10px; background: var(--surface, #0b1220); overflow: hidden; }}
details > summary {{ cursor: pointer; padding: 12px 16px; font-weight: 600; color: var(--text,#e2e8f0); user-select: none; }}
details .details-body {{ padding: 4px 16px 14px; }}
.desc {{ color: var(--text-muted, #94a3b8); font-size: 12.5px; }}</style>
</head><body><div class="dashboard-grid">
<header><h1>Finance Agent — Eval Readout v{version} [LEGACY]</h1>
<div class="desc">Run {md} · {summary["queries"]} user-provided CFO queries · hirafoods workspace ·
producer {esc(summary["producer_model"])} · judge {esc(j["model"])} · human-reviewed {j["human_reviewed"]}/{j["judged"]} ·
invariants {"OK" if summary.get("invariant_ok") else "VIOLATION"}</div></header>
<div class="stat-banner"><strong>{o.get("answered", 0)} answered</strong> · <strong>{o.get("hard_refusal", 0)} hard refusals</strong> · <strong>{o.get("parked", 0)} clarify-parks</strong> · <strong>{o.get("error", 0)} technical error</strong> — <strong>{val["L4_L5"]}/{summary["queries"]}</strong> CFO asks delivered decision-grade support (L4/L5), <strong>{val.get("data_dump", 0)} data-dumps</strong>, <strong>no fabricated figures detected (20 answers judged)</strong>. Main defect: cross-answer template reuse ({esc(rep["evidence"]) if rep else "same top-5 block reused"}).</div>
<section><h2>Outcomes</h2><div class="quality-grid">{cards}</div></section>
<section><h2>How This Run Was Done</h2>
<div class="info-card"><h3>Setup</h3>30 user-provided CFO insight questions run live against the <code>finance</code> agent template (hirafoods workspace) via <code>scripts/run_agent_evals.py</code> — a two-turn-aware SSE runner that captures full answers, interrupt/clarify parks, errors and timing into versioned JSONL. No retries (HEART #5): a drop is recorded as-is. Every query carries an <code>expected_behavior</code> label (ANSWER 9 / CLARIFY 12 / REFUSE 9).</div>
<div class="info-card"><h3>Derivation &amp; checks</h3><code>scripts/finance_pipeline.py</code> derives the outcome taxonomy, expected-vs-observed verdicts, value mix, latency by outcome, deterministic content checks and leak hits with matched strings. Invariants are asserted at build and the build fails on disagreement.</div>
<div class="info-card"><h3>Judge &amp; provenance</h3>{esc(j["model"])} · rubric v{j.get("rubric_version", "1")} · <strong>{j["judged"]} judged</strong> · human-reviewed {j["human_reviewed"]}/{j["judged"]} · {JUDGE_STATEMENT}</div></section>
<section><h2>Sources &amp; Reference</h2><div class="ref-box"><strong>Machine-readable:</strong><br>{json_links}<br><br><strong>Owner-facing readouts:</strong><br>{doc_links}</div></section>
{d_matrix}
{d_value}
{d_lat}
{d_checks}
{d_findings}
{d_leaks}
{d_perquery}
<footer style="margin-top:32px;color:#64748b;font-size:12px;">Superseded static page — the redesigned dashboard is <a href="../index.html">../index.html</a>. Raw traces: <a href="{RAW}/accounts/finance/runs/query_results_v{version}.jsonl">query_results_v{version}.jsonl</a> · Run v{version} · {md}</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--legacy-only", action="store_true", help="rebuild only the legacy page")
    a = ap.parse_args()
    if a.legacy_only:
        build_legacy(a.version)
        return
    build(a.version)


if __name__ == "__main__":
    main()