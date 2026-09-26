"""Integrity checks for the fresh, read-only V7 Day 3 Courses audit."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RAW_AUDIT = ROOT / "fixtures/v7/day3/courses-population-audit-2026.json"
RECONCILIATION = (
    ROOT / "fixtures/v7/day3/courses-population-reconciliation-2026.json"
)


def _payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def test_fresh_course_population_accounting_is_complete_and_read_only() -> None:
    raw = _payload(RAW_AUDIT)
    reconciliation = _payload(RECONCILIATION)
    course = raw["entity_classes"]["course"]
    population = reconciliation["population"]

    assert hashlib.sha256(RAW_AUDIT.read_bytes()).hexdigest() == (
        reconciliation["source_artifact_sha256"]
    )
    assert raw["status"] == "SUCCESS"
    assert raw["dry_run"] is True
    assert raw["full_detail_traversal"] is True
    assert raw["entity_census"]["courses"]["reconciled"] is True
    assert raw["entity_census"]["courses"]["observed_unique"]["course"] == 500
    assert population == {
        "discovered": 500,
        "detail_pages_attempted": 500,
        "fetched": 500,
        "parsed": 500,
        "accepted": 500,
        "explicit_rejects": 0,
        "fetch_failures": 0,
        "parse_failures": 0,
        "validation_failures": 0,
        "unexplained_losses": 0,
        "accounting_equation": (
            "500 discovered = 500 accepted + 0 explicitly accounted "
            "failures/rejects + 0 unexplained"
        ),
    }
    assert course["detail_pages_attempted"] == population["detail_pages_attempted"]
    assert course["detail_pages_fetched"] == population["fetched"]
    assert course["parsed_records"] == population["parsed"]
    assert course["approved_records"] == population["accepted"]
    assert course["rejected_records"] == population["explicit_rejects"]
    assert reconciliation["mutation_accounting"] == {
        "production_records_written": 0,
        "migrations_applied": 0,
        "subplans_persisted": 0,
    }


def test_course_identity_manifest_has_no_duplicates_missing_or_invalid_values() -> None:
    raw = _payload(RAW_AUDIT)
    reconciliation = _payload(RECONCILIATION)
    manifest = raw["entity_classes"]["course"]["identity_manifest"]
    identity_audit = reconciliation["identity_audit"]

    assert len(manifest) == identity_audit["identity_manifest_count"] == 500
    course_codes = [row["entity_id"].removesuffix("_2026") for row in manifest]
    record_ids = [row["record_id"] for row in manifest]
    entity_ids = [row["entity_id"] for row in manifest]
    canonical_urls = [row["canonical_url"] for row in manifest]
    assert _duplicates(course_codes) == identity_audit["duplicate_course_codes"] == []
    assert _duplicates(record_ids) == identity_audit["duplicate_record_ids"] == []
    assert _duplicates(entity_ids) == identity_audit["duplicate_entity_ids"] == []
    assert _duplicates(canonical_urls) == identity_audit["duplicate_canonical_urls"] == []

    assert all(
        re.fullmatch(r"[A-Z]{2,8}[0-9]{4}[A-Z]?", code)
        for code in course_codes
    )
    assert all(
        row["entity_id"] == f"{code}_2026"
        and row["record_id"] == f"courses:course:{code}_2026"
        and row["canonical_url"]
        == f"https://programsandcourses.anu.edu.au/2026/course/{code.casefold()}"
        and row["source_id"] == "courses_programs_and_courses"
        for row, code in zip(manifest, course_codes, strict=True)
    )
    for field in (
        "missing_course_codes",
        "missing_record_ids",
        "missing_entity_ids",
        "missing_canonical_urls",
        "invalid_course_codes",
        "invalid_record_ids",
        "invalid_entity_ids",
        "invalid_canonical_urls",
    ):
        assert identity_audit[field] == []


def test_fresh_course_count_is_compared_with_but_not_derived_from_day16() -> None:
    reconciliation = _payload(RECONCILIATION)

    assert reconciliation["observed_academic_years"] == ["2026"]
    assert reconciliation["day16_comparison"] == {
        "frozen_course_count": 500,
        "fresh_course_count": 500,
        "count_drift": 0,
        "interpretation": (
            "No count drift was observed; the fresh audit, not the frozen "
            "denominator, is the current evidence."
        ),
    }
