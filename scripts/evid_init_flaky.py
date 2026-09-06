#!/usr/bin/env python3
"""EVIDENCE: is /hub/copilot/threads/init flaky?
Call it 20x with a VALID chatTemplateCode, log HTTP status per attempt.
Triggers auto-OTP login once (cached 20-min token)."""
import sys, uuid, time
from pathlib import Path
sys.path.insert(0, "/home/sumit/AgentWork/eval-dashboard")
from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"]); auth.login()
client = CopilotClient(auth, cfg)

N = 20
results = []
for i in range(N):
    tid = str(uuid.uuid4())
    st, _ = client._request("POST", "/hub/copilot/threads/init", {
        "thread_id": tid,
        "sellerWorkspaceId": cfg["workspace_id"],
        "chatTemplateCode": cfg["chatTemplateCode"],   # real "collection_and_account_receivables" (works on hirafoods too)
    })
    results.append(st)
    print(f"attempt {i+1:2d}: HTTP {st}")
    time.sleep(0.4)

ok = sum(1 for s in results if s in (200, 201))
print(f"\nTOTAL={N}  200/201={ok}  non-2xx={N-ok}")
print("flaky rate = {:.0%}".format((N-ok)/N))
