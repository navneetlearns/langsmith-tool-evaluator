"""
Trace parser.

Extracts structured information from a LangSmith run dictionary.
Based on actual schema analysis of real LangSmith traces from
the seller-copilot-agent and evaluators projects.

Key findings from real data:
  - Tool runs: run.name IS the tool name, inputs ARE the args,
    extra.metadata.title has the user query
  - Chain runs: inputs.messages[0].content has the user query,
    child_runs is often null (not populated by list_runs API)
  - LLM runs: generations[0][0].message.kwargs.tool_calls
  - Evaluator runs: inputs.input.messages has the user query,
    inputs.output.messages has AI messages with tool_calls
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ParsedTrace:
    """Structured representation of a single LangSmith run.

    Handles multiple run types (chain, tool, llm) and multiple
    message formats (LangChain serialized, OpenAI API, evaluator).

    Attributes:
        run_id: The LangSmith run UUID.
        user_query: The user's input query string.
        selected_tool: The primary tool name selected (or 'none').
        tool_arguments: Dict or string of tool arguments.
        tool_calls: List of tool-call dicts, each with 'name' and 'arguments'.
        tool_names: Sorted list of unique tool names called.
        final_answer: The final output of the run (if any).
        metadata: Arbitrary metadata dict attached to the run.
        run_type: The LangSmith run type ('chain', 'llm', 'tool', etc.).
        raw: The original run dict (for debugging).
    """

    def __init__(self, run: dict[str, Any]) -> None:
        self.raw = run
        self.run_id: str = str(run.get("id", run.get("run_id", "")))
        self.run_type: str = run.get("run_type", "unknown")
        self.run_name: str = run.get("name", "")

        # Metadata lives in either 'metadata' or 'extra.metadata'
        self.metadata: dict[str, Any] = (
            run.get("metadata")
            or (run.get("extra") or {}).get("metadata", {})
            or {}
        )

        # Extract the user query — try multiple strategies
        self.user_query: str = self._extract_query(run)

        # Extract tool calls — depends on run type and format
        self.tool_calls: list[dict[str, Any]] = self._extract_tool_calls(run)
        self.tool_names: list[str] = sorted(
            {tc["name"] for tc in self.tool_calls}
        )

        # Convenience: get the first/primary tool and its arguments
        self.selected_tool: str = self._get_primary_tool()
        self.tool_arguments: str = self._get_primary_args()

        # Extract final answer
        self.final_answer: str = self._extract_answer(run)

    def __repr__(self) -> str:
        return (
            f"ParsedTrace(run_id={self.run_id[:8]}..., "
            f"type={self.run_type}, "
            f"tool={self.selected_tool}, "
            f"query={self.user_query[:50]})"
        )

    # ── Query Extraction ──────────────────────────────────────────

    def _extract_query(self, run: dict[str, Any]) -> str:
        """Extract the user query by trying known schema locations."""
        inputs = run.get("inputs") or {}
        extra = run.get("extra") or {}

        # Strategy 1: LangChain serialized messages in inputs.messages
        #   Format: [[{lc, type, id, kwargs: {content: "..."}}]]
        q = self._from_lc_messages(inputs.get("messages"))
        if q:
            return q

        # Strategy 2: Simple messages dict in inputs.messages
        #   Format: [{"content": "...", "type": "human", ...}]
        q = self._from_simple_messages(inputs.get("messages"))
        if q:
            return q

        # Strategy 3: Evaluator format — inputs.input.messages
        #   Format: {"input": {"messages": [{"content": "...", "role": "user"}]}}
        inner = inputs.get("input")
        if isinstance(inner, dict):
            q = self._from_role_messages(inner.get("messages"))
            if q:
                return q

        # Strategy 4: extra.metadata.title (used by LangGraph integration)
        meta = extra.get("metadata") or {}
        title = meta.get("title", "")
        if title:
            return title

        # Strategy 5: Direct string values in inputs
        for key in ("question", "query", "input", "user_query", "prompt"):
            val = inputs.get(key)
            if isinstance(val, str) and len(val) > 2:
                return val

        # Strategy 6: First long-ish string value in inputs
        for val in inputs.values():
            if isinstance(val, str) and 3 < len(val) < 2000:
                return val

        return ""

    @staticmethod
    def _from_lc_messages(messages: Any) -> str:
        """Extract from LangChain serialized format.

        [[{lc: 1, type: "constructor", id: [..., "HumanMessage"],
           kwargs: {content: "..."}}]]
        """
        if not isinstance(messages, list) or not messages:
            return ""
        first_group = messages[0]
        if not isinstance(first_group, list) or not first_group:
            return ""
        first_msg = first_group[0]
        if not isinstance(first_msg, dict):
            return ""
        # Check if it's a LangChain serialized message
        if first_msg.get("type") == "constructor":
            msg_id = first_msg.get("id", [])
            msg_type = msg_id[-1] if isinstance(msg_id, list) else ""
            if "HumanMessage" in msg_type or "human" in msg_type.lower():
                kwargs = first_msg.get("kwargs", {}) or {}
                content = kwargs.get("content", "")
                if isinstance(content, str) and content:
                    return content
        return ""

    @staticmethod
    def _from_simple_messages(messages: Any) -> str:
        """Extract from simple message dicts.

        [{"content": "...", "type": "human", ...}]
        """
        if not isinstance(messages, list):
            return ""
        for msg in messages:
            if isinstance(msg, dict):
                msg_type = msg.get("type", "")
                if msg_type in ("human", "user"):
                    content = msg.get("content", "")
                    if isinstance(content, str) and content:
                        return content
        return ""

    @staticmethod
    def _from_role_messages(messages: Any) -> str:
        """Extract from role-based messages (OpenAI format).

        [{"content": "...", "role": "user"}]
        """
        if not isinstance(messages, list):
            return ""
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str) and content:
                    return content
        return ""

    # ── Tool Call Extraction ──────────────────────────────────────

    def _extract_tool_calls(self, run: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract tool calls from all possible locations.

        Priority order:
          1. Tool run: name IS the tool
          2. Child runs of type 'tool'
          3. LLM generations with tool_calls
          4. Evaluator's inputs.output.messages
          5. Run outputs with tool_calls key
        """
        calls: list[dict[str, Any]] = []
        run_type = run.get("run_type")

        # ── Method 1: Tool run ──
        # A run of type "tool" IS itself a tool call.
        # Its name = tool name, its inputs = tool arguments.
        if run_type == "tool":
            name = run.get("name", "unknown")
            inputs = run.get("inputs") or {}
            calls.append({
                "name": name,
                "arguments": _stringify(inputs),
                "arguments_dict": inputs,
            })
            return calls  # Tool runs have exactly one tool call

        # ── Method 2: Child runs of type 'tool' ──
        # Note: child_runs is often null/None (not populated by list_runs API).
        child_runs = run.get("child_runs")
        if child_runs:
            for child in child_runs:
                if isinstance(child, dict) and child.get("run_type") == "tool":
                    name = child.get("name", "unknown")
                    child_inputs = child.get("inputs") or {}
                    calls.append({
                        "name": name,
                        "arguments": _stringify(child_inputs),
                        "arguments_dict": child_inputs,
                    })

        # ── Method 3: LLM generations ──
        # outputs.generations[0][0].message.kwargs.tool_calls
        # or generations[0][0].message.tool_calls
        outputs = run.get("outputs") or {}
        generations = outputs.get("generations")
        if isinstance(generations, list):
            for gen_list in generations:
                if isinstance(gen_list, list):
                    for gen in gen_list:
                        if isinstance(gen, dict):
                            msg = gen.get("message") or {}
                            if isinstance(msg, dict):
                                calls.extend(
                                    self._parse_tool_calls_from_message(msg)
                                )

        # ── Method 4: Evaluator format ──
        # inputs.output.messages[].tool_calls (with name + args)
        inputs = run.get("inputs") or {}
        inp = inputs.get("input") or {}
        out = inputs.get("output") or {}
        for container in (inp, out):
            if isinstance(container, dict):
                msgs = container.get("messages") or []
                for msg in msgs:
                    if isinstance(msg, dict):
                        calls.extend(
                            self._parse_tool_calls_from_message(msg)
                        )

        # ── Method 5: Run outputs with tool_calls key ──
        for key in ("tool_calls", "tools", "function_calls"):
            val = outputs.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        name = item.get("name", item.get("tool", "unknown"))
                        args = item.get("arguments", item.get("args", {}))
                        calls.append({
                            "name": name,
                            "arguments": _stringify(args),
                            "arguments_dict": args if isinstance(args, dict) else {},
                        })

        # ── Method 6: extra.invocation_params.tools ──
        # These are tool *definitions* available to the LLM,
        # not actual calls. Only use if no actual calls found.
        if not calls:
            extra = run.get("extra") or {}
            inv_params = extra.get("invocation_params") or {}
            tools_def = inv_params.get("tools") or []
            for td in tools_def:
                if isinstance(td, dict):
                    fn = td.get("function") or {}
                    name = fn.get("name", "")
                    if name:
                        calls.append({
                            "name": name,
                            "arguments": "{}",
                            "arguments_dict": {},
                            "_from_definitions": True,
                        })
            if calls:
                logger.debug(
                    "No actual tool calls found for run %s; "
                    "using tool definitions as candidates.",
                    str(run.get("id", ""))[:8],
                )

        return calls

    @staticmethod
    def _parse_tool_calls_from_message(
        msg: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract tool calls from a message dict.

        Handles:
          - message.kwargs.tool_calls (LangChain serialized)
          - message.tool_calls (OpenAI format / parsed)
          - message.additional_kwargs.tool_calls
        """
        results: list[dict[str, Any]] = []

        # 1. kwargs.tool_calls (LangChain serialized AI message)
        kwargs = msg.get("kwargs") or {}
        for tc in kwargs.get("tool_calls") or []:
            if isinstance(tc, dict):
                fn = tc.get("function") or {}
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                # Try to parse arguments JSON
                args_dict = _try_parse_json(raw_args)
                results.append({
                    "name": name,
                    "arguments": raw_args,
                    "arguments_dict": args_dict,
                })

        # 2. direct tool_calls (parsed format with name + args)
        for tc in msg.get("tool_calls") or []:
            if isinstance(tc, dict) and tc.get("type") == "tool_call":
                name = tc.get("name", "")
                args = tc.get("args", {})
                results.append({
                    "name": name,
                    "arguments": _stringify(args),
                    "arguments_dict": args if isinstance(args, dict) else {},
                })

        # 3. additional_kwargs.tool_calls (OpenAI raw format)
        addl = msg.get("additional_kwargs") or {}
        for tc in addl.get("tool_calls") or []:
            if isinstance(tc, dict) and isinstance(tc.get("function"), dict):
                fn = tc["function"]
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                args_dict = _try_parse_json(raw_args)
                results.append({
                    "name": name,
                    "arguments": raw_args,
                    "arguments_dict": args_dict,
                })

        return results

    # ── Convenience Getters ───────────────────────────────────────

    def _get_primary_tool(self) -> str:
        """Get the primary selected tool name."""
        if self.tool_calls:
            return self.tool_calls[0].get("name", "unknown")
        return "none"

    def _get_primary_args(self) -> str:
        """Get stringified arguments of the primary tool."""
        if not self.tool_calls:
            return "{}"
        return self.tool_calls[0].get("arguments", "{}")

    # ── Answer Extraction ─────────────────────────────────────────

    def _extract_answer(self, run: dict[str, Any]) -> str:
        """Extract the final answer from the run."""
        outputs = run.get("outputs") or {}

        # Chain / tool run: outputs.output.content (ToolMessage format)
        out = outputs.get("output")
        if isinstance(out, dict):
            content = out.get("content", "")
            if isinstance(content, str) and content:
                return content[:5000]

        # LLM run: generations[0][0].message.kwargs.content
        generations = outputs.get("generations")
        if isinstance(generations, list):
            for gen_list in generations:
                if isinstance(gen_list, list):
                    for gen in gen_list:
                        if isinstance(gen, dict):
                            msg = gen.get("message") or {}
                            if isinstance(msg, dict):
                                kwargs = msg.get("kwargs") or {}
                                content = kwargs.get("content", "")
                                if isinstance(content, str) and content:
                                    return content[:5000]

        # Direct output keys
        for key in ("answer", "response", "result", "text", "content"):
            val = outputs.get(key)
            if isinstance(val, str) and val:
                return val[:5000]

        # Evaluator format: last AI message in inputs.output.messages
        inputs = run.get("inputs") or {}
        for container in (inputs.get("output"), inputs.get("input")):
            if isinstance(container, dict):
                msgs = container.get("messages") or []
                for msg in reversed(msgs):
                    if isinstance(msg, dict):
                        msg_type = msg.get("type", "")
                        if msg_type == "ai":
                            content = msg.get("content", "")
                            if isinstance(content, str) and content:
                                return content[:5000]

        return ""

    # ── Serialisation ─────────────────────────────────────────────

    def to_feedback_dict(self) -> dict[str, Any]:
        """Format for LangSmith feedback comment (JSON-safe)."""
        return {
            "run_type": self.run_type,
            "query": self.user_query,
            "selected_tool": self.selected_tool,
            "all_candidate_tools": self.tool_names,
        }


# ── Helpers ────────────────────────────────────────────────────────

def _stringify(value: Any, max_len: int = 5000) -> str:
    """Safely convert a value to a string, with length cap."""
    if value is None:
        return "{}"
    if isinstance(value, str):
        return value[:max_len]
    if isinstance(value, (list, dict)):
        try:
            s = json.dumps(value, ensure_ascii=False, default=str)
            return s[:max_len]
        except Exception:
            return str(value)[:max_len]
    return str(value)[:max_len]


def _try_parse_json(value: str) -> dict[str, Any]:
    """Try to parse a JSON string; return empty dict on failure."""
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except (json.JSONDecodeError, ValueError):
        return {}
