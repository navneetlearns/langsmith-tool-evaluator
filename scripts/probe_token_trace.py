#!/usr/bin/env python3
import sys, uuid, json
from pathlib import Path
sys.path.insert(0, "/home/sumit/AgentWork/eval-dashboard")
import copilot_query_pipeline as P
from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"]); auth.login()
client = CopilotClient(auth, cfg)
tid = str(uuid.uuid4()); client.init_thread(tid)

# Monkeypatch-free: replicate stream_query parse inline to trace
import urllib.request
token = auth.token
url = f"{cfg['base_url']}/hub/copilot/stream"
body = json.dumps({"thread_id":tid,"message":"Show me top 5 products by sales this month.",
                   "sellerWorkspaceId":cfg["workspace_id"],"wa_config_id":cfg["wa_config_id"],
                   "seller_details":cfg["seller_details"],"llm_provider":cfg.get("llm_provider")}).encode()
req = urllib.request.Request(url, data=body, headers={"authorization":f"Bearer {token}","Content-Type":"application/json"}, method="POST")
resp=""
with urllib.request.urlopen(req, timeout=300) as r:
    buf=""
    while True:
        c=r.read(4096)
        if not c: break
        buf+=c.decode(errors="replace")
        while "\n\n" in buf:
            ev,buf=buf.split("\n\n",1)
            et=""; ed=""
            for line in ev.split("\n"):
                if line.startswith("event: "): et=line[7:].strip()
                elif line.startswith("data: "): ed+=line[6:]
            if et=="token":
                try: p=json.loads(ed)
                except: p={}
                print("TOKEN content=",repr(p.get("content")), "token=",repr(p.get("token")))
print("DONE")
