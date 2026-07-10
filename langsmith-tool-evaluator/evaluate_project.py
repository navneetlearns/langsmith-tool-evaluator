#!/usr/bin/env python3
"""
Entry point for the LangSmith Tool-Selection Evaluator.

Evaluate tool-selection accuracy on PAST and FUTURE traces from a LangSmith project.

Usage:
    # Evaluate all past tool runs (no limit)
    python evaluate_project.py

    # Evaluate last 100 runs
    python evaluate_project.py --limit 100

    # Evaluate runs since a date
    python evaluate_project.py --since 2026-07-01

    # Watch mode: continuously evaluate new tool runs as they appear
    python evaluate_project.py --watch

    # Watch mode with custom poll interval (default: 300s)
    python evaluate_project.py --watch --watch-interval 600

    # Run as a LangSmith experiment (results in Datasets & Testing section)
    python evaluate_project.py --experiment

    # Run on a different project
    python evaluate_project.py --project my-other-project

Reads configuration from .env in the project root.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    """Configure root logger with INFO or DEBUG level."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        if verbose
        else "%(asctime)s | %(levelname)-8s | %(message)s"
    )
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LangSmith Tool-Selection Evaluator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables (from .env):\n"
            "  LANGSMITH_API_KEY       LangSmith API key\n"
            "  LANGSMITH_ENDPOINT      LangSmith endpoint URL\n"
            "  LANGSMITH_PROJECT_NAME  Project to evaluate (default: seller-copilot-agent)\n"
            "  OPENCODE_API_KEY        OpenCode API key\n"
            "  OPENCODE_BASE_URL       OpenCode API base URL\n"
            "  MODEL_NAME              LLM model name (default: deepseek-v4-flash)\n"
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max runs to evaluate. 0 = all runs (default: 0)",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only evaluate runs after this time. "
             "Examples: '2026-07-01', '2026-07-01T00:00:00', '7d' (last 7 days), '24h'",
    )
    parser.add_argument(
        "--run-type",
        type=str,
        default="tool",
        help="Run type to evaluate: 'tool', 'chain', 'llm' (default: tool)",
    )
    parser.add_argument(
        "--experiment",
        action="store_true",
        help="Run as a LangSmith experiment (results in Datasets & Testing → Experiments)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode: continuously poll for new runs and evaluate them",
    )
    parser.add_argument(
        "--watch-interval",
        type=int,
        default=300,
        help="Poll interval in seconds for watch mode (default: 300 = 5 min)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Override LANGSMITH_PROJECT_NAME from .env",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override MODEL_NAME from .env",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser.parse_args()


def _parse_since(value: str | None) -> datetime | None:
    """Parse a --since argument into a datetime (UTC).

    Supports:
        - ISO date: '2026-07-01' or '2026-07-01T00:00:00'
        - Relative: '7d' (7 days ago), '24h' (24 hours ago)
    """
    if not value:
        return None

    # Relative formats
    if value.endswith("d"):
        try:
            days = int(value[:-1])
            return datetime.now(timezone.utc).replace(microsecond=0)
        except ValueError:
            pass
    if value.endswith("h"):
        try:
            hours = int(value[:-1])
            return datetime.now(timezone.utc).replace(microsecond=0)
        except ValueError:
            pass

    # ISO date
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    raise ValueError(
        f"Unrecognised --since format: '{value}'. "
        f"Use ISO date (2026-07-01), ISO datetime (2026-07-01T00:00:00), "
        f"or relative (7d, 24h)."
    )


def main() -> None:
    """Load .env, parse args, and run the evaluation."""
    args = _parse_args()
    _setup_logging(args.verbose)

    # Load .env
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path.cwd() / ".env"

    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        logger.info("Loaded environment from %s", env_path)
    else:
        logger.warning("No .env file found at %s or CWD.", env_path)

    # Apply CLI overrides
    if args.project:
        os.environ["LANGSMITH_PROJECT_NAME"] = args.project
    if args.model:
        os.environ["MODEL_NAME"] = args.model

    project_name = os.getenv("LANGSMITH_PROJECT_NAME", "seller-copilot-agent")
    os.environ.setdefault("LANGSMITH_PROJECT_NAME", project_name)

    # Validate critical env vars
    missing = [
        var for var in (
            "LANGSMITH_API_KEY",
            "LANGSMITH_PROJECT_NAME",
            "OPENCODE_API_KEY",
            "OPENCODE_BASE_URL",
        )
        if not os.getenv(var)
    ]
    if missing:
        print(
            f"ERROR: Missing required environment variables: {', '.join(missing)}\n"
            f"Create a .env file based on .env.example.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse --since
    try:
        since_dt = _parse_since(args.since)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    limit = args.limit if args.limit > 0 else None  # None = no limit
    run_type = args.run_type

    logger.info(
        "Target project: %s | run_type=%s | limit=%s | since=%s",
        project_name,
        run_type,
        limit or "unlimited",
        since_dt or "earliest",
    )

    # ── Run or Watch ────────────────────────────────────────────
    try:
        if args.watch:
            _run_watch_mode(
                limit=limit,
                run_type=run_type,
                since=since_dt,
                interval=args.watch_interval,
                use_experiment=args.experiment,
            )
        elif args.experiment:
            from evaluators.experiment import run_experiment
            run_experiment(
                limit=limit,
                run_type=run_type,
                since=since_dt,
            )
        else:
            from evaluators.tool_selection import ToolSelectionEvaluator
            evaluator = ToolSelectionEvaluator()
            evaluator.run(
                limit=limit,
                run_type=run_type,
                since=since_dt,
            )
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")
        sys.exit(0)
    except Exception:
        logger.exception("Evaluation failed.")
        sys.exit(1)


def _run_watch_mode(
    limit: int | None,
    run_type: str,
    since: datetime | None,
    interval: int,
    use_experiment: bool,
) -> None:
    """Continuously poll for new runs and evaluate them.

    Tracks already-seen run IDs in memory so each run is evaluated only once.
    """
    from evaluators.tool_selection import ToolSelectionEvaluator

    seen_ids: set[str] = set()
    poll_count = 0

    logger.info(
        "Watch mode enabled — polling every %ds for new %s runs.",
        interval,
        run_type,
    )

    while True:
        poll_count += 1
        logger.info("Watch poll #%d — checking for new runs...", poll_count)

        # For watch mode, we always start from "now minus interval" to catch new runs
        watch_since = since or datetime.now(timezone.utc)

        evaluator = ToolSelectionEvaluator()

        # We override list_runs behaviour per-poll by passing seen_ids
        new_count = 0
        for run_dict in evaluator.langsmith.list_runs(
            limit=limit,
            run_type=run_type,
        ):
            trace = evaluator._parse_run(run_dict)
            if not trace.run_id or trace.run_id in seen_ids:
                continue
            seen_ids.add(trace.run_id)

            evaluator._evaluate_single(run_dict)
            new_count += 1

        if new_count > 0:
            logger.info("Watch poll #%d — evaluated %d new run(s).", poll_count, new_count)
            evaluator._print_summary()
        else:
            logger.info("Watch poll #%d — no new runs found. Sleeping %ds...", poll_count, interval)

        # Also upload as experiment if requested (full batch)
        if use_experiment and new_count > 0:
            try:
                from evaluators.experiment import run_experiment
                run_experiment(limit=new_count, run_type=run_type)
            except Exception:
                logger.exception("Experiment upload failed (non-fatal).")

        time.sleep(interval)


if __name__ == "__main__":
    main()
