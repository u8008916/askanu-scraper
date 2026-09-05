"""
BaseParser abstract class for the AskANU scraper.

Each domain provides a concrete implementation of BaseParser that converts
raw HTML into a list of CommonRecord instances.

Rules:
- Never invent fields missing from the source HTML.
- canonical_url must come from the source, not be constructed.
- Missing optional fields should be left as None, not default-filled.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from askanu_scraper.common.models import CommonRecord


class ParseError(Exception):
    """Raised when a parser cannot produce a valid result from source content."""


class BaseParser(ABC):
    """Abstract parser interface for a single approved source."""

    @abstractmethod
    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        """
        Parse *raw_content* (HTML or text from *url*) into normalised records.

        Parameters
        ----------
        raw_content:
            The full HTML/text body returned by the fetcher.
        url:
            The canonical URL from which the content was fetched.

        Returns
        -------
        list[CommonRecord]
            Zero or more normalised records. An empty list is valid when the
            source page contains no structured entities (e.g. a listing page
            with zero results on a slow day). Do NOT return empty list to hide
            parse errors — raise ParseError instead.
        """

    def safe_parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        """
        Call parse() and return results. On ParseError, log and return empty
        list so the collector can preserve last-known-good data.

        Collectors should use safe_parse() in production and parse() in tests.
        """
        try:
            return self.parse(raw_content, url)
        except ParseError as exc:
            # In production: log exc and keep last-known-good
            # Structured logging is wired up by the collector/run harness
            return []
