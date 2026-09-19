#!/usr/bin/env python3
"""Derive the finance-agent eval summary from the raw run — single source of truth.

Reads  accounts/finance/runs/query_results_v{N}.jsonl  (+ value_phase2_judge.json,
value_phase1_v1.json when present) and writes the derived artifact set under
accounts/finance/runs/v{N}/:

    results.jsonl      raw traces (byte copy of the run)
    summary.json       derived — every count asserted against invariants
    findings.json      ranked, actionable findings (stable IDs, agent-consumable)
    judgments.jsonl    per-query judge rows + judge model / rubric / human_reviewed
    leaks.jsonl        per-hit leak rows: rule + matched string + context

Outcome taxonomy (mutually exclusive per query):
    answered   — non-empty response that is not a hard refusal
    hard_refusal — response begins "I can't answer ..."
    parked     — `interrupt` SSE event (clarify gate), empty response, no error
    error      — technical failure (error field set)

Verdict (expected_behavior from the query set vs observed outcome):
    match / partial / mismatch / error

Usage:
    python3 scripts/finance_pipeline.py            # latest run version
    python3 scripts/finance_pipeline.py --run 1    # specific version
    python3 scripts/finance_pipeline.py --print    # print the <=60-line summary block
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
ACCOUNT_DIR = SCRIPT_DIR / "accounts" / "finance"
RUNS_DIR = ACCOUNT_DIR / "runs"

JUDGE_FILE = RUNS_DIR / "value_phase2_judge.json"
PHASE1_FILE = RUNS_DIR / "value_phase1_v1.json"

# Known authoritative figures from the v1 run (used by content checks).
SALES_TOTAL = 24_17_71_682          # invoiced sales, stated across answers
OUTSTANDING_TOTAL = 17_48_30_219    # reconciled outstanding receivables
TOP5_BLOCK_MARKERS = [              # the recycled top-5 customer block
    "Ganesh Retail Traders", "Jai Wholesalers & Co", "Om Enterprises Traders",
    "Krishna Traders LLP", "Om Wholesalers & Co",
]

HEDGE_MARKERS = [
    "not tracked", "not reliably available", "cannot be determined", "not proven",
    "not available", "cannot be assessed", "can't answer", "no expense table",
    "not a complete", "not sufficient", "not present in the", "not yet proven",
    "cannot be calculated", "not tracked in your books", "cannot be quantified",
]

RULE_PATTERNS = {
    "workspace_ref": re.compile(r".{0,60}\bworkspace\b.{0,60}", re.I | re.S),
    "ui_component": re.compile(r".{0,60}\b(card|result preview|show more)\b.{0,60}", re.I | re.S),
    "tool_capability": re.compile(r".{0,60}\b(available tools|current tools|i have access to)\b.{0,60}", re.I | re.S),
}


def load_run(version):
    run_file = RUNS_DIR / f"query_results_v{version}.jsonl"
    if not run_file.exists():
        sys.exit(f"ERROR: {run_file} not found")
    records = [json.loads(l) for l in run_file.read_text().splitlines() if l.strip()]
    return run_file, records


def outcome_of(rec):
    if rec.get("error"):
        return "error"
    seq = rec.get("status_sequence") or []
    if rec.get("possible_clarify") or "interrupt" in seq:
        return "parked"
    resp = (rec.get("response") or "").strip()
    if not resp:
        return "parked"
    if resp.lower().startswith("i can't answer"):
        return "hard_refusal"
    return "answered"


def verdict_of(rec, outcome):
    exp = (rec.get("expected_behavior") or "ANSWER").upper()
    if outcome == "error":
        return "error", None
    if exp == "ANSWER":
        return ("match" if outcome == "answered" else "mismatch"), None
    if exp == "CLARIFY":
        return ("match" if outcome == "parked" else "mismatch"), None
    # REFUSE
    if outcome == "hard_refusal":
        return "match", None
    if outcome == "answered":
        resp = (rec.get("response") or "").lower()
        hedged = any(m in resp for m in HEDGE_MARKERS)
        if hedged:
            return "partial", "hedged refusal (boundary-named answer)"
        return "mismatch", "answered instead of refusing"
    return "mismatch", "parked instead of refusing"


def derive(version):
    run_file, records = load_run(version)
    judge = {}
    if JUDGE_FILE.exists():
        judge = json.loads(JUDGE_FILE.read_text()).get("records", {})
    phase1 = {}
    if PHASE1_FILE.exists():
        phase1 = json.loads(PHASE1_FILE.read_text())

    rows = []          # per-query derived rows
    outcomes = Counter()
    verdicts = Counter()
    mismatch_details = Counter()
    leaks = []
    for rec in records:
        qi = rec["query_index"]
        out = outcome_of(rec)
        outcomes[out] += 1
        verdict, vnote = verdict_of(rec, out)
        verdicts[verdict] += 1
        if verdict == "mismatch":
            exp = (rec.get("expected_behavior") or "ANSWER").upper()
            mismatch_details[f"{exp}\u2192{out}"] += 1
        jr = judge.get(str(qi), {})
        resp = rec.get("response") or ""
        for rule, pat in RULE_PATTERNS.items():
            m = pat.search(resp)
            if m:
                leaks.append({
                    "query_index": qi, "rule": rule,
                    "matched": m.group(0).strip(),
                    "context": f"q{qi} {'answered' if out == 'answered' else out}",
                    "note": "reconcile banner (intentional user-facing warning) \u2014 review allowlist",
                })
        rows.append({
            "query_index": qi,
            "query": rec.get("query", ""),
            "expected_behavior": (rec.get("expected_behavior") or "ANSWER").upper(),
            "outcome": out,
            "verdict": verdict,
            "verdict_note": vnote,
            "value_level": jr.get("level", ""),
            "value_errors": jr.get("errors", []),
            "value_note": (jr.get("note") or "")[:200],
            "latency_s": rec.get("response_time_seconds"),
            "error": rec.get("error"),
            "step_count": len(rec.get("status_sequence") or []),
            "response_len": len(resp),
            "response_excerpt": resp[:900],
        })

    # ---- invariants (design principle #1) ----
    n = len(records)
    inv = []
    if sum(outcomes.values()) == n:
        inv.append("outcomes sum == queries \u2713")
    else:
        inv.append(f"OUTCOMES SUM VIOLATION {sum(outcomes.values())} != {n}")
    if sum(verdicts.values()) == n:
        inv.append("verdicts sum == queries \u2713")
    else:
        inv.append(f"VERDICTS SUM VIOLATION {sum(verdicts.values())} != {n}")
    judged = sum(1 for r in rows if r["value_level"])
    if judged + outcomes["parked"] + outcomes["error"] == n:
        inv.append(f"judged + parked + error == queries \u2713 ({judged}+{outcomes['parked']}+{outcomes['error']}={n})")
    else:
        inv.append(f"JUDGE COUNT VIOLATION judged={judged} parked={outcomes['parked']} error={outcomes['error']} != {n}")
    exp_counter = Counter(r["expected_behavior"] for r in rows)
    if sum(exp_counter.values()) == n:
        inv.append("expected_behavior labels sum == queries \u2713")
    else:
        inv.append("EXPECTED LABELS VIOLATION")

    # ---- content checks (first-class metrics) ----
    checks = content_checks(rows, records)

    # ---- findings (ranked, actionable, stable IDs) ----
    findings = build_findings(checks, rows, judge)

    value_counts = Counter(r["value_level"] for r in rows if r["value_level"])
    lat = latency_by_outcome(rows)

    summary = {
        "account": "finance",
        "run": f"v{version}",
        "run_file": str(run_file.relative_to(SCRIPT_DIR)),
        "date": _run_date(run_file, version),
        "queries": n,
        "producer_model": "gpt-5.4-mini (classify gate + answer fm)",
        "judge": {
            "model": (json.loads(JUDGE_FILE.read_text()).get("judge", "in-session judge")
                      if JUDGE_FILE.exists() else "none"),
            "rubric_version": (json.loads(JUDGE_FILE.read_text()).get("rubric_version", "v1")
                               if JUDGE_FILE.exists() else None),
            "human_reviewed": 0,
            "judged": judged,
            "note": "L-levels are model self-consistency (judge same family as grader); "
                    "10-answer human calibration spot-check is the open item",
        },
        "outcomes": dict(outcomes),
        "vs_expected": {
            "match": verdicts.get("match", 0), "partial": verdicts.get("partial", 0),
            "mismatch": verdicts.get("mismatch", 0), "error": verdicts.get("error", 0),
            "mismatch_details": dict(mismatch_details),
        },
        "value": {
            "L4_L5": value_counts.get("L4", 0) + value_counts.get("L5", 0),
            "L3": value_counts.get("L3", 0),
            "correct_refusals": value_counts.get("REF", 0),
            "not_judged": n - judged,
            "errors": dict(Counter(e for r in rows for e in r["value_errors"])),
        },
        "latency_by_outcome": lat,
        "tools": {
            "tool_events": sum(1 for r in rows if False),  # finance streams no tool events
            "accuracy_pct": None,
            "reason": "no tool events in finance stream (backend SQL) \u2014 tool accuracy N/A; "
                      "step count is the SSE status depth, not agent steps",
        },
        "content_checks": checks,
        "leaks": {"flagged": len(leaks), "by_rule": dict(Counter(l["rule"] for l in leaks))},
        "invariants": inv,
        "invariant_ok": all("VIOLATION" not in i for i in inv),
        "row_count": len(rows),
    }
    return summary, rows, findings, leaks


# ============================================================
# CONTENT CHECKS
# ============================================================

def _amount(s):
    return int(s.replace(",", ""))


def content_checks(rows, records):
    by_q = {r["query_index"]: r for r in rows}
    resp_by_q = {r["query_index"]: (r.get("response") or "") for r in records}
    checks = []

    # 1) ratio_reconcile — "% of <total>" claims whose implied denominator
    #    contradicts the known sales total (FAIL q16: 50.3%/49.6% -> 32.2cr/48.3cr vs 24.18cr)
    ratio_cases = []
    for qi, resp in resp_by_q.items():
        if not resp:
            continue
        for m in re.finditer(r"\u20b9([\d,]+)[^.]{0,120}?representing ([\d.]+)%", resp):
            amt, pct = _amount(m.group(1)), float(m.group(2))
            if pct <= 0:
                continue
            implied = amt / (pct / 100)
            if implied > SALES_TOTAL * 1.15:
                ratio_cases.append((qi, amt, pct, implied))
    if ratio_cases:
        qs = sorted({c[0] for c in ratio_cases})
        ev = "; ".join(f"q{c[0]} \u20b9{c[1]:,} as {c[2]}% => implied {c[3]/1e7:.1f}cr vs sales {SALES_TOTAL/1e7:.2f}cr"
                       for c in ratio_cases[:3])
        checks.append({"id": "C-01", "name": "ratio_reconcile", "status": "FAIL",
                       "queries": qs, "evidence": ev,
                       "suggested_fix": "reconcile segment/product aggregation (likely double count); "
                                        "percentage denominators must match the sales total"})
    else:
        checks.append({"id": "C-01", "name": "ratio_reconcile", "status": "PASS", "queries": [],
                       "evidence": "no % claims imply a denominator > sales total", "suggested_fix": ""})

    # 2) topN_coverage — the top-5 block's share of the outstanding portfolio (WARN q9: 1.3%)
    top5_sum = 4_94_550 + 4_50_426 + 4_43_121 + 4_33_051 + 4_19_575
    cov_rows = []
    for qi, r in by_q.items():
        if r["outcome"] != "answered":
            continue
        if all(m in resp_by_q[qi] for m in TOP5_BLOCK_MARKERS) and "\u20b917,48,30,219" in resp_by_q[qi]:
            cov_rows.append(qi)
    if cov_rows:
        pct = top5_sum / OUTSTANDING_TOTAL * 100
        verdict = "WARN" if pct < 5 else "PASS"
        checks.append({"id": "C-02", "name": "topN_coverage", "status": verdict,
                       "queries": cov_rows,
                       "evidence": f"top-5 block \u20b9{top5_sum:,} = {pct:.1f}% of outstanding "
                                   f"\u20b9{OUTSTANDING_TOTAL:,} in q{','.join(map(str, cov_rows))}",
                       "suggested_fix": "when naming top accounts, quantify their share of the "
                                        "portfolio so the coverage limit is visible"})
    else:
        checks.append({"id": "C-02", "name": "topN_coverage", "status": "PASS", "queries": [],
                       "evidence": "no answer pairs the top-5 block with the outstanding total",
                       "suggested_fix": ""})

    # 3) cross_view — movement view contradicts the outstanding/ranking view (FAIL q21:
    #    Krishna Wholesalers 14.5L movement "largest" vs 4.9L ranking "largest")
    cross = []
    for qi, resp in resp_by_q.items():
        if not resp or "movement" not in resp:
            continue
        # amounts claimed in a movement-view sentence
        mv = [(_amount(m.group(1)), m.group(0)[:100])
              for m in re.finditer(r"in the movement view[^.\u20b9]{0,60}?\u20b9([\d,]+)", resp)]
        mv_amt = max((a for a, _ in mv), default=0)
        if not mv_amt:
            continue
        # ranking/outstanding "largest" claims (movement sentences masked out)
        masked = re.sub(r"in the movement view[^.]*\.", " ", resp)
        rank = [(_amount(m.group(1)), m.group(0)[:100])
                for m in re.finditer(r"largest [^.]{0,60}?\u20b9([\d,]+)", masked)]
        rank_amt = max((a for a, _ in rank), default=0)
        if rank_amt and mv_amt > rank_amt * 1.2:
            cross.append((qi, rank_amt, mv_amt))
    if cross:
        checks.append({"id": "C-03", "name": "cross_view", "status": "FAIL",
                       "queries": sorted({c[0] for c in cross}),
                       "evidence": "; ".join(f"q{c[0]} movement-view \u20b9{c[2]:,} > ranking "
                                             f"\"largest\" \u20b9{c[1]:,} (>1.2x)" for c in cross),
                       "suggested_fix": "label the view/source per figure (movement vs ranking vs "
                                        "outstanding) so contradictory 'largest' claims are impossible"})
    else:
        checks.append({"id": "C-03", "name": "cross_view", "status": "PASS", "queries": [],
                       "evidence": "no movement-view amount exceeds the ranking 'largest' claim",
                       "suggested_fix": ""})

    # 4) repetition — recycled top-5 block share of answered answers (WARN when > 50%)
    answered = [qi for qi, r in by_q.items() if r["outcome"] == "answered"]
    if answered:
        with_block = [qi for qi in answered if all(m in resp_by_q[qi] for m in TOP5_BLOCK_MARKERS)]
        share = len(with_block) / len(answered)
        status = "WARN" if share > 0.5 else "PASS"
        checks.append({"id": "C-04", "name": "repetition", "status": status,
                       "queries": with_block,
                       "evidence": f"top-5 block reused in {len(with_block)}/{len(answered)} "
                                   f"answered answers ({share:.0%})",
                       "suggested_fix": "per-intent evidence selection: same KPI trio + top-5 block "
                                        "must not be the 'insight' for 8 different questions"})
    else:
        checks.append({"id": "C-04", "name": "repetition", "status": "PASS", "queries": [],
                       "evidence": "no answered answers", "suggested_fix": ""})

    # 5) data_recency — cannot be auto-verified from the run (UNKNOWN by design)
    checks.append({"id": "C-05", "name": "data_recency", "status": "UNKNOWN", "queries": [],
                   "evidence": "answers cite latest-month drop 9.77cr\u219211.98L; max invoice date "
                               "not checked (no invoice-date column in the run) \u2014 manual "
                               "verification required",
                   "suggested_fix": "add invoice_date to the query set so recency is checkable"})

    # 6) hygiene — judge-flagged defects (deterministic counts across answers)
    days_days = [qi for qi, r in by_q.items() if "days days" in resp_by_q[qi]]
    if days_days:
        checks.append({"id": "C-06", "name": "unit_duplication", "status": "WARN",
                       "queries": days_days,
                       "evidence": f"'days days' in {len(days_days)} answers: q{','.join(map(str, days_days))}",
                       "suggested_fix": "deduplicate unit tokens in the format node"})
    unverified = [qi for qi, r in by_q.items() if "[unverified]" in resp_by_q[qi]]
    if unverified:
        checks.append({"id": "C-07", "name": "grounding_artifact", "status": "WARN",
                       "queries": unverified,
                       "evidence": f"literal '[unverified]' emitted in q{','.join(map(str, unverified))}",
                       "suggested_fix": "re-probe or drop the sentence; never emit the placeholder "
                                        "token to the user"})
    return checks


def build_findings(checks, rows, judge):
    """Ranked, actionable findings — stable IDs so an agent can fix and close them."""
    findings = []
    fid = 0
    sev = {"FAIL": "high", "WARN": "medium", "UNKNOWN": "low"}
    for c in checks:
        if c["status"] in ("FAIL", "WARN", "UNKNOWN"):
            fid += 1
            findings.append({
                "id": f"F-{fid:03d}",
                "severity": sev[c["status"]],
                "type": c["name"],
                "queries": c["queries"],
                "evidence": c["evidence"],
                "suggested_fix": c["suggested_fix"],
                "status": "open",
            })
    # judge-flagged craft defect: ".. I can work" double period on refusals
    craft_q = [qi for qi, r in ((r["query_index"], r) for r in rows)
               if "Craft" in r["value_errors"] and ".." in (r.get("response_excerpt") or "")
               if r["outcome"] in ("hard_refusal", "answered")]
    if craft_q:
        fid += 1
        findings.append({
            "id": f"F-{fid:03d}", "severity": "medium", "type": "refusal_craft",
            "queries": craft_q,
            "evidence": f"double-period '.. I can work' glitch in q{','.join(map(str, craft_q))}",
            "suggested_fix": "strip trailing period duplication in the refusal template",
            "status": "open",
        })
    # clarify-gate noise: answerable queries parked (cost, not just consistency)
    parked_answerable = [qi for qi, r in ((r["query_index"], r) for r in rows)
                         if r["outcome"] == "parked"
                         and r["expected_behavior"] in ("ANSWER", "REFUSE")]
    if len(parked_answerable) >= 3:
        fid += 1
        findings.append({
            "id": f"F-{fid:03d}", "severity": "high", "type": "clarify_gate_noise",
            "queries": parked_answerable,
            "evidence": f"{len(parked_answerable)} ANSWER/REFUSE-labeled queries parked by the "
                        f"clarify gate (q{','.join(map(str, parked_answerable))}) \u2014 q14 "
                        f"margin-pressure is provably answerable (see q2/q15)",
            "suggested_fix": "tighten the classify gate; multi-reading queries should split, "
                             "not park (gate is non-deterministic: q3 parked in-run, answered "
                             "on re-probe ~30% park rate on clarify-prone queries)",
            "status": "open",
        })
    # latency: analysis-heavy answers 35-245s, q20 dropped at 244.7s
    slow = [qi for qi, r in ((r["query_index"], r) for r in rows)
            if (r["latency_s"] or 0) > 120 and r["outcome"] in ("answered", "error")]
    if slow:
        fid += 1
        findings.append({
            "id": f"F-{fid:03d}", "severity": "medium", "type": "latency",
            "queries": slow,
            "evidence": f"answers >120s: q{','.join(map(str, slow))} (q20 dropped at 244.7s "
                        f"IncompleteRead)",
            "suggested_fix": "chunk the analysis branch or raise the read timeout; 300s client "
                             "timeout is the ceiling per HEART #2",
            "status": "open",
        })
    return findings


def latency_by_outcome(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["outcome"], []).append(r["latency_s"] or 0)
    out = {}
    for k, v in groups.items():
        v = sorted(v)
        n = len(v)
        med = (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2)
        out[k] = {"median": round(med, 1),
                  "p95": round(v[min(n - 1, int(n * 0.95))], 1),
                  "min": round(min(v), 1), "max": round(max(v), 1), "n": n}
    return out


def _run_date(run_file, version):
    mf = RUNS_DIR / "manifest.json"
    import datetime
    if mf.exists():
        for v in json.loads(mf.read_text()).get("runs", []):
            if v.get("version") == version and v.get("timestamp"):
                return v["timestamp"][:10]
    return datetime.date.today().isoformat()


# ============================================================
# SUMMARY BLOCK (<=60 lines, read this first)
# ============================================================

def format_summary(s):
    o = s["outcomes"]; v = s["vs_expected"]; val = s["value"]; j = s["judge"]
    lat = s["latency_by_outcome"]
    lines = []
    lines.append(f"finance {s['run']} · {s['date']} · {s['queries']} queries · producer {s['producer_model']} · judge {j['model'].split('(')[0].strip()} · human-reviewed {j['human_reviewed']}/{j['judged']}")
    ok = "\u2713" if s["invariant_ok"] else "\u2717"
    lines.append(f"OUTCOMES (sum={s['queries']} {ok})   answered {o.get('answered',0)} · hard_refusal {o.get('hard_refusal',0)} · parked {o.get('parked',0)} · error {o.get('error',0)}")
    lines.append(f"VS EXPECTED           match {v['match']} · partial {v['partial']} · mismatch {v['mismatch']} · error {v['error']}")
    for k, cnt in (v.get("mismatch_details") or {}).items():
        qs = [r["query_index"] for r in s.get("_rows", []) if f"{r['expected_behavior']}\u2192{r['outcome']}" == k]
        lines.append(f"  mismatches: {k} q{' '.join(map(str, qs))}")
    lines.append(f"VALUE (judge)         L4/L5 {val['L4_L5']} · L3 {val['L3']} · correct refusals {val['correct_refusals']} · not judged {val['not_judged']}")
    lt = lat.get("answered", {})
    lr = lat.get("hard_refusal", {}); lp = lat.get("parked", {}); le = lat.get("error", {})
    lines.append(f"LATENCY by outcome    answered median {lt.get('median','-')}s · parked {lp.get('median','-')}s · refusal {lr.get('median','-')}s · error {le.get('max','-')}s (client timeout 300s \u2192 upstream drop)")
    lines.append(f"TOOLS                 n/a ({s['tools']['reason']})")
    lines.append("CONTENT CHECKS")
    for c in s["content_checks"]:
        lines.append(f"  {c['name']:<18} {c['status']:<7} {c['evidence'][:110]}")
    lines.append(f"LEAKS                 {s['leaks']['flagged']} flagged — rules: " +
                 ", ".join(f"'{k}' x{v}" for k, v in s["leaks"]["by_rule"].items()) +
                 " \u2192 review allowlist (reconcile banner is intentional)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=None, help="run version (default: latest)")
    ap.add_argument("--print", action="store_true", help="print summary block to stdout")
    ap.add_argument("--json", action="store_true", help="dump summary.json to stdout")
    args = ap.parse_args()

    mf = json.loads((RUNS_DIR / "manifest.json").read_text())
    versions = sorted(v["version"] for v in mf.get("runs", []))
    version = args.run or (versions[-1] if versions else 1)

    summary, rows, findings, leaks = derive(version)
    outdir = RUNS_DIR / f"v{version}"
    outdir.mkdir(parents=True, exist_ok=True)

    raw = RUNS_DIR / f"query_results_v{version}.jsonl"
    (outdir / "results.jsonl").write_text(raw.read_text())

    summary["_rows"] = rows  # attached for the formatter; stripped before write
    if args.print or args.json:
        print(format_summary(summary))
    summary.pop("_rows", None)

    (outdir / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    (outdir / "findings.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False))
    (outdir / "judgments.jsonl").write_text(
        "\n".join(json.dumps({
            "query_index": r["query_index"], "query": r["query"],
            "level": r["value_level"], "errors": r["value_errors"], "note": r["value_note"],
            "judge_model": summary["judge"]["model"], "rubric_version": summary["judge"]["rubric_version"],
            "human_reviewed": summary["judge"]["human_reviewed"], "run": f"v{version}",
        }, ensure_ascii=False) for r in rows) + "\n")
    (outdir / "leaks.jsonl").write_text(
        "\n".join(json.dumps(l, ensure_ascii=False) for l in leaks) + "\n")

    print(f"[finance] v{version} derived artifacts -> {outdir}/")
    print(f"  outcomes={dict(summary['outcomes'])} verdicts={ {k: summary['vs_expected'][k] for k in ('match','partial','mismatch','error')} }")
    print(f"  invariants: {summary['invariant_ok']}")
    if not summary["invariant_ok"]:
        print("  " + "\n  ".join(i for i in summary["invariants"] if "VIOLATION" in i))
        sys.exit(1)
    return outdir


if __name__ == "__main__":
    main()