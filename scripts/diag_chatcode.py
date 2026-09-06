#!/usr/bin/env python3
import json, sys, uuid
from pathlib import Path
sys.path.insert(0, "/home/sumit/AgentWork/eval-dashboard")
from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"]); auth.login()
client = CopilotClient(auth, cfg)
wid = cfg["workspace_id"]
tid = str(uuid.uuid4())

# Hypothesis A: maybe chatTemplateCode can be empty string or a known default
candidates = [
    "", "default", "copilot", "chat", "general",
    "tmpl-collect-leads", "tmpl-complaint-tracker",
]
for code in candidates:
    body = {"thread_id": tid, "sellerWorkspaceId": wid, "chatTemplateCode": code}
    st, resp = client._request("POST", "/hub/copilot/threads/init", body)
    print(f"code={code!r:24} -> {st}  {json.dumps(resp, ensure_ascii=False)[:160]}")
