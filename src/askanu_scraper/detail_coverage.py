"""Read-only V6 detail-page field coverage audit.

The audit deliberately separates source-presence detection from parser output.
It never invokes persistence; discovery collectors receive a dry-run local store
that does not create record or ingestion-run output.
Subplans are parsed into ephemeral evidence only; they are not CommonRecords.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import urljoin, urlparse, urlsplit

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, HttpFetcher
from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.normalizer import normalize_text, now_canberra
from askanu_scraper.common.parser import ParseError
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.courses.collector import CoursesCollector
from askanu_scraper.sources.courses.parser import CoursesParser
from askanu_scraper.sources.jobs import JobsCollector
from askanu_scraper.sources.jobs.parser import JobsParser, normalize_job_url
from askanu_scraper.sources.scholarships import ScholarshipsCollector
from askanu_scraper.sources.scholarships.parser import (
    ScholarshipsParser,
    normalize_scholarship_url,
)
from askanu_scraper.sources.accommodation import (
    FROZEN_ENTITY_COUNT as ACCOMMODATION_FROZEN_COUNT,
    LISTING_URL as ACCOMMODATION_LISTING_URL,
)
from askanu_scraper.sources.accommodation.discovery import AccommodationDiscovery
from askanu_scraper.sources.accommodation.parser import (
    AccommodationParser,
    normalize_accommodation_url,
)
from askanu_scraper.sources.events import EventsCollector
from askanu_scraper.sources.events.parser import EventsParser, normalize_event_url
from askanu_scraper.sources.support import (
    FROZEN_ENTITY_COUNT as SUPPORT_FROZEN_COUNT,
    LISTING_URL as SUPPORT_LISTING_URL,
)
from askanu_scraper.sources.support.discovery import SupportDiscovery
from askanu_scraper.sources.support.parser import SupportParser, normalize_support_url


FIELDS: dict[str, tuple[str, ...]] = {
    "course": (
        "title", "course_code", "academic_year", "career", "units",
        "delivery_mode", "description", "learning_outcomes", "prerequisites",
        "corequisites", "incompatibilities", "assumed_knowledge", "offerings",
        "canonical_url", "provenance",
    ),
    "program": (
        "title", "program_code", "academic_year", "career", "units",
        "duration", "delivery_mode", "overview", "learning_outcomes",
        "program_requirements", "admission_requirements", "prerequisites",
        "minors", "elective_study", "study_options", "canonical_url",
        "provenance",
    ),
    "major": (
        "title", "code", "academic_year", "career", "units", "subplan_type",
        "overview", "learning_outcomes", "requirements", "other_information",
        "canonical_url", "provenance",
    ),
    "minor": (
        "title", "code", "academic_year", "career", "units", "subplan_type",
        "overview", "learning_outcomes", "requirements", "relevant_degrees",
        "canonical_url", "provenance",
    ),
    "specialisation": (
        "title", "code", "academic_year", "career", "units", "subplan_type",
        "overview", "learning_outcomes", "requirements", "relevant_degrees",
        "other_information", "canonical_url", "provenance",
    ),
    "scholarship": (
        "title", "featured", "status", "application_required", "study_stage",
        "student_type", "study_level", "area_of_study", "value",
        "selection_basis", "opening_date", "closing_date", "eligibility",
        "canonical_url", "provenance",
    ),
    "job": (
        "job_id", "title", "category", "employment_types", "location",
        "classification", "salary", "closing_text", "closing_date",
        "closing_at", "status", "summary", "role_requirements",
        "canonical_url", "provenance",
    ),
    "residence": (
        "title", "category", "location", "catering_options", "audiences",
        "advertised_rate", "cost_period", "rooms", "features", "overview",
        "accessibility", "application_text", "application_url", "eligibility",
        "contact", "vacancy_status", "canonical_url", "provenance",
    ),
    "support_service": (
        "title", "category", "purpose", "audiences", "contact", "hours",
        "access", "cost", "topics", "referrals", "canonical_url", "provenance",
    ),
    "event": (
        "title", "event_id", "start_date", "end_date", "start_at", "end_at",
        "timezone", "location", "format", "categories", "tags", "organiser",
        "description", "registration_links", "status", "cancellation_text",
        "canonical_url", "provenance",
    ),
}


@dataclass(frozen=True)
class DetailCandidate:
    entity_class: str
    identifier: str
    url: str
    listing_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass
class FieldCount:
    source_present: int = 0
    captured: int = 0
    missed: int = 0
    representative_misses: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        coverage = (
            round(100 * self.captured / self.source_present, 2)
            if self.source_present
            else None
        )
        return {
            "source_present": self.source_present,
            "captured": self.captured,
            "missed": self.missed,
            "coverage_percent": coverage,
            "representative_misses": list(self.representative_misses),
        }


def _text(node: Tag | None) -> str | None:
    return normalize_text(node.get_text(" ", strip=True)) if node else None


def _section_presence(soup: BeautifulSoup, *labels: str) -> bool:
    """Detect non-empty source sections without consulting parser output."""
    return _section_text(soup, *labels) is not None


def _section_text(soup: BeautifulSoup, *labels: str) -> str | None:
    """Extract an identified section for ephemeral audit evidence."""
    wanted = {label.casefold() for label in labels}
    for heading in soup.find_all(["h2", "h3"]):
        if (_text(heading) or "").casefold() not in wanted:
            continue
        stop_names = {"h1", "h2"}
        if heading.name == "h3":
            stop_names.add("h3")
        parts: list[str] = []
        for sibling in heading.next_siblings:
            name = getattr(sibling, "name", None)
            if name in stop_names:
                break
            if name:
                value = _text(sibling)
                if value and value not in parts:
                    parts.append(value)
        if parts:
            return " ".join(parts)
    return None


def _meta_value(soup: BeautifulSoup, name: str) -> str | None:
    node = soup.find("meta", attrs={"name": name})
    value = normalize_text(str(node.get("content"))) if node and node.get("content") else None
    return None if value is None or value.casefold() in {"none", "null", "n/a"} else value


def _scholarship_value(soup: BeautifulSoup, label: str) -> str | None:
    """Read non-placeholder source text paired with a Scholarship heading."""
    expected = label.casefold()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if (_text(heading) or "").casefold().rstrip(":") != expected:
            continue
        container = heading.parent
        if container is None:
            continue
        while _text(container) == _text(heading) and container.parent is not None:
            container = container.parent
        values: list[str] = []
        value_tags = {"p", "span", "li"}
        for node in container.find_all(value_tags):
            if heading in node.parents:
                continue
            if any(
                parent is not container and parent.name in value_tags
                for parent in node.parents
                if parent is not container.parent
            ):
                continue
            value = _text(node)
            if value and value not in {"-", "–", "—"} and value not in values:
                values.append(value)
        if values:
            return " ".join(values)
    return None


def _scholarship_period(soup: BeautifulSoup) -> str | None:
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if (_text(heading) or "").casefold().rstrip(":") != "application period":
            continue
        container = heading.parent
        period = container.find_next_sibling("p") if container else None
        value = _text(period)
        return None if value in {None, "-", "–", "—"} else value
    return None


def _content_value(record: CommonRecord, label: str) -> str | None:
    prefix = label + ":"
    for line in record.content.splitlines():
        if line.casefold().startswith(prefix.casefold()):
            return line[len(prefix):].strip() or None
    return None


def _has_captured_value(value: object) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, Mapping):
        return any(_has_captured_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_captured_value(item) for item in value)
    return True


def _summary_value(soup: BeautifulSoup, *labels: str) -> str | None:
    wanted = {label.casefold() for label in labels}
    for item in soup.select(".degree-summary li"):
        heading = item.select_one(
            ".degree-summary__code-heading, .degree-summary__requirements-heading"
        )
        heading_text = _text(heading)
        if heading is None or not heading_text or heading_text.casefold() not in wanted:
            continue
        value = item.select_one(
            ".degree-summary__code-text, .tooltip-area"
        )
        if value and _text(value):
            return _text(value)
        item_text = _text(item)
        if item_text:
            remainder = item_text[len(heading_text):].strip()
            if remainder:
                return remainder
    return None


def _table_labels(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2 and _text(cells[0]) and _text(cells[1]):
            values[(_text(cells[0]) or "").casefold()] = _text(cells[1]) or ""
    return values


def _accommodation_presence(
    candidate: DetailCandidate, soup: BeautifulSoup
) -> dict[str, bool]:
    result = {name: False for name in FIELDS["residence"]}
    result["canonical_url"] = result["provenance"] = True
    result["title"] = bool(soup.select_one("h1.banner-title"))
    for field_name in (
        "category", "catering_options", "audiences", "advertised_rate",
    ):
        result[field_name] = candidate.listing_metadata.get(field_name) not in (
            None, "", [], {},
        )
    result["overview"] = _section_presence(soup, "Overview") or bool(
        candidate.listing_metadata.get("listing_description")
    )
    result["features"] = bool(soup.select("#key-features .view-content .d-flex"))
    room_panels = soup.select(".room-overview .tab-content > .tab-pane")
    result["rooms"] = bool(room_panels)
    result["cost_period"] = any(
        "cost" in (_text(node) or "").casefold() for node in soup.find_all("h2")
    )
    result["accessibility"] = _section_presence(soup, "Accessibility")
    application = soup.select_one('.anu-accommodation-footer a[href*="starrezhousing.com"]')
    result["application_text"] = bool(_text(application))
    result["application_url"] = bool(application and application.get("href"))
    result["location"] = _section_presence(soup, "Location")
    result["eligibility"] = _section_presence(soup, "Eligibility")
    result["vacancy_status"] = _section_presence(soup, "Vacancy", "Availability")
    footer = soup.select_one(".anu-accommodation-footer")
    result["contact"] = bool(
        footer
        and footer.select_one(
            'a[href^="mailto:"], a[href^="tel:"], p.text-white strong, p.text-white'
        )
    )
    return result


def _support_presence(
    candidate: DetailCandidate, soup: BeautifulSoup
) -> dict[str, bool]:
    result = {name: False for name in FIELDS["support_service"]}
    result["canonical_url"] = result["provenance"] = True
    main = soup.select_one("main#content, main")
    result["title"] = bool(
        main
        and main.select_one(".elementor-widget-heading h1, .elementor-widget-heading h2")
    )
    for field_name in ("category", "audiences", "cost"):
        result[field_name] = candidate.listing_metadata.get(field_name) not in (
            None, "", [], {},
        )
    result["purpose"] = bool(
        main
        and (
            main.select_one(".elementor-widget-heading + .elementor-widget-text-editor")
            or candidate.listing_metadata.get("listing_description")
        )
    )
    contact = main.select_one(".elementor-global-2660") if main else None
    if contact is None and main is not None:
        contact = next(
            (
                node
                for node in main.select(".elementor-widget-text-editor")
                if "contact" in (_text(node) or "").casefold()
            ),
            None,
        )
    contact_text = _text(contact) or ""
    result["contact"] = bool(
        contact_text
        or candidate.listing_metadata.get("registry_email")
        or (main and main.select_one('a[href^="mailto:"], a[href^="tel:"]'))
    )
    result["hours"] = bool(
        re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
            r"\d{1,2}(?::\d{2})?\s*(?:am|pm))",
            contact_text,
            re.I,
        )
    )
    result["access"] = _section_presence(soup, "Access", "How to access") or bool(
        re.search(
            r"\b(?:book(?:ing)? an appointment|make an appointment|drop[- ]?in|walk[- ]?in)\b",
            _text(main) or "",
            re.I,
        )
    )
    topic_count = 0
    referral_count = 0
    for link in (main.select("a[href]") if main else []):
        href = str(link.get("href", ""))
        absolute = urljoin(candidate.url, href)
        parsed = urlsplit(absolute)
        if (
            parsed.scheme == "https"
            and (parsed.hostname or "").casefold() in {"anusa.com.au", "www.anusa.com.au"}
            and parsed.path.rstrip("/").count("/") >= 3
        ):
            topic_count += 1
        elif (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and parsed.hostname.casefold() not in {"anusa.com.au", "www.anusa.com.au"}
        ):
            referral_count += 1
    result["topics"] = topic_count > 0
    result["referrals"] = referral_count > 0
    return result


def _event_presence(soup: BeautifulSoup) -> dict[str, bool]:
    result = {name: False for name in FIELDS["event"]}
    result["canonical_url"] = result["provenance"] = True
    result["title"] = bool(soup.select_one("h1.page-title span, h1.page-title, h1"))
    article = soup.select_one("article[data-history-node-id]")
    scripts = " ".join(script.get_text(" ", strip=True) for script in soup.select("script"))
    result["event_id"] = bool(
        article
        and str(article.get("data-history-node-id", "")).isdigit()
        and re.search(r'["\']entityId["\']\s*:\s*["\']?\d+', scripts)
    )
    displayed = [
        value
        for node in soup.select(".field-type-datetime li, .field--type-datetime li, time")
        if (value := _text(node))
    ]
    displayed_text = " ".join(displayed)
    result["start_date"] = result["end_date"] = bool(displayed)
    has_time = bool(re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", displayed_text, re.I))
    result["start_at"] = result["end_at"] = has_time
    # Canberra is the normalization contract for this local source; it is not
    # counted as source-present unless the page explicitly publishes a zone.
    result["timezone"] = bool(re.search(r"\b(?:AEST|AEDT|Australia/Canberra)\b", displayed_text))
    selector_map = {
        "location": ".views-field-field-event-location .field-content, .event-location",
        "format": ".field--name-field-event-format, .event-format",
        "categories": ".field--name-field-event-category .field__item, .event-category a",
        "tags": ".field--name-field-tags .field__item, .field--name-field-event-tags .field__item",
        "organiser": ".views-field-field-colleges .field-content, .field--name-field-colleges",
        "description": ".field--name-body.field--type-text-with-summary, .field--name-body",
        "cancellation_text": ".field--name-field-event-status, .event-cancellation, .cancelled, .canceled",
    }
    for field_name, selector in selector_map.items():
        result[field_name] = any(_text(node) for node in soup.select(selector))
    result["location"] = result["location"] or _section_presence(soup, "Location")
    result["format"] = result["format"] or _section_presence(soup, "Format")
    result["organiser"] = result["organiser"] or _section_presence(
        soup, "Presented by"
    )
    page_text = soup.get_text(" ", strip=True)
    result["status"] = result["cancellation_text"] or bool(
        re.search(r"\bcancell?ed\b", page_text, re.I)
    )
    result["registration_links"] = any(
        urlsplit(str(link.get("href", ""))).scheme.casefold() in {"http", "https"}
        and re.search(
            r"\b(register|registration|book tickets?)\b",
            " ".join(
                filter(
                    None,
                    (
                        _text(link),
                        _text(link.parent if isinstance(link.parent, Tag) else None),
                    ),
                )
            ),
            re.I,
        )
        for link in soup.select("a[href]")
    )
    return result


def _source_presence(
    candidate: DetailCandidate, soup: BeautifulSoup
) -> dict[str, bool]:
    entity = candidate.entity_class
    if entity == "residence":
        return _accommodation_presence(candidate, soup)
    if entity == "support_service":
        return _support_presence(candidate, soup)
    if entity == "event":
        return _event_presence(soup)
    result = {name: False for name in FIELDS[entity]}
    result["canonical_url"] = True
    result["provenance"] = True
    result["title"] = bool(
        soup.select_one("h1.intro-title, h1.intro__degree-title, h3.job-title, h1.banner-title")
        or candidate.listing_metadata.get("title")
    )
    tables = _table_labels(soup)

    if entity in {"course", "program", "major", "minor", "specialisation"}:
        result["academic_year"] = bool(re.search(r"/20\d{2}/", candidate.url))
        result["career"] = bool(tables.get("career") or _summary_value(soup, "Academic career"))
        result["units"] = bool(
            tables.get("units")
            or _summary_value(soup, "Unit value", "Minimum", "Total units")
        )
    if entity == "course":
        result["course_code"] = bool(re.search(r"/course/[^/]+$", candidate.url))
        result["delivery_mode"] = bool(
            tables.get("mode of delivery") or _summary_value(soup, "Mode of delivery")
        )
        result["description"] = bool(
            _text(soup.select_one(".course-description"))
            or _meta_value(soup, "course-description")
        )
        result["learning_outcomes"] = _section_presence(soup, "Learning Outcomes")
        requisite_text = _section_text(soup, "Requisite and Incompatibility") or ""
        incompat_marker = re.search(
            r"(?:\b(?:This course is incompatible with|Incompatible with|"
            r"You are not able to enrol in this course if)\b|\bIncompatible:)",
            requisite_text,
            re.IGNORECASE,
        )
        prerequisite_text = (
            requisite_text[:incompat_marker.start()]
            if incompat_marker
            else requisite_text
        )
        result["prerequisites"] = (
            bool(soup.select_one(".prerequisites"))
            or _section_presence(soup, "Prerequisites")
            or bool(
                re.search(
                    r"\bto enrol in this course\b",
                    prerequisite_text,
                    re.I,
                )
            )
        )
        result["corequisites"] = (
            bool(soup.select_one(".corequisites"))
            or _section_presence(soup, "Corequisites")
            or bool(re.search(r"\b(?:co-?requisite|concurrently enrolled)\b", requisite_text, re.I))
        )
        result["incompatibilities"] = bool(soup.select_one(".incompatibilities")) or bool(
            re.search(
                r"(?:\bincompatib|\bnot able to enrol\b)",
                requisite_text,
                re.IGNORECASE,
            )
        )
        result["assumed_knowledge"] = bool(soup.select_one(".assumed-knowledge")) or _section_presence(
            soup, "Assumed Knowledge"
        )
        legacy_rows = soup.select(".offering-data tr:nth-of-type(n+2)")
        tab_menu = soup.select_one(".course-tabs-menu")
        current_year_rows = []
        year_match = re.search(r"/(20\d{2})/", candidate.url)
        if tab_menu is not None and year_match:
            years = re.findall(r"\b20\d{2}\b", tab_menu.get_text(" ", strip=True))
            if year_match.group(1) in years:
                panel = soup.select_one(
                    f"#course-tab-{years.index(year_match.group(1)) + 1}"
                )
                current_year_rows = (
                    panel.select(".table-terms tr:nth-of-type(n+2)") if panel else []
                )
        result["offerings"] = bool(legacy_rows or current_year_rows)
    elif entity == "program":
        result["program_code"] = bool(re.search(r"/program/[^/]+$", candidate.url))
        result["duration"] = bool(tables.get("duration") or _summary_value(soup, "Length", "Duration"))
        result["delivery_mode"] = bool(tables.get("mode of delivery") or _summary_value(soup, "Mode of delivery"))
        result["overview"] = bool(
            _text(soup.select_one(".program-description"))
            or _meta_value(soup, "program-description")
        )
        section_map = {
            "learning_outcomes": ("Learning Outcomes",),
            "program_requirements": ("Program Requirements",),
            "admission_requirements": ("Admission Requirements",),
            "prerequisites": ("Prerequisites",),
            "minors": ("Minors",),
            "elective_study": ("Elective Study",),
            "study_options": ("Study Options",),
        }
        for field_name, labels in section_map.items():
            result[field_name] = _section_presence(soup, *labels)
    elif entity in {"major", "minor", "specialisation"}:
        result["code"] = bool(re.search(rf"/{entity}/[^/]+$", candidate.url))
        result["subplan_type"] = bool(soup.select_one(".intro__degree-type"))
        result["overview"] = bool(soup.select_one(".intro__degree-description"))
        section_map = {
            "learning_outcomes": ("Learning Outcomes",),
            "requirements": ("Requirements",),
            "relevant_degrees": ("Relevant Degrees",),
            "other_information": ("Other Information",),
        }
        for field_name, labels in section_map.items():
            if field_name in result:
                result[field_name] = _section_presence(soup, *labels)
    elif entity == "scholarship":
        source_values = {
            "featured": tables.get("featured"),
            "status": tables.get("status") or _scholarship_value(soup, "Application period"),
            "application_required": tables.get("application requirement") or _scholarship_value(soup, "Application requirement"),
            "study_stage": tables.get("study stage"),
            "student_type": tables.get("student type") or _scholarship_value(soup, "Student type"),
            "study_level": tables.get("study level") or _scholarship_value(soup, "Study level"),
            "area_of_study": tables.get("study area") or tables.get("field of study") or _scholarship_value(soup, "Field of study"),
            "value": tables.get("value") or _scholarship_value(soup, "Value"),
            "selection_basis": tables.get("selection basis") or tables.get("selection bases") or _scholarship_value(soup, "Selection bases"),
        }
        for field_name, value in source_values.items():
            result[field_name] = bool(value and value not in {"-", "–", "—"})
        application_period = _scholarship_period(soup)
        application_closes = tables.get("application closes")

        # Structured ISO dates are source-present only when the source
        # explicitly supplies a calendar year. Yearless ranges such as
        # "04-Sep to 31-Oct" are preserved in canonical content but must not
        # be counted as structured-date evidence because doing so would
        # require inventing a year.
        opening_source = None
        closing_source = application_closes

        if application_period:
            pieces = re.split(
                r"\s+to\s+",
                application_period,
                maxsplit=1,
                flags=re.I,
            )
            if len(pieces) == 2:
                opening_source = normalize_text(pieces[0])
                closing_source = normalize_text(pieces[1])

        explicit_year = re.compile(r"\b(?:19|20)\d{2}\b")

        result["opening_date"] = bool(
            opening_source and explicit_year.search(opening_source)
        )
        result["closing_date"] = bool(
            closing_source and explicit_year.search(closing_source)
        )
        eligibility_node = soup.select_one("#cs_block_3 .text-field, .eligibility")
        result["eligibility"] = bool(_text(eligibility_node))
        for field_name in ("featured", "status", "application_required"):
            if candidate.listing_metadata.get(field_name) is not None:
                result[field_name] = True
        if candidate.listing_metadata.get("application_requirement") is not None:
            result["application_required"] = True
    elif entity == "job":
        listing_map = {
            "job_id": "job_id", "category": "category",
            "employment_types": "employment_types", "location": "location",
            "classification": "classification", "salary": "salary",
            "closing_text": "closing_text", "summary": "summary",
        }
        for field_name, key in listing_map.items():
            value = candidate.listing_metadata.get(key)
            result[field_name] = bool(value) or field_name.casefold() in soup.get_text(" ", strip=True).casefold()
        result["closing_date"] = result["closing_text"]
        result["closing_at"] = result["closing_text"]
        result["status"] = bool(candidate.listing_metadata.get("source_status") or soup.select_one(".job-status, .status"))
        result["role_requirements"] = _section_presence(
            soup, "Requirements", "Selection Criteria", "Essential Criteria"
        )
    return result


def _subplan_values(candidate: DetailCandidate, soup: BeautifulSoup) -> dict[str, object]:
    entity = candidate.entity_class
    name_meta = soup.find("meta", attrs={"name": f"{entity}-name"})
    title = name_meta.get("content") if name_meta else None
    if not title:
        headings = soup.select("h1.intro__degree-title, h1.intro-title")
        title = _text(headings[-1]) if headings else None
    match = re.search(rf"/20(\d{{2}})/{entity}/([^/]+)$", candidate.url)
    year_match = re.search(r"/(20\d{2})/", candidate.url)
    return {
        "title": normalize_text(str(title)) if title else None,
        "code": candidate.identifier if match else None,
        "academic_year": year_match.group(1) if year_match else None,
        "career": _summary_value(soup, "Academic career"),
        "units": _summary_value(soup, "Total units", "Unit value", "Minimum"),
        "subplan_type": _text(soup.select_one(".intro__degree-type")),
        "overview": _text(soup.select_one(".intro__degree-description")),
        "learning_outcomes": _section_text(soup, "Learning Outcomes"),
        "requirements": _section_text(soup, "Requirements"),
        "relevant_degrees": _section_text(soup, "Relevant Degrees"),
        "other_information": _section_text(soup, "Other Information"),
        "canonical_url": candidate.url,
        "provenance": "courses_programs_and_courses",
        "_entity_id": candidate.identifier,
        "_record_id": None,
        "_source_id": "courses_programs_and_courses",
        "_content_hash": None,
    }


def _record_values(candidate: DetailCandidate, record: CommonRecord) -> dict[str, object]:
    metadata = record.metadata_json
    common = {
        "title": record.title,
        "canonical_url": record.canonical_url if record.canonical_url == candidate.url else None,
        "provenance": record.source_id,
        "_entity_id": record.entity_id,
        "_record_id": record.record_id,
        "_source_id": record.source_id,
        "_content_hash": record.content_hash,
    }
    if candidate.entity_class == "course":
        return common | {
            "course_code": metadata.get("course_code"),
            "academic_year": metadata.get("academic_year"), "career": metadata.get("career"),
            "units": metadata.get("units"), "delivery_mode": metadata.get("delivery_mode"),
            "description": _content_value(record, "Description"),
            "learning_outcomes": _content_value(record, "Learning Outcomes"),
            "prerequisites": metadata.get("prerequisites"),
            "corequisites": _content_value(record, "Corequisites"),
            "incompatibilities": metadata.get("incompatibilities"),
            "assumed_knowledge": metadata.get("assumed_knowledge"),
            "offerings": metadata.get("offerings"),
        }
    if candidate.entity_class == "program":
        return common | {
            "program_code": metadata.get("program_code"),
            "academic_year": metadata.get("academic_year"), "career": metadata.get("career"),
            "units": metadata.get("units"), "duration": metadata.get("duration"),
            "delivery_mode": metadata.get("delivery_mode"),
            "overview": _content_value(record, "Overview"),
            "learning_outcomes": metadata.get("learning_outcomes"),
            "program_requirements": _content_value(record, "Program Requirements"),
            "admission_requirements": _content_value(record, "Admission Requirements"),
            "prerequisites": _content_value(record, "Prerequisites"),
            "minors": _content_value(record, "Minors"),
            "elective_study": _content_value(record, "Elective Study"),
            "study_options": _content_value(record, "Study Options"),
        }
    return common | dict(metadata)


class DetailCoverageAuditor:
    """Audit approved candidates without invoking any persistence interface."""

    def __init__(
        self,
        fetcher: BaseFetcher | None = None,
        *,
        min_request_interval_seconds: float = 1.0,
        events_window_start: date = date(2026, 9, 19),
        events_window_days: int = 43,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        if min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be non-negative")
        if not 1 <= events_window_days <= 366:
            raise ValueError("events_window_days must be between 1 and 366")
        self._fetcher = fetcher or HttpFetcher()
        self._interval = min_request_interval_seconds
        self._sleep = sleep_func
        self._events_window_start = events_window_start
        self._events_window_end = events_window_start + timedelta(days=events_window_days - 1)
        self._courses = CoursesParser()
        self._scholarships = ScholarshipsParser()
        self._jobs = JobsParser()
        self._accommodation = AccommodationParser()
        self._support = SupportParser()
        self._events = EventsParser()

    def audit(self, candidates: Sequence[DetailCandidate]) -> dict[str, object]:
        reports: dict[str, dict[str, object]] = {}
        seen: set[tuple[str, str]] = set()
        blocked_classes: set[str] = set()
        last_fetch = False
        for candidate in candidates:
            report = reports.setdefault(candidate.entity_class, {
                "detail_pages_attempted": 0, "detail_pages_fetched": 0,
                "approved_records": 0, "malformed_pages": 0,
                "rejected_records": 0, "duplicate_identities": 0,
                "canonical_mismatches": 0, "parser_exceptions": 0,
                "consecutive_fetch_failures": 0, "stopped_early": False,
                "source_shape_anomalies": [], "rejected_by_reason": {},
                "parsed_records": 0, "outside_window": 0,
                "identity_manifest": [],
                "fields": {name: FieldCount() for name in FIELDS[candidate.entity_class]},
            })
            if candidate.entity_class in blocked_classes:
                continue
            identity = (candidate.entity_class, candidate.identifier)
            if identity in seen:
                report["duplicate_identities"] = int(report["duplicate_identities"]) + 1
                continue
            seen.add(identity)
            report["detail_pages_attempted"] = int(report["detail_pages_attempted"]) + 1
            try:
                self._validate_candidate(candidate)
            except (ParseError, ValueError) as exc:
                report["rejected_records"] = int(report["rejected_records"]) + 1
                report["source_shape_anomalies"].append(f"{candidate.identifier}: {exc}")
                continue
            try:
                if last_fetch and self._interval:
                    self._sleep(self._interval)
                raw = self._fetcher.fetch(candidate.url)
                if not raw or not raw.strip():
                    raise FetchError("empty response body")
                last_fetch = True
                report["consecutive_fetch_failures"] = 0
                report["detail_pages_fetched"] = int(report["detail_pages_fetched"]) + 1
            except FetchError as exc:
                failures = int(report["consecutive_fetch_failures"]) + 1
                report["consecutive_fetch_failures"] = failures
                report["source_shape_anomalies"].append(f"{candidate.identifier}: fetch: {exc}")
                if failures >= 3:
                    report["stopped_early"] = True
                    report["source_shape_anomalies"].append(
                        "detail traversal stopped after three consecutive fetch failures"
                    )
                    blocked_classes.add(candidate.entity_class)
                continue
            soup = BeautifulSoup(raw, "lxml")
            presence = _source_presence(candidate, soup)
            try:
                values = self._extract(candidate, raw, soup)
            except (ParseError, ValueError, IndexError) as exc:
                message = str(exc)
                canonical_failure = "canonical" in message.casefold()
                if canonical_failure:
                    report["rejected_records"] = int(report["rejected_records"]) + 1
                    report["canonical_mismatches"] = int(
                        report["canonical_mismatches"]
                    ) + 1
                else:
                    report["parser_exceptions"] = int(report["parser_exceptions"]) + 1
                    report["malformed_pages"] = int(report["malformed_pages"]) + 1
                report["source_shape_anomalies"].append(f"{candidate.identifier}: parse: {exc}")
                if canonical_failure:
                    # A rejected off-boundary/mismatched page is not an
                    # approved-record field denominator.
                    continue
                values = {}
            if values:
                report["parsed_records"] = int(report["parsed_records"]) + 1
                if candidate.entity_class == "event":
                    event_start = date.fromisoformat(str(values["start_date"]))
                    event_end = date.fromisoformat(str(values["end_date"]))
                    if not (
                        event_start <= self._events_window_end
                        and event_end >= self._events_window_start
                    ):
                        report["outside_window"] = int(report["outside_window"]) + 1
                        reasons = report["rejected_by_reason"]
                        reasons["outside-frozen-window"] = (
                            int(reasons.get("outside-frozen-window", 0)) + 1
                        )
                        continue
                report["approved_records"] = int(report["approved_records"]) + 1
                if presence.get("canonical_url") and not values.get("canonical_url"):
                    report["canonical_mismatches"] = int(
                        report["canonical_mismatches"]
                    ) + 1
                report["identity_manifest"].append(
                    {
                        "entity_id": values.get("_entity_id") or candidate.identifier,
                        "record_id": values.get("_record_id"),
                        "source_id": values.get("_source_id"),
                        "canonical_url": values.get("canonical_url"),
                        "content_hash": values.get("_content_hash"),
                    }
                )
            for name, counter in report["fields"].items():
                if presence.get(name):
                    counter.source_present += 1
                    if _has_captured_value(values.get(name)):
                        counter.captured += 1
                    else:
                        counter.missed += 1
                        if len(counter.representative_misses) < 5:
                            counter.representative_misses.append(
                                f"{candidate.identifier} {candidate.url}"
                            )

        serialised: dict[str, object] = {}
        total_source_present = total_captured = 0
        for entity, report in reports.items():
            fields = {
                name: count.as_dict() for name, count in report["fields"].items()
            }
            entity_source_present = sum(
                int(value["source_present"]) for value in fields.values()
            )
            entity_captured = sum(int(value["captured"]) for value in fields.values())
            total_source_present += entity_source_present
            total_captured += entity_captured
            manifest = sorted(
                report["identity_manifest"],
                key=lambda item: (str(item["source_id"]), str(item["entity_id"])),
            )
            identities = [
                (str(item["source_id"]), str(item["entity_id"])) for item in manifest
            ]
            record_ids = [str(item["record_id"]) for item in manifest if item["record_id"]]
            canonical_urls = [
                str(item["canonical_url"]) for item in manifest if item["canonical_url"]
            ]
            serialised[entity] = report | {
                "fields": fields,
                "identity_manifest": manifest,
                "source_present_fact_numerator": entity_captured,
                "source_present_fact_denominator": entity_source_present,
                "source_present_fact_coverage_percent": (
                    round(100 * entity_captured / entity_source_present, 2)
                    if entity_source_present
                    else None
                ),
                "duplicate_normalized_identity_count": len(identities) - len(set(identities)),
                "duplicate_record_id_count": len(record_ids) - len(set(record_ids)),
                "duplicate_canonical_url_count": (
                    len(canonical_urls) - len(set(canonical_urls))
                ),
            }
        return {
            "captured_at": now_canberra().isoformat(),
            "dry_run": True,
            "production_records_written": 0,
            "migrations_applied": 0,
            "subplans_persisted": 0,
            "pd_documents_fetched": 0,
            "events_window_start": self._events_window_start.isoformat(),
            "events_window_end_inclusive": self._events_window_end.isoformat(),
            "source_present_fact_numerator": total_captured,
            "source_present_fact_denominator": total_source_present,
            "source_present_fact_coverage_percent": (
                round(100 * total_captured / total_source_present, 2)
                if total_source_present
                else None
            ),
            "entity_classes": serialised,
        }

    @staticmethod
    def _validate_candidate(candidate: DetailCandidate) -> None:
        if candidate.entity_class in {"course", "program", "major", "minor", "specialisation"}:
            parsed = urlparse(candidate.url)
            expected = rf"/20\d{{2}}/{candidate.entity_class}/{re.escape(candidate.identifier.lower())}"
            if parsed.scheme != "https" or parsed.netloc != "programsandcourses.anu.edu.au" or re.fullmatch(expected, parsed.path) is None or parsed.query or parsed.fragment:
                raise ValueError("outside approved canonical Courses detail boundary")
        elif candidate.entity_class == "scholarship":
            if normalize_scholarship_url(candidate.url) != candidate.url:
                raise ValueError("non-canonical Scholarship URL")
        elif candidate.entity_class == "job":
            if normalize_job_url(candidate.url) != candidate.url:
                raise ValueError("non-canonical Job URL")
        elif candidate.entity_class == "residence":
            if normalize_accommodation_url(candidate.url) != candidate.url:
                raise ValueError("non-canonical Accommodation URL")
        elif candidate.entity_class == "support_service":
            if normalize_support_url(candidate.url) != candidate.url:
                raise ValueError("non-canonical Support URL")
        elif candidate.entity_class == "event":
            if normalize_event_url(candidate.url) != candidate.url:
                raise ValueError("non-canonical Event URL")
        else:
            raise ValueError("unsupported entity class")

    def _extract(
        self, candidate: DetailCandidate, raw: str, soup: BeautifulSoup
    ) -> dict[str, object]:
        if candidate.entity_class in {"major", "minor", "specialisation"}:
            return _subplan_values(candidate, soup)
        if candidate.entity_class in {"course", "program"}:
            records = self._courses.parse(raw, candidate.url)
        elif candidate.entity_class == "scholarship":
            records = self._scholarships.parse(
                raw, candidate.url, listing_metadata=candidate.listing_metadata
            )
        elif candidate.entity_class == "job":
            records = self._jobs.parse(
                raw, candidate.url, listing_metadata=candidate.listing_metadata
            )
        elif candidate.entity_class == "residence":
            records = self._accommodation.parse(
                raw, candidate.url, listing_metadata=candidate.listing_metadata
            )
        elif candidate.entity_class == "support_service":
            records = self._support.parse(
                raw, candidate.url, listing_metadata=candidate.listing_metadata
            )
        else:
            records = self._events.parse(raw, candidate.url)
        if len(records) != 1:
            raise ParseError(f"expected one parsed detail record, got {len(records)}")
        values = _record_values(candidate, records[0])
        if candidate.entity_class == "job":
            values["role_requirements"] = _section_text(
                soup, "Requirements", "Selection Criteria", "Essential Criteria"
            )
        return values


def _limit_by_class(
    candidates: Sequence[DetailCandidate], limit: int | None
) -> list[DetailCandidate]:
    if limit is None:
        return list(candidates)
    counts: Counter[str] = Counter()
    selected: list[DetailCandidate] = []
    for item in candidates:
        if counts[item.entity_class] < limit:
            selected.append(item)
            counts[item.entity_class] += 1
    return selected


def discover_candidates(
    domain: str,
    *,
    academic_year: str,
    max_listing_pages: int,
    interval: float,
) -> tuple[list[DetailCandidate], dict[str, object]]:
    candidates: list[DetailCandidate] = []
    census: dict[str, object] = {}
    dry_run_store = LocalDataStore(dry_run=True)
    if domain in {"courses", "all"}:
        result = CoursesCollector(
            store=dry_run_store,
            min_request_interval_seconds=interval,
        ).discover_full_catalogue(
            academic_year=academic_year
        )
        if not result.primary_feeds_reconciled:
            raise RuntimeError("Courses primary feeds are unreconciled; detail audit stopped")
        candidates.extend(
            DetailCandidate(item.entity_type.value, item.identifier, item.url)
            for item in result.items
        )
        frozen_counts = {
            "course": 500,
            "program": 393,
            "major": 109,
            "minor": 126,
            "specialisation": 128,
        }
        census["courses"] = {
            "frozen_denominators": frozen_counts,
            "observed_unique": result.counts_by_type,
            "count_drift": {
                key: int(result.counts_by_type.get(key, 0)) - expected
                for key, expected in frozen_counts.items()
            },
            "reconciled": True,
        }
    if domain in {"scholarships", "all"}:
        result = ScholarshipsCollector(
            store=dry_run_store,
            min_request_interval_seconds=interval,
        ).discover_full_listing(
            max_listing_pages=max_listing_pages
        )
        if result.headline_total_count is None:
            raise RuntimeError(
                "Scholarships headline total is missing; detail audit stopped"
            )
        if result.headline_total_count <= 0:
            raise RuntimeError(
                "Scholarships headline total is suspiciously zero; detail audit stopped"
            )
        if result.discovered_candidate_count != result.headline_total_count:
            raise RuntimeError(
                "Scholarships listing is unreconciled: "
                f"headline_total={result.headline_total_count}, "
                f"discovered={result.discovered_candidate_count}; "
                "detail audit stopped"
            )
        candidates.extend(
            DetailCandidate("scholarship", item.url.rsplit("/", 1)[-1], item.url, item.listing_metadata)
            for item in result.candidates
        )
        census["scholarships"] = {
            "prior_frozen_approved_denominator": 379,
            "headline_total": result.headline_total_count,
            "discovered_total": result.discovered_candidate_count,
            "approved_unique": len(result.candidates),
            "approved_count_drift": len(result.candidates) - 379,
            "rejected_count": len(result.rejected_links),
            "duplicate_count": len(result.duplicate_links),
            "rejected_by_reason": result.rejected_by_reason or {},
            "reconciled": True,
        }
    if domain in {"jobs", "all"}:
        result = JobsCollector(
            store=dry_run_store,
            min_request_interval_seconds=interval,
        ).discover_full_listing(
            max_listing_pages=max_listing_pages
        )
        if result.advertised_total_count is None:
            raise RuntimeError(
                "Jobs advertised total is missing; detail audit stopped"
            )
        if result.advertised_total_count <= 0:
            raise RuntimeError(
                "Jobs advertised total is suspiciously zero; detail audit stopped"
            )
        if len(result.candidates) != result.advertised_total_count:
            raise RuntimeError(
                "Jobs listing is unreconciled: "
                f"advertised_total={result.advertised_total_count}, "
                f"approved_unique={len(result.candidates)}; "
                "detail audit stopped"
            )
        candidates.extend(
            DetailCandidate("job", item.url.rsplit("/", 1)[-1], item.url, item.listing_metadata)
            for item in result.candidates
        )
        census["jobs"] = {
            "prior_observed_totals": [55, 50, 57],
            "advertised_total": result.advertised_total_count,
            "approved_unique": len(result.candidates),
            "drift_from_latest_observed_57": result.advertised_total_count - 57,
            "rejected_count": len(result.rejected_links),
            "duplicate_count": len(result.duplicate_links),
            "rejected_by_reason": result.rejected_by_reason or {},
            "reconciled": True,
        }
    if domain in {"accommodation", "all"}:
        listing_raw = HttpFetcher().fetch(ACCOMMODATION_LISTING_URL)
        result = AccommodationDiscovery().discover(
            listing_raw,
            ACCOMMODATION_LISTING_URL,
            max_details=None,
        )
        if result.advertised_total_count is None:
            raise RuntimeError("Accommodation advertised total is missing; detail audit stopped")
        if result.approved_candidate_count != result.advertised_total_count:
            raise RuntimeError("Accommodation listing is unreconciled; detail audit stopped")
        if result.approved_candidate_count != ACCOMMODATION_FROZEN_COUNT:
            raise RuntimeError("Accommodation count differs from the frozen universe")
        candidates.extend(
            DetailCandidate(
                "residence",
                urlsplit(item.url).path.rstrip("/").rsplit("/", 1)[-1],
                item.url,
                item.listing_metadata,
            )
            for item in result.candidates
        )
        census["accommodation"] = {
            "frozen_denominator": ACCOMMODATION_FROZEN_COUNT,
            "advertised_total": result.advertised_total_count,
            "discovered_total": result.discovered_candidate_count,
            "approved_unique": result.approved_candidate_count,
            "rejected_count": len(result.rejected_links),
            "duplicate_count": len(result.duplicate_links),
            "reconciled": True,
        }
        if interval:
            time.sleep(interval)
    if domain in {"support", "all"}:
        listing_raw = HttpFetcher().fetch(SUPPORT_LISTING_URL)
        result = SupportDiscovery().discover(
            listing_raw,
            SUPPORT_LISTING_URL,
            max_details=None,
        )
        if result.approved_candidate_count != SUPPORT_FROZEN_COUNT:
            raise RuntimeError("Support count differs from the frozen registry")
        candidates.extend(
            DetailCandidate(
                "support_service",
                urlsplit(item.url).path.rstrip("/").rsplit("/", 1)[-1],
                item.url,
                item.listing_metadata,
            )
            for item in result.candidates
        )
        census["support"] = {
            "frozen_denominator": SUPPORT_FROZEN_COUNT,
            "discovered_total": result.discovered_candidate_count,
            "approved_unique": result.approved_candidate_count,
            "rejected_count": len(result.rejected_links),
            "duplicate_count": len(result.duplicate_links),
            "reconciled": True,
        }
        if interval:
            time.sleep(interval)
    if domain in {"events", "all"}:
        result = EventsCollector(
            store=dry_run_store,
            min_request_interval_seconds=interval,
        ).discover_full_listing(
            max_listing_pages=max_listing_pages,
            max_details=None,
        )
        if not result.pagination_complete:
            raise RuntimeError("Events listing pagination is incomplete; detail audit stopped")
        if result.unique_link_count <= 0:
            raise RuntimeError("Events listing is suspiciously zero; detail audit stopped")
        candidates.extend(
            DetailCandidate(
                "event",
                urlsplit(item.url).path.rstrip("/").rsplit("/", 1)[-1],
                item.url,
            )
            for item in result.candidates
        )
        census["events"] = {
            "frozen_denominator": 30,
            "raw_cards": result.raw_card_count,
            "unique_links": result.unique_link_count,
            "duplicate_count": len(result.duplicate_links),
            "rejected_by_reason": result.rejected_by_reason,
            "pages_traversed": result.pages_traversed,
            "advertised_last_page": result.advertised_last_page,
            "pagination_complete": True,
            "reconciled": True,
        }
        if interval:
            time.sleep(interval)
    return candidates, census


def _health_classifications(
    report: Mapping[str, object], census: dict[str, object]
) -> dict[str, object]:
    entity_reports = report.get("entity_classes", {})
    if not isinstance(entity_reports, dict):
        return {}
    domain_entities = {
        "courses": ("course", "program", "major", "minor", "specialisation"),
        "scholarships": ("scholarship",),
        "jobs": ("job",),
        "accommodation": ("residence",),
        "support": ("support_service",),
        "events": ("event",),
    }
    health: dict[str, object] = {}
    for domain, entity_names in domain_entities.items():
        selected = [entity_reports[name] for name in entity_names if name in entity_reports]
        if not selected:
            continue
        denominator = 0
        if domain == "courses":
            course_census = census.get("courses", {})
            frozen = course_census.get("frozen_denominators", {}) if isinstance(course_census, dict) else {}
            denominator = sum(int(frozen.get(name, 0)) for name in entity_names)
        elif domain == "scholarships":
            item = census.get("scholarships", {})
            denominator = int(item.get("approved_unique", 0)) if isinstance(item, dict) else 0
        elif domain == "jobs":
            item = census.get("jobs", {})
            denominator = int(item.get("advertised_total", 0)) if isinstance(item, dict) else 0
        elif domain == "accommodation":
            denominator = ACCOMMODATION_FROZEN_COUNT
        elif domain == "support":
            denominator = SUPPORT_FROZEN_COUNT
        else:
            denominator = 30
        numerator = sum(int(item.get("approved_records", 0)) for item in selected)
        field_numerator = sum(
            int(item.get("source_present_fact_numerator", 0)) for item in selected
        )
        field_denominator = sum(
            int(item.get("source_present_fact_denominator", 0)) for item in selected
        )
        entity_coverage = round(100 * numerator / denominator, 2) if denominator else None
        field_coverage = (
            round(100 * field_numerator / field_denominator, 2)
            if field_denominator
            else None
        )
        reasons: list[str] = []
        fetch_shortfall = any(
            int(item.get("detail_pages_fetched", 0))
            < int(item.get("detail_pages_attempted", 0))
            or bool(item.get("stopped_early"))
            for item in selected
        )
        parser_or_identity_failure = any(
            any(
                int(item.get(key, 0)) > 0
                for key in (
                    "parser_exceptions", "canonical_mismatches", "rejected_records",
                    "duplicate_normalized_identity_count", "duplicate_record_id_count",
                    "duplicate_canonical_url_count",
                )
            )
            for item in selected
        )
        if fetch_shortfall:
            reasons.append("one or more approved details could not be fetched")
        if parser_or_identity_failure:
            reasons.append("parser, identity, canonical, or duplicate validation failed")
        if entity_coverage is None or entity_coverage < 99:
            reasons.append("entity coverage is below 99 percent")
        if field_coverage is None or field_coverage < 99:
            reasons.append("source-present fact coverage is below 99 percent")
        if fetch_shortfall and not parser_or_identity_failure:
            status = "FALLBACK_LAST_KNOWN_GOOD"
        elif reasons:
            status = "BLOCKED"
        else:
            status = "GREEN"
        health[domain] = {
            "status": status,
            "entity_numerator": numerator,
            "entity_denominator": denominator,
            "entity_coverage_percent": entity_coverage,
            "source_present_fact_numerator": field_numerator,
            "source_present_fact_denominator": field_denominator,
            "source_present_fact_coverage_percent": field_coverage,
            "reasons": reasons,
        }
    event_health = health.get("events")
    event_census = census.get("events")
    if isinstance(event_health, dict) and isinstance(event_census, dict):
        event_census["current_eligible_count"] = event_health["entity_numerator"]
        event_census["count_drift_from_frozen_30"] = int(
            event_health["entity_numerator"]
        ) - 30
    return health


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only V6 detail field coverage")
    parser.add_argument(
        "--domain",
        choices=(
            "courses", "scholarships", "jobs", "accommodation", "support",
            "events", "all",
        ),
        default="all",
    )
    parser.add_argument("--academic-year", default="2026")
    parser.add_argument("--max-listing-pages", type=int, default=100)
    parser.add_argument("--max-details-per-class", type=int)
    parser.add_argument("--min-request-interval-seconds", type=float, default=1.0)
    parser.add_argument("--events-window-start", default="2026-09-19")
    parser.add_argument("--events-window-days", type=int, default=43)
    parser.add_argument(
        "--output",
        help="Optionally write the same JSON report printed to stdout",
    )
    args = parser.parse_args(argv)
    if args.max_details_per_class is not None and args.max_details_per_class < 1:
        parser.error("--max-details-per-class must be at least 1")
    try:
        events_window_start = date.fromisoformat(args.events_window_start)
    except ValueError:
        parser.error("--events-window-start must be an ISO date")
    if not 1 <= args.events_window_days <= 366:
        parser.error("--events-window-days must be between 1 and 366")
    if args.output and Path(args.output).name == "detail-coverage-evidence.json":
        parser.error("the stale detail-coverage-evidence.json artifact cannot be overwritten")
    try:
        candidates, census = discover_candidates(
            args.domain,
            academic_year=args.academic_year,
            max_listing_pages=args.max_listing_pages,
            interval=args.min_request_interval_seconds,
        )
        selected = _limit_by_class(candidates, args.max_details_per_class)
        report = DetailCoverageAuditor(
            min_request_interval_seconds=args.min_request_interval_seconds,
            events_window_start=events_window_start,
            events_window_days=args.events_window_days,
        ).audit(selected)
        report["entity_census"] = census
        report["domain_health"] = _health_classifications(report, census)
        entity_reports = report.get("entity_classes", {})
        stopped_early = (
            isinstance(entity_reports, dict)
            and any(
                isinstance(value, dict) and bool(value.get("stopped_early"))
                for value in entity_reports.values()
            )
        )
        report["full_detail_traversal"] = (
            args.max_details_per_class is None
            and not stopped_early
        )
        report["selected_detail_pages"] = len(selected)
        blocked = any(
            isinstance(value, dict) and value.get("status") == "BLOCKED"
            for value in report["domain_health"].values()
        )
        fallback = any(
            isinstance(value, dict)
            and value.get("status") == "FALLBACK_LAST_KNOWN_GOOD"
            for value in report["domain_health"].values()
        )
        report["status"] = (
            "BLOCKED" if blocked else "INCOMPLETE" if stopped_early or fallback else "SUCCESS"
        )
        serialized = json.dumps(report, indent=2, sort_keys=True)
        if args.output:
            Path(args.output).write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
        return 1 if blocked or stopped_early or fallback else 0
    except Exception as exc:
        failure = {
            "captured_at": now_canberra().isoformat(), "dry_run": True,
            "production_records_written": 0, "status": "FAILED",
            "error": str(exc)[:500],
        }
        serialized = json.dumps(failure, indent=2, sort_keys=True)
        if args.output:
            Path(args.output).write_text(serialized + "\n", encoding="utf-8")
        print(serialized)
        return 1


if __name__ == "__main__":
    sys.exit(main())
