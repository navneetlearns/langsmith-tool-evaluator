#!/usr/bin/env python3
"""Step-0.1 gate: enumerate deployed chat templates on a workspace (pipeline's own auth).

GET /hub/copilot/api/agent-platform/deployed-chat-templates?sellerWorkspaceId=<WS>
The ONLY listing endpoint that works (diag_templates.py /templates or /agents return empty/0).
Dumps the FULL system_prompt per template to /tmp/agent-discovery/<workspace__code>.txt —
prompt is the eval ground truth (tool allow-list, UNSUPPORTED section, response contract).

Usage (from repo root): python3 scripts/enumerate_templates.py <account_name>
"""
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from copilot_query_pipeline import load_account_config, CopilotAuth  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: enumerate_templates.py <account_name>")
        return 2
    cfg = load_account_config(sys.argv[1])
    ws = cfg["workspace_id"]
    auth = CopilotAuth(cfg["phone"], cfg["base_url"])
    if not auth.login():
        print("AUTH-FAIL")
        return 1

    out_dir = Path("/tmp/agent-discovery")
    out_dir.mkdir(parents=True, exist_ok=True)

    url = (f"{cfg['base_url']}/hub/copilot/api/agent-platform/"
           f"deployed-chat-templates?sellerWorkspaceId={ws}")
    import urllib.request
    req = urllib.request.Request(url, headers={
        "authorization": f"Bearer {auth.token}",
        "accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as e:
        print(f"ENUM-FAIL: {e}")
        return 1

    templates = payload.get("deployedChatTemplates") or []
    print(f"WORKSPACE: {ws}  ->  {len(templates)} deployed template(s)")
    for t in templates:
        code = t.get("code") or "(empty-code)"
        tid = t.get("id")
        sp = t.get("system_prompt") or ""
        p = out_dir / f"{ws}__{code.replace('/', '_')}.txt"
        p.write_text(sp)
        print(f"- code={code!r} id={tid} prompt_chars={len(sp)} -> {p}")
    ask = [t for t in templates if (t.get("code") or "").lower() == "ask_chats"]
    print("ASK_CHATS_PRESENT:", bool(ask))
    return 0 if ask else 1


if __name__ == "__main__":
    sys.exit(main())