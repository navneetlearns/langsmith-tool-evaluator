"""
OpenCode LLM client.

Calls the OpenCode API (OpenAI-compatible) with the evaluation prompt.
Handles JSON response parsing with one retry.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenCodeClient:
    """Client for the OpenCode LLM API (OpenAI-compatible).

    Attributes:
        client: The openai.Client configured for OpenCode.
        model: Model name to use (e.g. 'deepseek-v4-flash').
    """

    _TOOL_SELECTION_FIELDS = {
        "expected_tool", "selected_tool", "score", "reason", "candidate_tools",
    }

    def __init__(self) -> None:
        api_key = os.getenv("OPENCODE_API_KEY", "")
        base_url = os.getenv("OPENCODE_BASE_URL", "")
        self.model = os.getenv("MODEL_NAME", "deepseek-v4-flash")

        if not api_key:
            raise ValueError(
                "OPENCODE_API_KEY is not set. Check your .env file."
            )
        if not base_url:
            raise ValueError(
                "OPENCODE_BASE_URL is not set. Check your .env file."
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        logger.info(
            "OpenCode client ready (model=%s, base_url=%s).",
            self.model,
            base_url,
        )

    def evaluate(
        self,
        prompt: str,
        required_fields: set[str] | None = None,
    ) -> dict[str, Any] | None:
        """Send a prompt to the LLM judge and parse the JSON response.

        Args:
            prompt: The full evaluation prompt (including tool registry, query, etc.).
            required_fields: Fields the parsed JSON must contain. Defaults to the
                tool-selection set (expected_tool, selected_tool, score, reason,
                candidate_tools). Multi-turn evaluation passes its own field set.

        Returns:
            Parsed JSON dict on success, or None if both attempts fail.
        """
        required = required_fields or self._TOOL_SELECTION_FIELDS

        messages = [
            {"role": "system", "content": "You are a precise evaluation judge."},
            {"role": "user", "content": prompt},
        ]

        for attempt in (1, 2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=0.0,
                )

                content = response.choices[0].message.content or ""
                if not content:
                    logger.warning("Empty response from OpenCode (attempt %d).", attempt)
                    continue

                # Strip markdown code fences if present
                content = self._strip_fences(content)

                parsed = json.loads(content)
                validated = self._validate(parsed, required)
                if validated:
                    return validated

                logger.warning(
                    "Invalid JSON structure (attempt %d): %s", attempt, content[:200]
                )

            except json.JSONDecodeError as exc:
                logger.warning(
                    "JSON decode failed (attempt %d): %s", attempt, exc
                )
            except Exception:
                logger.exception(
                    "OpenCode request failed (attempt %d).", attempt
                )

        logger.error("Both OpenCode evaluation attempts failed.")
        return None

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown JSON code fences if present."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[len("```json"):].strip()
        elif text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        return text

    @staticmethod
    def _validate(parsed: dict[str, Any], required: set[str]) -> dict[str, Any] | None:
        """Ensure the response contains all required fields and a valid score.

        Args:
            parsed: The parsed judge response.
            required: Field names that must be present.
        """
        if not required.issubset(parsed.keys()):
            missing = required - parsed.keys()
            logger.warning("Missing fields in judge response: %s", missing)
            return None

        score = parsed.get("score")
        if not isinstance(score, (int, float)) or not (0.0 <= score <= 1.0):
            logger.warning("Invalid score value: %s", score)
            return None

        return parsed
