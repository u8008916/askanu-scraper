"""
Fetcher abstractions for the AskANU scraper.

HttpFetcher is the production client; MockFetcher replays local fixtures in
tests and CI without making any real network requests.

Rules:
- User-agent set from SCRAPER_USER_AGENT env var.
- Every production fetch must go through assert_source_allowed() before calling fetch().
- Never bypass login, auth, or paywall controls.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

import requests


class FetchError(Exception):
    """Raised when a fetch attempt fails irrecoverably."""


class BaseFetcher(ABC):
    """Abstract fetcher interface."""

    @abstractmethod
    def fetch(self, url: str) -> str:
        """Fetch *url* and return the raw HTML/text body as a string."""


class HttpFetcher(BaseFetcher):
    """
    Production HTTP fetcher using the requests library.

    Timeout, user-agent, and basic error handling are applied.
    Rate limiting is the responsibility of the caller (collector).
    """

    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        user_agent: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._user_agent = user_agent or os.getenv(
            "SCRAPER_USER_AGENT", "AskANU/0.1"
        )
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self._user_agent})

    def fetch(self, url: str) -> str:
        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            raise FetchError(f"Failed to fetch {url!r}: {exc}") from exc


class MockFetcher(BaseFetcher):
    """
    Fixture-replay fetcher for tests and CI.

    Resolves URLs to local HTML files via a simple mapping.
    Raises FetchError for URLs not present in the map (simulates fetch failure).
    """

    def __init__(self, url_to_fixture: dict[str, str | Path]) -> None:
        """
        Parameters
        ----------
        url_to_fixture:
            Mapping of URL -> path to a local HTML fixture file.
        """
        self._map: dict[str, Path] = {
            url: Path(path) for url, path in url_to_fixture.items()
        }

    def fetch(self, url: str) -> str:
        if url not in self._map:
            raise FetchError(
                f"MockFetcher has no fixture for {url!r}. "
                "Register the URL in the url_to_fixture mapping."
            )
        fixture_path = self._map[url]
        if not fixture_path.exists():
            raise FetchError(
                f"Fixture file not found: {fixture_path}. "
                "Ensure the file exists under fixtures/."
            )
        return fixture_path.read_text(encoding="utf-8")
