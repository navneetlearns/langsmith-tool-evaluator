"""
LangSmith client wrapper.

Connects to LangSmith (Cloud or self-hosted) and reads runs from a project
with pagination. All configuration comes from environment variables.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Generator

from langsmith import Client as LangSmithClient

logger = logging.getLogger(__name__)


class LangSmithClientWrapper:
    """Thin wrapper around the LangSmith SDK for reading project runs.

    Attributes:
        client: The underlying langsmith.Client instance.
        project_name: Name of the LangSmith project to read from.
    """

    def __init__(self) -> None:
        api_key = os.getenv("LANGSMITH_API_KEY", "")
        endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        self.project_name = os.getenv("LANGSMITH_PROJECT_NAME", "")

        if not api_key:
            raise ValueError(
                "LANGSMITH_API_KEY is not set. Check your .env file."
            )
        if not self.project_name:
            raise ValueError(
                "LANGSMITH_PROJECT_NAME is not set. Check your .env file."
            )

        self.client = LangSmithClient(
            api_key=api_key,
            api_url=endpoint,
        )
        logger.info(
            "Connected to LangSmith at %s (project=%s)",
            endpoint,
            self.project_name,
        )

    def list_runs(
        self,
        run_type: str | None = None,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> Generator[dict, None, None]:
        """Yield runs from the project with pagination.

        Args:
            run_type: Optional filter — 'chain', 'llm', 'tool', etc.
            limit: Maximum number of runs to fetch. ``None`` = no limit.
            since: Only yield runs created after this datetime.

        Yields:
            Each run as a dictionary.
        """
        try:
            kwargs: dict[str, Any] = {
                "project_name": self.project_name,
                "run_type": run_type,
            }
            if since is not None:
                kwargs["filter"] = f'and(gte(start_time, "{since.isoformat()}"))'
            runs = self.client.list_runs(**kwargs)
            count = 0
            for run in runs:
                if limit is not None and count >= limit:
                    logger.warning("Reached run limit of %d, stopping.", limit)
                    break
                yield run.dict() if hasattr(run, "dict") else run
                count += 1

            logger.info("Fetched %d runs from project '%s'.", count, self.project_name)

        except Exception:
            logger.exception(
                "Failed to list runs for project '%s'.", self.project_name
            )
            raise
