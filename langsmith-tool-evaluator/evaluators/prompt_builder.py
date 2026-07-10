"""
Prompt builder.

Loads the tool registry from markdown, builds the evaluation prompt
by substituting template variables in the prompt file.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Tool Registry Parser ────────────────────────────────────────────

class ToolEntry:
    """A single tool from the registry.

    Attributes:
        name: Tool identifier (e.g. 'search_threads').
        family: Functional family (e.g. 'conversation_read').
        enabled: Whether the tool is currently enabled.
        description: Human-readable description of what the tool does.
    """

    def __init__(
        self,
        name: str,
        family: str,
        enabled: bool,
        description: str,
    ) -> None:
        self.name = name
        self.family = family
        self.enabled = enabled
        self.description = description

    def __repr__(self) -> str:
        return f"ToolEntry(name={self.name}, enabled={self.enabled})"

    def format(self) -> str:
        """Format as a single line for the prompt."""
        status = "✅" if self.enabled else "❌"
        return f"- `{self.name}` ({self.family}) {status}: {self.description}"


def load_tool_registry(path: str | os.PathLike | None = None) -> list[ToolEntry]:
    """Parse a markdown tool registry file into structured ToolEntry objects.

    Expects a pipe-delimited table with columns: Tool, Family, Enabled, Description.

    Args:
        path: Path to the markdown file. Defaults to
              ``<project_root>/registry/tool_registry.md``.

    Returns:
        List of ToolEntry objects extracted from the table.
    """
    if path is None:
        # Default to <project_root>/registry/tool_registry.md
        project_root = _find_project_root()
        path = project_root / "registry" / "tool_registry.md"

    path = Path(path)
    if not path.exists():
        logger.warning("Tool registry not found at %s. Returning empty list.", path)
        return []

    raw = path.read_text(encoding="utf-8")
    entries: list[ToolEntry] = []
    in_table = False

    for line in raw.splitlines():
        line = line.strip()

        # Skip empty lines inside tables (common in markdown)
        if not line:
            continue

        # Detect table header
        if line.startswith("|") and "Tool" in line and "Family" in line:
            in_table = True
            continue

        # Skip separator row
        if line.startswith("|") and all(c in "|- " for c in line):
            continue

        # Parse data rows
        if in_table and line.startswith("|"):
            cells = [c.strip() for c in line.split("|")]
            # cells[0] is empty (before first |), cells[1..4] are the columns
            if len(cells) >= 5:
                name_raw = cells[1]
                family = cells[2]
                enabled_raw = cells[3]
                description = cells[4]

                # Clean tool name (remove backticks AND escaped underscores)
                name = name_raw.strip("`").strip().replace("\\_", "_")
                family = family.replace("\\_", "_")
                enabled = "✅" in enabled_raw or "check" in enabled_raw.lower()

                if name and description:
                    entries.append(ToolEntry(
                        name=name,
                        family=family,
                        enabled=enabled,
                        description=description.strip(),
                    ))

            continue

        # End of table: non-empty, non-pipe line after being in the table
        if in_table:
            break

    logger.info("Loaded %d tools from registry at %s.", len(entries), path)
    return entries


def format_registry_for_prompt(entries: list[ToolEntry]) -> str:
    """Format tool entries as a readable block for the prompt."""
    if not entries:
        return "(No tools registered.)"

    lines = ["| # | Tool | Family | Enabled | Description |", "|---|------|--------|---------|-------------|"]
    for i, tool in enumerate(entries, 1):
        status = "✅" if tool.enabled else "❌"
        lines.append(
            f"| {i} | `{tool.name}` | {tool.family} | {status} | {tool.description} |"
        )
    return "\n".join(lines)


# ── Prompt Builder ──────────────────────────────────────────────────

def load_prompt_template(path: str | os.PathLike | None = None) -> str:
    """Load the evaluation prompt template from disk.

    The template contains placeholders like ``{{TOOL_REGISTRY}}``,
    ``{{USER_QUERY}}``, ``{{SELECTED_TOOL}}``, ``{{SELECTED_TOOL_ARGS}}``.

    Args:
        path: Path to the prompt file. Defaults to
              ``<project_root>/prompts/tool_selection_prompt.txt``.

    Returns:
        The raw prompt template string.
    """
    if path is None:
        project_root = _find_project_root()
        path = project_root / "prompts" / "tool_selection_prompt.txt"

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found at {path}")

    return path.read_text(encoding="utf-8")


def build_prompt(
    template: str,
    registry_lines: str,
    query: str,
    selected_tool: str,
    tool_args: str,
) -> str:
    """Substitute variables into the prompt template.

    Args:
        template: Raw prompt template with ``{{...}}`` placeholders.
        registry_lines: Formatted tool registry string.
        query: The user's original query.
        selected_tool: Name of the tool the agent selected.
        tool_args: Stringified tool arguments.

    Returns:
        The complete prompt ready to send to the LLM judge.
    """
    return (
        template.replace("{{TOOL_REGISTRY}}", registry_lines)
        .replace("{{USER_QUERY}}", query)
        .replace("{{SELECTED_TOOL}}", selected_tool)
        .replace("{{SELECTED_TOOL_ARGS}}", tool_args)
    )


# ── Helpers ─────────────────────────────────────────────────────────

def _find_project_root() -> Path:
    """Walk up from cwd until we find a directory with 'evaluators/' or 'registry/'."""
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "registry").is_dir() or (parent / "evaluators").is_dir():
            return parent
    # Fallback: use cwd
    return cwd
