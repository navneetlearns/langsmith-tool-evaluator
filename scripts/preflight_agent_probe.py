#!/usr/bin/env python3
"""One-query live gate before a full agent-template eval run (finance/ar/...).

Proves, using ONLY the pipeline's own loader/client/parser:
1. parse-count + labels truth via run_agent_evals.parse_xlsx (a naive openpyxl pass reads the
   header row as a query and misses the col-E expected_behavior labels)
2. quota alive (no 402 topup_required on the metered Zops provider)
3. /threads/init 200 with the account's configured chatTemplateCode
4. parser still reads the done frame: empty response + no error = parser regression after a
   backend/interface change (e.g. an answer-stats footer added to the done frame)

Streams the first REFUSE-class query when one exists (minimal quota burn). A REFUSE-labeled
query may still run the analysis branch (~30s) — fine, it still validates the wire.
Exit 0 = pass (start the run), 1 = fail (do NOT start), 2 = usage.

Usage (from the eval-dashboard repo root): python3 scripts/preflight_agent_probe.py <account>
"""
import sys, time, uuid
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("usage: preflight_agent_probe.py <account>")
        return 2
    account = sys.argv[1]
    repo = Path.cwd()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "scripts"))

    from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient
    import run_agent_evals

    queries = run_agent_evals.parse_xlsx(account)
    print(f"PARSE-COUNT: {len(queries)} queries (runner's own parser)")
    beh = {}
    for i, q in enumerate(queries, 1):
        beh.setdefault(q.get("expected_behavior", "?"), []).append(i)
    print("behavior summary:", {k: len(v) for k, v in beh.items()})

    probe_idx = next((i for i, q in enumerate(queries, 1)
                      if q.get("expected_behavior") == "REFUSE"), 1)
    pq = queries[probe_idx - 1]
    print(f"PROBE: q{probe_idx} (expected_behavior={pq.get('expected_behavior')!r})")

    cfg = load_account_config(account)
    print("chatTemplateCode:", repr(cfg.get("chatTemplateCode")),
          "| ws:", cfg.get("workspace_id"))
    auth = CopilotAuth(cfg["phone"], cfg["base_url"])
    auth.login()
    client = CopilotClient(auth, cfg)

    tid = str(uuid.uuid4())
    t0 = time.time()
    init_ok = client.init_thread(tid)
    print(f"INIT: ok={init_ok} ({time.time()-t0:.1f}s)")
    if not init_ok:
        print("GATE-FAIL: thread init failed (chatTemplateCode wrong/regressed?)")
        return 1

    res = client.stream_query(tid, pq["query"])
    resp = (res.get("response") or "").strip()
    err = res.get("error")
    print(f"STREAM: {res.get('response_time_seconds')}s err={err!r} "
          f"resp_chars={len(resp)} tools={res.get('tool_calls')}")
    if err:
        low = str(err).lower()
        if any(k in low for k in ("402", "topup", "quota", "usage limit")):
            print("GATE-FAIL: 402/quota — do NOT start the full run (top up Zops)")
        else:
            print(f"GATE-FAIL: stream error -> {err}")
        return 1
    if not resp:
        print("GATE-FAIL: empty response, no error -> parser/done-frame regression")
        return 1
    print("GATE-PASS: quota alive, init 200, parser reads the done frame")
    return 0


if __name__ == "__main__":
    sys.exit(main())
