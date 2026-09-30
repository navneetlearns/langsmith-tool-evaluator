#!/usr/bin/env python3
"""Dump the raw ask_chats template payload from the deployed-chat-templates endpoint."""
import json, sys, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from copilot_query_pipeline import load_account_config, CopilotAuth  # noqa: E402

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"])
auth.login()
url = (f"{cfg['base_url']}/hub/copilot/api/agent-platform/"
       f"deployed-chat-templates?sellerWorkspaceId={cfg['workspace_id']}")
req = urllib.request.Request(url, headers={
    "authorization": f"Bearer {auth.token}", "accept": "application/json"})
payload = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
for t in payload.get("deployedChatTemplates", []):
    if t.get("code") == "ask_chats":
        print(json.dumps(t, indent=2, default=str)[:4000])
        break
else:
    print("ask_chats not found; codes:", [t.get("code") for t in payload.get("deployedChatTemplates", [])])