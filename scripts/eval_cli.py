#!/usr/bin/env python3
"""eval — CLI for the finance (agent-template) eval derived artifacts.

The main consumer is a CLI agent (Claude Code-style) that reads results, picks
fixes and reruns — plus a terminal view for a human. Every command takes --json;
response text is truncated by default to save tokens.

    eval summary finance v1        # <=60 lines, read this first
    eval findings --open           # ranked, actionable
    eval show q21 [--full]         # one query: response, labels, judge, flags
    eval diff v1 v2                # per-query verdict changes, metric deltas
    eval rerun --failed            # creates v2; never overwrites (HEART #4/#5)
    eval gate --min-match 0.6      # nonzero exit code for CI

Uses the derived artifacts at accounts/<name>/runs/v<N>/ written by
finance_pipeline.py (single source of truth; invariants asserted at build).
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.resolve()


def load(account: str, version: str):
    version = version.lower().lstrip("v")  # accept "v1" or "1"
    d = SCRIPT_DIR / "accounts" / account / "runs" / f"v{version}"
    if not (d / "summary.json").exists():
        sys.exit(f"ERROR: no derived artifacts for {account} v{version} — "
                 f"run: python3 scripts/finance_pipeline.py --run {version} first")
    sys.path.insert(0, str(SCRIPT_DIR / "scripts"))
    from finance_pipeline import derive  # recompute from results.jsonl — can't drift
    summary, rows, findings, _ = derive(int(version))
    summary = json.loads((d / "summary.json").read_text())
    findings = json.loads((d / "findings.json").read_text()) if (d / "findings.json").exists() else []
    return summary, findings, rows, d


def qrow(rows, qid):
    qi = int(qid.lstrip("qQ"))
    for r in rows:
        if r.get("query_index") == qi:
            return r
    sys.exit(f"ERROR: query q{qi} not in run")


# ---------- summary ----------

def cmd_summary(args):
    summary, _, rows, _ = load(args.account, args.version)
    if args.json:
        safe = {k: v for k, v in summary.items() if k != "_rows"}
        print(json.dumps(safe, indent=1, ensure_ascii=False))
        return
    sys.path.insert(0, str(SCRIPT_DIR / "scripts"))
    from finance_pipeline import format_summary
    summary["_rows"] = rows
    print(format_summary(summary))


# ---------- findings ----------

def cmd_findings(args):
    _, findings, _, _ = load(args.account, args.version)
    if args.open:
        findings = [f for f in findings if f.get("status") == "open"]
    if args.json:
        print(json.dumps(findings, indent=1, ensure_ascii=False))
        return
    sev_order = {"high": 0, "medium": 1, "low": 2}
    for f in sorted(findings, key=lambda x: sev_order.get(x["severity"], 9)):
        qs = ",".join(map(str, f["queries"])) if f["queries"] else "-"
        print(f"{f['id']} [{f['severity']}] {f['type']} q{qs}")
        print(f"    {f['evidence']}")
        print(f"    fix: {f['suggested_fix']}")
        print()


# ---------- show ----------

def cmd_show(args):
    summary, _, rows, d = load(args.account, args.version)
    r = qrow(rows, args.query)
    jq = {}
    jf = d / "judgments.jsonl"
    if jf.exists():
        for l in jf.read_text().splitlines():
            j = json.loads(l)
            if j["query_index"] == r["query_index"]:
                jq = j
    if args.json:
        print(json.dumps({"run": r, "judgment": jq}, indent=1, ensure_ascii=False))
        return
    print(f"q{r['query_index']} · expected {r.get('expected_behavior')} · outcome {r.get('outcome')} · "
          f"verdict {r.get('verdict')} · {r.get('latency_s')}s")
    if r.get("value_level"):
        print(f"judge: {r['value_level']} {r.get('value_errors') or ''}  ({jq.get('judge_model','')})")
        if jq.get("note"):
            print(f"  note: {jq['note']}")
    if r.get("error"):
        print(f"error: {r['error']}")
    full_resp = next((json.loads(l).get("response", "") for l in
                      (d / "results.jsonl").read_text().splitlines()
                      if json.loads(l).get("query_index") == r["query_index"]), "")
    resp = full_resp or r.get("response_excerpt") or "(no response)"
    limit = None if args.full else 1200
    if limit and len(resp) > limit:
        resp = resp[:limit] + f"\n… [truncated {len(full_resp)-limit} chars — use --full]"
    print(f"\n{resp}")


# ---------- diff ----------

def cmd_diff(args):
    s1, _, r1, _ = load(args.account, args.v1)
    s2, _, r2, _ = load(args.account, args.v2)
    v1, v2 = {}, {}
    for r in r1:
        v1[r["query_index"]] = (r.get("outcome"), r.get("verdict"), r.get("value_level"))
    for r in r2:
        v2[r["query_index"]] = (r.get("outcome"), r.get("verdict"), r.get("value_level"))
    changed = {qi for qi in v1 if qi in v2 and v1[qi] != v2[qi]}
    if args.json:
        print(json.dumps({
            "run": [args.v1, args.v2],
            "query_count": len(v2), "changed": sorted(changed),
            "deltas": {
                "outcomes": {k: s2["outcomes"].get(k, 0) - s1["outcomes"].get(k, 0)
                             for k in ("answered", "hard_refusal", "parked", "error")},
                "verdicts": {k: s2["vs_expected"].get(k, 0) - s1["vs_expected"].get(k, 0)
                             for k in ("match", "partial", "mismatch", "error")},
                "L4_L5": s2["value"]["L4_L5"] - s1["value"]["L4_L5"],
                "median_latency": (s2["latency_by_outcome"].get("answered", {}).get("median")
                                   - s1["latency_by_outcome"].get("answered", {}).get("median")),
            },
        }, indent=1, ensure_ascii=False))
        return
    if v1 and not v2:
        print(f"ERROR: {args.v2} has no rows") if not v2 else None
    print(f"{args.v1} -> {args.v2}: {len(changed)} queries changed verdict/outcome")
    for qi in sorted(changed):
        print(f"  q{qi}: {v1[qi]} -> {v2[qi]}")
    o = s2["outcomes"]; o1 = s1["outcomes"]
    print(f"\noutcome deltas: answered {o1.get('answered',0)}->{o.get('answered',0)} · "
          f"hard_refusal {o1.get('hard_refusal',0)}->{o.get('hard_refusal',0)} · "
          f"parked {o1.get('parked',0)}->{o.get('parked',0)} · error {o1.get('error',0)}->{o.get('error',0)}")
    vv = s2["vs_expected"]; vv1 = s1["vs_expected"]
    print(f"verdict deltas: match {vv1['match']}->{vv['match']} · partial {vv1['partial']}->{vv['partial']} · "
          f"mismatch {vv1['mismatch']}->{vv['mismatch']}")
    print(f"value: L4/L5 {s1['value']['L4_L5']}->{s2['value']['L4_L5']}")


# ---------- rerun ----------

def cmd_rerun(args):
    summary, _, rows, _ = load(args.account, args.version)
    manifest = json.loads((SCRIPT_DIR / "accounts" / args.account / "runs" / "manifest.json").read_text())
    versions = sorted(v["version"] for v in manifest.get("runs", []))
    next_v = (versions[-1] + 1) if versions else 1
    if args.failed:
        # rerun candidates = verdict mismatches + technical errors (a fix could change these)
        failed_idx = sorted({str(r["query_index"]) for r in rows
                             if r.get("verdict") in ("mismatch", "error")})
        only = "--only " + ",".join(failed_idx)
        print(f"[eval] rerunning {len(failed_idx)} failed/mismatched queries as v{next_v}: "
              f"q{' '.join(failed_idx)}")
    else:
        only = ""
        print(f"[eval] rerunning full set as v{next_v}")
    cmd = [sys.executable, str(SCRIPT_DIR / "scripts" / "run_agent_evals.py"),
           "--account", args.account, "--run", str(next_v)] + (only.split() if only else [])
    print("$ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if r.returncode == 0:
        print(f"\n[eval] v{next_v} done — regenerate derived artifacts:")
        print(f"  python3 scripts/finance_pipeline.py --run {next_v}")
        print(f"  python3 build_dashboard.py --account {args.account}")
        print(f"  eval diff {args.version} v{next_v}")
    sys.exit(r.returncode)


# ---------- gate ----------

def cmd_gate(args):
    summary, _, _, _ = load(args.account, args.version)
    v = summary["vs_expected"]
    n = summary["queries"]
    err = v.get("error", 0)
    denom = n - err
    # pass rate = queries that matched expected behavior (match+partial over non-error)
    rate = (v.get("match", 0) + v.get("partial", 0)) / denom if denom else 1.0
    ok = rate >= args.min_match
    if args.json:
        print(json.dumps({
            "account": args.account, "run": args.version, "pass_rate": round(rate, 3),
            "min_match": args.min_match, "pass": ok, "denominator": denom,
            "match": v.get("match", 0), "partial": v.get("partial", 0), "error": err,
        }, indent=1))
    else:
        print(f"gate {args.account} {args.version}: {(rate*100):.1f}% match+partial "
              f"(min {args.min_match*100:.0f}%) → {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(prog="eval")
    ap.add_argument("--account", default="finance", help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def mk(name, **kw):
        p = sub.add_parser(name, **kw)
        p.add_argument("--json", action="store_true", help="machine-readable output")
        return p

    p = mk("summary")
    p.add_argument("account", nargs="?", default="finance")
    p.add_argument("version", nargs="?", default="v1")

    p = mk("findings")
    p.add_argument("--open", action="store_true", help="only open findings")
    p.add_argument("account", nargs="?", default="finance")
    p.add_argument("version", nargs="?", default="v1")

    p = mk("show")
    p.add_argument("query")
    p.add_argument("--full", action="store_true", help="show full response")
    p.add_argument("account", nargs="?", default="finance")
    p.add_argument("version", nargs="?", default="v1")

    p = mk("diff")
    p.add_argument("account", nargs="?", default="finance")
    p.add_argument("v1", nargs="?", default="v1")
    p.add_argument("v2", default="v2")

    p = mk("rerun")
    p.add_argument("--failed", action="store_true")
    p.add_argument("account", nargs="?", default="finance")
    p.add_argument("version", nargs="?", default="v1")

    p = mk("gate")
    p.add_argument("--min-match", type=float, default=0.6)
    p.add_argument("account", nargs="?", default="finance")
    p.add_argument("version", nargs="?", default="v1")

    args = ap.parse_args()
    args.account = getattr(args, "account", None) or args.account
    args.json = args.json or getattr(args, "json", False)
    {  # dispatch
        "summary": cmd_summary, "findings": cmd_findings, "show": cmd_show,
        "diff": cmd_diff, "rerun": cmd_rerun, "gate": cmd_gate,
    }[args.cmd](args)


if __name__ == "__main__":
    main()