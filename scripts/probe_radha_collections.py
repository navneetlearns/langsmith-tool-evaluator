#!/usr/bin/env python3
"""Collections/AR v2 probe — 1-query live SSE probe of the Radha Agencies
customer to confirm (a) thread init OK with collection_and_account_receivables,
(b) 'Radha Agencies Pvt Ltd 787' RESOLVES (agent calls search_customers_master
+ intended data tool) instead of dead-ending at 'customer not found'.

Modeled on scripts/probe_hirafoods_v4.py. Uses real auth + stream client.
Does NOT write JSONL. Safe to repeat.
"""
import json, time, uuid, urllib.request, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("collections")
auth = CopilotAuth(cfg["phone"], cfg["base_url"])
client = CopilotClient(auth, cfg)

print("[probe] logging in (auto-OTP)...")
token = auth.login()
if not token:
    print("[probe] LOGIN FAILED"); sys.exit(1)

thread_id = str(uuid.uuid4())
init_st, init_resp = client._request("POST", "/hub/copilot/threads/init", {
    "thread_id": thread_id,
    "sellerWorkspaceId": cfg["workspace_id"],
    "chatTemplateCode": cfg["chatTemplateCode"],
})
print("[probe] thread init:", init_st, init_resp)
if init_st not in (200, 201):
    print("[probe] INIT FAILED"); sys.exit(1)
print("[probe] init OK — auth + thread_init path works")

query = "Show me all outstanding invoices for Radha Agencies Pvt Ltd 787."
out = SCRIPT_DIR / "accounts/collections/runs/probe_radha_v2.txt"
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
                print("EVENT:", et, "|", ev[:160].replace("\n", " "))
    print(f"[probe] stream done in {time.time()-t0:.1f}s")

# Parser path on same thread — see what the pipeline would capture
res = client.stream_query(thread_id, "Confirm which tools you called and what you found for Radha Agencies.")
print("[probe] parser response_len:", len(res.get("response", "")),
      "| tool_calls:", res.get("tool_calls"),
      "| status_sequence:", res.get("status_sequence"))
print("[probe] RAW dumped to", out)
print("[probe] distinct event types seen:", sorted(set(event_types)))
