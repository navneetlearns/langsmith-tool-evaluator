#!/usr/bin/env python3
import json, sys
from pathlib import Path
sys.path.insert(0, "/home/sumit/AgentWork/eval-dashboard")
from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"]); auth.login()
client = CopilotClient(auth, cfg)
wid = cfg["workspace_id"]
for path in [f"/hub/copilot/api/agent-platform/templates?{wid}",
             f"/hub/copilot/api/agent-platform/templates?sellerWorkspaceId={wid}",
             f"/hub/copilot/api/agent-platform/agents?sellerWorkspaceId={wid}"]:
    st, resp = client._request("GET", path)
    print("====", path, "status", st)
    print(json.dumps(resp, ensure_ascii=False)[:2000])
    print()
