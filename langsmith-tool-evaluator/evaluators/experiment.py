"""
Experiment-based evaluation.

Creates a LangSmith dataset from evaluated runs and runs `evaluate()`
so results appear in the "Datasets & Testing → Experiments" UI section.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from langsmith import evaluate as ls_evaluate

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

DATASET_NAME = "tool-selection-evaluator"


def run_experiment(
    limit: int | None = None,
    run_type: str | None = "tool",
    since: datetime | None = None,
) -> None:
    """Run tool-selection evaluation as a LangSmith experiment.

    Creates a dataset from project runs, then runs ``evaluate()``
    which logs results as an experiment visible in the UI's
    "Datasets & Testing → Experiments" section.

    Args:
        limit: Maximum number of runs to evaluate. ``None`` = no limit.
        run_type: Run type filter (default: 'tool').
        since: Only evaluate runs after this datetime.
    """
    langsmith = LangSmithClientWrapper()
    judge = OpenCodeClient()

    registry_entries = load_tool_registry()
    registry_text = format_registry_for_prompt(registry_entries)
    prompt_template = load_prompt_template()

    # ── Step 1: Parse runs into examples ──────────────────────
    logger.info("Fetching runs from project '%s'...", langsmith.project_name)
    examples: list[dict[str, Any]] = []

    for run_dict in langsmith.list_runs(limit=limit, run_type=run_type, since=since):
        trace = ParsedTrace(run_dict)
        if not trace.run_id or not trace.user_query.strip():
            continue
        if _is_system_prompt(trace.user_query):
            continue
        # Skip runs where tool only came from definitions
        if trace.tool_calls and trace.tool_calls[0].get("_from_definitions"):
            continue

        examples.append({
            "run_id": trace.run_id,
            "query": trace.user_query,
            "selected_tool": trace.selected_tool,
            "tool_args": trace.tool_arguments,
            "run_type": trace.run_type,
        })

    if not examples:
        logger.warning("No evaluable runs found. Aborting experiment.")
        return

    logger.info("Collected %d evaluable examples.", len(examples))

    # ── Step 2: Create/update dataset ─────────────────────────
    try:
        ds = langsmith.client.read_dataset(dataset_name=DATASET_NAME)
        logger.info("Dataset '%s' already exists (id=%s).", DATASET_NAME, ds.id)
        # Clear old examples
        existing = list(langsmith.client.list_examples(dataset_id=ds.id))
        for ex in existing:
            try:
                langsmith.client.delete_example(example_id=ex.id)
            except Exception:
                pass
        logger.info("Cleared %d old examples.", len(existing))
    except Exception:
        ds = langsmith.client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Tool-selection evaluation examples from seller-copilot-agent runs",
        )
        logger.info("Created dataset '%s' (id=%s).", DATASET_NAME, ds.id)

    # Add examples to dataset
    for ex in examples:
        langsmith.client.create_example(
            dataset_id=ds.id,
            inputs={"query": ex["query"], "tool_args": ex["tool_args"]},
            outputs={"selected_tool": ex["selected_tool"]},
            metadata={"run_id": ex["run_id"], "run_type": ex["run_type"]},
        )
    logger.info("Added %d examples to dataset.", len(examples))

    # ── Step 3: Build a factory for evaluator fns that close over our deps ──
    def make_evaluator(
        registry: str,
        template: str,
        judge_client: OpenCodeClient,
    ):
        """Return an evaluator function compatible with ``ls.evaluate()``.

        The evaluator receives a ``run`` (the target's output) and an
        ``example`` (the dataset example). It calls the LLM judge
        and returns an ``EvaluationResult`` dict.
        """

        def evaluator(run, example) -> dict[str, Any]:
            inputs = example.inputs if hasattr(example, "inputs") else example.get("inputs", {})
            outputs = example.outputs if hasattr(example, "outputs") else example.get("outputs", {})

            query = (inputs or {}).get("query", "")
            tool_args = (inputs or {}).get("tool_args", "{}")
            selected_tool = (outputs or {}).get("selected_tool", "none")

            prompt = build_prompt(
                template=template,
                registry_lines=registry,
                query=query,
                selected_tool=selected_tool,
                tool_args=tool_args,
            )

            t0 = time.perf_counter()
            result = judge_client.evaluate(prompt)
            elapsed = time.perf_counter() - t0

            if result is None:
                logger.warning("Judge returned no result (elapsed=%.2fs).", elapsed)
                return {
                    "key": "tool_selection",
                    "score": 0.0,
                    "comment": json.dumps({"error": "Judge call failed"}),
                }

            expected = result.get("expected_tool", "?")
            score = result.get("score", 0.0)
            reason = result.get("reason", "")

            logger.info(
                "Query=%-40.40s Tool=%-20s Expected=%-20s Score=%.2f Elapsed=%.2fs",
                query,
                selected_tool,
                expected,
                score,
                elapsed,
            )

            return {
                "key": "tool_selection",
                "score": score,
                "comment": json.dumps({
                    "reason": reason,
                    "expected_tool": expected,
                    "selected_tool": selected_tool,
                    "candidate_tools": result.get("candidate_tools", []),
                }),
            }

        return evaluator

    # ── Step 4: Run evaluate() ────────────────────────────────
    target_fn = lambda inputs: {"selected_tool_from_query": inputs.get("query", "")}

    eval_fn = make_evaluator(registry_text, prompt_template, judge)

    logger.info("Running evaluate() experiment...")

    experiment_results = ls_evaluate(
        target_fn,
        data=ds.id,
        evaluators=[eval_fn],
        experiment_prefix="tool-selection",
        client=langsmith.client,
        metadata={"source_project": langsmith.project_name},
    )

    logger.info(
        "Experiment complete. See results in LangSmith UI → Datasets & Testing → Experiments."
    )
    print(f"\n✅ Experiment created!")
    print(f"   Open in browser: https://smith.langchain.com/datasets/{ds.id}/experiments")


def _is_system_prompt(query: str) -> bool:
    """Detect if the extracted query is a system prompt."""
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
    return len(query) > 500
