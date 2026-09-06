#!/usr/bin/env python3
import json, sys, uuid
from pathlib import Path
sys.path.insert(0, "/home/sumit/AgentWork/eval-dashboard")
from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"])
auth.login()
client = CopilotClient(auth, cfg)
tid = str(uuid.uuid4())
st, resp = client._request("POST", "/hub/copilot/threads/init",
                           {"thread_id": tid, "sellerWorkspaceId": cfg["workspace_id"]})
print("INIT status:", st)
print("INIT resp:", json.dumps(resp, ensure_ascii=False)[:800])
