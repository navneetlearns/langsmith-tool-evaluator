#!/usr/bin/env python3
"""Ask My Groups ENTITY-grounding probe — READ-ONLY, pre-v2-run.

The v2 set's new section is ENTITY-ANCHORED (v1 readout F1: real customers are now visible
in answers, so named-entity rows are authorable). Before labelling them, probe whether each
anchor type actually resolves in the LIVE tagged window (10 Aug - 8 Oct 2026):

  E1 customer-name     — does a named customer's group traffic answer?
  E2 chase-list        — do chasing/pending answers return real customer names?
  E3 invoice-anchor    — do invoice numbers quoted in groups resolve?
  E4 group-entity      — a group that IS the customer (Pragya/Laxmi/Durga wings)
  E5 payment-followup  — the AR-collections topic, entity list shape
  E6 sender-harvest    — who is actually talking (senders/staff)

READ-ONLY: only /threads/init + /stream. Nothing written or sent.
Output: accounts/<account>/runs/entity_probe_v1.jsonl

Usage (from repo root): python3 scripts/probe_askgroups_entities.py --account hirafoods-askgroups
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

PROBES = [
    ("E1-customer-name", "What did Laxmi Agency ask us for this week?"),
    ("E2-chase-list", "Which customers are chasing us for a reply right now?"),
    ("E3-invoice-anchor", "INV-4007 aur INV-4012 ke baare me pichle hafte kya bola gaya?"),
    ("E4-group-entity", "Pragya Traders ke saath pichle hafte kya hua?"),
    ("E5-payment-followup", "Payment follow-up pending kaun kaun hai?"),
    ("E6-sender-harvest", "Last 7 days me sabse zyada kisne messages kiye?"),
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
    logs_dir.mkdir(exist_ok=True)
    out = runs_dir / f"entity_probe_v{args.version}.jsonl"
    log = logs_dir / f"{args.account}_entity_probe.log"

    def say(msg: str):
        print(msg, flush=True)
        with open(log, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} | {msg}\n")

    say(f"[entity] account={args.account} ws={cfg['workspace_id']} lane={cfg.get('chatTemplateCode')}")
    auth = CopilotAuth(cfg["phone"], cfg["base_url"])
    if not auth.login():
        say("[entity] LOGIN FAILED")
        return 1
    client = CopilotClient(auth, cfg)

    out.write_text("")
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
        say(f"[entity] {i}/{len(PROBES)} {rec['elapsed_s']:6.1f}s {tag:22} "
            f"err={str(rec['error'])[:40]}")
        say(f"         resp: {rec['response'][:700].replace(chr(10), ' ')}")
    say(f"[entity] WROTE {out} | ok={ok}/{len(PROBES)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
