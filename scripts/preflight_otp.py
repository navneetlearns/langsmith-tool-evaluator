#!/usr/bin/env python3
"""Probe: confirm a phone is registered on the target env before a long run.

POST {base_url}/hub/orgs/api/copilot/sendOtp {"mobile": phone}
Expect 201 + success + data.otp echoed (prod SIGNIN flow) = number registered.
Note: QA env flow differs (4-digit auto-fill, OTP NOT echoed in response) —
on QA the probe passes if flow/otpSent is present without an OTP value.

Usage: python3 scripts/preflight_otp.py <phone> [base_url]
"""
import json
import sys
import urllib.request


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    phone = sys.argv[1]
    base = sys.argv[2] if len(sys.argv) > 2 else "https://api.zotok.ai"
    url = f"{base}/hub/orgs/api/copilot/sendOtp"
    body = json.dumps({"mobile": phone}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            d = data.get("data", {})
            registered = bool(
                bool(data.get("success"))
                and (d.get("otp") or d.get("otpSent") is True)
            )
            print(
                f"HTTP {r.status} | registered={registered} | "
                f"flow={d.get('flow')} | otpSent={d.get('otpSent')} | "
                f"otp={d.get('otp')}"
            )
            sys.exit(0 if registered else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
