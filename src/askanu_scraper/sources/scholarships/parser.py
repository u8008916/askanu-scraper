"""Parse approved public ANU scholarship detail pages."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import (
    make_content_hash,
    normalize_text,
    normalize_url,
    now_canberra,
    parse_date_safe,
)
from askanu_scraper.common.parser import BaseParser, ParseError


SOURCE_ID = "scholarships_anu_finder"
DETAIL_HOST = "study.anu.edu.au"
DETAIL_PATH_RE = re.compile(
    r"^/scholarships/find-scholarship/([a-z0-9]+(?:-[a-z0-9]+)*)/?$"
)


def normalize_scholarship_url(url: str) -> str:
    """Validate a detail URL and remove query, fragment, and trailing slash."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    match = DETAIL_PATH_RE.fullmatch(path)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ParseError("Scholarship canonical URL has an invalid port") from exc
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != DETAIL_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or match is None
    ):
        raise ParseError(
            "Scholarship canonical URL is outside the approved detail boundary"
        )

    return urlunparse(("https", DETAIL_HOST, path, "", "", ""))


def scholarship_identity(url: str) -> tuple[str, str]:
    """Return the source-supported slug and stable record ID for a detail URL."""
    canonical_url = normalize_scholarship_url(url)
    match = DETAIL_PATH_RE.fullmatch(urlparse(canonical_url).path)
    if match is None:  # Defensive: normalization already requires this shape.
        raise ParseError("Scholarship URL has no stable source slug")
    entity_id = match.group(1)
    return entity_id, f"scholarships:scholarship:{entity_id}"


def _text(node: Tag | None) -> str | None:
    if node is None:
        return None
    return normalize_text(node.get_text(" ", strip=True))


def _as_text(value: object) -> str | None:
    return normalize_text(value) if isinstance(value, str) else None


def _optional(value: str | None) -> str | None:
    """Treat source placeholder dashes as absent evidence."""
    normalized = normalize_text(value)
    return None if normalized in {None, "-", "–", "—"} else normalized


def _table_values(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        label = _text(cells[0])
        value = _text(cells[1])
        if label and value:
            values[label.casefold().rstrip(":")] = value
    return values


def _find_heading(soup: BeautifulSoup, label: str) -> Tag | None:
    expected = label.casefold()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        value = _text(heading)
        if value is not None and value.casefold().rstrip(":") == expected:
            return heading
    return None


def _current_detail_value(soup: BeautifulSoup, label: str) -> str | None:
    """Read a value paired with a heading in the current ANU detail markup."""
    heading = _find_heading(soup, label)
    if heading is None:
        return None

    if heading.parent is not None and heading.parent.name == "td":
        return _text(heading.parent.find_next_sibling("td"))

    container = heading.parent
    if container is None:
        return None
    if _text(container) == _text(heading) and container.parent is not None:
        container = container.parent

    values = [
        value
        for child in container.find_all(["p", "span"], recursive=False)
        if (value := _text(child))
    ]
    return normalize_text(" ".join(values)) if values else None


def _section_text(soup: BeautifulSoup, *, current_id: str, legacy: str) -> str | None:
    current = soup.select_one(f"#{current_id} .text-field")
    if current is not None:
        return _text(current)

    section = soup.select_one(legacy)
    if section is None:
        return None
    parts = [
        value
        for node in section.find_all(["p", "li"])
        if (value := _text(node))
    ]
    return normalize_text(" ".join(parts)) if parts else None


def _canonical_url(soup: BeautifulSoup, fetched_url: str) -> str:
    candidates: list[str] = []
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if isinstance(canonical, Tag) and canonical.get("href"):
        candidates.append(str(canonical["href"]))

    explicit = soup.select_one(".canonical-url a[href]")
    if isinstance(explicit, Tag):
        candidates.append(str(explicit["href"]))

    candidates.append(fetched_url)
    for candidate in candidates:
        normalized = normalize_url(candidate)
        if normalized is None:
            continue
        try:
            canonical_url = normalize_scholarship_url(normalized)
        except ParseError:
            continue
        return canonical_url
    raise ParseError("Scholarship page has no approved canonical detail URL")


def _parse_yes_no(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.casefold()
    if normalized in {"yes", "true", "featured"}:
        return True
    if normalized in {"no", "false", "not featured"}:
        return False
    return None


def _period_dates(
    application_period: str | None,
    application_closes: str | None,
) -> tuple[str | None, str | None, datetime | None, datetime | None]:
    opens_text: str | None = None
    closes_text = application_closes
    if application_period:
        pieces = re.split(r"\s+to\s+", application_period, maxsplit=1, flags=re.I)
        if len(pieces) == 2:
            opens_text = normalize_text(pieces[0])
            closes_text = normalize_text(pieces[1])

    return (
        opens_text,
        closes_text,
        parse_date_safe(opens_text),
        parse_date_safe(closes_text),
    )


def _application_required(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.casefold()
    if "no application is required" in normalized or "automatic consideration" in normalized:
        return False
    if "application is required" in normalized or "requires application" in normalized:
        return True
    return None


def _filter_values(value: str | None, known_options: tuple[str, ...]) -> list[str]:
    """Return source-backed filter values without guessing comma boundaries."""
    normalized = _optional(value)
    if normalized is None:
        return []
    matches = [
        (normalized.casefold().find(option.casefold()), option)
        for option in known_options
        if option.casefold() in normalized.casefold()
    ]
    if matches:
        return [option for _position, option in sorted(matches)]
    return [normalized]


STUDY_STAGE_OPTIONS = ("Future study", "Current study", "Alumni")
STUDENT_TYPE_OPTIONS = ("Domestic", "International")
STUDY_LEVEL_OPTIONS = (
    "Undergraduate/Bachelor",
    "Honours",
    "Postgraduate/Masters, and Graduate certificate",
    "Postgraduate research (HDR)",
)
AREA_OF_STUDY_OPTIONS = (
    "Arts & social sciences",
    "Business & economics",
    "Health, medicine & psychology",
    "Law, governance & policy",
    "Security, international affairs & Asia-Pacific studies",
    "Science, technology, engineering & mathematics",
)


class ScholarshipsParser(BaseParser):
    """Normalize one scholarship detail page into the shared record contract."""
    SOURCE_ID = SOURCE_ID

    def parse(
        self,
        raw_content: str,
        url: str,
        *,
        listing_metadata: Mapping[str, object] | None = None,
    ) -> list[CommonRecord]:
        soup = BeautifulSoup(raw_content, "lxml")
        canonical_url = _canonical_url(soup, url)
        entity_id, record_id = scholarship_identity(canonical_url)

        title = _text(
            soup.select_one("h1.banner-title")
            or soup.select_one(".scholarship-detail h1.intro-title")
            or soup.select_one("h1.intro-title")
        )
        if title is None:
            raise ParseError("Scholarship title is missing")

        table = _table_values(soup)
        evidence = dict(listing_metadata or {})
        status = _optional(table.get("status")) or _as_text(evidence.get("status"))

        featured = _parse_yes_no(table.get("featured"))
        if featured is None and isinstance(evidence.get("featured"), bool):
            featured = bool(evidence["featured"])

        application_requirement = _optional(
            table.get("application requirement")
            or _current_detail_value(soup, "Application requirement")
            or _as_text(evidence.get("application_requirement"))
        )
        scholarship_type = _optional(
            table.get("scholarship type")
            or _current_detail_value(soup, "Scholarship type")
        )
        study_stage = _optional(table.get("study stage"))
        study_type = _optional(table.get("study type"))
        student_type = _optional(
            table.get("student type") or _current_detail_value(soup, "Student type")
        )
        study_level = _optional(
            table.get("study level") or _current_detail_value(soup, "Study level")
        )
        study_area = _optional(
            table.get("study area")
            or table.get("field of study")
            or _current_detail_value(soup, "Field of study")
        )
        value = _optional(table.get("value") or _current_detail_value(soup, "Value"))
        selection_basis = _optional(
            table.get("selection basis")
            or table.get("selection bases")
            or _current_detail_value(soup, "Selection bases")
        )

        application_period = None
        period_heading = _find_heading(soup, "Application period")
        if period_heading is not None and period_heading.parent is not None:
            status = _optional(_text(period_heading.parent.find("span"))) or status
            application_period = _optional(
                _text(period_heading.parent.find_next_sibling("p"))
            )

        raw_closes = _optional(table.get("application closes"))
        opens_text, closes_text, opening_datetime, closing_datetime = _period_dates(
            application_period,
            raw_closes,
        )
        description = _section_text(
            soup, current_id="cs_block_2", legacy=".scholarship-description"
        )
        eligibility = _section_text(
            soup, current_id="cs_block_3", legacy=".eligibility"
        )

        application_required = _application_required(application_requirement)
        metadata: dict[str, object] = {
            "entity_type": "scholarship",
            "featured": featured,
            "status": status,
            "application_required": application_required,
            "study_stage": _filter_values(study_stage, STUDY_STAGE_OPTIONS),
            "student_type": _filter_values(student_type, STUDENT_TYPE_OPTIONS),
            "study_level": _filter_values(study_level, STUDY_LEVEL_OPTIONS),
            "area_of_study": _filter_values(study_area, AREA_OF_STUDY_OPTIONS),
            "value": value,
            "selection_basis": selection_basis,
            "opening_date": (
                opening_datetime.date().isoformat() if opening_datetime else None
            ),
            "closing_date": (
                closing_datetime.date().isoformat() if closing_datetime else None
            ),
            "eligibility": eligibility,
        }
        content_fields = (
            ("Title", title),
            ("Status", status),
            (
                "Featured",
                "Yes" if featured is True else "No" if featured is False else None,
            ),
            ("Application Requirement", application_requirement),
            ("Scholarship Type", scholarship_type),
            ("Study Stage", study_stage),
            ("Study Type", study_type),
            ("Student Type", student_type),
            ("Study Level", study_level),
            ("Study Area", study_area),
            ("Value", value),
            ("Selection Basis", selection_basis),
            ("Application Period", application_period),
            ("Application Opens", opens_text),
            ("Application Closes", closes_text),
            ("Description", description),
            ("Eligibility", eligibility),
        )
        content = "\n".join(
            f"{label}: {value}" for label, value in content_fields if value is not None
        )

        record = CommonRecord(
            record_id=record_id,
            source_id=SOURCE_ID,
            entity_id=entity_id,
            domain=Domain.SCHOLARSHIPS,
            title=title,
            content=content,
            canonical_url=canonical_url,
            # An application window is not the record's general validity period.
            effective_from=None,
            effective_to=None,
            collected_at=now_canberra(),
            last_seen_at=now_canberra(),
            content_hash=make_content_hash(content),
            metadata_json=metadata,
        )
        return [record]
