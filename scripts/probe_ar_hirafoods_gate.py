#!/usr/bin/env python3
"""AR agent data-gate probe (Phase 1, READ-ONLY) — parameterized sibling of probe_ar_harvest.py.

Answers the go/no-go gates for an AR eval run on a workspace BEFORE any query set is generated
or any metered full run is spent:

  G2 LEDGER GATE  — does the ledger leg (receivables summary / invoices / balances) return rows?
  G3 SIGNAL GATE  — does the WhatsApp-signal leg (objects / activity / worklist) return rows?
  G4 IDENTITY     — how does a typed alias resolve vs the master customer name?
  (B2 boundary)   — does the invoice x WA-signal JOIN refuse-with-offer, as observed 2026-10-08?

READ-ONLY: only /threads/init + /stream are touched; nothing is written or sent to any customer.
Output: accounts/<account>/runs/gate_probe_v1.jsonl (incremental) + logs/<account>_gate_probe.log
Safe to re-run (appends a new file with a version suffix if v1 exists).

Usage (from repo root): python3 scripts/probe_ar_hirafoods_gate.py --account hirafoods-ar
"""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient  # noqa: E402

# (gate_tag, query) — gate_tag names the leg the row tests.
PROBES = [
    ("G2-ledger-summary", "total outstanding kitna hai?"),
    ("G2-ledger-invoices", "konsi invoices abhi pending hain?"),
    ("G3-wa-signal", "kis-kis ne bola paid, par system me abhi pending hai?"),
    ("G4-identity-alias", "Lakshmi Agencies ka outstanding kya hai?"),
    ("G4-identity-short", "Laxmi wale ka kya status hai?"),
    ("B2-join-boundary", "Show me overdue bills where the customer has already promised payment."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    ap.add_argument("--version", type=int, default=1)
    args = ap.parse_args()

    cfg = load_account_config(args.account)
    runs_dir = Path("accounts") / args.account / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    out = runs_dir / f"gate_probe_v{args.version}.jsonl"
    log = logs_dir / f"{args.account}_gate_probe.log"

    def say(msg: str):
        print(msg, flush=True)
        with open(log, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} | {msg}\n")

    say(f"[gate] account={args.account} ws={cfg['workspace_id']} lane={cfg.get('chatTemplateCode')}")
    auth = CopilotAuth(cfg["phone"], cfg["base_url"])
    if not auth.login():
        say("[gate] LOGIN FAILED")
        return 1
    client = CopilotClient(auth, cfg)

    out.write_text("")  # fresh v-file for this probe
    ok = 0
    for i, (tag, q) in enumerate(PROBES, 1):
        tid = str(uuid.uuid4())
        t0 = time.time()
        init_ok = client.init_thread(tid)
        if not init_ok:
            rec = {"probe_index": i, "gate": tag, "query": q, "init_ok": False,
                   "response": "", "tool_calls": [], "status_sequence": [],
                   "ui_payload_type": None, "error": "Thread init failed",
                   "elapsed_s": round(time.time() - t0, 1), "thread_id": tid}
        else:
            res = client.stream_query(tid, q)
            rec = {"probe_index": i, "gate": tag, "query": q, "init_ok": True,
                   "response": (res.get("response") or "").strip(),
                   "tool_calls": res.get("tool_calls", []),
                   "status_sequence": res.get("status_sequence", [])[:60],
                   "ui_payload_type": res.get("ui_payload_type"),
                   "suggestions": res.get("suggestions", []),
                   "error": res.get("error"),
                   "elapsed_s": round(time.time() - t0, 1), "thread_id": tid}
        with open(out, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if not rec["error"] and rec["response"]:
            ok += 1
        tools = [t.get("tool") for t in rec["tool_calls"]]
        say(f"[gate] {i}/{len(PROBES)} {rec['elapsed_s']:6.1f}s {tag:20} "
            f"err={str(rec['error'])[:50]} tools={tools}")
        say(f"        resp: {rec['response'][:400].replace(chr(10), ' ')}")
    say(f"[gate] WROTE {out} | ok={ok}/{len(PROBES)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
