#!/usr/bin/env python3
"""
copilot_query_pipeline.py

Eval testing pipeline following HEART.md principles:
1. Auto-OTP auth (user never sees this — internal)
2. Reads all 50 user queries from Surana Polycot test Excel
3. Sends each query to Copilot API via SSE stream (300s timeout per query)
4. NO RETRY — captures the response as a real user would see it
5. Tracks response_time_seconds per query for latency analysis
6. Versioned output: query_results_v{N}.jsonl (never overwrites past runs)
7. Updates runs/manifest.json to track all run versions

Usage:
    python3 copilot_query_pipeline.py

Output:
    query_results_v{N}.jsonl  — one JSON line per query, versioned
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
import base64
from pathlib import Path
from datetime import datetime

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Log file for progress tracking
LOG_FILE = Path(__file__).parent / "pipeline_run.log"
def log_msg(msg: str):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {msg}\n")
    print(msg, flush=True)

# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).parent.resolve()

# Phone (10-digit, no country code)
PHONE = "9595259595"

# Workspace ID (from HAR auth token payload)
WORKSPACE_ID = "6c4ad886-8bf6-4202-8dfb-10ae6905dd3f"

# Seller details (from HAR stream request)
SELLER_DETAILS = {
    "firstName": "Sarthak Rajendra Surana",
    "lastName": "",
    "email": "sarthak@suranagroup.co.in",
    "mobile": "919595259595",
}
WA_CONFIG_ID = f"{WORKSPACE_ID}_917262960095"
LLM_PROVIDER = "gpt-5.4-mini"

# API base
BASE_URL = "https://api.zotok.ai"

# Input Excel
EXCEL_FILE = SCRIPT_DIR / "langsmith-tool-evaluator" / "Copilot Test Cases ---Surana Polycot.xlsx"

# Runs directory for versioned output
RUNS_DIR = SCRIPT_DIR / "runs"
MANIFEST_FILE = RUNS_DIR / "manifest.json"

# SSE stream timeout (seconds) — generous because queries are multi-turn, data-driven,
# and may include large table data in the response
SSE_TIMEOUT = 300

# Headers for all requests
BASE_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "user-agent": "hermes-pipeline/2.0",
    "origin": "https://copilot.zotok.ai",
    "referer": "https://copilot.zotok.ai/",
}

# Socket-level read timeout (seconds) — if no bytes for this long, we give up.
# This catches genuine hangs while still allowing long pauses between SSE events.
SSE_READ_TIMEOUT = 120


# ============================================================
# VERSIONING
# ============================================================

def get_next_version() -> int:
    """Determine the next version number from existing run files."""
    RUNS_DIR.mkdir(exist_ok=True)
    existing = sorted(RUNS_DIR.glob("query_results_v*.jsonl"))
    if not existing:
        return 1
    # Extract version number from filename
    versions = []
    for f in existing:
        try:
            v = int(f.stem.split("_v")[1])
            versions.append(v)
        except (IndexError, ValueError):
            continue
    return max(versions) + 1 if versions else 1


def load_manifest() -> dict:
    """Load or create the runs manifest."""
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text())
    return {"runs": []}


def save_manifest(manifest: dict) -> None:
    """Save the runs manifest."""
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def update_manifest(version: int, output_file: Path, total: int,
                    success: int, fail: int, avg_time: float) -> None:
    """Add a run entry to the manifest."""
    manifest = load_manifest()
    manifest["runs"].append({
        "version": version,
        "file": output_file.name,
        "timestamp": datetime.now().isoformat(),
        "total_queries": total,
        "success": success,
        "failed": fail,
        "avg_response_time_seconds": round(avg_time, 2),
    })
    save_manifest(manifest)


# ============================================================
# AUTH
# ============================================================

class CopilotAuth:
    """Handles OTP-based authentication with auto-refresh.

    Auth is INTERNAL — the user never sees it. 401 errors trigger silent
    re-auth so the pipeline never stops due to token expiry.
    """

    def __init__(self, phone: str):
        self.phone = phone
        self.token: str | None = None
        self.refresh_token: str | None = None
        self.token_expires_at: float = 0

    def _api_call(self, method: str, path: str, body: dict | None = None,
                  auth: bool = False) -> tuple[int, dict]:
        url = f"{BASE_URL}{path}"
        data = json.dumps(body).encode() if body else None
        headers = dict(BASE_HEADERS)
        if auth and self.token:
            headers["authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode()
                return resp.status, json.loads(content)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            try:
                return e.code, json.loads(body_text)
            except Exception:
                return e.code, {"_error": body_text[:300]}
        except Exception as e:
            return 0, {"_error": str(e)}

    def login(self) -> str | None:
        print(f"  [auth] Sending OTP to {self.phone}...")
        status, resp = self._api_call("POST", "/hub/orgs/api/copilot/sendOtp",
                                      {"mobile": self.phone})
        if status not in (200, 201):
            print(f"  [auth] sendOtp failed: {status} {resp.get('_error', resp)}")
            return None

        data = resp.get("data", {})
        otp = data.get("otp")
        otp_token = data.get("otpToken")
        flow = data.get("flow", "?")
        if not otp:
            print(f"  [auth] No OTP received. Response: {resp}")
            return None

        print(f"  [auth] OTP received ({flow} flow), verifying...")
        status, resp = self._api_call("POST", "/hub/orgs/api/copilot/verifyOtp", {
            "mobile": self.phone,
            "otp": otp,
            "otpToken": otp_token,
        })
        if status not in (200, 201):
            print(f"  [auth] verifyOtp failed: {status} {resp.get('_error', resp)}")
            return None

        data = resp.get("data", {})
        token = data.get("token") or data.get("accessToken")
        self.refresh_token = data.get("refreshToken")
        if not token:
            print(f"  [auth] No token in response. Flow: {data.get('flow')}.")
            return None

        self.token = token
        self._decode_expiry(token)
        print(f"  [auth] Authenticated. Token valid for {self._mins_remaining():.0f} min")
        return token

    def refresh(self) -> str | None:
        if not self.refresh_token:
            print("  [auth] No refresh token, re-logging in...")
            return self.login()

        print(f"  [auth] Refreshing token...")
        status, resp = self._api_call("POST", "/hub/orgs/api/copilot/refresh-token",
                                      {"refreshToken": self.refresh_token})
        if status not in (200, 201):
            print(f"  [auth] Refresh failed ({status}), re-logging in...")
            return self.login()

        data = resp.get("data", {})
        new_token = data.get("token") or data.get("accessToken")
        if new_token:
            self.token = new_token
            self._decode_expiry(new_token)
            print(f"  [auth] Token refreshed. Valid for {self._mins_remaining():.0f} min")
        return new_token

    def ensure_token(self) -> str:
        if not self.token:
            if not self.login():
                raise RuntimeError("Authentication failed")
        elif self._mins_remaining() < 2:
            print(f"  [auth] Token expiring ({self._mins_remaining():.0f} min), refreshing...")
            if not self.refresh():
                raise RuntimeError("Token refresh failed")
        return self.token

    def invalidate(self):
        """Force re-auth on next call (e.g. after 401)."""
        self.token = None

    def _decode_expiry(self, token: str) -> None:
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                padding = 4 - len(payload_b64) % 4
                if padding != 4:
                    payload_b64 += "=" * padding
                payload = json.loads(base64.b64decode(payload_b64))
                self.token_expires_at = payload.get("exp", 0)
        except Exception:
            self.token_expires_at = 0

    def _mins_remaining(self) -> float:
        return max(0, (self.token_expires_at - time.time()) / 60)


# ============================================================
# API CLIENT
# ============================================================

class CopilotClient:
    """Client for the ZoTok Copilot API."""

    def __init__(self, auth: CopilotAuth):
        self.auth = auth

    def _request(self, method: str, path: str, body: dict | None = None,
                 timeout: int = 30) -> tuple[int, dict | str]:
        token = self.auth.ensure_token()
        url = f"{BASE_URL}{path}"
        data = json.dumps(body).encode() if body else None
        headers = dict(BASE_HEADERS)
        headers["authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                try:
                    return resp.status, json.loads(content.decode())
                except Exception:
                    return resp.status, content.decode()
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            try:
                return e.code, json.loads(body_text)
            except Exception:
                return e.code, body_text
        except Exception as e:
            return 0, str(e)

    def init_thread(self, thread_id: str) -> bool:
        status, _ = self._request("POST", "/hub/copilot/threads/init", {
            "thread_id": thread_id,
            "sellerWorkspaceId": WORKSPACE_ID,
        })
        return status in (200, 201)

    def stream_query(self, thread_id: str, message: str) -> dict:
        """Send a query via /stream and parse SSE response.

        NO RETRY. Captures whatever comes back as a user would see it.
        Records response_time_seconds from POST /stream to event: done.

        Returns dict with:
            response: reconstructed text from token events
            tool_calls: list of {tool, input} from tool_start events
            status_sequence: ordered list of phase names
            suggestions: follow-up suggestions if any
            response_time_seconds: wall-clock time for this query
            error: error message if any (user-visible reality)
        """
        body = {
            "thread_id": thread_id,
            "message": message,
            "sellerWorkspaceId": WORKSPACE_ID,
            "wa_config_id": WA_CONFIG_ID,
            "seller_details": SELLER_DETAILS,
            "llm_provider": LLM_PROVIDER,
        }

        token = self.auth.ensure_token()
        url = f"{BASE_URL}/hub/copilot/stream"
        data = json.dumps(body).encode()
        headers = dict(BASE_HEADERS)
        headers["authorization"] = f"Bearer {token}"

        result = {
            "response": "",
            "tool_calls": [],
            "status_sequence": [],
            "suggestions": [],
            "response_time_seconds": 0.0,
            "error": None,
        }

        query_start = time.time()

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=SSE_TIMEOUT) as resp:
                buffer = ""
                event_type = None
                last_data_time = time.time()

                while True:
                    # Check for socket-level hang (no data for SSE_READ_TIMEOUT seconds)
                    if time.time() - last_data_time > SSE_READ_TIMEOUT:
                        result["error"] = f"Stream hang: no data for {SSE_READ_TIMEOUT}s"
                        break

                    chunk = resp.read(4096)
                    if not chunk:
                        break

                    last_data_time = time.time()
                    buffer += chunk.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line:
                            event_type = None
                            continue

                        if line.startswith("event: "):
                            event_type = line[7:]
                            continue

                        if line.startswith("data: ") and line[6:].strip():
                            data_str = line[6:]
                            try:
                                parsed = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if event_type == "status":
                                phase = parsed.get("phase", "")
                                result["status_sequence"].append(phase)
                                if phase == "tool_start":
                                    result["tool_calls"].append({
                                        "tool": parsed.get("tool"),
                                        "input": parsed.get("input"),
                                    })

                            elif event_type == "token":
                                result["response"] += parsed.get("content", "")

                            elif event_type == "message":
                                if not result["response"]:
                                    result["response"] = parsed.get("content", "")

                            elif event_type == "suggestions":
                                s = parsed.get("suggestions") or parsed.get("data") or []
                                if isinstance(s, list):
                                    result["suggestions"] = s

                            elif event_type == "done":
                                pass

        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")[:300]
            result["error"] = f"HTTP {e.code}: {body_text}"
            if e.code == 401:
                self.auth.invalidate()

        except Exception as e:
            result["error"] = str(e)

        result["response_time_seconds"] = round(time.time() - query_start, 2)
        return result


# ============================================================
# EXCEL PARSER
# ============================================================

def parse_chat_queries(excel_path: str) -> list[dict]:
    """Parse the Chat Queries sheet from the Excel file.

    Category headers are bold rows. Real queries are never bold.
    """
    import openpyxl

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb["Chat Queries"]

    queries = []
    current_category = "General"

    for row_idx in range(2, ws.max_row + 1):
        query = ws.cell(row_idx, 1).value
        response = ws.cell(row_idx, 2).value
        remarks = ws.cell(row_idx, 3).value
        cell = ws.cell(row_idx, 1)
        is_bold = bool(cell.font and cell.font.bold)

        if is_bold and query:
            current_category = str(query).strip()
            continue
        if not query:
            continue

        queries.append({
            "query": str(query).strip(),
            "copilot_response": str(response).strip() if response else "",
            "remarks": str(remarks).strip() if remarks else "",
            "category": current_category,
        })

    wb.close()
    return queries


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    log_msg("=" * 70)
    log_msg("  COPILOT QUERY PIPELINE — Eval Testing")
    log_msg("  Principles: No retry | Patient SSE | Response timing | Versioned")
    log_msg("=" * 70)

    # Determine version
    version = get_next_version()
    output_file = RUNS_DIR / f"query_results_v{version}.jsonl"
    RUNS_DIR.mkdir(exist_ok=True)
    log_msg(f"  Run version: v{version}")
    log_msg(f"  Output: {output_file}")

    # Step 1: Parse Excel queries
    log_msg("Reading test queries from Excel...")
    if not EXCEL_FILE.exists():
        log_msg(f"  Excel not found: {EXCEL_FILE}")
        sys.exit(1)

    queries = parse_chat_queries(str(EXCEL_FILE))
    log_msg(f"  Found {len(queries)} queries across categories")
    categories = {}
    for q in queries:
        categories[q["category"]] = categories.get(q["category"], 0) + 1
    for cat, count in sorted(categories.items()):
        log_msg(f"    {cat}: {count} queries")

    # Step 2: Authenticate
    log_msg("Authenticating to Copilot API...")
    auth = CopilotAuth(PHONE)
    try:
        token = auth.login()
        if not token:
            log_msg("  Authentication failed!")
            sys.exit(1)
    except Exception as e:
        log_msg(f"  Auth error: {e}")
        sys.exit(1)

    client = CopilotClient(auth)

    # Step 3: Process each query
    log_msg("Processing queries (no retry, patient SSE, timing each response)...")

    results = []
    total = len(queries)
    success_count = 0
    fail_count = 0

    start_time = time.time()

    for idx, q in enumerate(queries, 1):
        query_text = q["query"]
        category = q["category"]
        elapsed = time.time() - start_time
        eta = (elapsed / max(1, idx - 1)) * (total - idx + 1) if idx > 1 else 0

        log_msg(f"  [{idx}/{total}] ({category[:22]:22s}) {query_text[:55]:.55s}")

        # 3a. Ensure auth token (silent refresh)
        try:
            auth.ensure_token()
        except Exception as e:
            log_msg(f"         [FAIL] Auth refresh failed: {e}")
            results.append({
                "query_index": idx, **q,
                "thread_id": None, "tool_calls": [], "response": "",
                "status_sequence": [], "suggestions": [],
                "response_time_seconds": 0.0,
                "error": f"Auth failed: {e}",
                "timestamp": datetime.now().isoformat(),
                "run_version": version,
            })
            fail_count += 1
            continue

        # 3b. Init thread
        thread_id = str(uuid.uuid4())
        if not client.init_thread(thread_id):
            print(f"         [FAIL] Thread init failed")
            results.append({
                "query_index": idx, **q,
                "thread_id": thread_id, "tool_calls": [], "response": "",
                "status_sequence": [], "suggestions": [],
                "response_time_seconds": 0.0,
                "error": "Thread init failed",
                "timestamp": datetime.now().isoformat(),
                "run_version": version,
            })
            fail_count += 1
            continue

        # 3c. Stream query (NO RETRY — capture what user sees)
        result = client.stream_query(thread_id, query_text)

        # 3d. Store result
        record = {
            "query_index": idx,
            **q,
            "thread_id": thread_id,
            "tool_calls": result.get("tool_calls", []),
            "response": result.get("response", ""),
            "status_sequence": result.get("status_sequence", []),
            "suggestions": result.get("suggestions", []),
            "response_time_seconds": result.get("response_time_seconds", 0.0),
            "error": result.get("error"),
            "timestamp": datetime.now().isoformat(),
            "run_version": version,
        }
        results.append(record)

        # 3e. Log result
        error = record.get("error")
        resp_time = record.get("response_time_seconds", 0)
        if error:
            log_msg(f"         [FAIL] {error}  (time: {resp_time}s)")
            fail_count += 1
        else:
            tools = record.get("tool_calls", [])
            resp_len = len(record.get("response", ""))
            tool_names = [t.get("tool", "?") for t in tools]
            log_msg(f"         [OK]   tools={tool_names} resp_len={resp_len}  (time: {resp_time}s)")
            success_count += 1

        # Small delay between queries
        time.sleep(1)

    # Step 4: Write results (versioned)
    log_msg(f"Writing results to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        for record in results:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log_msg(f"  Written {len(results)} records to {output_file}")

    # Step 5: Update manifest
    avg_time = sum(r.get("response_time_seconds", 0) for r in results) / max(1, len(results))
    total_elapsed = time.time() - start_time
    update_manifest(version, output_file, total, success_count, fail_count, avg_time)
    log_msg(f"  Manifest updated: {MANIFEST_FILE}")

    # Summary
    log_msg("=" * 70)
    log_msg("  PIPELINE COMPLETE")
    log_msg("=" * 70)
    log_msg(f"  Version:        v{version}")
    log_msg(f"  Total queries:  {total}")
    log_msg(f"  Success:        {success_count}")
    log_msg(f"  Failed:         {fail_count}")
    log_msg(f"  Avg response:   {avg_time:.1f}s")
    log_msg(f"  Total elapsed:  {total_elapsed:.0f}s ({total_elapsed / 60:.1f} min)")
    log_msg(f"  Output:         {output_file}")

    # Tool usage stats
    tools_used = {}
    for r in results:
        for tc in r.get("tool_calls", []):
            tn = tc.get("tool", "?")
            tools_used[tn] = tools_used.get(tn, 0) + 1

    if tools_used:
        log_msg("  Tool usage:")
        for tn, count in sorted(tools_used.items(), key=lambda x: -x[1]):
            log_msg(f"    {tn}: {count}x")

    # Response time by category
    cat_times = {}
    for r in results:
        cat = r.get("category", "?")
        t = r.get("response_time_seconds", 0)
        cat_times.setdefault(cat, []).append(t)

    if cat_times:
        log_msg("  Response time by category:")
        for cat, times in sorted(cat_times.items()):
            avg = sum(times) / len(times)
            mn = min(times)
            mx = max(times)
            log_msg(f"    {cat}: avg={avg:.1f}s  min={mn:.1f}s  max={mx:.1f}s  (n={len(times)})")


if __name__ == "__main__":
    main()