"""Fixture-safe catalogue discovery for ANU Programs & Courses."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from askanu_scraper.common.normalizer import normalize_url


class CatalogueEntityType(str, Enum):
    """Entity types exposed by the approved Programs & Courses catalogue."""

    COURSE = "course"
    PROGRAM = "program"
    MAJOR = "major"
    MINOR = "minor"
    SPECIALISATION = "specialisation"


PERSISTED_ENTITY_TYPES = frozenset(
    {CatalogueEntityType.COURSE, CatalogueEntityType.PROGRAM}
)


@dataclass(frozen=True)
class CatalogueItem:
    """One classified catalogue link; not a normalized persisted record."""

    entity_type: CatalogueEntityType
    identifier: str
    academic_year: str
    url: str

    @property
    def discovery_id(self) -> str:
        """Return a deterministic identity used only for discovery dedupe."""
        return f"{self.entity_type.value}:{self.identifier}_{self.academic_year}"


@dataclass(frozen=True)
class CatalogueDiscoveryResult:
    """Deterministic discovery output and pre-ingestion sanity evidence."""

    items: tuple[CatalogueItem, ...]
    counts_by_type: dict[str, int]
    duplicate_identities: tuple[str, ...]
    rejected_links: tuple[str, ...]

    @property
    def persisted_candidates(self) -> tuple[CatalogueItem, ...]:
        """Return only entities currently supported by schema v1."""
        return tuple(
            item for item in self.items
            if item.entity_type in PERSISTED_ENTITY_TYPES
        )


class CoursesCatalogueDiscovery:
    """Discover approved detail links without fetching their target pages."""

    _DETAIL_PATH = re.compile(
        r"^/(?P<year>\d{4})/"
        r"(?P<entity_type>course|program|major|minor|specialisation)/"
        r"(?P<identifier>[^/]+?)/?$",
        re.IGNORECASE,
    )

    def discover(
        self,
        html: str,
        catalogue_url: str,
        canonical_root: str,
    ) -> CatalogueDiscoveryResult:
        """Classify, normalize and deduplicate detail links in source order."""
        soup = BeautifulSoup(html, "lxml")
        approved = urlparse(canonical_root)
        seen: set[str] = set()
        items: list[CatalogueItem] = []
        duplicates: list[str] = []
        rejected: list[str] = []

        for anchor in soup.find_all("a", href=True):
            raw_href = str(anchor.get("href", "")).strip()
            absolute_url = normalize_url(urljoin(catalogue_url, raw_href))
            if absolute_url is None:
                continue

            parsed = urlparse(absolute_url)
            if (
                parsed.scheme != approved.scheme
                or parsed.netloc != approved.netloc
            ):
                rejected.append(absolute_url)
                continue

            match = self._DETAIL_PATH.fullmatch(parsed.path)
            if match is None:
                rejected.append(absolute_url)
                continue

            entity_type = CatalogueEntityType(
                match.group("entity_type").lower()
            )
            identifier = unquote(match.group("identifier")).strip().upper()
            if not identifier:
                rejected.append(absolute_url)
                continue

            item = CatalogueItem(
                entity_type=entity_type,
                identifier=identifier,
                academic_year=match.group("year"),
                url=absolute_url,
            )
            if item.discovery_id in seen:
                duplicates.append(item.discovery_id)
                continue

            seen.add(item.discovery_id)
            items.append(item)

        counts = Counter(item.entity_type.value for item in items)
        return CatalogueDiscoveryResult(
            items=tuple(items),
            counts_by_type={
                entity_type.value: counts[entity_type.value]
                for entity_type in CatalogueEntityType
            },
            duplicate_identities=tuple(duplicates),
            rejected_links=tuple(rejected),
        )

    def discover_api_payload(
        self,
        payload: dict[str, object],
        *,
        entity_type: str,
        canonical_root: str,
    ) -> CatalogueDiscoveryResult:
        """Convert one bounded live catalogue API payload into discovery items."""
        try:
            requested_type = CatalogueEntityType(entity_type.lower())
        except ValueError as exc:
            raise ValueError(
                f"Unsupported catalogue API entity type: {entity_type!r}"
            ) from exc

        if requested_type not in PERSISTED_ENTITY_TYPES:
            raise ValueError(
                "Live API persistence is only supported for course/program"
            )

        raw_items = payload.get("Items")
        if not isinstance(raw_items, list):
            raise ValueError("Catalogue API payload must contain an Items list")

        seen: set[str] = set()
        items: list[CatalogueItem] = []
        duplicates: list[str] = []
        rejected: list[str] = []

        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                rejected.append(f"api-item:{index}")
                continue

            if requested_type == CatalogueEntityType.COURSE:
                raw_identifier = raw_item.get("CourseCode")
                raw_year = raw_item.get("Year")

                if not isinstance(raw_identifier, str):
                    rejected.append(f"api-item:{index}")
                    continue

                identifier = re.sub(r"\s+", "", raw_identifier).upper()

                if re.fullmatch(r"[A-Z]{4}\d{4}[A-Z]?", identifier) is None:
                    rejected.append(f"api-item:{index}")
                    continue

            else:
                raw_identifier = raw_item.get("AcademicPlanCode")
                raw_year = raw_item.get("ProgramAcademicYear")

                if not isinstance(raw_identifier, str):
                    rejected.append(f"api-item:{index}")
                    continue

                identifier = raw_identifier.strip().upper()

                if (
                    not identifier
                    or "/" in identifier
                    or "\\" in identifier
                ):
                    rejected.append(f"api-item:{index}")
                    continue

            year = str(raw_year).strip()

            if re.fullmatch(r"\d{4}", year) is None:
                rejected.append(f"api-item:{index}")
                continue

            canonical_url = normalize_url(
                urljoin(
                    canonical_root,
                    f"{year}/{requested_type.value}/{identifier}",
                )
            )

            if canonical_url is None:
                rejected.append(f"api-item:{index}")
                continue

            item = CatalogueItem(
                entity_type=requested_type,
                identifier=identifier,
                academic_year=year,
                url=canonical_url,
            )

            if item.discovery_id in seen:
                duplicates.append(item.discovery_id)
                continue

            seen.add(item.discovery_id)
            items.append(item)

        counts = Counter(item.entity_type.value for item in items)

        return CatalogueDiscoveryResult(
            items=tuple(items),
            counts_by_type={
                known_type.value: counts[known_type.value]
                for known_type in CatalogueEntityType
            },
            duplicate_identities=tuple(duplicates),
            rejected_links=tuple(rejected),
        )
