#!/usr/bin/env python3
"""AR agent eval run analyzer — deterministic checks over accounts/ar-agent/runs/query_results_v<N>.jsonl.

Mirrors the finance pipeline's role for AR: bucket counts, behavior matrix, tool accuracy
(strict + lenient), format-compliance bans, hedge-pattern presence, latency by outcome,
tool-surface inventory, cross-answer repetition. Prints a <=70-line first-read block.

Usage: python3 scripts/analyze_ar_run.py [--run N] [--json]
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_dashboard as bd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "accounts/ar-agent/runs"

TOOLS_DECLARED = [
    "query_ar", "query_ar_financials", "get_ar_evidence", "resolve_ar_identity",
    "resolve_ar_customer", "get_receivables", "list_invoices", "ar_position",
    "ar_worklist", "ar_promises", "ar_payments_reported", "search_threads",
    "search_customers_master", "get_paid_collections", "get_ar_conversation_snapshot",
]
TOOL_BAN_RE = re.compile(
    r"\b(query_ar[a-z_]*|get_receivables|list_invoices|ar_position|ar_worklist|"
    r"ar_promises|ar_payments_reported|search_threads|search_customers_master|"
    r"resolve_ar_identity|resolve_ar_customer|get_ar_evidence|get_paid_collections|"
    r"run-[0-9a-f]+|thread_[0-9a-f]+)\b", re.I)
WORD_BAN_RE = re.compile(r"\b(stale|stale data|partial data|\bsql\b|\boffset\b|\bpage\s+\d)\b", re.I)
HEDGE_RE = re.compile(r"(not (yet )?(confirmed|received|matched|entered)|reported|"
                      r"not proof|may have changed|older list|dated read|doesn't cover|"
                      r"may not cover|not independently (confirmed|verified))", re.I)
PAISE_SUSPECT_RE = re.compile(r"₹\s*\d{6,}(?![\d,])")  # ₹ followed by >=6 digits without comma separators


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if s.strip()]


def analyze(run):
    recs = [json.loads(l) for l in (RUNS / f"query_results_v{run}.jsonl").read_text().splitlines()]
    n = len(recs)
    buckets = Counter()
    observed = {}
    tool_strict = tool_lenient = tool_predicted = 0
    format_hits = []
    hedge_ok = 0
    tools_used = Counter()
    latency_by = defaultdict(list)
    answers_text = []
    parks, errors = [], []

    for r in recs:
        idx = r.get("query_index")
        q = r.get("query", "")
        exp_b = r.get("expected_behavior", "?")
        exp_t = r.get("expected_tool", "?")
        resp = r.get("response", "") or ""
        tools = [t.get("tool") for t in (r.get("tool_calls") or [])]
        el = r.get("error")
        seq = r.get("status_sequence") or []
        secs = r.get("response_time_seconds") or 0

        b = bd.classify_quality(r)
        buckets[b] += 1
        for t in tools:
            tools_used[t] += 1

        # observed label
        if el:
            obs = "ERROR"
            errors.append(idx)
        elif b == "clarify":
            obs = "CLARIFY-PARK"
            parks.append(idx)
        elif b == "no_data":
            obs = "NO_DATA"
        elif b == "fail":
            obs = "FAIL"
            errors.append(idx)
        else:
            obs = "ANSWER" if b == "success" else "ANSWER-WEAK"
        observed[idx] = (exp_b, obs)

        # tool accuracy
        if exp_t and exp_t != "ASK_BACK" and exp_t != "NO_TOOL":
            tool_predicted += 1
            if tools and tools[0] == exp_t:
                tool_strict += 1
            if tools and any(re.match(r"^(query_ar|query_ar_financials|get_|resolve_|search_|list_|ar_|get_receivables)", t) for t in tools):
                tool_lenient += 1

        # format bans (only on non-empty answers)
        if resp:
            if TOOL_BAN_RE.search(resp):
                format_hits.append((idx, "tool-name", TOOL_BAN_RE.findall(resp)[:3]))
            if WORD_BAN_RE.search(resp):
                format_hits.append((idx, "banned-word", WORD_BAN_RE.findall(resp)[:3]))
            if PAISE_SUSPECT_RE.search(resp):
                format_hits.append((idx, "paise-suspect", PAISE_SUSPECT_RE.findall(resp)[:3]))
            if HEDGE_RE.search(resp):
                hedge_ok += 1
            if b in ("success", "marginal"):
                answers_text.append((idx, resp))

        latency_by[obs].append(secs)

    # Repetition: longest common prefix of first sentence across answers
    reps = []
    if len(answers_text) >= 3:
        heads = [sentences(r)[0].lower() if sentences(r) else "" for _, r in answers_text]
        from difflib import SequenceMatcher
        # pairwise longest matching block length of first sentences
        pairs = []
        for i in range(len(heads)):
            for j in range(i + 1, len(heads)):
                if heads[i] and heads[j]:
                    sm = SequenceMatcher(None, heads[i], heads[j])
                    m = sm.find_longest_match(0, len(heads[i]), 0, len(heads[j]))
                    pairs.append((m.size, answers_text[i][0], answers_text[j][0]))
        pairs.sort(reverse=True)
        reps = [(s, a, b2) for s, a, b2 in pairs[:4] if s > 20]

    def pct(x):
        return f"{100.0 * x / n:.0f}%" if n else "0%"

    print(f"AR RUN v{run} — {n} queries | buckets: " +
          " ".join(f"{k}={v} ({pct(v)})" for k, v in sorted(buckets.items())))
    print(f"parks(idx)={parks} | errors(idx)={errors}")
    print(f"tool accuracy (predicted={tool_predicted}): strict={tool_strict} ({pct(tool_strict) if tool_predicted else 0} of predicted) "
          f"lenient={tool_lenient} ({pct(tool_lenient) if tool_predicted else 0})")
    print("tool surface used:", dict(tools_used.most_common()))
    print("hedged answers (good):", hedge_ok, f"({pct(hedge_ok)} of answered)")
    print("format violations:", len(format_hits))
    for h in format_hits[:12]:
        print("   q%d %s: %s" % h)
    cont = Counter(latency_by)
    print("latency by outcome (avg s):", {k: round(sum(v) / len(v), 1) for k, v in latency_by.items()})
    print("latency total avg/P95:", round(sum(sum(v) for v in latency_by.values()) / max(n, 1), 1),
          round(sorted([r.get("response_time_seconds") or 0 for r in recs])[int(n * 0.95) - 1] if n else 0, 1))
    print("behavior matrix (expected>observed):")
    for (e, o), c in sorted(Counter(observed.values()).items()):
        print(f"   {e} > {o}: {c}")

    if "--json" in sys.argv:
        out = {
            "run": run, "n": n, "buckets": dict(buckets), "parks": parks, "errors": errors,
            "tool_accuracy": {"predicted": tool_predicted, "strict": tool_strict, "lenient": tool_lenient},
            "tool_surface": dict(tools_used), "hedged": hedge_ok,
            "format_violations": [list(h) for h in format_hits],
            "latency_by_outcome": {k: round(sum(v) / len(v), 1) for k, v in latency_by.items()},
            "behavior_matrix": {f"{e}>{o}": c for (e, o), c in sorted(Counter(observed.values()).items())},
        }
        print("JSON:", json.dumps(out))
    return recs


if __name__ == "__main__":
    run = None
    if "--run" in sys.argv:
        run = int(sys.argv[sys.argv.index("--run") + 1])
    if run is None:
        vs = sorted(p.stem.split("_v")[-1] for p in RUNS.glob("query_results_v*.jsonl") if p.stem.startswith("query_results_v"))
        run = int(vs[-1]) if vs else 1
    analyze(run)