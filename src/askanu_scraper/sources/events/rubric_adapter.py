"""
Rubric adapter placeholder — DISABLED, PENDING_APPROVAL.

This file exists only to document the known Rubric schema for future
approved integration. No production calls are made here.

Per SOURCE_REGISTRY.md and V3_LOCKED_DECISIONS.md:
- Rubric is PENDING_APPROVAL, non-production.
- No use of undocumented/internal API (getUnifiedSearch or similar) without approved access.
- This adapter is DISABLED by default via the feature flag RUBRIC_ENABLED=false.
- Official ANU Events/calendar (events_anu_official) is the release source
  regardless of Rubric approval status.
"""
from __future__ import annotations

import os

from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.registry import UnapprovedSourceError


RUBRIC_ENABLED = os.getenv("RUBRIC_ENABLED", "false").lower() == "true"


class RubricAdapter:
    """
    Placeholder for future approved Rubric integration.

    Will always raise UnapprovedSourceError in the current bootstrap.
    """

    def collect(self, *args, **kwargs) -> list[CommonRecord]:  # noqa: ANN002
        raise UnapprovedSourceError(
            "Rubric integration is PENDING_APPROVAL and must not be used in production. "
            "See docs/SOURCE_REGISTRY.md and docs/V3_LOCKED_DECISIONS.md."
        )
