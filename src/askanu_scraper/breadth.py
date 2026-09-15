"""Read-only V6 source-universe census command.

This command fetches approved listing/search APIs only. It never fetches detail
pages and uses a dry-run store, so it cannot publish records or ingestion runs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from askanu_scraper.common.normalizer import now_canberra
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.sources.courses.collector import CoursesCollector
from askanu_scraper.sources.jobs import JobsCollector
from askanu_scraper.sources.scholarships import ScholarshipsCollector


def _dry_store() -> LocalDataStore:
    return LocalDataStore(Path(".breadth-read-only"), dry_run=True)


def courses_report(year: str, page_size: int, interval: float) -> dict[str, object]:
    collector = CoursesCollector(
        store=_dry_store(), min_request_interval_seconds=interval
    )
    result = collector.discover_full_catalogue(
        academic_year=year, page_size=page_size
    )
    return {
        "source_id": "courses_programs_and_courses",
        "academic_year": year,
        "unique_by_entity_type": result.counts_by_type,
        "raw_by_entity_type": result.raw_counts_by_type,
        "source_totals_by_feed": result.source_totals,
        "duplicate_count": len(result.duplicate_identities),
        "rejected_count": len(result.rejected_links),
        "source_anomalies": list(result.anomalies),
        "listing_requests": collector.last_run_sanity["request_count"],
        "persistence_scope": ["course", "program"],
        "persisted": False,
    }


def scholarships_report(max_pages: int, interval: float) -> dict[str, object]:
    collector = ScholarshipsCollector(
        store=_dry_store(), min_request_interval_seconds=interval
    )
    result = collector.discover_full_listing(max_listing_pages=max_pages)
    reconciled = (
        result.headline_total_count is not None
        and result.discovered_candidate_count == result.headline_total_count
    )
    return {
        "source_id": "scholarships_anu_finder",
        "headline_total": result.headline_total_count,
        "raw_discovered": result.discovered_candidate_count,
        "approved_unique": len(result.candidates),
        "duplicate_count": len(result.duplicate_links),
        "rejected_count": len(result.rejected_links),
        "rejected_by_reason": result.rejected_by_reason or {},
        "listing_requests": collector.last_run_sanity["listing_request_count"],
        "reconciled": reconciled,
        "persisted": False,
    }


def jobs_report(max_pages: int, interval: float) -> dict[str, object]:
    collector = JobsCollector(
        store=_dry_store(), min_request_interval_seconds=interval
    )
    result = collector.discover_full_listing(max_listing_pages=max_pages)
    reconciled = (
        result.advertised_total_count is not None
        and len(result.candidates) == result.advertised_total_count
    )
    return {
        "source_id": "jobs_anu_search",
        "advertised_total": result.advertised_total_count,
        "raw_discovered": result.discovered_candidate_count,
        "approved_unique": len(result.candidates),
        "duplicate_count": len(result.duplicate_links),
        "rejected_count": len(result.rejected_links),
        "rejected_by_reason": result.rejected_by_reason or {},
        "listing_requests": collector.last_run_sanity["listing_request_count"],
        "reconciled": reconciled,
        "persisted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only V6 breadth census")
    parser.add_argument(
        "--domain",
        choices=("courses", "scholarships", "jobs", "all"),
        default="all",
    )
    parser.add_argument("--academic-year", default="2026")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-listing-pages", type=int, default=100)
    parser.add_argument("--min-request-interval-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    selected = (
        ("courses", "scholarships", "jobs")
        if args.domain == "all"
        else (args.domain,)
    )
    report: dict[str, object] = {
        "captured_at": now_canberra().isoformat(),
        "dry_run": True,
        "details_fetched": False,
        "records_written": False,
    }
    try:
        if "courses" in selected:
            report["courses"] = courses_report(
                args.academic_year,
                args.page_size,
                args.min_request_interval_seconds,
            )
        if "scholarships" in selected:
            report["scholarships"] = scholarships_report(
                args.max_listing_pages,
                args.min_request_interval_seconds,
            )
        if "jobs" in selected:
            report["jobs"] = jobs_report(
                args.max_listing_pages,
                args.min_request_interval_seconds,
            )
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)[:500]
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    reconciled = all(
        not isinstance(report.get(domain), dict)
        or domain == "courses"
        or bool(report[domain].get("reconciled"))  # type: ignore[union-attr]
        for domain in selected
    )
    report["status"] = "SUCCESS" if reconciled else "UNRECONCILED"
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if reconciled else 1


if __name__ == "__main__":
    sys.exit(main())
