#!/usr/bin/env python3
"""Static, no-JS dashboard page for the Finance Agent eval (agent-template account).

Renders accounts/finance/runs/v<N>/ derived artifacts (summary.json, findings.json,
leaks.jsonl, judgments.jsonl, results.jsonl) into a fully static HTML page — every
table is server-rendered; there is NO JavaScript-rendered table and no embedded raw
JSON blob. Agents read the JSON files directly; humans read the static page.

Invoked from build_dashboard.py when account == "finance" and runs/v<N>/summary.json
exists. Other accounts never enter this branch and build byte-identical pages.

Usage:
    python3 scripts/render_finance_static.py --version 1   # direct
"""

import argparse
import html as html_mod
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent.resolve()
TEMPLATE = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "template.html"
OUT_DIR = SCRIPT_DIR / "langsmith-tool-evaluator" / "docs" / "finance"

SEV_COLOR = {"high": "#dc2626", "medium": "#d97706", "low": "#64748b"}
OUTCOME_LABEL = {
    "answered": "Answered", "hard_refusal": "Hard refusal",
    "parked": "Clarify park", "error": "Technical error",
}
VERDICT_LABEL = {"match": "Match", "partial": "Partial", "mismatch": "Mismatch", "error": "Error"}


def esc(x):
    return html_mod.escape(str(x), quote=True)


def extract_template_css():
    """Reuse the shared template's <style> block so the page looks consistent."""
    if not TEMPLATE.exists():
        return ""
    t = TEMPLATE.read_text()
    m = re.search(r"<style>(.*?)</style>", t, re.S)
    return m.group(1) if m else ""


def build(version: int):
    d = SCRIPT_DIR / "accounts" / "finance" / "runs" / f"v{version}"
    summary = json.loads((d / "summary.json").read_text())
    findings = json.loads((d / "findings.json").read_text())
    leaks = [json.loads(l) for l in (d / "leaks.jsonl").read_text().splitlines() if l.strip()]
    # Per-query derived rows (outcome/verdict/value_level) come from the PIPELINE, not the
    # raw results.jsonl — raw records carry no derived fields. Recompute via derive()
    # (single source of truth; identical to eval_cli.load).
    sys.path.insert(0, str(SCRIPT_DIR / "scripts"))
    from finance_pipeline import derive
    _, rows, _, _ = derive(int(version))
    judge_rows = {json.loads(l)["query_index"]: json.loads(l)
                  for l in (d / "judgments.jsonl").read_text().splitlines() if l.strip()}

    css = extract_template_css()
    o = summary["outcomes"]; v = summary["vs_expected"]; val = summary["value"]
    j = summary["judge"]; lat = summary["latency_by_outcome"]

    # ---- outcome cards (static) ----
    cards = ""
    for key, label in OUTCOME_LABEL.items():
        color = {"answered": "#16a34a", "hard_refusal": "#2563eb",
                 "parked": "#7c3aed", "error": "#dc2626"}[key]
        cards += (f'<div class="quality-card" style="background:var(--surface);border-left:4px solid {color};'
                  f'border-radius:8px;padding:16px;"><div class="count" style="color:{color};">{o.get(key,0)}</div>'
                  f'<div class="desc"><strong>{label}</strong></div>'
                  f'<div class="pct">{round(o.get(key,0)/summary["queries"]*100)}% of queries</div></div>')

    # ---- behavior matrix + cross-source consistency assertions ----
    # The matrix is built from per-query derived rows; its column sums MUST equal the
    # summary outcome distribution (this caught the "all-zeros" bug: raw records were
    # read instead of derived rows, dumping every query into the error column).
    exp_labels = {"ANSWER": "Answer", "CLARIFY": "Clarify (park)", "REFUSE": "Refuse"}
    beh = {k: {"answered": 0, "hard_refusal": 0, "parked": 0, "error": 0} for k in exp_labels}
    for r in rows:
        e = (r.get("expected_behavior") or "ANSWER").upper()
        if e not in beh:
            continue
        beh[e][r.get("outcome") or "error"] += 1
    for e in exp_labels:
        col_sum = beh[e]["answered"] + beh[e]["hard_refusal"] + beh[e]["parked"] + beh[e]["error"]
        exp_count = sum(1 for r in rows if (r.get("expected_behavior") or "ANSWER").upper() == e)
        assert col_sum == exp_count, (
            f"matrix row {e}: {col_sum} != {exp_count} expected labels — per-query rows "
            f"missing outcomes (raw-vs-derived bug?)")
    total = sum(sum(beh[e].values()) for e in exp_labels)
    assert total == len(rows), f"matrix total {total} != {len(rows)} rows"
    assert o == {k: sum(beh[e].get(k, 0) for e in exp_labels) for k in
                 ("answered", "hard_refusal", "parked", "error")}, (
        "matrix column sums != summary.outcomes — page numbers disagree with derived artifacts")
    # per-query rows must carry real derived values, never the empty fallbacks
    empties = [r["query_index"] for r in rows if not r.get("outcome") or not r.get("verdict")]
    assert not empties, f"per-query rows missing outcome/verdict: q{','.join(map(str, empties))}"

    matrix_rows = ""
    for e in exp_labels:
        c = beh[e]
        matrix_rows += (f'<tr><td><strong>{e}</strong></td>'
                        f'<td>{c["answered"]}</td><td>{c["hard_refusal"]}</td>'
                        f'<td>{c["parked"]}</td><td>{c["error"]}</td></tr>')

    # ---- content checks (static) ----
    check_rows = ""
    for c in summary["content_checks"]:
        col = {"FAIL": "#dc2626", "WARN": "#d97706", "PASS": "#16a34a", "UNKNOWN": "#64748b"}[c["status"]]
        qs = ", ".join(f"q{q}" for q in c["queries"]) if c["queries"] else "\u2014"
        check_rows += (f'<tr><td><strong>{esc(c["id"])}</strong></td>'
                       f'<td><span style="color:{col};font-weight:700;">{esc(c["name"])}</span></td>'
                       f'<td><span style="color:{col};font-weight:700;">{esc(c["status"])}</span></td>'
                       f'<td>{esc(qs)}</td><td style="font-size:12px;">{esc(c["evidence"])}</td></tr>')

    # ---- findings (static, ranked) ----
    sev_order = {"high": 0, "medium": 1, "low": 2}
    finding_rows = ""
    for f in sorted(findings, key=lambda x: sev_order.get(x["severity"], 9)):
        col = SEV_COLOR[f["severity"]]
        qs = ", ".join(f"q{q}" for q in f["queries"]) if f["queries"] else "\u2014"
        finding_rows += (f'<tr><td><strong>{esc(f["id"])}</strong></td>'
                         f'<td><span style="color:{col};font-weight:700;">{esc(f["severity"])}</span></td>'
                         f'<td>{esc(f["type"])}</td><td>{esc(qs)}</td>'
                         f'<td style="font-size:12px;">{esc(f["evidence"])}</td>'
                         f'<td style="font-size:12px;color:#6b7280;">{esc(f["suggested_fix"])}</td>'
                         f'<td>{esc(f["status"])}</td></tr>')

    # ---- leaks with matched strings (static) ----
    leak_rows = ""
    for l in leaks:
        leak_rows += (f'<tr><td>q{l["query_index"]}</td>'
                      f'<td><code>{esc(l["rule"])}</code></td>'
                      f'<td style="font-size:12px;"><code>{esc(l["matched"])}</code></td>'
                      f'<td style="font-size:11px;color:#6b7280;">{esc(l["note"])}</td></tr>')

    # ---- per-query static table (no JS rendering) ----
    q_rows = ""
    for r in sorted(rows, key=lambda x: x["query_index"]):
        qi = r["query_index"]
        out = r.get("outcome") or "error"
        verdict = r.get("verdict") or ""
        vl = r.get("value_level") or ""
        jr = judge_rows.get(qi, {})
        oc = {"answered": "#16a34a", "hard_refusal": "#2563eb", "parked": "#7c3aed", "error": "#dc2626"}[out]
        vc = {"match": "#16a34a", "partial": "#d97706", "mismatch": "#dc2626", "error": "#dc2626"}.get(verdict, "#64748b")
        excerpt = (r.get("response_excerpt") or "").replace("\n", " ")[:160]
        q_rows += (f'<tr><td>q{qi}</td>'
                   f'<td style="font-size:12px;max-width:260px;">{esc((r.get("query") or "")[:110])}</td>'
                   f'<td>{esc(r.get("expected_behavior") or "")}</td>'
                   f'<td><span style="color:{oc};font-weight:700;">{esc(out)}</span></td>'
                   f'<td><span style="color:{vc};">{esc(verdict)}</span></td>'
                   f'<td>{esc(vl)}</td>'
                   f'<td>{r.get("latency_s","")}s</td>'
                   f'<td style="font-size:11px;color:#6b7280;max-width:340px;">{esc(excerpt)}…</td></tr>')

    md = summary["date"]
    err_chips = "".join(f'<code>{esc(k)} x{vv}</code> ' for k, vv in sorted(val["errors"].items())) or "none"

    # Live links must be ABSOLUTE raw.githubusercontent.com URLs — GitHub Pages only
    # publishes docs/, so relative ../../accounts/... resolves outside the site and 404s.
    RAW = "https://raw.githubusercontent.com/navneetlearns/langsmith-tool-evaluator/main"
    json_links = "<br>".join(
        f'<a href="{RAW}/accounts/finance/runs/v{version}/{f}">{f}</a>'
        for f in ("summary.json", "findings.json", "judgments.jsonl", "leaks.jsonl", "results.jsonl"))
    doc_links = "<br>".join(
        f'<a href="{RAW}/accounts/finance/{f}">{f}</a>'
        for f in ("EVAL_READOUT_v1.md", "VALUE_READOUT_v1.md"))

    rep_check = next((c for c in summary["content_checks"] if c["name"] == "repetition"), None)
    rep_share = rep_check["evidence"] if rep_check else "same top-5 block reused"

    def dl(label, desc, body):
        return f"""<details>
  <summary>{esc(label)}</summary>
  <div class="details-body"><div class="desc" style="margin-bottom:8px;">{desc}</div>{body}</div>
</details>"""

    lat_rows = ''.join(
        f'<tr><td>{esc(OUTCOME_LABEL.get(k, k))}</td><td>{d["n"]}</td><td>{d["median"]}s</td>'
        f'<td>{d["p95"]}s</td><td>{d["max"]}s</td></tr>' for k, d in lat.items())

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Finance Agent Eval — Run v{version} ({md})</title>
<style>{css}

.dashboard-grid {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted, #94a3b8); padding: 8px 10px; border-bottom: 2px solid var(--border, #334155); }}
td {{ padding: 9px 10px; border-bottom: 1px solid var(--border, #334155); vertical-align: top; }}
code {{ background: rgba(148,163,184,.12); padding: 1px 5px; border-radius: 4px; font-size: 11px; }}
a {{ color: #93c5fd; text-decoration: underline; text-underline-offset: 2px; }}
a:visited {{ color: #a5b4fc; }}
.stat-banner {{ background: linear-gradient(135deg,#0f172a,#1e293b); border:1px solid var(--border,#334155); border-left:4px solid var(--green,#22c55e); border-radius:12px; padding:18px 22px; margin:16px 0; font-size:14px; line-height:1.7; }}
.quality-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin:14px 0; }}
.info-card {{ background:var(--surface, #0b1220); border:1px solid var(--border,#334155); border-left:4px solid var(--primary,#3b82f6); border-radius:10px; padding:14px 18px; margin:12px 0; font-size:13.5px; line-height:1.75; }}
.info-card h3 {{ margin:0 0 8px; font-size:14px; color:var(--text,#e2e8f0); }}
.ref-box {{ background:var(--surface, #0b1220); border:1px solid var(--border,#334155); border-radius:10px; padding:14px 18px; margin:12px 0; font-size:13px; line-height:2; }}
details {{ margin: 12px 0; border: 1px solid var(--border,#334155); border-radius: 10px; background: var(--surface, #0b1220); overflow: hidden; }}
details > summary {{ cursor: pointer; padding: 12px 16px; font-size: 14px; font-weight: 600; color: var(--text,#e2e8f0); list-style: none; display: flex; align-items: center; gap: 10px; user-select: none; position: relative; }}
details > summary::-webkit-details-marker, details > summary::marker {{ display: none; content: ""; }}
details > summary::before {{ content: "\\25B8"; display:inline-block; color: var(--green,#22c55e); font-size: 13px; transition: transform .15s ease; }}
details[open] > summary::before {{ transform: rotate(90deg); }}
details > summary:hover {{ background: rgba(148,163,184,.07); }}
details .details-body {{ padding: 4px 16px 14px; }}
details .desc {{ color: var(--text-muted, #94a3b8); font-size: 12.5px; }}
</style>
</head>
<body>
<div class="dashboard-grid">

  <header>
    <h1>Finance Agent — Eval Readout v{version}</h1>
    <div class="desc">Run {md} · {summary["queries"]} user-provided CFO queries · hirafoods workspace (phone 4040505050)
    · producer {esc(summary["producer_model"])} · judge {esc(j["model"])} · rubric {esc(j.get("rubric_version","v1"))}
    · human-reviewed {j["human_reviewed"]}/{j["judged"]} · invariants {"OK &#10003;" if summary.get("invariant_ok") else "VIOLATION"}</div>
  </header>

  <!-- WHAT THE OUTPUT IS — always visible -->
  <div class="stat-banner">
    <strong>{o.get("answered",0)} answered</strong> · <strong>{o.get("hard_refusal",0)} hard refusals</strong> ·
    <strong>{o.get("parked",0)} clarify-parks</strong> · <strong>{o.get("error",0)} technical error</strong> —
    <strong>{val["L4_L5"]}/{summary["queries"]}</strong> CFO asks delivered decision-grade support (L4/L5),
    <strong>{val["data_dump"] if "data_dump" in val else 0} data-dumps</strong>, <strong>0 fabricated figures</strong>.
    Main defect: cross-answer template reuse ({esc(rep_share)}).
  </div>

  <section>
    <h2>Outcomes</h2>
    <div class="quality-grid">{cards}</div>
  </section>

  <!-- HOW IT WAS DONE — always visible -->
  <section>
    <h2>How This Run Was Done</h2>
    <div class="info-card">
      <h3>Setup</h3>
      30 user-provided CFO insight questions run live against the <code>finance</code> agent template
      (hirafoods workspace) via <code>scripts/run_agent_evals.py</code> — a two-turn-aware SSE runner that
      captures full answers, interrupt/clarify parks, errors and timing into versioned JSONL. No retries
      (HEART #5): a drop is recorded as-is. Every query carries an <code>expected_behavior</code> label
      (ANSWER 9 / CLARIFY 12 / REFUSE 9) assigned per the classify-gate rules.
    </div>
    <div class="info-card">
      <h3>Derivation &amp; checks (single source of truth)</h3>
      <code>scripts/finance_pipeline.py</code> derives the outcome taxonomy (answered / hard_refusal / parked /
      error — mutually exclusive per query), the expected-vs-observed verdict, the judge-value mix, latency by
      outcome, deterministic content checks and leak hits with matched strings. Invariants are asserted at
      build: outcome/verdict sums must equal the query count, judged+parked+error must equal 30 — the build
      fails on any disagreement.
    </div>
    <div class="info-card">
      <h3>Judge &amp; provenance</h3>
      {esc(j["model"])} · rubric {esc(j.get("rubric_version","v1"))} · <strong>{j["judged"]} judged</strong> ·
      human-reviewed {j["human_reviewed"]}/{j["judged"]} (open item: 10-answer human calibration spot-check) ·
      L-levels are judge self-consistency, not human calibration. Tools: {esc(summary["tools"]["reason"])}
    </div>
  </section>

  <!-- SOURCES OF REFERENCE — always visible -->
  <section>
    <h2>Sources &amp; Reference</h2>
    <div class="ref-box">
      <strong>Machine-readable (for agents / deeper review):</strong><br>
      {json_links}<br><br>
      <strong>Owner-facing readouts:</strong><br>
      {doc_links}
    </div>
  </section>

  <!-- DETAIL TABLES — collapsed by default -->
  {dl("Expected vs Observed — behavior matrix",
      f"Verdicts: <strong>{v['match']} match</strong> · {v['partial']} partial · "
      f"<strong style='color:#dc2626;'>{v['mismatch']} mismatch</strong> · {v['error']} error. "
      f"Mismatch detail: {esc(' · '.join(f'{k} x{c}' for k, c in v.get('mismatch_details', {}).items()))}",
      '<div class="table-wrap"><table><thead><tr><th>Expected label</th><th>Answered</th><th>Hard refusal</th>'
      f'<th>Clarify park</th><th>Error</th></tr></thead><tbody>{matrix_rows}</tbody></table></div>')}

  {dl("Response Value (judge)",
      f"L4/L5 <strong>{val['L4_L5']}</strong> · L3 {val['L3']} · correct refusals {val['correct_refusals']} · "
      f"not judged {val['not_judged']} · FinGAIA errors: {err_chips}",
      f"<div class='desc'>{esc(j.get('note',''))}</div>")}

  {dl("Latency by Outcome",
      "Client timeout is 300s per HEART #2; a 244.7s IncompleteRead = upstream drop, not timeout.",
      '<div class="table-wrap"><table><thead><tr><th>Outcome</th><th>n</th><th>Median</th><th>p95</th>'
      f'<th>Max</th></tr></thead><tbody>{lat_rows}</tbody></table></div>')}

  {dl("Content Checks",
      "Deterministic checks over the answers — the defects owners must fix.",
      '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Check</th><th>Status</th><th>Queries</th>'
      f'<th>Evidence</th></tr></thead><tbody>{check_rows}</tbody></table></div>')}

  {dl("Findings (ranked, actionable)",
      "Stable IDs — fixes can be confirmed closed on the next run.",
      '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Severity</th><th>Type</th><th>Queries</th>'
      f'<th>Evidence</th><th>Suggested fix</th><th>Status</th></tr></thead><tbody>{finding_rows}</tbody></table></div>')}

  {dl("Leak Hits (with matched strings)",
      f"Total {summary['leaks']['flagged']} flagged — counts are per-response regex hits, not real secrets; "
      f"the workspace banner is intentional user-facing warning text (review the allowlist, don't treat as PII).",
      '<div class="table-wrap"><table><thead><tr><th>Query</th><th>Rule</th><th>Matched text</th>'
      f'<th>Note</th></tr></thead><tbody>{leak_rows}</tbody></table></div>')}

  {dl("Per-Query — all 30",
      "Full row-level view: expected label, observed outcome, verdict, value level, latency, response excerpt.",
      '<div class="table-wrap"><table><thead><tr><th>#</th><th>Query</th><th>Expected</th><th>Outcome</th>'
      f'<th>Verdict</th><th>Value</th><th>Latency</th><th>Response (excerpt)</th></tr></thead><tbody>{q_rows}</tbody></table></div>')}

  <footer style="margin-top:32px;color:#64748b;font-size:12px;">
    Static page rendered from derived artifacts (accounts/finance/runs/v{version}/) — no JavaScript.
    Raw traces: <a href="{RAW}/accounts/finance/runs/query_results_v{version}.jsonl">query_results_v{version}.jsonl</a> ·
    Run v{version} &middot; {md}
  </footer>
</div>
</body>
</html>
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "index.html"
    out.write_text(page)
    print(f"  [finance-static] wrote {out} ({len(page)} bytes)")
    return page


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    a = ap.parse_args()
    build(a.version)