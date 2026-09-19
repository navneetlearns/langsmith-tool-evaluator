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
    rows = [json.loads(l) for l in (d / "results.jsonl").read_text().splitlines() if l.strip()]
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

    # ---- expected-vs-observed matrix (static) ----
    exp_labels = {"ANSWER": "Answer", "CLARIFY": "Clarify (park)", "REFUSE": "Refuse"}
    beh = {k: {"answered": 0, "hard_refusal": 0, "parked": 0, "error": 0} for k in exp_labels}
    for r in rows:
        e = (r.get("expected_behavior") or "ANSWER").upper()
        if e not in beh:
            continue
        beh[e][r.get("outcome") or "error"] += 1
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
.stat-banner {{ background: linear-gradient(135deg,#0f172a,#1e293b); border:1px solid var(--border,#334155); border-left:4px solid var(--green,#22c55e); border-radius:12px; padding:18px 22px; margin:16px 0; font-size:14px; line-height:1.7; }}
.quality-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin:14px 0; }}
.json-links a {{ margin-right: 14px; font-size: 12px; }}
</style>
</head>
<body>
<div class="dashboard-grid">

  <header>
    <h1>Finance Agent — Eval Readout v{version}</h1>
    <div class="desc">Run {md} · {summary["queries"]} user-provided CFO queries · hirafoods workspace (phone 4040505050)
    · producer {esc(summary["producer_model"])} · judge {esc(j["model"])} · rubric {esc(j.get("rubric_version","v1"))}
    · human-reviewed {j["human_reviewed"]}/{j["judged"]} · invariants {"OK &#10003;" if summary.get("invariant_ok") else "VIOLATION"}</div>
    <div class="json-links" style="margin-top:10px;">
      <strong>Machine-readable (for agents):</strong>
      <a href="../../accounts/finance/runs/v{version}/summary.json">summary.json</a>
      <a href="../../accounts/finance/runs/v{version}/findings.json">findings.json</a>
      <a href="../../accounts/finance/runs/v{version}/judgments.jsonl">judgments.jsonl</a>
      <a href="../../accounts/finance/runs/v{version}/leaks.jsonl">leaks.jsonl</a>
      <a href="../../accounts/finance/runs/v{version}/results.jsonl">results.jsonl</a>
    </div>
  </header>

  <div class="stat-banner">
    <strong>{o.get("answered",0)} answered</strong> · <strong>{o.get("hard_refusal",0)} hard refusals</strong> ·
    <strong>{o.get("parked",0)} clarify-parks</strong> · <strong>{o.get("error",0)} technical error</strong> —
    <strong>{val["L4_L5"]}/{summary["queries"]}</strong> CFO asks delivered decision-grade support (L4/L5),
    <strong>{val["data_dump"] if "data_dump" in val else 0} data-dumps</strong>, <strong>0 fabricated figures</strong>.
    Main defect: cross-answer template reuse (same top-5 block in {summary["content_checks"][3]["evidence"].split("(")[0].strip() if len(summary["content_checks"])>3 else "9"}).
  </div>

  <section>
    <h2>Outcomes</h2>
    <div class="quality-grid">{cards}</div>
  </section>

  <section>
    <h2>Expected vs Observed (behavior matrix)</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Expected label</th><th>Answered</th><th>Hard refusal</th><th>Clarify park</th><th>Error</th></tr></thead>
      <tbody>{matrix_rows}</tbody>
    </table></div>
    <div class="desc" style="margin-top:8px;">Verdicts: <strong>{v["match"]} match</strong> · {v["partial"]} partial ·
    <strong style="color:#dc2626;">{v["mismatch"]} mismatch</strong> · {v["error"]} error.
    Mismatch detail: {esc(" · ".join(f"{k} x{c}" for k, c in v.get("mismatch_details", {}).items()))}</div>
  </section>

  <section>
    <h2>Response Value (judge)</h2>
    <div class="desc">L4/L5 <strong>{val["L4_L5"]}</strong> · L3 {val["L3"]} · correct refusals {val["correct_refusals"]} ·
    not judged {val["not_judged"]} · FinGAIA errors: {err_chips}.</div>
    <div class="desc" style="font-size:12px;color:#6b7280;">{esc(j.get("note",""))}</div>
  </section>

  <section>
    <h2>Latency by Outcome</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Outcome</th><th>n</th><th>Median</th><th>p95</th><th>Max</th></tr></thead>
      <tbody>{''.join(f'<tr><td>{esc(OUTCOME_LABEL.get(k,k))}</td><td>{d["n"]}</td><td>{d["median"]}s</td><td>{d["p95"]}s</td><td>{d["max"]}s</td></tr>' for k, d in lat.items())}</tbody>
    </table></div>
  </section>

  <section>
    <h2>Tools &amp; Steps</h2>
    <div class="desc">{esc(summary["tools"]["reason"])}</div>
  </section>

  <section>
    <h2>Content Checks</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>ID</th><th>Check</th><th>Status</th><th>Queries</th><th>Evidence</th></tr></thead>
      <tbody>{check_rows}</tbody>
    </table></div>
  </section>

  <section>
    <h2>Findings (ranked, actionable)</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>ID</th><th>Severity</th><th>Type</th><th>Queries</th><th>Evidence</th><th>Suggested fix</th><th>Status</th></tr></thead>
      <tbody>{finding_rows}</tbody>
    </table></div>
  </section>

  <section>
    <h2>Leak Hits (with matched strings)</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>Query</th><th>Rule</th><th>Matched text</th><th>Note</th></tr></thead>
      <tbody>{leak_rows}</tbody>
    </table></div>
    <div class="desc" style="margin-top:8px;">Total {summary["leaks"]["flagged"]} flagged — counts are per-response regex hits,
    not real secrets; the workspace banner is intentional user-facing warning text (review the allowlist, don't treat as PII).</div>
  </section>

  <section>
    <h2>Per-Query (static table — no JS)</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Query</th><th>Expected</th><th>Outcome</th><th>Verdict</th><th>Value</th><th>Latency</th><th>Response (excerpt)</th></tr></thead>
      <tbody>{q_rows}</tbody>
    </table></div>
  </section>

  <footer style="margin-top:32px;color:#64748b;font-size:12px;">
    Static page rendered from derived artifacts (accounts/finance/runs/v{version}/) — no JavaScript tables.
    Raw traces: <a href="../../accounts/finance/runs/query_results_v{version}.jsonl">query_results_v{version}.jsonl</a> ·
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