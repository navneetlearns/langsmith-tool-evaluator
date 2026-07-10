"""
Tool-selection evaluator.

Orchestrates the end-to-end evaluation loop:
  1. Read runs from LangSmith.
  2. For each run, build a prompt and call the LLM judge.
  3. Upload the judge's score as LangSmith feedback.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from evaluators.prompt_builder import (
    load_tool_registry,
    format_registry_for_prompt,
    load_prompt_template,
    build_prompt,
)
from utils.langsmith_client import LangSmithClientWrapper
from utils.opencode_client import OpenCodeClient
from utils.trace_parser import ParsedTrace

logger = logging.getLogger(__name__)


class ToolSelectionEvaluator:
    """Evaluates tool-selection accuracy for all runs in a LangSmith project.

    Attributes:
        langsmith: Wrapped LangSmith client.
        judge: OpenCode LLM judge client.
        registry_entries: Parsed ToolEntry list.
        registry_text: Formatted registry string for prompts.
        prompt_template: Raw prompt template with ``{{...}}`` placeholders.
        feedback_key: LangSmith feedback key (default 'tool_selection').
    """

    def __init__(self) -> None:
        self.langsmith = LangSmithClientWrapper()
        self.judge = OpenCodeClient()
        self.feedback_key = "tool_selection"

        # Load registry
        self.registry_entries = load_tool_registry()
        self.registry_text = format_registry_for_prompt(self.registry_entries)

        # Load prompt template
        self.prompt_template = load_prompt_template()

        # Stats
        self.total = 0
        self.succeeded = 0
        self.failed = 0
        self.skipped = 0

    def run(self, limit: int | None = None, run_type: str | None = "tool",
            since: datetime | None = None) -> None:
        """Execute the full evaluation loop.

        Args:
            limit: Maximum runs to evaluate. ``None`` = no limit.
            run_type: Optional filter — 'tool', 'chain', 'llm', etc. Default: 'tool'.
            since: Only evaluate runs after this datetime.
        """
        logger.info(
            "Starting tool-selection evaluation (limit=%s, run_type=%s, since=%s).",
            limit or "all", run_type, since or "earliest",
        )
        start_wall = time.time()

        for run_dict in self.langsmith.list_runs(limit=limit, run_type=run_type, since=since):
            self.total += 1
            self._evaluate_single(run_dict)

        elapsed = time.time() - start_wall
        logger.info(
            "Evaluation complete. "
            "Total=%d, Succeeded=%d, Failed=%d, Skipped=%d, "
            "Elapsed=%.2fs",
            self.total,
            self.succeeded,
            self.failed,
            self.skipped,
            elapsed,
        )

        self._print_summary()

    def _parse_run(self, run_dict: dict[str, Any]) -> ParsedTrace | None:
        """Parse a run dict into a ParsedTrace, or None if it should be skipped."""
        trace = ParsedTrace(run_dict)
        if not trace.run_id or not trace.user_query.strip():
            return None
        if _is_system_prompt(trace.user_query):
            return None
        if trace.tool_calls and trace.tool_calls[0].get("_from_definitions"):
            return None
        return trace

    def _evaluate_single(self, run_dict: dict[str, Any]) -> None:
        """Evaluate a single LangSmith run.

        Args:
            run_dict: Raw run dictionary from LangSmith.
        """
        trace = self._parse_run(run_dict)
        if trace is None:
            self.skipped += 1
            return
        run_id = trace.run_id

        selected_tool = trace.selected_tool
        tool_args = trace.tool_arguments

        # Build the evaluation prompt
        try:
            prompt = build_prompt(
                template=self.prompt_template,
                registry_lines=self.registry_text,
                query=trace.user_query,
                selected_tool=selected_tool,
                tool_args=tool_args,
            )
        except Exception:
            logger.exception("Failed to build prompt for run %s.", run_id[:8])
            self.failed += 1
            return

        # Call the LLM judge
        t0 = time.perf_counter()
        try:
            result = self.judge.evaluate(prompt)
        except Exception:
            logger.exception("Judge call failed for run %s.", run_id[:8])
            self.failed += 1
            return

        elapsed = time.perf_counter() - t0

        if result is None:
            logger.warning(
                "Judge returned no result for run %s (%.2fs).",
                run_id[:8],
                elapsed,
            )
            self.failed += 1
            return

        self.succeeded += 1

        # Log the result
        logger.info(
            "Run=%-8s Query=%-40.40s Tool=%-20s Expected=%-20s "
            "Score=%.2f Elapsed=%.2fs",
            run_id[:8],
            trace.user_query,
            result.get("selected_tool", "?"),
            result.get("expected_tool", "?"),
            result.get("score", -1),
            elapsed,
        )

        # Upload feedback to LangSmith
        self._upload_feedback(run_id, trace, result)

    def _upload_feedback(
        self, run_id: str, trace: ParsedTrace, result: dict[str, Any]
    ) -> None:
        """Write evaluation feedback back to LangSmith.

        Args:
            run_id: The LangSmith run UUID.
            trace: The parsed trace (for context).
            result: Judge output dict (expected_tool, selected_tool, score, reason, candidate_tools).
        """
        try:
            self.langsmith.client.create_feedback(
                run_id=run_id,
                key=self.feedback_key,
                score=result.get("score", 0.0),
                comment=json_safe({
                    "reason": result.get("reason", ""),
                    "expected_tool": result.get("expected_tool", ""),
                    "selected_tool": result.get("selected_tool", ""),
                    "candidate_tools": result.get("candidate_tools", []),
                    "query": trace.user_query,
                    "run_type": trace.run_type,
                }),
            )
            logger.debug("Feedback uploaded for run %s.", run_id[:8])
        except Exception:
            logger.exception("Failed to upload feedback for run %s.", run_id[:8])

    def _print_summary(self) -> None:
        """Print a final summary to the log."""
        summary = (
            f"\n{'=' * 60}\n"
            f"  EVALUATION SUMMARY\n"
            f"{'=' * 60}\n"
            f"  Total runs seen:   {self.total}\n"
            f"  Evaluated:         {self.succeeded}\n"
            f"  Failed:            {self.failed}\n"
            f"  Skipped:           {self.skipped}\n"
            f"{'=' * 60}"
        )
        print(f"\n{summary}")
        logger.info(summary)


def json_safe(obj: Any) -> str:
    """Safely serialize an object to JSON for feedback comments."""
    import json
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _is_system_prompt(query: str) -> bool:
    """Heuristic: detect if the extracted query is a system prompt, not a user query."""
    indicators = [
        "you are an expert",
        "you are a helpful assistant",
        "your task is to",
        "you are the zotok seller copilot",
        "you are a tool selector",
        "do not evaluate the quality",
        "evaluate whether the agent selected",
    ]
    q_lower = query.lower()
    for indicator in indicators:
        if indicator in q_lower:
            return True
    # System prompts are typically very long
    if len(query) > 500:
        return True
    return False
