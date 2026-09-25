"""V7 Day 4 Accommodation evidence, comparison, and boundary proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from askanu_scraper.common.fetcher import MockFetcher
from askanu_scraper.common.models import Domain, IngestionRunStatus
from askanu_scraper.common.registry import get_source
from askanu_scraper.common.search_metadata import build_resolver_search_metadata
from askanu_scraper.common.storage import LocalDataStore
from askanu_scraper.common.v7_contract import producer_contract_for, source_authority_for
from askanu_scraper.sources.accommodation import (
    LISTING_URL,
    AccommodationCollector,
    AccommodationParser,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT / "fixtures" / "v7" / "day4" / "accommodation-evidence-contract.json"
)
AUDIT_PATH = ROOT / "day4-accommodation-source-health.json"
FIXTURES = ROOT / "fixtures" / "accommodation"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _case(name: str) -> dict[str, object]:
    return next(
        case
        for case in _manifest()["representative_cases"]
        if case["name"] == name
    )


def _record(case: dict[str, object], *, include_advertised_rate: bool = True):
    listing_metadata = dict(case["listing_metadata"])
    if not include_advertised_rate:
        listing_metadata.pop("advertised_rate")
    return AccommodationParser().parse(
        (ROOT / str(case["source_fixture"])).read_text(encoding="utf-8"),
        str(case["source_url"]),
        listing_metadata=listing_metadata,
    )[0]


def test_manifest_is_offline_and_composes_frozen_shared_contracts() -> None:
    manifest = _manifest()

    assert manifest["contract_version"] == "v7-day4-accommodation-evidence-v1"
    assert manifest["depends_on"] == [
        "v7-day1-producer-capabilities-v1",
        "v7-day2-resolver-search-metadata-v1",
    ]
    assert manifest["network_calls_allowed"] is False
    assert manifest["source_id"] == "accommodation_anu_study"
    assert manifest["entity_type"] == "residence"
    assert manifest["frozen_entity_denominator"] == 19


def test_field_matrix_covers_exact_day1_accommodation_fact_paths() -> None:
    case = _case("multiple room facts and complete contact subfields")
    record = _record(case)
    contract = producer_contract_for(record)
    matrix = _manifest()["field_capabilities"]

    assert {item["path"] for item in matrix} == set(contract.structured_fact_paths)
    assert len(matrix) == len(contract.structured_fact_paths) == 15
    assert contract.absent_facts == ("inferred_vacancy", "personal_room_offer")


def test_live_audit_artifact_is_immutable_dry_run_evidence() -> None:
    manifest_audit = _manifest()["live_audit"]
    raw = AUDIT_PATH.read_bytes()
    audit = json.loads(raw)
    residence = audit["entity_classes"]["residence"]

    normalized_raw = raw.replace(b"\r\n", b"\n")
    assert (
        hashlib.sha256(normalized_raw).hexdigest()
        == manifest_audit["sha256_lf_normalized"]
    )
    assert audit["captured_at"] == manifest_audit["captured_at"]
    assert audit["dry_run"] is manifest_audit["dry_run"] is True
    assert audit["production_records_written"] == 0
    assert audit["migrations_applied"] == 0
    assert audit["selected_detail_pages"] == 19
    assert residence["approved_records"] == 19
    assert residence["detail_pages_fetched"] == 19
    assert residence["parsed_records"] == 19
    assert residence["parser_exceptions"] == 0
    assert residence["canonical_mismatches"] == 0
    assert residence["duplicate_identities"] == 0
    assert residence["source_shape_anomalies"] == []
    assert residence["source_present_fact_numerator"] == 255
    assert residence["source_present_fact_denominator"] == 255


def test_live_field_counts_match_capability_matrix_without_claiming_absence() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    fields = audit["entity_classes"]["residence"]["fields"]

    for item in _manifest()["field_capabilities"]:
        field = item["path"].removeprefix("metadata_json.")
        assert fields[field]["source_present"] == item["live_source_present"]
        assert fields[field]["captured"] == item["live_captured"]

    assert fields["advertised_rate"]["source_present"] == 18
    assert fields["application_url"]["source_present"] == 14
    assert fields["vacancy_status"]["source_present"] == 0


def test_representative_records_preserve_identity_authority_and_day2_projection() -> None:
    for case in _manifest()["representative_cases"]:
        record = _record(case)
        before = record.model_dump(mode="json")
        search = build_resolver_search_metadata(record)
        authority = source_authority_for(record)

        assert record.domain == Domain.ACCOMMODATION
        assert record.record_id == case["expected_record_id"]
        assert record.canonical_url == case["source_url"]
        assert record.source_id == _manifest()["source_id"]
        assert search.temporal_values == ()
        assert [(term.kind.value, term.value) for term in search.lookup_terms] == [
            ("canonical_name", record.title)
        ]
        assert authority.source_id == "accommodation_anu_study"
        assert authority.authority_rank == 1
        assert authority.approval_status.value == "APPROVED"
        assert record.model_dump(mode="json") == before


def test_catering_and_audience_filters_are_exact_membership_only() -> None:
    record = _record(_case("multiple room facts and complete contact subfields"))

    assert record.metadata_json["catering_options"] == ["Self-catered"]
    assert record.metadata_json["audiences"] == ["Undergraduate", "Postgraduate"]
    assert "self catered" not in record.metadata_json["catering_options"]
    assert "students" not in record.metadata_json["audiences"]


def test_price_comparison_preserves_wording_period_and_room_pairing() -> None:
    yukeembruk = _record(_case("multiple room facts and complete contact subfields"))
    davey = _record(_case("single room facts and missing optional contact subfields"))

    assert yukeembruk.metadata_json["advertised_rate"] == "Rates from A$380.00 /wk"
    assert davey.metadata_json["advertised_rate"] == "Rates from A$365.00 /wk"
    assert yukeembruk.metadata_json["cost_period"] == "2027 Indicative costs"
    assert davey.metadata_json["cost_period"] == "2027 Indicative costs"
    assert yukeembruk.metadata_json["rooms"] == [
        {
            "name": "Standard",
            "rate": "$380.00",
            "contract": "44 weeks",
            "inclusions": "Internet included",
            "other_fees": "Refundable Deposit: $1,300",
        },
        {
            "name": "Ensuite Room",
            "rate": "$473.00",
            "contract": "44 weeks",
            "inclusions": "Utilities included",
            "other_fees": "Registration Fee: $400",
        },
    ]
    assert davey.metadata_json["rooms"] == [
        {
            "name": "Studio Long",
            "rate": "$365.00",
            "contract": "48 weeks",
            "inclusions": None,
            "other_fees": None,
        }
    ]
    assert isinstance(yukeembruk.metadata_json["rooms"][0]["rate"], str)


def test_missing_comparison_facts_stay_unknown_and_are_not_backfilled() -> None:
    complete = _record(_case("multiple room facts and complete contact subfields"))
    partial = _record(_case("single room facts and missing optional contact subfields"))
    no_listing_rate = _record(
        _case("single room facts and missing optional contact subfields"),
        include_advertised_rate=False,
    )

    assert complete.metadata_json["contact"]["hours"] == (
        "Monday to Friday, 10am-4pm AEDT/AEST"
    )
    assert partial.metadata_json["contact"]["hours"] is None
    assert no_listing_rate.metadata_json["advertised_rate"] is None
    assert no_listing_rate.metadata_json["rooms"][0]["rate"] == "$365.00"
    assert no_listing_rate.metadata_json["vacancy_status"] is None


def test_application_link_is_navigation_only_and_starrezz_is_never_fetched(
    tmp_path: Path,
) -> None:
    class RecordingFetcher(MockFetcher):
        def __init__(self, mapping: dict[str, Path]) -> None:
            super().__init__(mapping)
            self.urls: list[str] = []

        def fetch(self, url: str) -> str:
            self.urls.append(url)
            return super().fetch(url)

    yukeembruk_case = _case("multiple room facts and complete contact subfields")
    davey_case = _case("single room facts and missing optional contact subfields")
    fetcher = RecordingFetcher(
        {
            LISTING_URL: FIXTURES / "anu_residences_listing_sample.html",
            str(yukeembruk_case["source_url"]): ROOT
            / str(yukeembruk_case["source_fixture"]),
            str(davey_case["source_url"]): ROOT / str(davey_case["source_fixture"]),
        }
    )

    run, records, _ = AccommodationCollector(
        fetcher=fetcher,
        store=LocalDataStore(tmp_path),
        frozen_entity_count=2,
    ).run_listing(max_details=2)

    assert run.status == IngestionRunStatus.SUCCESS
    assert len(records) == 2
    assert all(record.metadata_json["application_text"] == "Apply now" for record in records)
    assert all(
        record.metadata_json["application_url"]
        == "https://anucomb.starrezhousing.com/StarRezPortalX/public-token"
        for record in records
    )
    assert all(record.metadata_json["vacancy_status"] is None for record in records)
    assert all("starrezhousing.com" not in url for url in fetcher.urls)


def test_registry_and_audit_identity_manifest_remain_inside_approved_boundary() -> None:
    source = get_source("accommodation_anu_study")
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    identities = audit["entity_classes"]["residence"]["identity_manifest"]

    assert source.canonical_root == "https://study.anu.edu.au/accommodation"
    assert len(identities) == 19
    assert len({item["record_id"] for item in identities}) == 19
    assert len({item["canonical_url"] for item in identities}) == 19
    assert all(item["source_id"] == source.source_id for item in identities)
    assert all(
        item["record_id"] == f"accommodation:residence:{item['entity_id']}"
        for item in identities
    )
    assert all(
        item["canonical_url"].startswith(
            "https://study.anu.edu.au/accommodation/our-residences/"
        )
        for item in identities
    )


def test_unsupported_operations_are_explicit_not_magic_wording() -> None:
    unsupported = set(_manifest()["unsupported_filters_and_claims"])

    assert unsupported == {
        "numeric_price_sort_or_range",
        "cheapest_or_total_cost_ranking",
        "vacancy_or_room_availability",
        "personal_eligibility",
        "inferred_location",
        "inferred_accessibility",
        "application_status_or_outcome",
        "magic_wording_or_unreviewed_synonyms",
    }
