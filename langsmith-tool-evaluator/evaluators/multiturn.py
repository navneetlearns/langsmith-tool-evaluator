"""
Multi-turn conversation evaluator.

Groups LangSmith chain runs by langfuse_session_id, reconstructs the
conversation from inputs.messages, and scores each turn's response with
the LLM judge in full conversation context.

Discovery (2026-08-13): every node run embeds the ENTIRE conversation in
inputs.messages (observed 43 msgs / 11 user turns, roles
human->ai->tool->ai...). Metadata carries langfuse_session_id. The same
conversation appears in multiple node runs -> dedupe by session, keep the
fullest message list.

Usage: python evaluate_project.py --eval multiturn [--limit N] [--since ...]
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluators.prompt_builder import load_prompt_template
from utils.langsmith_client import LangSmithClientWrapper as LangSmithClient
from utils.opencode_client import OpenCodeClient

logger = logging.getLogger(__name__)

PROMPT_NAME = "multiturn_prompt.txt"
RESULTS_DIR = "runs"
MANIFEST = "multiturn_manifest.json"

REQUIRED_FIELDS = {"quality", "score", "data_present", "context_used", "new_flow", "reason"}


class MultiTurnEvaluator:
    """Evaluate per-turn response quality inside multi-turn conversations."""

    def __init__(self) -> None:
        self.langsmith = LangSmithClient()
        self.judge = OpenCodeClient()
        project_root = Path(__file__).resolve().parent.parent
        self.prompt_template = load_prompt_template(project_root / "prompts" / PROMPT_NAME)

        self.total_conversations = 0
        self.total_turns = 0
        self.succeeded = 0
        self.failed = 0
        self.skipped = 0
        self.scores: list[float] = []
        self.qualities: Counter[str] = Counter()
        self.results: list[dict[str, Any]] = []

    # ── main loop ────────────────────────────────────────────────────

    def run(self, limit: int | None = None, since: datetime | None = None) -> None:
        """Collect conversations from chain runs and evaluate every turn."""
        logger.info(
            "Starting multi-turn evaluation (limit=%s, since=%s).",
            limit or "all", since or "earliest",
        )
        start = time.time()

        conversations = self._collect_conversations(limit=limit, since=since)
        for conv in conversations:
            self.total_conversations += 1
            self._evaluate_conversation(conv)

        elapsed = time.time() - start
        if self.results:
            self._write_results()
        logger.info(
            "Multi-turn eval complete. Conversations=%d, Turns=%d, "
            "Succeeded=%d, Failed=%d, Skipped=%d, Elapsed=%.1fs",
            self.total_conversations, self.total_turns,
            self.succeeded, self.failed, self.skipped, elapsed,
        )
        self._print_summary()

    # ── data layer ───────────────────────────────────────────────────

    def _collect_conversations(
        self, limit: int | None = None, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Group chain runs by session id; keep the fullest message list per session."""
        by_session: dict[str, dict[str, Any]] = {}
        for run in self.langsmith.list_runs(run_type="chain", limit=limit, since=since):
            messages = self._extract_messages(run)
            run_id = str(run.get("id", ""))
            if not messages and run_id:
                # list_runs dicts may omit inputs — fetch the full run
                try:
                    full = self.langsmith.client.read_run(run_id)
                    raw = full.model_dump() if hasattr(full, "model_dump") else full.dict()
                    messages = self._extract_messages(raw)
                except Exception:
                    logger.debug("read_run failed for %s", run_id[:8], exc_info=True)
            if not messages:
                continue

            md = run.get("extra", {}).get("metadata", {}) or run.get("metadata", {}) or {}
            session_id = (
                md.get("langfuse_session_id")
                or md.get("session_id")
                or run_id
            )
            existing = by_session.get(session_id)
            if existing is None or len(messages) > len(existing["messages"]):
                by_session[session_id] = {
                    "session_id": session_id,
                    "messages": messages,
                    "metadata": md,
                    "first_run_id": run_id,
                }

        logger.info("Collected %d conversation(s) from chain runs.", len(by_session))
        return list(by_session.values())

    @staticmethod
    def _extract_messages(run: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull the message list from a run's inputs."""
        inp = run.get("inputs") or {}
        msgs = inp.get("messages") or inp.get("input") or []
        if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
            return msgs
        return []

    # ── turn reconstruction ──────────────────────────────────────────

    def _messages_to_turns(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Walk the message list and split into user turns with response + tool calls."""
        turns: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for m in messages:
            role = str(m.get("role") or m.get("type") or "")
            content = self._msg_text(m)
            if role in ("human", "user"):
                if current is not None:
                    turns.append(current)
                current = {"query": content, "response": "", "tool_calls": []}
            elif current is not None:
                if role in ("ai", "assistant"):
                    if content:
                        current["response"] = content  # last ai text wins
                elif role == "tool":
                    name = str(m.get("name") or m.get("tool_name") or "tool")
                    if name not in current["tool_calls"]:
                        current["tool_calls"].append(name)
        if current is not None:
            turns.append(current)
        return [t for t in turns if t["query"].strip()]

    @staticmethod
    def _msg_text(m: dict[str, Any]) -> str:
        """Stringify message content (handles multimodal content lists)."""
        content = m.get("content", "")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("text"):
                    parts.append(str(block["text"]))
            return " ".join(parts)
        return str(content or "")

    # ── evaluation ───────────────────────────────────────────────────

    def _evaluate_conversation(self, conv: dict[str, Any]) -> None:
        turns = self._messages_to_turns(conv["messages"])
        if not turns:
            self.skipped += 1
            return
        n_turns = len(turns)
        for idx, turn in enumerate(turns):
            prompt = self._build_turn_prompt(turns, idx)
            t0 = time.perf_counter()
            try:
                result = self.judge.evaluate(prompt, required_fields=REQUIRED_FIELDS)
            except Exception:
                logger.exception(
                    "Judge call failed for %s turn %d.",
                    conv["session_id"][:12], idx + 1,
                )
                result = None
            elapsed = time.perf_counter() - t0

            self.total_turns += 1
            if result is None:
                self.failed += 1
                continue
            self.succeeded += 1
            self.scores.append(float(result.get("score", 0.0)))
            self.qualities[str(result.get("quality", "fail"))] += 1
            self.results.append({
                "session_id": conv["session_id"],
                "turn_index": idx + 1,
                "total_turns": n_turns,
                "query": turn["query"][:500],
                "response": turn["response"][:800],
                "tool_calls": turn["tool_calls"],
                "quality": result.get("quality"),
                "score": result.get("score"),
                "data_present": result.get("data_present"),
                "context_used": result.get("context_used"),
                "new_flow": result.get("new_flow"),
                "reason": result.get("reason"),
                "judge_seconds": round(elapsed, 2),
                "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })

        logger.info(
            "Conversation %s: %d turns, all judged.", conv["session_id"][:12], n_turns
        )

    def _build_turn_prompt(self, turns: list[dict[str, Any]], focus_idx: int) -> str:
        """Build the judge prompt: last 8 prior turns + the focus turn."""
        window = max(0, focus_idx - 8)
        lines = []
        for i in range(window, focus_idx + 1):
            t = turns[i]
            tool_str = ", ".join(t["tool_calls"]) if t["tool_calls"] else "none"
            resp = (t["response"] or "(no text response)")[:800]
            lines.append(
                f"TURN {i + 1} — USER: {t['query'][:400]}\n"
                f"  TOOLS: {tool_str}\n"
                f"  AGENT: {resp}"
            )
        transcript = "\n\n".join(lines)
        return (
            self.prompt_template
            .replace("{{CONVERSATION}}", transcript)
            .replace("{{TURN_INDEX}}", str(focus_idx + 1))
        )

    # ── output ───────────────────────────────────────────────────────

    def _write_results(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        runs_dir = project_root / RESULTS_DIR
        runs_dir.mkdir(exist_ok=True)

        manifest_path = runs_dir / MANIFEST
        manifest: dict[str, Any] = {"runs": []}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = {"runs": []}

        version = 1
        if manifest.get("runs"):
            version = max(int(r.get("version", 0)) for r in manifest["runs"]) + 1

        out_file = f"multiturn_results_v{version}.jsonl"
        with open(runs_dir / out_file, "w", encoding="utf-8") as f:
            for row in self.results:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        manifest["runs"].append({
            "version": version,
            "file": out_file,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "conversations": self.total_conversations,
            "turns": self.total_turns,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "avg_score": round(sum(self.scores) / len(self.scores), 3) if self.scores else 0.0,
            "quality": dict(self.qualities),
        })
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Wrote %s and updated %s.", out_file, MANIFEST)

    def _print_summary(self) -> None:
        if not self.scores:
            print("\nMulti-turn eval summary: nothing evaluated.")
            return
        avg = sum(self.scores) / len(self.scores)
        summary = (
            "\n=== Multi-Turn Evaluation Summary ===\n"
            f"  Conversations: {self.total_conversations}\n"
            f"  Turns evaluated: {self.total_turns} "
            f"(ok={self.succeeded}, failed={self.failed}, skipped={self.skipped})\n"
            f"  Average score: {avg:.3f}\n"
            f"  Quality: {dict(self.qualities)}"
        )
        print(summary)
        logger.info(summary)
