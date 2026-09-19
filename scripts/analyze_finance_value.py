#!/usr/bin/env python3
"""Phase 1 deterministic value analysis for agent-template eval runs.

Measures, per record (and across records), the repetition / boilerplate /
info-density / value-signal structure of responses WITHOUT any LLM:
  - inner repetition: duplicate sentences inside one answer, figure restatement
  - cross-answer repetition: sentences that appear verbatim in >=2 answers,
    and the boilerplate share of each answer's chars
  - value signals: comparative anchors ("vs", "compared", "last month"...),
    action/decision language ("chase", "focus", "should", "priority"...),
    prioritization ("biggest", "top N", "first"...)
  - info density: distinct figures + signals per 100 chars
  - consistency ledger: every currency figure per answer, cross-checked
    against a known-figures set (drift = finding)

Usage: python3 scripts/analyze_finance_value.py [account] [runs_file]
Defaults: account=finance, latest runs/query_results_v*.jsonl (highest version).
Output: JSON to stdout (also written next to the runs dir).
"""
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

ACCOUNT = sys.argv[1] if len(sys.argv) > 1 else "finance"
RUNS_FILE = None
if len(sys.argv) > 2:
    RUNS_FILE = Path(sys.argv[2])

FIG_RE = re.compile(r"₹\s?[\d,]+(?:\.\d+)?|\b[\d,]+\.\d{2}\b")

COMPARATIVE_RE = re.compile(
    r"\b(vs\.?|compared?|compared with|last (month|quarter|period|year)|"
    r"previous|prior|since|than|higher|lower|increased|decreased|grew|rose|fell|"
    r"rising|falling|trend|change[d]?|month[- ]on[- ]month|yoy|year[- ]over[- ]year|"
    r"over the (last|past)|vs\.?)\b",
    re.IGNORECASE,
)

ACTION_RE = re.compile(
    r"\b(chase|focus|monitor|should|recommend|investigate|watch|flag|act|follow up|"
    r"collect|prioriti[sz]e|need to|worth|ask|review|check|call|visit|block)\b",
    re.IGNORECASE,
)

PRIORITY_RE = re.compile(
    r"\b(biggest|largest|most|top\s?\d|top|priority|primary|first|key|critical|"
    r"important|material|highest)\b",
    re.IGNORECASE,
)

# Known consistent figures from EVAL_READOUT_v1 (ground set for drift checks)
KNOWN_FIGURES = [
    "17,48,30,219",
    "1,549",
    "120.8",
    "33.8",
    "8,16,34,549",
    "24,17,71,682",
]


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 25]


def longest_common_prefix(strings):
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        i = 0
        while i < len(prefix) and i < len(s) and prefix[i] == s[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix


def common_prefix_len(a, b):
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


BOILER_RE = re.compile(r"payments are not fully reconciled", re.IGNORECASE)


def main():
    global RUNS_FILE
    if RUNS_FILE is None:
        runs_dir = REPO_ROOT / "accounts" / ACCOUNT / "runs"
        candidates = sorted(
            runs_dir.glob("query_results_v*.jsonl"),
            key=lambda p: [int(x) for x in re.findall(r"\d+", p.name)],
        )
        if not candidates:
            sys.exit(f"no runs found under {runs_dir}")
        RUNS_FILE = candidates[-1]

    records = [json.loads(l) for l in RUNS_FILE.open()]
    recs = [
        (i + 1, r.get("query", ""), r.get("response") or "", r.get("error"))
        for i, r in enumerate(records)
    ]

    # ---- cross-answer sentence census ----
    sent_counts = {}
    for _, _, resp, _ in recs:
        if not resp.strip():
            continue
        for s in sentences(resp):
            norm = re.sub(r"\s+", " ", s).lower()
            sent_counts[norm] = sent_counts.get(norm, 0) + 1
    repeated_sents = {k for k, v in sent_counts.items() if v >= 2}

    # boilerplate: common prefix among answers that OPEN with the reconcile
    # warning (hard refusals start differently and must not kill the prefix)
    answered = [resp for _, _, resp, _ in recs if resp.strip()]
    warn_group = [r for r in answered if BOILER_RE.search(r[:400])]
    boilerplate = longest_common_prefix(warn_group).strip() if warn_group else ""
    boilerplate = boilerplate[:1200]  # keep printouts sane

    # top repeated sentences across answers (template blocks)
    top_repeated = sorted(
        ((c, k) for k, c in sent_counts.items() if c >= 2),
        reverse=True,
    )[:10]

    # ---- per-record scoring ----
    results = []
    for idx, query, resp, err in recs:
        is_answer = bool(resp.strip())
        row = {
            "query_index": idx,
            "query": query,
            "answered": is_answer,
            "error": err,
            "response_len_chars": len(resp),
        }
        if not is_answer:
            seq = json.dumps(records[idx - 1].get("status_sequence", []))
            row.update(
                {
                    "verdict": "no_response",
                    "park_or_fail": "interrupt" if "interrupt" in seq else "error",
                }
            )
            results.append(row)
            continue

        sents = sentences(resp)
        norm_sents = [re.sub(r"\s+", " ", s).lower() for s in sents]

        # inner repetition: duplicate sentences within this answer
        seen = set()
        inner_dups = []
        for s in norm_sents:
            if s in seen and s not in inner_dups:
                inner_dups.append(s)
            seen.add(s)

        # cross-answer repetition: chars belonging to sentences seen elsewhere
        cross_repeated_chars = sum(
            len(sents[i]) for i, s in enumerate(norm_sents) if s in repeated_sents
        )

        # boilerplate share of this answer (prefix match against the group boilerplate)
        bp_share = (
            round(common_prefix_len(resp, boilerplate) / len(resp) * 100, 1)
            if boilerplate
            else 0.0
        )

        figs = FIG_RE.findall(resp)
        distinct_figs = len(set(figs))
        comparatives = COMPARATIVE_RE.findall(resp)
        actions = ACTION_RE.findall(resp)
        priorities = PRIORITY_RE.findall(resp)

        # info density: unique figures + signals per 100 chars
        signals = distinct_figs + len(comparatives) + len(actions) + len(priorities)
        density = round(signals / len(resp) * 100, 2)

        # heuristic verdict on value tier (deterministic only)
        if bp_share > 50:
            tier_hint = "L1/L2 (boilerplate-dominated)"
        elif distinct_figs >= 5 and len(comparatives) >= 3 and len(actions) >= 2:
            tier_hint = "L3+ (comparative + action signals present)"
        elif distinct_figs == 0 and len(actions) == 0 and not comparatives:
            tier_hint = "L1 (fetch/refusal, no value signals)"
        elif distinct_figs <= 2 and len(actions) <= 1:
            tier_hint = "L1/L2 (thin data, minimal interpretation)"
        else:
            tier_hint = "L2/L3 (mixed)"

        row.update(
            {
                "figure_mentions": len(figs),
                "distinct_figures": distinct_figs,
                "comparative_signals": len(comparatives),
                "action_signals": len(actions),
                "priority_signals": len(priorities),
                "info_density_per_100chars": density,
                "inner_dup_sentences": len(inner_dups),
                "cross_repeated_chars": cross_repeated_chars,
                "cross_repeat_pct": round(cross_repeated_chars / len(resp) * 100, 1),
                "boilerplate_pct": round(bp_share, 1),
                "tier_hint": tier_hint,
            }
        )
        results.append(row)

    # ---- consistency ledger: all figures per answered record ----
    ledger = {
        str(idx): sorted(set(FIG_RE.findall(resp)))
        for idx, _, resp, _ in recs
        if resp.strip()
    }

    # ---- aggregates ----
    answered_rows = [r for r in results if r["answered"]]
    n_answer = len(answered_rows)
    agg = {
        "records": len(recs),
        "answered": n_answer,
        "no_response": len(results) - n_answer,
        "avg_response_len": round(sum(r["response_len_chars"] for r in answered_rows) / n_answer, 0) if n_answer else 0,
        "answers_starting_with_boilerplate": sum(
            1 for r in answered_rows if r["boilerplate_pct"] >= 5
        ),
        "cross_repeat_gt_30pct": sum(1 for r in answered_rows if r["cross_repeat_pct"] > 30),
        "any_inner_duplicates": sum(1 for r in answered_rows if r["inner_dup_sentences"]),
        "avg_boilerplate_pct": round(
            sum(r["boilerplate_pct"] for r in answered_rows) / n_answer, 1
        ) if n_answer else 0,
        "avg_info_density": round(
            sum(r["info_density_per_100chars"] for r in answered_rows) / n_answer, 2
        ) if n_answer else 0,
        "tier_hint_counts": {},
        "boilerplate_prefix": boilerplate[:300],
    }
    for r in answered_rows:
        hint = r["tier_hint"]
        agg["tier_hint_counts"][hint] = agg["tier_hint_counts"].get(hint, 0) + 1

    out = {
        "account": ACCOUNT,
        "run_file": str(RUNS_FILE),
        "aggregates": agg,
        "top_repeated_sentences": top_repeated,
        "consistency_ledger": ledger,
        "known_figures": KNOWN_FIGURES,
        "per_record": results,
    }

    out_path = RUNS_FILE.parent / f"value_phase1_{RUNS_FILE.stem.replace('query_results_', '')}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"\n[written] {out_path}")


if __name__ == "__main__":
    main()