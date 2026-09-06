#!/usr/bin/env python3
"""EVIDENCE 2: compare chatTemplateCode values on /threads/init (hirafoods workspace).
Proves which value yields 2xx and which yields 404/422."""
import sys, uuid, time
from pathlib import Path
sys.path.insert(0, "/home/sumit/AgentWork/eval-dashboard")
from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"]); auth.login()
client = CopilotClient(auth, cfg)

tests = {
    '"" (empty  -> loader mangles to {})': "",
    '"collection_and_account_receivables"': "collection_and_account_receivables",
    '"default"': "default",
}
for label, code in tests.items():
    st, body = client._request("POST", "/hub/copilot/threads/init", {
        "thread_id": str(uuid.uuid4()),
        "sellerWorkspaceId": cfg["workspace_id"],
        "chatTemplateCode": code,
    })
    snippet = (body[:80] if isinstance(body, str) else "")
    print(f"{label:42s} -> HTTP {st}  {snippet}")
    time.sleep(0.4)
