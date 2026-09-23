#!/usr/bin/env python3
"""AR harvest round 2 — WhatsApp-claims visibility + invoice-number harvest (Zainab).

Answers three design questions the round-1 harvest left open before the user-query set is
built: (a) can the AR agent pull WhatsApp-side payment claims at all? (b) are invoice numbers
retrievable in text for anchoring? (c) does the agent CHAIN chat claims + ERP (the core of the
user's "WhatsApp vs ERP" category)?
"""
import json
import sys
import time
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient  # noqa: E402

OUT = SCRIPT_DIR / "accounts/ar-agent/harvest_results_v2.json"

PROBES = [
    "List the newest 10 invoices with their invoice numbers and amounts, one per line.",
    "What have customers said about payments in our WhatsApp groups recently?",
    "Which customers have promised to pay from the group chats?",
    "Show me the payment claims from WhatsApp for Interworld Furnishings.",
    "Which payments were claimed on WhatsApp but are not in ERP?",
]

cfg = load_account_config("ar-agent")
auth = CopilotAuth(cfg["phone"], cfg["base_url"])
client = CopilotClient(auth, cfg)

print("[harvest2] logging in (auto-OTP)...")
if not auth.login():
    print("[harvest2] LOGIN FAILED")
    sys.exit(1)

results = []
for i, q in enumerate(PROBES, 1):
    t0 = time.time()
    try:
        res = client.stream_query(str(uuid.uuid4()), q)
        res["query"] = q
        res["elapsed_s"] = round(time.time() - t0, 1)
        results.append(res)
        tools = [t["tool"] for t in (res.get("tool_calls") or [])]
        txt = (res.get("response") or "")[:280].replace("\n", " | ")
        print(f"[harvest2] {i}/5 {time.time()-t0:.0f}s tools={tools} | {txt}")
    except Exception as e:  # noqa: BLE001
        print(f"[harvest2] {i}/5 EXC {e}")
        results.append({"query": q, "error": str(e), "elapsed_s": round(time.time() - t0, 1)})

OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False))
print(f"[harvest2] WROTE {OUT} | ok={sum(1 for r in results if not r.get('error'))}/{len(results)}")