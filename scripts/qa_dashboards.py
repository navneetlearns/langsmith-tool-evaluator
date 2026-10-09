#!/usr/bin/env python3
"""QA the rendered AR dashboards: real Chromium render + assertions against the run files.

Not a file-size check: it loads the page, exercises the tabs, counts rendered rows/tiles,
extracts rendered text and asserts the figures on the page match values present in the
run JSONL, checks for JS errors, horizontal overflow and blank rendering, and writes a
full-page screenshot per page for human inspection.

Usage: python3 scripts/qa_dashboards.py [port]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "langsmith-tool-evaluator/docs"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8891

PAGES = {
    "hirafoods-ar": {
        "rows": 32,
        "tiles": 6,
        "must_contain": ["₹57,77,21,622.19", "14,592", "₹36,255.75", "₹5,48,000",
                         "₹1,78,611.84", "Lakshmi Agencies & Co 84", "INV-4007"],
        "run": ROOT / "accounts/hirafoods-ar/runs/query_results_v2.jsonl",
    },
    "ar-agent": {
        "rows": 56,
        "tiles": 6,
        "must_contain": ["POPULAR MATTRESS", "₹10,749", "₹9,776", "Interworld"],
        "run": ROOT / "accounts/ar-agent/runs/query_results_v2.jsonl",
    },
}

results = {}
server = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                          cwd=str(DOCS), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for account, spec in PAGES.items():
            url = f"http://127.0.0.1:{PORT}/{account}/index.html"
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.goto(url, wait_until="load")
            page.wait_for_timeout(400)
            r = {"url": url, "js_errors": errs}
            r["title"] = page.title()
            r["tiles"] = page.locator(".grid .tile").count()
            r["tile_numbers"] = [t.strip() for t in page.locator(".tile-n").all_inner_texts()]
            r["cards_goes"] = page.locator(".card").count()
            r["explorer_rows"] = page.locator("#tbody tr").count()
            r["rowcount_label"] = page.locator("#rc").inner_text()
            r["scorecard_sum"] = sum(int(x) for x in r["tile_numbers"] if x.isdigit())
            r["has_empty_answer_blocks"] = page.locator(".empty").count()
            r["doc_scroll_w"] = page.evaluate("document.documentElement.scrollWidth")
            r["viewport_w"] = page.evaluate("window.innerWidth")
            r["h1"] = page.locator("h1").inner_text()

            ov = page.locator("#pane-ov").inner_text()
            missing = [m for m in spec["must_contain"] if m not in ov]
            r["missing_on_overview"] = missing

            # figures on the page must exist in the account's run artifacts (the eval run file,
            # plus the read-only gate probe when the page cites it)
            runs_dir = spec["run"].parent
            runtext = "\n".join(p.read_text() for p in sorted(runs_dir.glob("*.jsonl")))
            r["artifacts_searched"] = [p.name for p in sorted(runs_dir.glob("*.jsonl"))]
            r["figures_not_in_runfile"] = [m for m in spec["must_contain"]
                                          if m.startswith("₹") and m not in runtext]

            # tab switch works and the dev pane has content
            page.click('button[data-tab="dev"]')
            page.wait_for_timeout(250)
            r["dev_pane_visible"] = page.locator("#pane-dev").is_visible()
            r["dev_text_len"] = len(page.locator("#pane-dev").inner_text())
            r["dev_latency_rows"] = page.locator("#pane-dev table.tbl tbody tr").count()

            # filter interaction
            page.click('button[data-tab="ov"]')
            page.select_option("#f-out", "No answer")
            page.wait_for_timeout(200)
            r["filter_no_answer_label"] = page.locator("#rc").inner_text()

            shot = ROOT / f"qa/{account}.png"
            shot.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(shot), full_page=True)
            r["screenshot"] = str(shot)
            r["screenshot_bytes"] = shot.stat().st_size
            page.close()
            results[account] = r
        browser.close()
finally:
    server.terminate()

print(json.dumps(results, indent=1, ensure_ascii=False))

# ---- verdict ----
ok = True
for account, r in results.items():
    spec = PAGES[account]
    checks = [
        ("rows", r["explorer_rows"] == spec["rows"], f"{r['explorer_rows']} vs {spec['rows']}"),
        ("tiles", r["tiles"] == spec["tiles"], f"{r['tiles']} vs {spec['tiles']}"),
        ("scorecard sums to rows", r["scorecard_sum"] == spec["rows"],
         f"{r['scorecard_sum']} vs {spec['rows']}"),
        ("no JS errors", not r["js_errors"], str(r["js_errors"])[:200]),
        ("figures present", not r["missing_on_overview"], str(r["missing_on_overview"])),
        ("figures traceable to run file", not r["figures_not_in_runfile"], str(r["figures_not_in_runfile"])),
        ("no h-overflow", r["doc_scroll_w"] <= r["viewport_w"] + 4, f"{r['doc_scroll_w']} vs {r['viewport_w']}"),
        ("dev pane renders", r["dev_pane_visible"] and r["dev_text_len"] > 1500, str(r["dev_text_len"])),
        ("screenshot non-trivial", r["screenshot_bytes"] > 60000, str(r["screenshot_bytes"])),
    ]
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {account:14} {name:32} {detail}" if not passed
              else f"PASS  {account:14} {name:32} {detail}")
        ok = ok and passed
print("QA VERDICT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
