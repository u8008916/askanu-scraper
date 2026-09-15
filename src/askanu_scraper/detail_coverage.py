"""Read-only V6 detail-page field coverage audit.

The audit deliberately separates source-presence detection from parser output.
It never instantiates a data store and therefore cannot write records or runs.
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
from typing import Callable, Mapping, Sequence
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.fetcher import BaseFetcher, FetchError, HttpFetcher
from askanu_scraper.common.models import CommonRecord
from askanu_scraper.common.normalizer import normalize_text, now_canberra
from askanu_scraper.common.parser import ParseError
from askanu_scraper.sources.courses.collector import CoursesCollector
from askanu_scraper.sources.courses.parser import CoursesParser
from askanu_scraper.sources.jobs import JobsCollector
from askanu_scraper.sources.jobs.parser import JobsParser, normalize_job_url
from askanu_scraper.sources.scholarships import ScholarshipsCollector
from askanu_scraper.sources.scholarships.parser import (
    ScholarshipsParser,
    normalize_scholarship_url,
)


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
    wanted = {label.casefold() for label in labels}
    for heading in soup.find_all(["h2", "h3"]):
        if (_text(heading) or "").casefold() not in wanted:
            continue
        for sibling in heading.next_siblings:
            name = getattr(sibling, "name", None)
            if name in {"h1", "h2", "h3"}:
                break
            if name and _text(sibling):
                return True
    return False


def _section_text(soup: BeautifulSoup, *labels: str) -> str | None:
    """Extract an identified section for ephemeral audit evidence."""
    wanted = {label.casefold() for label in labels}
    for heading in soup.find_all(["h2", "h3"]):
        if (_text(heading) or "").casefold() not in wanted:
            continue
        parts: list[str] = []
        for sibling in heading.next_siblings:
            name = getattr(sibling, "name", None)
            if name in {"h1", "h2", "h3"}:
                break
            if name:
                value = _text(sibling)
                if value and value not in parts:
                    parts.append(value)
        return " ".join(parts) or None
    return None


def _content_value(record: CommonRecord, label: str) -> str | None:
    prefix = label + ":"
    for line in record.content.splitlines():
        if line.casefold().startswith(prefix.casefold()):
            return line[len(prefix):].strip() or None
    return None


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


def _source_presence(
    candidate: DetailCandidate, soup: BeautifulSoup
) -> dict[str, bool]:
    entity = candidate.entity_class
    result = {name: False for name in FIELDS[entity]}
    result["canonical_url"] = True
    result["provenance"] = True
    result["title"] = bool(
        soup.select_one("h1.intro-title, h1.intro__degree-title, h3.job-title, h1.banner-title")
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
            soup.select_one(".course-description, meta[name='course-description']")
        )
        result["learning_outcomes"] = _section_presence(soup, "Learning Outcomes")
        requisite_text = _section_text(soup, "Requisite and Incompatibility") or ""
        result["prerequisites"] = (
            bool(soup.select_one(".prerequisites"))
            or _section_presence(soup, "Prerequisites")
            or bool(re.search(r"\bto enrol\b.+?\bcompleted\b", requisite_text, re.I))
        )
        result["corequisites"] = (
            bool(soup.select_one(".corequisites"))
            or _section_presence(soup, "Corequisites")
            or bool(re.search(r"\b(?:co-?requisite|concurrently|must be enrolled)\b", requisite_text, re.I))
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
        result["offerings"] = bool(
            soup.select(".offering-data tr:nth-of-type(n+2), .table-terms tr:nth-of-type(n+2)")
        )
    elif entity == "program":
        result["program_code"] = bool(re.search(r"/program/[^/]+$", candidate.url))
        result["duration"] = bool(tables.get("duration") or _summary_value(soup, "Length", "Duration"))
        result["delivery_mode"] = bool(tables.get("mode of delivery") or _summary_value(soup, "Mode of delivery"))
        result["overview"] = bool(soup.select_one(".program-description, meta[name='program-description']"))
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
        label_map = {
            "featured": ("featured",),
            "status": ("status", "application period"),
            "application_required": ("application requirement",),
            "study_stage": ("study stage",),
            "student_type": ("student type",),
            "study_level": ("study level",),
            "area_of_study": ("study area", "field of study"),
            "value": ("value",),
            "selection_basis": ("selection basis", "selection bases"),
            "opening_date": ("application period", "application opens"),
            "closing_date": ("application period", "application closes"),
        }
        text_lower = soup.get_text(" ", strip=True).casefold()
        for field_name, labels in label_map.items():
            result[field_name] = any(label in tables or label in text_lower for label in labels)
        date_evidence = bool(
            re.search(
                r"\b(?:\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2}|20\d{2}-\d{2}-\d{2})\b",
                soup.get_text(" ", strip=True),
            )
        )
        result["opening_date"] = result["opening_date"] and date_evidence
        result["closing_date"] = result["closing_date"] and date_evidence
        result["eligibility"] = bool(soup.select_one(".eligibility, #cs_block_3"))
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
    }


def _record_values(candidate: DetailCandidate, record: CommonRecord) -> dict[str, object]:
    metadata = record.metadata_json
    common = {
        "title": record.title,
        "canonical_url": record.canonical_url if record.canonical_url == candidate.url else None,
        "provenance": record.source_id,
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
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        if min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be non-negative")
        self._fetcher = fetcher or HttpFetcher()
        self._interval = min_request_interval_seconds
        self._sleep = sleep_func
        self._courses = CoursesParser()
        self._scholarships = ScholarshipsParser()
        self._jobs = JobsParser()

    def audit(self, candidates: Sequence[DetailCandidate]) -> dict[str, object]:
        reports: dict[str, dict[str, object]] = {}
        seen: set[tuple[str, str]] = set()
        last_fetch = False
        for candidate in candidates:
            report = reports.setdefault(candidate.entity_class, {
                "detail_pages_attempted": 0, "detail_pages_fetched": 0,
                "approved_records": 0, "malformed_pages": 0,
                "rejected_records": 0, "duplicate_identities": 0,
                "canonical_mismatches": 0, "parser_exceptions": 0,
                "source_shape_anomalies": [],
                "fields": {name: FieldCount() for name in FIELDS[candidate.entity_class]},
            })
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
                last_fetch = True
                report["detail_pages_fetched"] = int(report["detail_pages_fetched"]) + 1
            except FetchError as exc:
                report["source_shape_anomalies"].append(f"{candidate.identifier}: fetch: {exc}")
                continue
            soup = BeautifulSoup(raw, "lxml")
            presence = _source_presence(candidate, soup)
            try:
                values = self._extract(candidate, raw, soup)
            except (ParseError, ValueError, IndexError) as exc:
                report["parser_exceptions"] = int(report["parser_exceptions"]) + 1
                report["malformed_pages"] = int(report["malformed_pages"]) + 1
                report["source_shape_anomalies"].append(f"{candidate.identifier}: parse: {exc}")
                values = {}
            if values:
                report["approved_records"] = int(report["approved_records"]) + 1
            if presence.get("canonical_url") and not values.get("canonical_url"):
                report["canonical_mismatches"] = int(report["canonical_mismatches"]) + 1
            for name, counter in report["fields"].items():
                if presence.get(name):
                    counter.source_present += 1
                    if values.get(name) not in (None, "", [], {}):
                        counter.captured += 1
                    else:
                        counter.missed += 1
                        if len(counter.representative_misses) < 5:
                            counter.representative_misses.append(
                                f"{candidate.identifier} {candidate.url}"
                            )

        serialised: dict[str, object] = {}
        for entity, report in reports.items():
            serialised[entity] = report | {
                "fields": {name: count.as_dict() for name, count in report["fields"].items()}
            }
        return {
            "captured_at": now_canberra().isoformat(),
            "dry_run": True,
            "production_records_written": 0,
            "migrations_applied": 0,
            "subplans_persisted": 0,
            "pd_documents_fetched": 0,
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
        else:
            records = self._jobs.parse(
                raw, candidate.url, listing_metadata=candidate.listing_metadata
            )
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
    if domain in {"courses", "all"}:
        result = CoursesCollector(min_request_interval_seconds=interval).discover_full_catalogue(
            academic_year=academic_year
        )
        if not result.primary_feeds_reconciled:
            raise RuntimeError("Courses primary feeds are unreconciled; detail audit stopped")
        candidates.extend(
            DetailCandidate(item.entity_type.value, item.identifier, item.url)
            for item in result.items
        )
        census["courses"] = result.counts_by_type
    if domain in {"scholarships", "all"}:
        result = ScholarshipsCollector(min_request_interval_seconds=interval).discover_full_listing(
            max_listing_pages=max_listing_pages
        )
        candidates.extend(
            DetailCandidate("scholarship", item.url.rsplit("/", 1)[-1], item.url, item.listing_metadata)
            for item in result.candidates
        )
        census["scholarships"] = {
            "headline_total": result.headline_total_count,
            "approved_unique": len(result.candidates),
        }
    if domain in {"jobs", "all"}:
        result = JobsCollector(min_request_interval_seconds=interval).discover_full_listing(
            max_listing_pages=max_listing_pages
        )
        candidates.extend(
            DetailCandidate("job", item.url.rsplit("/", 1)[-1], item.url, item.listing_metadata)
            for item in result.candidates
        )
        census["jobs"] = {
            "advertised_total": result.advertised_total_count,
            "approved_unique": len(result.candidates),
        }
    return candidates, census


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only V6 detail field coverage")
    parser.add_argument("--domain", choices=("courses", "scholarships", "jobs", "all"), default="all")
    parser.add_argument("--academic-year", default="2026")
    parser.add_argument("--max-listing-pages", type=int, default=100)
    parser.add_argument("--max-details-per-class", type=int)
    parser.add_argument("--min-request-interval-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.max_details_per_class is not None and args.max_details_per_class < 1:
        parser.error("--max-details-per-class must be at least 1")
    try:
        candidates, census = discover_candidates(
            args.domain,
            academic_year=args.academic_year,
            max_listing_pages=args.max_listing_pages,
            interval=args.min_request_interval_seconds,
        )
        selected = _limit_by_class(candidates, args.max_details_per_class)
        report = DetailCoverageAuditor(
            min_request_interval_seconds=args.min_request_interval_seconds
        ).audit(selected)
        report["entity_census"] = census
        report["full_detail_traversal"] = args.max_details_per_class is None
        report["selected_detail_pages"] = len(selected)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            "captured_at": now_canberra().isoformat(), "dry_run": True,
            "production_records_written": 0, "status": "FAILED",
            "error": str(exc)[:500],
        }, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
