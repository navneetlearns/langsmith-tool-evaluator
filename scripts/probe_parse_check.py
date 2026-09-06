#!/usr/bin/env python3
"""Focused check: does stream_query() capture response tokens + tool_calls for ONE query?"""
import sys, uuid
from pathlib import Path
sys.path.insert(0, "/home/sumit/AgentWork/eval-dashboard")
from copilot_query_pipeline import load_account_config, CopilotAuth, CopilotClient

cfg = load_account_config("hirafoods")
auth = CopilotAuth(cfg["phone"], cfg["base_url"]); auth.login()
client = CopilotClient(auth, cfg)
tid = str(uuid.uuid4())
assert client.init_thread(tid), "init failed"
res = client.stream_query(tid, "Show me top 5 products by sales this month.")
print("response_len:", len(res.get("response", "")))
print("tool_calls:", res.get("tool_calls"))
print("response_head:", repr(res.get("response", "")[:200]))
print("error:", res.get("error"))
