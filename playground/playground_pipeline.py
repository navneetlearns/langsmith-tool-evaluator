#!/usr/bin/env python3
"""
Playground Eval — Non-Streaming REST Pipeline for ZoTok WhatsApp Bot Testing.

Hits POST /hub/bot/api/v1/chat/preview with declarative JSON scenarios,
logs versioned results, and feeds the dashboard builder.

Usage:
    python3 playground_pipeline.py                    # All scenarios
    python3 playground_pipeline.py --scenario mybot.json
    python3 playground_pipeline.py --workspace <ws-id>
    python3 playground_pipeline.py --no-chat-persistence
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── constants ────────────────────────────────────────────────────────
BASE_URL = "https://api-qa.zotok.ai"
ENDPOINT = "/hub/bot/api/v1/chat/preview"
DEFAULT_TIMEOUT = 30  # seconds

RUNS_DIR = Path(__file__).parent / "runs"
SCENARIOS_DIR = Path(__file__).parent / "scenarios"
DOCS_DIR = Path(__file__).parent / "docs"

QUALITY_FALLBACK_PHRASES = [
    "sorry", "couldn't", "something went wrong", "unable to", "went wrong"
]

# ── helpers ───────────────────────────────────────────────────────────


def extract_response_info(response_json: dict) -> dict:
    """Parse the /chat/preview response into a flat info dict."""
    messages = response_json.get("messages") or []
    response_type = "empty"
    response_text = ""
    menu_options = []

    for msg in messages:
        msg_type = msg.get("type", "")
        if msg_type == "text":
            response_type = "text"
            response_text = msg.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            response_type = "interactive"
            template = msg.get("template", {})
            body = template.get("body", {})
            response_text = body.get("text", "")
            action = template.get("action", {})
            for section in action.get("sections", []):
                for row in section.get("rows", []):
                    menu_options.append({
                        "title": row.get("title", ""),
                        "description": row.get("description", ""),
                    })
        elif msg_type == "cta_url":
            response_type = "cta_url"
            response_text = msg.get("text", {}).get("body", "")
        elif msg_type == "document":
            # document messages — keep text if available
            response_type = "document"
            response_text = msg.get("text", {}).get("body", "")
        else:
            # unknown type — try text body anyway
            response_text = msg.get("text", {}).get("body", response_text)

    agent_meta = response_json.get("agentMetadata") or {}
    tools_used = agent_meta.get("tools_used") or []
    knowledge_files = agent_meta.get("knowledge_files_referenced") or []

    return {
        "response_type": response_type,
        "response_text": response_text,
        "menu_options": menu_options,
        "tools_used": tools_used,
        "knowledge_files": knowledge_files,
    }


def classify_quality(response_text: str, error: str | None) -> str:
    """Classify response into success / marginal / fail."""
    if error:
        return "fail"
    text = response_text.lower().strip()
    if not text:
        return "fail"
    for phrase in QUALITY_FALLBACK_PHRASES:
        if phrase in text:
            return "marginal"
    return "success"


def check_expectations(info: dict, expected: dict) -> tuple[bool, str]:
    """Return (passed, reason) for a test case's expectation checks."""
    if not expected:
        return True, ""

    # response_type exact match
    if "response_type" in expected:
        got = info["response_type"]
        want = expected["response_type"]
        if got != want:
            return False, f"expected response_type={want!r}, got {got!r}"

    # contains (all must be present, case-insensitive)
    if "contains" in expected:
        text_lower = info["response_text"].lower()
        for phrase in expected["contains"]:
            if phrase.lower() not in text_lower:
                return False, f"expected to contain {phrase!r}, not found"

    # not_contains (none may be present, case-insensitive)
    if "not_contains" in expected:
        text_lower = info["response_text"].lower()
        for phrase in expected["not_contains"]:
            if phrase.lower() in text_lower:
                return False, f"unexpected phrase {phrase!r} found in response"

    # tool expected
    if "tool" in expected:
        tool_names = [t.get("name", "") for t in info["tools_used"]]
        if expected["tool"] not in tool_names:
            return False, f"expected tool {expected['tool']!r}, used: {tool_names}"

    # not_tool forbidden
    if "not_tool" in expected:
        tool_names = [t.get("name", "") for t in info["tools_used"]]
        for forbidden in expected["not_tool"]:
            if forbidden in tool_names:
                return False, f"forbidden tool {forbidden!r} was invoked"

    return True, ""


def load_scenarios(scenario_path: str | None) -> list[dict]:
    """Load one or all scenario files."""
    if scenario_path:
        path = Path(scenario_path)
        if not path.exists():
            print(f"ERROR: scenario file not found: {path}")
            sys.exit(1)
        with open(path) as f:
            return [json.load(f)]
    else:
        if not SCENARIOS_DIR.exists():
            print(f"ERROR: scenarios directory not found: {SCENARIOS_DIR}")
            sys.exit(1)
        scenarios = []
        for fpath in sorted(SCENARIOS_DIR.glob("*.json")):
            with open(fpath) as f:
                scenarios.append(json.load(f))
        if not scenarios:
            print("ERROR: no .json scenario files found in scenarios/")
            sys.exit(1)
        return scenarios


def pick_chat_id(results: list[dict], use_chat: bool) -> str | None:
    """Return the last non-None chatId from results if multi-turn."""
    if not use_chat:
        return None
    for r in reversed(results):
        if r.get("chat_id"):
            return r["chat_id"]
    return None


# ── main pipeline ────────────────────────────────────────────────────


def run_scenario(scenario: dict, chat_persistence: bool) -> list[dict]:
    """Execute all test cases in a scenario. Returns list of result dicts."""
    bot_name = scenario.get("bot_name", "unknown")
    workspace_id = scenario["workspace_id"]
    customer_id = scenario["customer_id"]
    test_cases = scenario["test_cases"]

    results = []
    current_chat_id = None

    print(f"\n{'='*60}")
    print(f"  Bot: {bot_name}")
    print(f"  Workspace: {workspace_id}")
    print(f"  Cases: {len(test_cases)}")
    print(f"{'='*60}")

    for tc in test_cases:
        tc_id = tc.get("id", "?")
        query = tc["query"]
        expected = tc.get("expected", {})
        category = tc.get("category", "")

        print(f"  [{tc_id}] {query[:60]}...", end=" ")

        # Build request
        params = {
            "sellerWorkspaceId": workspace_id,
            "customerId": customer_id,
        }
        if current_chat_id:
            params["chatId"] = current_chat_id

        payload = {"message": query}
        start = time.time()
        error = None
        response_json = None
        status_code = None

        try:
            resp = requests.post(
                f"{BASE_URL}{ENDPOINT}",
                params=params,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            status_code = resp.status_code
            if resp.status_code != 200:
                error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                response_json = resp.json()
        except requests.Timeout:
            error = "timeout (30s)"
        except requests.RequestException as e:
            error = str(e)

        elapsed = round(time.time() - start, 2)

        # Parse
        info = extract_response_info(response_json) if response_json else {}
        quality = classify_quality(info.get("response_text", ""), error)
        passed, fail_reason = check_expectations(info, expected)

        # Override quality: if expectation checks failed, mark as fail
        if error:
            quality = "fail"
            passed = False
            fail_reason = fail_reason or error

        result = {
            "query_id": tc_id,
            "bot_name": bot_name,
            "workspace_id": workspace_id,
            "customer_id": customer_id,
            "query": query,
            "category": category,
            "response_type": info.get("response_type", "error"),
            "response_text": info.get("response_text", ""),
            "menu_options": info.get("menu_options", []),
            "tools_used": info.get("tools_used", []),
            "knowledge_files": info.get("knowledge_files", []),
            "response_time_seconds": elapsed,
            "status_code": status_code,
            "error": error,
            "passed": passed,
            "fail_reason": fail_reason,
            "response_quality": quality,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chat_id": response_json.get("chatId") if response_json else None,
        }

        results.append(result)

        # Update chat_id for multi-turn
        if chat_persistence and result["chat_id"]:
            current_chat_id = result["chat_id"]

        status = "PASS" if passed else "FAIL"
        qual = quality.upper()
        print(f"→ {status} [{qual}] ({elapsed}s)")
        if fail_reason:
            print(f"     ↳ {fail_reason}")

    return results


def save_run(results: list[dict], run_id: str, manifest: dict):
    """Save results to a versioned JSONL file and update manifest."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    # Write JSONL
    results_path = RUNS_DIR / f"results_{run_id}.jsonl"
    with open(results_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Update manifest
    manifest_path = RUNS_DIR / "manifest.json"
    runs = manifest.get("runs", [])
    runs.append({
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results_file": str(results_path.name),
        "total_cases": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
    })
    manifest["runs"] = sorted(runs, key=lambda x: x["timestamp"], reverse=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n📁 Results written to {results_path}")
    return results_path


def print_summary(results: list[dict]):
    """Print a quick summary to stdout."""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    by_quality = {}
    for r in results:
        by_quality.setdefault(r["response_quality"], 0)
        by_quality[r["response_quality"]] += 1

    avg_time = round(
        sum(r["response_time_seconds"] for r in results) / total, 1
    ) if total else 0

    print(f"\n{'─'*40}")
    print(f"  Total:   {total}")
    print(f"  Passed:  {passed}  ({passed/total*100:.0f}%)" if total else "  Passed:  0")
    print(f"  Failed:  {failed}")
    print(f"  Quality: {by_quality}")
    print(f"  Avg time: {avg_time}s")
    print(f"{'─'*40}\n")


def main():
    parser = argparse.ArgumentParser(description="Playground Eval Pipeline")
    parser.add_argument(
        "--scenario", "-s",
        help="Path to a specific scenario JSON file (default: all in scenarios/)"
    )
    parser.add_argument(
        "--workspace", "-w",
        help="Override workspace ID (quick mode — runs default.json)"
    )
    parser.add_argument(
        "--no-chat-persistence", "-n",
        action="store_true",
        help="Fresh chat per query (default: multi-turn within each bot)"
    )
    args = parser.parse_args()

    # Quick mode: run default.json with override workspace
    if args.workspace:
        default_path = SCENARIOS_DIR / "default.json"
        if not default_path.exists():
            print("ERROR: --workspace mode requires scenarios/default.json")
            sys.exit(1)
        with open(default_path) as f:
            scenario = json.load(f)
        scenario["workspace_id"] = args.workspace
        scenarios = [scenario]
    else:
        scenarios = load_scenarios(args.scenario)

    chat_persistence = not args.no_chat_persistence
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    all_results = []

    manifest_path = RUNS_DIR / "manifest.json"
    manifest = {"project": "playground-eval", "runs": []}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

    for scenario in scenarios:
        results = run_scenario(scenario, chat_persistence)
        all_results.extend(results)

    if all_results:
        save_run(all_results, run_id, manifest)
        print_summary(all_results)
    else:
        print("No results generated. Check scenario files.")


if __name__ == "__main__":
    main()
