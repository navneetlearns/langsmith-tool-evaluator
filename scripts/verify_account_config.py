#!/usr/bin/env python3
"""Probe: parse an account config with the pipeline's OWN loader and assert fields.

Catches the empty-value YAML bug (hand-rolled line parser turns `key: ""`
inside a nested section into a nested dict) before committing to a long run.

Usage: python3 scripts/verify_account_config.py <account> [expected_phone]
"""
import sys

sys.path.insert(0, ".")
from copilot_query_pipeline import load_account_config  # noqa: E402

REQUIRED_FIELDS = (
    "account_name",
    "phone",
    "workspace_id",
    "base_url",
    "sse_timeout",
    "sse_read_timeout",
    "wa_config_id",
    "llm_provider",
)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    name = sys.argv[1]
    expected_phone = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        c = load_account_config(name)
    except SystemExit as e:
        print(f"FAIL: loader exited: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAIL: loader raised: {e}")
        sys.exit(1)

    problems = []
    for field in REQUIRED_FIELDS:
        if not c.get(field):
            problems.append(f"missing/invalid: {field}")

    sd = c.get("seller_details", {})
    if not isinstance(sd, dict) or "firstName" not in sd or "mobile" not in sd:
        problems.append(f"seller_details malformed (empty-value bug?): {sd!r}")

    if expected_phone and str(c.get("phone")) != str(expected_phone):
        problems.append(
            f"phone mismatch: got {c.get('phone')} expected {expected_phone}"
        )

    if problems:
        print("FAIL")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    print(
        f"OK: {c.get('account_name')} | phone={c.get('phone')} | "
        f"ws={str(c.get('workspace_id'))[:8]}... | {c.get('base_url')}"
    )


if __name__ == "__main__":
    main()
