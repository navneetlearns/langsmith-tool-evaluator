#!/usr/bin/env python3
"""Ask My Groups (ask_chats) data-gate probe — READ-ONLY, pre-run.

Answers the go/no-go questions for an ask-groups eval run on a workspace BEFORE any set is
generated or any metered full run is spent, and establishes the LIVE tagged window for
re-anchoring (the corpus moves as nightly tagging extends covered_range):

  W1 WINDOW        — what does the agent itself disclose as the covered/tagged range?
  W2 TODAY         — is today (or the last working day) inside the tagged window?
  W3 LIVE-7D       — does the current 7-day band return traffic?
  W4 OLD-CONTROL   — a day inside the PREVIOUS run's band (expect it to have aged out or thinned)
  W5 TOPIC-WINDOW  — does a topic+day-band question filter correctly on live traffic?
  W6 REFUSE-HONESTY— does a known engine cap still refuse cleanly (ledger != chat messages)?

READ-ONLY: only /threads/init + /stream. Nothing is written or sent to any customer.
Output: accounts/<account>/runs/gate_probe_v1.jsonl (+ logs/<account>_gate_probe.log).
Safe to re-run (use --version N to keep the earlier probe).

Usage (from repo root): python3 scripts/probe_askgroups_gate.py --account hirafoods-askgroups
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

# (gate_tag, query) — gate_tag names the property the row tests.
PROBES = [
    ("W1-window-disclosure", "How much of my group traffic is covered or tagged right now?"),
    ("W2-today-anchored", "Aaj mere groups me kitne messages aaye?"),
    ("W3-live-7d-traffic", "How many messages were exchanged across my groups in the last 7 days?"),
    ("W4-old-band-control", "How many messages were exchanged in my groups on 24 September?"),
    ("W5-topic-window", "What was discussed about order dispatch yesterday?"),
    ("W6-refuse-honesty", "Show me the ledger balance for our top customers."),
    # v1 caught these two REFUSE classes DRIFTING (answered instead of refusing). Re-probe before
    # labelling them in a new set: "if intentional, move the label to ANSWER/NEAREST_SHAPE".
    ("W7-cap-photo_content", "How many photos were shared as proof of delivery this week?"),
    ("W8-cap-event_timing", "What time of day do most orders get placed?"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    ap.add_argument("--version", type=int, default=1)
    ap.add_argument("--only", default=None,
                    help="comma list of 1-based probe indices (subset e.g. --only 7,8)")
    args = ap.parse_args()

    probes = PROBES
    if args.only:
        want = {int(x) for x in args.only.split(",") if x.strip()}
        probes = [p for i, p in enumerate(PROBES, 1) if i in want]

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

    out.write_text("")
    ok = 0
    for i, (tag, q) in enumerate(probes, 1):
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
        say(f"[gate] {i}/{len(probes)} {rec['elapsed_s']:6.1f}s {tag:22} "
            f"err={str(rec['error'])[:40]} tools={tools}")
        say(f"        resp: {rec['response'][:600].replace(chr(10), ' ')}")
    say(f"[gate] WROTE {out} | ok={ok}/{len(probes)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
