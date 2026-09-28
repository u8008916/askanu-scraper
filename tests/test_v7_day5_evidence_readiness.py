"""V7 Day 5 Courses and Scholarships producer-evidence checkpoint."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from askanu_scraper.common.models import Domain
from askanu_scraper.common.search_metadata import build_resolver_search_metadata
from askanu_scraper.common.v7_contract import get_v7_producer_contracts
from askanu_scraper.sources.courses.parser import CoursesParser
from askanu_scraper.sources.scholarships.parser import ScholarshipsParser


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/v7/day5/courses-scholarships-evidence.json"
COURSE_AUDIT = ROOT / "fixtures/v7/day3/courses-population-audit-2026.json"
COURSE_RECONCILIATION = (
    ROOT / "fixtures/v7/day3/courses-population-reconciliation-2026.json"
)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _contract(entity_type: str):
    return next(
        item
        for item in get_v7_producer_contracts()
        if item.entity_type == entity_type
    )


def _scholarship(fixture: str, *, status: str):
    urls = {
        "anu_scholarship_missing_deadline_sample.html": (
            "https://study.anu.edu.au/scholarships/find-scholarship/start-life"
        ),
        "anu_humanitarian_scholarship_sample.html": (
            "https://study.anu.edu.au/scholarships/find-scholarship/"
            "anu-humanitarian-scholarship"
        ),
    }
    return ScholarshipsParser().parse(
        (ROOT / "fixtures/scholarships" / fixture).read_text(encoding="utf-8"),
        urls[fixture],
        listing_metadata={"featured": False, "status": status},
    )[0]


def test_manifest_is_offline_read_only_and_keeps_cross_repo_gate_honest() -> None:
    manifest = _manifest()

    assert manifest["contract_version"] == (
        "v7-day5-courses-scholarships-evidence-v2"
    )
    assert manifest["parent_scraper_sha"] == (
        "79f939a7dfbd36e7321d4b20e31b3255eb9d6c46"
    )
    assert manifest["network_calls_allowed"] is False
    assert manifest["production_writes_allowed"] is False
    cross_repo = manifest["cross_repo"]
    assert cross_repo["carmen_day5_sha"] == (
        "75c017ba7db3551e74a4326afd514bd26d898573"
    )
    assert cross_repo["consumer_matrix_status"] == "FAIL_CONSUMER_ALIGNMENT"
    assert cross_repo["course_paths_checked"] == 17
    assert cross_repo["scholarship_paths_checked"] == 21
    assert cross_repo["structured_matches"] == 31
    assert cross_repo["content_only_approved_matches"] == 2
    assert cross_repo["shape_mismatches"] == 1
    assert cross_repo["semantic_mismatches"] == 4
    assert cross_repo["producer_paths_materially_unconsumed"] == 1
    assert cross_repo["consumer_claims_without_producer_evidence"] == 0
    assert (
        cross_repo["structured_matches"]
        + cross_repo["content_only_approved_matches"]
        + cross_repo["shape_mismatches"]
        + cross_repo["semantic_mismatches"]
        == cross_repo["course_paths_checked"]
        + cross_repo["scholarship_paths_checked"]
    )
    assert cross_repo["identity_provenance"] == "FAIL"
    assert cross_repo["course_year"] == "PASS"
    assert cross_repo["comp2120"] == "FAIL"
    assert cross_repo["scholarship_missing_date"] == "PASS"
    assert cross_repo["scholarship_eligibility_boundary"] == "PASS"


def test_cross_repo_mismatches_are_classified_at_the_consumer_layer() -> None:
    cross_repo = _manifest()["cross_repo"]
    mismatches = cross_repo["mismatches"]

    assert len(mismatches) == 5
    assert Counter(item["classification"] for item in mismatches) == {
        "CONSUMER_SHAPE_DEFECT": 1,
        "CONSUMER_SEMANTIC_DEFECT": 4,
    }
    assert {item["producer_path"] for item in mismatches} == {
        "canonical_url",
        "content.Description",
        "content.Corequisites",
        "metadata_json.status",
        "metadata_json.study_level",
    }
    assert all(item["owner"] == "askanu-rag" for item in mismatches)
    assert all(item["canonical_content_impact"] == "none" for item in mismatches)
    assert all(item["hash_impact"] == "none" for item in mismatches)
    assert all(item["retrieval_unit_impact"] == "none" for item in mismatches)
    assert all(item["index_embedding_impact"] == "none" for item in mismatches)


def test_course_and_scholarship_matrices_match_frozen_producer_contracts() -> None:
    manifest = _manifest()

    for key, entity_type in (("course", "course"), ("scholarship", "scholarship")):
        expected = manifest[key]
        contract = _contract(entity_type)
        assert expected["source_id"] in contract.source_ids
        assert expected["structured_paths"] == list(contract.structured_fact_paths)
        assert expected["content_only_facts"] == list(contract.content_only_facts)
        assert expected["unsupported_facts"] == list(contract.absent_facts)


def test_course_population_and_identity_are_fully_accounted_for() -> None:
    audit = json.loads(COURSE_AUDIT.read_text(encoding="utf-8"))
    reconciliation = json.loads(COURSE_RECONCILIATION.read_text(encoding="utf-8"))
    expected = _manifest()["course"]["identity"]
    records = audit["entity_classes"]["course"]["identity_manifest"]

    def duplicates(field: str) -> int:
        counts = Counter(item[field] for item in records)
        return sum(count > 1 for count in counts.values())

    assert reconciliation["population"]["accepted"] == expected[
        "audited_course_records"
    ]
    assert audit["selected_detail_pages"] == expected[
        "audited_all_course_family_records"
    ]
    assert reconciliation["population"]["unexplained_losses"] == 0
    assert duplicates("record_id") == expected["duplicate_record_ids"] == 0
    assert duplicates("entity_id") == expected["duplicate_entity_ids"] == 0
    assert duplicates("canonical_url") == expected["duplicate_canonical_urls"] == 0
    assert all(item["entity_id"].endswith("_2026") for item in records)


def test_comp2120_concurrent_study_and_incompatibilities_remain_complete() -> None:
    expected = _manifest()["course"]["comp2120_regression"]
    record = CoursesParser().parse(
        (ROOT / expected["source_fixture"]).read_text(encoding="utf-8"),
        "https://programsandcourses.anu.edu.au/2026/course/COMP2120",
    )[0]

    assert record.record_id == expected["record_id"]
    assert record.metadata_json["prerequisites"] == expected["prerequisites"]
    assert record.metadata_json["incompatibilities"] == expected[
        "incompatibilities"
    ]
    assert record.canonical_url == (
        "https://programsandcourses.anu.edu.au/2026/course/COMP2120"
    )
    assert not record.metadata_json["prerequisites"].startswith("or ")


def test_course_year_is_identity_and_is_not_silently_collapsed() -> None:
    html = (ROOT / "fixtures/courses/comp1100_course_sample.html").read_text(
        encoding="utf-8"
    )
    current = CoursesParser().parse(
        html, "https://programsandcourses.anu.edu.au/2026/course/COMP1100"
    )[0]
    historical = CoursesParser().parse(
        html.replace("2026", "2025"),
        "https://programsandcourses.anu.edu.au/2025/course/COMP1100",
    )[0]

    assert current.metadata_json["course_code"] == historical.metadata_json[
        "course_code"
    ]
    assert current.entity_id == "COMP1100_2026"
    assert historical.entity_id == "COMP1100_2025"
    assert current.record_id != historical.record_id


def test_scholarship_missing_dimensions_and_dates_remain_unknown() -> None:
    record = _scholarship(
        "anu_scholarship_missing_deadline_sample.html",
        status="Open for applications",
    )
    filter_fields = {
        path.removeprefix("metadata_json.")
        for path in _manifest()["scholarship"]["filter_arrays"]
    }

    assert all(isinstance(record.metadata_json[field], list) for field in filter_fields)
    assert record.metadata_json["study_stage"] == []
    assert record.metadata_json["area_of_study"] == []
    assert record.metadata_json["opening_date"] is None
    assert record.metadata_json["closing_date"] is None
    assert record.effective_from is None
    assert record.effective_to is None
    assert build_resolver_search_metadata(record).temporal_values == ()


def test_scholarship_dates_are_date_only_and_do_not_prove_personal_eligibility() -> None:
    record = _scholarship(
        "anu_humanitarian_scholarship_sample.html",
        status="Application closed",
    )
    temporal = build_resolver_search_metadata(record).temporal_values

    assert record.domain == Domain.SCHOLARSHIPS
    assert [(item.value, item.precision.value) for item in temporal] == [
        ("2025-01-16", "date"),
        ("2025-02-07", "date"),
    ]
    assert record.effective_from is None
    assert record.effective_to is None
    assert "personal_eligibility_decision" in _manifest()["scholarship"][
        "unsupported_facts"
    ]


def test_day5_does_not_change_course_content_or_start_reembedding() -> None:
    impact = _manifest()["change_impact"]

    assert impact == {
        "canonical_content_changed": False,
        "content_hashes_changed": 0,
        "retrieval_units_changed": 0,
        "reindex_required": False,
        "reembedding_required": False,
        "production_mutation": False,
        "production_backfill_started": False,
    }
