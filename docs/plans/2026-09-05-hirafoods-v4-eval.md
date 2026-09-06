# HiraFoods Eval v4 — Re-run Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-run the HiraFoods Copilot evaluation as version 4 (full 80-query set), capturing the *current* live SSE stream after the chat interface changed, and publish a refreshed dashboard.

**Architecture:** Reuse the existing `copilot_query_pipeline.py` + `build_dashboard.py` multi-account harness. The only uncertainty is whether the live SSE event set changed (user reports "chat interface changed, not as direct as earlier"). Task 1 therefore runs ONE live probe query and dumps the raw SSE so we can confirm the parser still captures `response`/`tool_calls` correctly — or patch it — BEFORE spending ~17 min on a full 80-query run. Output goes to `accounts/hirafoods/runs/query_results_v4.jsonl` (incremental append, resumable).

**Tech Stack:** Python 3.12 stdlib (urllib), openpyxl (Excel query loader), existing hand-rolled YAML config loader. No new deps.

**Current state (verified 2026-09-05):**
- Repo HEAD `2a1af21`; working tree had no `git status` output in prior check (clean).
- HiraFoods config: `accounts/hirafoods/config.yaml` (phone 4040505050, workspace `c331ac11-…`, wa_config_id derived).
- Last run v3 (2026-08-18): 79/80 OK, 1 fail (q74 SSE read timeout @591.9s), avg 13.17s, quality 51 success/15 marginal/13 no_data/1 fail.
- Parser events handled: `tool_start`, `message`, `token`, `ui`, `suggestions` (copilot_query_pipeline.py:407-431). Chat-style protocol also emits `connected/status/todo/done` (appended to `status_sequence`, not parsed for content).
- HiraFoods uses the **chat-style** protocol: tools run server-side, `tool_calls=[]` is FAITHFUL (never 0% due to a bug). Tool Selection Accuracy truthfully stays 0% until backend surfaces tool events.

---

### Task 1: Live single-query SSE probe (de-risk the "interface changed" signal)

**Files:**
- Create: `accounts/hirafoods/runs/probe_v4_raw.txt` (raw SSE dump)
- Create: `scripts/probe_hirafoods_v4.py`

This is the gate. Run ONE real query through the existing auth + stream path and dump every raw SSE line so we can see the actual current event vocabulary and response shape.

- [ ] **Step 1: Write the probe script**

```python
#!/usr/bin/env python3
"""One-shot live SSE probe for HiraFoods v4 — dumps RAW stream to inspect
current event vocabulary after the chat UI changed. Does NOT write JSONL."""
import json, time, uuid, urllib.request, urllib.error, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from copilot_query_pipeline import load_account_config, CopilotClient  # reuses auth+stream

cfg = load_account_config("hirafoods")
client = CopilotClient(cfg)
if not client.login():
    print("LOGIN FAILED"); sys.exit(1)
thread_id = str(uuid.uuid4())
assert client.init_thread(thread_id), "thread init failed"
# Use a benign real query from the set
query = "Show me the sales report for the last 30 days and summarize the key insights."
out = Path(__file__).resolve().parent.parent / "accounts/hirafoods/runs/probe_v4_raw.txt"
with open(out, "w") as f:
    f.write(f"# probe {time.time()} query={query!r}\n")
    # Re-run stream_query but tee raw lines: monkeypatch by calling low-level stream
    res = client.stream_query(thread_id, query)
    # stream_query doesn't expose raw; re-implement minimal raw dump:
    import copilot_query_pipeline as P
    url = f"{cfg['base_url']}/hub/copilot/stream"
    body = json.dumps({
        "thread_id": thread_id,
        "message": query,
        "sellerWorkspaceId": cfg["workspace_id"],
        "wa_config_id": cfg["wa_config_id"],
        "llm_provider": cfg.get("llm_provider", "gpt-5.4-mini"),
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"authorization": f"Bearer {client.token}",
                                          "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=cfg.get("sse_timeout", 300)) as resp:
        buf = ""
        while True:
            chunk = resp.read(4096)
            if not chunk: break
            buf += chunk.decode(errors="replace")
            while "\n\n" in buf:
                ev, buf = buf.split("\n\n", 1)
                f.write("----EVENT----\n" + ev + "\n")
                print("EVENT:", ev[:200].replace("\n", " "))
print("PARSED result keys:", list(res.keys()))
print("response_len:", len(res.get("response","")), "tool_calls:", res.get("tool_calls"),
      "status_sequence:", res.get("status_sequence"))
print("RAW dumped to", out)
```

- [ ] **Step 2: Run the probe**

Run: `cd /home/sumit/AgentWork/eval-dashboard && python3 scripts/probe_hirafoods_v4.py`
Expected: prints `EVENT: event: <type>` lines; final line shows `status_sequence` and `response_len`.

- [ ] **Step 3: Inspect `probe_v4_raw.txt` and decide**

Open `accounts/hirafoods/runs/probe_v4_raw.txt`. Confirm:
  - (a) Is `response` captured (non-empty, sensible)? If `response_len` ~0 but raw `token`/`message`/`ui` events exist → parser mismatch; go to Task 2.
  - (b) New event types present that the parser ignores? (e.g. `reasoning`, `artifact`, `card`, `tool_call` instead of `tool_start`). List them.
  - (c) Is the response now structured differently (e.g. arrives in a new `ui` sub-key, or as `data.summary` only)?

If (a)+(b)+(c) all match the old chat-style shape → SKIP Task 2, go to Task 3 (full run).
If anything changed → Task 2 patches the parser, THEN Task 3.

---

### Task 2: Patch SSE parser for new event vocabulary (ONLY if Task 1 shows a change)

**Files:**
- Modify: `copilot_query_pipeline.py:407-431` (the `if event_type == ...` block inside `stream_query`)
- Test: `scripts/probe_hirafoods_v4.py` (re-run after patch)

- [ ] **Step 1: Extend the event handler block**

In `stream_query`, replace the `if event_type == "tool_start":` … `elif event_type == "suggestions":` chain with one that also captures the new types observed in Task 1. Example safe extension (add these branches; keep existing ones):

```python
                            elif event_type in ("tool_call", "tool_exec"):
                                tool_name = (parsed.get("tool") or parsed.get("tool_name")
                                             or parsed.get("name") or parsed.get("function", {}).get("name", "?"))
                                tool_input = (parsed.get("input") or parsed.get("arguments")
                                              or parsed.get("parameters") or {})
                                result["tool_calls"].append({"tool": tool_name, "input": tool_input})

                            elif event_type in ("reasoning", "think"):
                                # optional: surface model reasoning; do not overwrite response
                                pass

                            elif event_type in ("artifact", "card", "result"):
                                extra = parsed.get("content") or parsed.get("data") or ""
                                if isinstance(extra, str):
                                    result["response"] += extra
```

NOTE: only add the branches for types you actually saw in `probe_v4_raw.txt`. Do not add speculative branches.

- [ ] **Step 2: Re-run probe**

Run: `python3 scripts/probe_hirafoods_v4.py`
Expected: `response_len` now non-zero AND matches the visible answer; `tool_calls` populated if the new protocol exposes them.

- [ ] **Step 3: Commit the parser fix**

```bash
git add copilot_query_pipeline.py
git commit -m "fix(hirafoods): extend SSE parser for changed chat interface event vocabulary"
```

---

### Task 3: Full v4 run (80 queries, incremental + resumable)

**Files:**
- Run: `python3 copilot_query_pipeline.py --account hirafoods --run 4` (background, notify_on_complete)
- Output: `accounts/hirafoods/runs/query_results_v4.jsonl` + updated `manifest.json`

- [ ] **Step 1: Kick off the run in background**

Run:
```bash
cd /home/sumit/AgentWork/eval-dashboard && \
python3 copilot_query_pipeline.py --account hirafoods --run 4
```
Run it backgrounded (notify_on_complete) — v3 took ~17 min. Do NOT use `--resume` for a fresh run.

- [ ] **Step 2: Mid-run sanity check (optional, after ~10 queries land)**

Run: `wc -l accounts/hirafoods/runs/query_results_v4.jsonl`
Expected: grows; each line is a complete JSON record.
Spot-check one: `head -1 accounts/hirafoods/runs/query_results_v4.jsonl | python3 -m json.tool` → confirm `response` non-empty and `error` null for early queries.

- [ ] **Step 3: Confirm completion**

Wait for notify. Then: `tail -3 accounts/hirafoods/runs/manifest.json` → new entry `version: 4` with `success`/`failed`/`total_queries`.

- [ ] **Step 4: Handle the known q74-style timeout if it recurs**

If v4 shows a single SSE read-timeout failure (like v3 q74), re-run just the missing query via resume:
```bash
python3 copilot_query_pipeline.py --account hirafoods --resume 4
```
Resume skips already-completed `query_index` values (incremental writes make this safe).

---

### Task 4: Quality classifier review (chat-style responses)

**Files:**
- Read: `copilot_query_pipeline.py` quality-classification function (search `no_data`)
- Read: `accounts/hirafoods/runs/query_results_v4.jsonl`

The v3 classifier buckets responses as success / marginal / no_data / fail via ~18 no-data text patterns. The "interface changed, not as direct" report suggests responses may now be more conversational/indirect → more `marginal`/`no_data` false-positives.

- [ ] **Step 1: Sample-classify 10 v4 responses manually**

Pull 10 records: `python3 -c "import json;[print(json.loads(l)['query_index'], json.loads(l).get('response','')[:160]) for i,l in enumerate(open('accounts/hirafoods/runs/query_results_v4.jsonl')) if i<10]"`
Judge by eye: does the bucket the dashboard will assign match reality?

- [ ] **Step 2: Tune patterns only if false positives found**

If indirect answers are being mis-bucketed as `no_data`, add the missed phrasings to the no-data indicator list in the classifier (read the function to find the exact list variable). Do NOT rewrite the classifier.

- [ ] **Step 3: Commit classifier tweak (if any)**

```bash
git add copilot_query_pipeline.py
git commit -m "eval: tune no_data classifier for indirect chat-style HiraFoods v4 responses"
```

---

### Task 5: Rebuild + deploy dashboard

**Files:**
- Run: `python3 build_dashboard.py --account hirafoods --version 4`
- Output: `langsmith-tool-evaluator/docs/hirafoods/index.html`

- [ ] **Step 1: Build v4 dashboard**

Run: `python3 build_dashboard.py --account hirafoods --version 4`
Expected: prints internal checks passed; `langsmith-tool-evaluator/docs/hirafoods/index.html` regenerated.

- [ ] **Step 2: Headless render check (reuse verify pattern)**

Run the existing Playwright verify approach (see `verify_hirafoods2.py` at `~/`): load the HTML, assert 80/80 stats render and zero console errors.
Expected: dashboard stats correct (success/failed/avg time), no JS console errors.

- [ ] **Step 3: Commit + push**

```bash
git add langsmith-tool-evaluator/docs/hirafoods/index.html accounts/hirafoods/runs/
git commit -m "eval: HiraFoods v4 dashboard (80q, re-run after chat UI change)"
git push
```

- [ ] **Step 4: Live verify**

`curl -sI https://navneetlearns.github.io/langsmith-tool-evaluator/hirafoods/` → expect `200`.
Open the URL, confirm title + v4 stats.

---

## Verification Checklist

After all tasks, verify:

1. `accounts/hirafoods/runs/query_results_v4.jsonl` has 80 lines (or 79 + 1 legitimately failed/retried).
2. `manifest.json` contains `version: 4` with correct `success`/`failed`/`total_queries`.
3. `response` field non-empty for ≥95% of records (chat-style capture working post-change).
4. `tool_calls` is `[]` for all → expected for chat-style HiraFoods; NOT a regression (confirmed protocol behavior).
5. Dashboard `langsmith-tool-evaluator/docs/hirafoods/index.html` builds with internal checks passing.
6. `curl -sI https://navneetlearns.github.io/langsmith-tool-evaluator/hirafoods/` returns `200`.
7. No JS console errors on the rendered dashboard (Playwright check).
8. README account table updated to "v4" with new success/fail/avg-time numbers.

## Notes / risks

- **Interface change is the only real unknown.** Task 1 is a hard gate — do not start Task 3 until the probe confirms capture works.
- Chat-style protocol = tools never surfaced → Tool Selection Accuracy remains 0% by design. Do not "fix" this by faking tool calls.
- q74-style single SSE timeout is recurrent, not systemic — resume handles it.
- Credentials: auth is auto-OTP via `CopilotClient.login()` (sendOtp→verifyOtp). If OTP is NOT echoed (QA flow) the probe script's `client.login()` must handle the verify step — confirm against `copilot_query_pipeline.py:210-241` before running.

---

## State Refresh (2026-09-05, during execution)

Task 1 (probe) ran LIVE and found the interface change is concrete and BREAKING — not cosmetic. Two defects fixed before the v4 run:

1. **`/hub/copilot/threads/init` now REQUIRES `chatTemplateCode`** (HTTP 422 "Field required" without it). Empty string is accepted. Fixed in `init_thread()` + added `chatTemplateCode: ""` to `accounts/hirafoods/config.yaml`.
2. **HiraFoods switched from chat-style to AGENTIC protocol** — tool calls now surface as `event: status` with `data.phase == "tool_start"`/`"tool_done"` (e.g. `get_sales` with full input), followed by `token` streaming. The old parser only read top-level `event: tool_start`, so `tool_calls` stayed `[]` (the "0% is faithful" assumption in the plan is now OBSOLETE for HiraFoods). Patched `stream_query` to extract tool calls from BOTH top-level `tool_start` AND nested `status.phase`.

   SECOND BUG INTRODUCED + FIXED during patching: my first edit nested the `message/token/ui/suggestions` branches INSIDE the `status` branch (wrong indentation), so token events never appended → `response` was empty (response_len 0) while tool_calls worked. Re-indented to a correct flat `if/elif` chain. Verified: a test query now yields `response_len 299` + `tool_calls: ['get_sales']`.

**Updated assumptions:**
- HiraFoods v4 will now show REAL tool-call data (get_sales etc.) — Tool Selection Accuracy becomes meaningful for the first time. Verify checklist item #4 (expecting `[]`) is NOW WRONG; v4 should show non-empty tool_calls.
- The "chat-style, tools server-side" note in Current State (line 16) is stale as of 2026-09-05.

**v4 run status:** launched `python3 copilot_query_pipeline.py --account hirafoods --run 4` in background (session proc_8f3e1c3127de, ~17 min ETA). Output → `accounts/hirafoods/runs/query_results_v4.jsonl`. Tasks 3–5 (run / classifier / dashboard) pending completion of this run.

**Flakiness noted:** `/threads/init` intermittently returns non-200 (~1 in 4) on first attempt even with chatTemplateCode — transient, retries succeed. Pipeline creates a fresh thread per query, so a transient init failure fails only that one query (resumable via `--resume 4`).
