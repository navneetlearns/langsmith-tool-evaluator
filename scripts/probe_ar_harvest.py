#!/usr/bin/env python3
"""AR agent ERP-side harvest probe on Zainab (d53279c2) — Phase 1 Step 0.

Runs a small set of AR-agent queries to harvest the ERP/object side the ask-groups recon
cannot see: customer master (top outstanding), recent invoices, position/worklist (signal
objects = the Phase 3 data-presence gate), entity resolution of group aliases, the
WhatsApp-anchored invoice (B NO 15293), and payment-claims visibility.

Does NOT touch queries.xlsx or runs/ — output goes to accounts/ar-agent/harvest_results_v1.json
(pattern: probe_hirafoods_v4.py / probe_radha_collections.py). Safe to re-run.
"""
import json
import sys
import time
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient  # noqa: E402

OUT = SCRIPT_DIR / "accounts/ar-agent/harvest_results_v1.json"

PROBES = [
    "Show me the top 10 customers by outstanding balance.",
    "List the recent invoices from the last 30 days.",
    "Show me the outstanding position and the follow-up worklist.",
    "What is the outstanding balance of Casa Walls?",
    "What is the outstanding balance of Palette?",
    "Was invoice 15293 paid?",
    "What is the outstanding balance of Whistling Wood Enterprises?",
    "What is the outstanding balance of MOHANLAL COMPANY FURNISHINGS?",
]

cfg = load_account_config("ar-agent")
auth = CopilotAuth(cfg["phone"], cfg["base_url"])
client = CopilotClient(auth, cfg)

print("[harvest] logging in (auto-OTP)...")
token = auth.login()
if not token:
    print("[harvest] LOGIN FAILED")
    sys.exit(1)

results = []
for i, q in enumerate(PROBES, 1):
    thread_id = str(uuid.uuid4())
    t0 = time.time()
    try:
        res = client.stream_query(thread_id, q)  # does init + stream + parse
        res["query"] = q
        res["elapsed_s"] = round(time.time() - t0, 1)
        results.append(res)
        txt = (res.get("response") or "")[:160].replace("\n", " ")
        print(f"[harvest] {i}/{len(PROBES)} {time.time()-t0:.1f}s tools={res.get('tool_calls')} "
              f"err={res.get('error')} | {txt}")
    except Exception as e:  # noqa: BLE001
        print(f"[harvest] {i}/{len(PROBES)} EXC {time.time()-t0:.1f}s {e}")
        results.append({"query": q, "error": str(e), "elapsed_s": round(time.time() - t0, 1)})

OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False))
print(f"[harvest] WROTE {OUT} | ok={sum(1 for r in results if not r.get('error'))}/"
      f"{len(results)}")