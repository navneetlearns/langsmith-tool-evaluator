#!/usr/bin/env python3
"""HiraFoods v4 live SSE probe — dumps RAW stream to inspect current event
vocabulary after the chat UI changed. Reuses real auth + stream client.
Does NOT write JSONL. Safe to run repeatedly (1 query only)."""
import json, time, uuid, urllib.request, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"])
client = CopilotClient(auth, cfg)

print("[probe] logging in (auto-OTP)...")
token = auth.login()
if not token:
    print("[probe] LOGIN FAILED"); sys.exit(1)

thread_id = str(uuid.uuid4())
# FIX for interface change: threads/init now requires chatTemplateCode
init_st, init_resp = client._request("POST", "/hub/copilot/threads/init", {
    "thread_id": thread_id,
    "sellerWorkspaceId": cfg["workspace_id"],
    "chatTemplateCode": "",   # required post-change; empty accepted
})
print("[probe] thread init:", init_st, init_resp)
if init_st not in (200, 201):
    print("[probe] INIT FAILED"); sys.exit(1)

query = "Show me the sales report for the last 30 days and summarize the key insights."
out = SCRIPT_DIR / "accounts/hirafoods/runs/probe_v4_raw.txt"
with open(out, "w") as f:
    f.write(f"# probe {time.time()} query={query!r}\n")
    url = f"{cfg['base_url']}/hub/copilot/stream"
    body = json.dumps({
        "thread_id": thread_id,
        "message": query,
        "sellerWorkspaceId": cfg["workspace_id"],
        "wa_config_id": cfg["wa_config_id"],
        "seller_details": cfg["seller_details"],
        "llm_provider": cfg.get("llm_provider", "gpt-5.4-mini"),
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    event_types = []
    with urllib.request.urlopen(req, timeout=cfg.get("sse_timeout", 300)) as resp:
        buf = ""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk.decode(errors="replace")
            while "\n\n" in buf:
                ev, buf = buf.split("\n\n", 1)
                et = ""
                for line in ev.split("\n"):
                    if line.startswith("event: "):
                        et = line[7:].strip()
                event_types.append(et)
                f.write("----EVENT " + et + "----\n" + ev + "\n")
                print("EVENT:", et, "|", ev[:140].replace("\n", " "))
    print(f"[probe] stream done in {time.time()-t0:.1f}s")

# Also run the parser path on the SAME thread (cheap follow-up) to compare capture
res = client.stream_query(thread_id, "Confirm the total sales value you just reported.")
print("[probe] parser response_len:", len(res.get("response", "")),
      "| tool_calls:", res.get("tool_calls"),
      "| status_sequence:", res.get("status_sequence"))
print("[probe] RAW dumped to", out)
print("[probe] distinct event types seen:", sorted(set(event_types)))
