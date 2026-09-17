"""Parser for approved public ANU residence detail pages."""
from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import make_content_hash, normalize_text, now_canberra
from askanu_scraper.common.parser import BaseParser, ParseError


SOURCE_ID = "accommodation_anu_study"
DETAIL_PATH_RE = re.compile(r"/accommodation/our-residences/([a-z0-9]+(?:-[a-z0-9]+)*)")


def normalize_accommodation_url(url: str) -> str:
    """Return a canonical approved residence URL."""
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ParseError("Accommodation canonical URL is malformed") from exc
    path = parsed.path.rstrip("/")
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != "study.anu.edu.au"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or DETAIL_PATH_RE.fullmatch(path) is None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise ParseError("Accommodation URL is outside the approved residence boundary")
    return urlunsplit(("https", "study.anu.edu.au", path, "", ""))


def _text(node: Tag | None) -> str | None:
    return normalize_text(node.get_text(" ", strip=True)) if node else None


def _mapping_text(metadata: Mapping[str, object], key: str) -> str | None:
    value = metadata.get(key)
    return (normalize_text(value) or None) if isinstance(value, str) else None


def _mapping_list(metadata: Mapping[str, object], key: str) -> list[str]:
    value = metadata.get(key)
    if not isinstance(value, list):
        return []
    return [text for item in value if isinstance(item, str) and (text := normalize_text(item))]


def _canonical_url(soup: BeautifulSoup, fetched_url: str) -> str:
    fetched = normalize_accommodation_url(fetched_url)
    node = soup.find("link", rel=lambda value: value and "canonical" in value)
    if isinstance(node, Tag) and isinstance(node.get("href"), str):
        source = normalize_accommodation_url(str(node["href"]))
        if source != fetched:
            raise ParseError("Accommodation canonical URL does not match fetched URL")
    return fetched


def _section_text(heading: Tag | None) -> str | None:
    if heading is None or heading.parent is None:
        return None
    sibling = heading.find_next_sibling()
    if isinstance(sibling, Tag):
        value = _text(sibling)
        if value:
            return value
    row = heading.find_parent(class_=lambda value: value and "row" in value)
    if isinstance(row, Tag):
        columns = row.find_all("div", recursive=False)
        if len(columns) > 1:
            return _text(columns[1])
    return None


def _heading(soup: BeautifulSoup, exact: str) -> Tag | None:
    return next(
        (
            node
            for node in soup.find_all(["h1", "h2", "h3"])
            if (_text(node) or "").casefold() == exact.casefold()
        ),
        None,
    )


def _rooms(soup: BeautifulSoup) -> tuple[str | None, list[dict[str, object]]]:
    cost_heading = next(
        (node for node in soup.find_all("h2") if "cost" in (_text(node) or "").casefold()),
        None,
    )
    cost_period = _text(cost_heading)
    container = soup.select_one(".room-overview")
    if container is None:
        return cost_period, []
    names = [_text(node) for node in container.select(".pagetabs-nav-tint > ul > li > a")]
    panes = container.select(".tab-content > .tab-pane")
    if len(names) != len(panes):
        raise ParseError("Accommodation room names and fee panels do not align")
    rooms: list[dict[str, object]] = []
    for name, pane in zip(names, panes, strict=True):
        if not name:
            raise ParseError("Accommodation room panel has no room name")
        fields: dict[str, str] = {}
        for row in pane.select("table tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) != 2:
                continue
            label = (_text(cells[0]) or "").rstrip(":")
            value = _text(cells[1])
            if label and value:
                fields[label] = value
        rooms.append(
            {
                "name": name,
                "rate": fields.get("Weekly Inclusive Tariff"),
                "contract": fields.get("Contract Term Length"),
                "inclusions": fields.get("Inclusions"),
                "other_fees": fields.get("Other fees"),
            }
        )
    return cost_period, rooms


def _contact(soup: BeautifulSoup) -> dict[str, str | None]:
    footer = soup.select_one(".anu-accommodation-footer")
    if footer is None:
        return {"email": None, "phone": None, "location": None, "hours": None}
    email_node = footer.select_one('a[href^="mailto:"]')
    phone_node = footer.select_one('a[href^="tel:"]')
    location_node = footer.select_one("p.text-white strong")
    hours_node = footer.select_one("p.text-white")
    email = str(email_node.get("href", ""))[7:] if isinstance(email_node, Tag) else None
    hours_text = _text(hours_node) if isinstance(hours_node, Tag) else None
    hours_match = re.search(
        r"(?:from\s+)?(Monday\s+to\s+Friday[^.]*?(?:AEDT/AEST|AEDT|AEST))",
        hours_text or "",
        re.IGNORECASE,
    )
    return {
        "email": normalize_text(email),
        "phone": _text(phone_node) if isinstance(phone_node, Tag) else None,
        "location": _text(location_node) if isinstance(location_node, Tag) else None,
        "hours": normalize_text(hours_match.group(1)) if hours_match else None,
    }


class AccommodationParser(BaseParser):
    """Convert one residence page into one source-faithful record."""

    SOURCE_ID = SOURCE_ID

    def parse(
        self,
        raw_content: str,
        url: str,
        *,
        listing_metadata: Mapping[str, object] | None = None,
    ) -> list[CommonRecord]:
        metadata = listing_metadata or {}
        soup = BeautifulSoup(raw_content, "lxml")
        for node in soup.select("script, style, noscript, template, iframe"):
            node.decompose()
        canonical_url = _canonical_url(soup, url)
        entity_match = DETAIL_PATH_RE.fullmatch(urlsplit(canonical_url).path)
        if entity_match is None:
            raise ParseError("Accommodation residence identity is missing")
        entity_id = entity_match.group(1)
        title = _text(soup.select_one("h1.banner-title"))
        if not title:
            raise ParseError("Accommodation detail is missing a title")

        overview = _section_text(_heading(soup, "Overview")) or _mapping_text(
            metadata, "listing_description"
        )
        feature_container = soup.select_one("#key-features .view-content")
        features: list[str] = []
        if feature_container:
            for node in feature_container.select(".d-flex"):
                value = _text(node)
                if value and value not in features:
                    features.append(value)
        cost_period, rooms = _rooms(soup)
        accessibility = _section_text(_heading(soup, "Accessibility"))
        contact = _contact(soup)
        application_link = soup.select_one('.anu-accommodation-footer a[href*="starrezhousing.com"]')
        application_url = str(application_link.get("href")) if isinstance(application_link, Tag) else None
        application_text = _text(application_link) if isinstance(application_link, Tag) else None

        normalized_metadata: dict[str, object] = {
            "entity_type": "residence",
            "category": _mapping_text(metadata, "category"),
            "location": None,
            "catering_options": _mapping_list(metadata, "catering_options"),
            "audiences": _mapping_list(metadata, "audiences"),
            "advertised_rate": _mapping_text(metadata, "advertised_rate"),
            "cost_period": cost_period,
            "rooms": rooms,
            "features": features,
            "overview": overview,
            "accessibility": accessibility,
            "application_text": application_text,
            "application_url": application_url,
            "eligibility": None,
            "contact": contact,
            "vacancy_status": None,
        }
        labels: list[tuple[str, object]] = [
            ("Residence", title),
            ("Category", normalized_metadata["category"]),
            ("Catering", "; ".join(normalized_metadata["catering_options"])),
            ("Audience", "; ".join(normalized_metadata["audiences"])),
            ("Advertised rate", normalized_metadata["advertised_rate"]),
            ("Overview", overview),
            ("Features", "; ".join(features)),
            ("Cost period", cost_period),
        ]
        for room in rooms:
            room_bits = [f"{key}: {value}" for key, value in room.items() if key != "name" and value]
            labels.append((f"Room {room['name']}", "; ".join(room_bits)))
        labels.extend(
            [
                ("Accessibility", accessibility),
                ("Application", application_text),
                ("Application URL", application_url),
                ("Contact email", contact["email"]),
                ("Contact phone", contact["phone"]),
                ("Contact location", contact["location"]),
                ("Contact hours", contact["hours"]),
            ]
        )
        content = "\n".join(
            f"{label}: {value}" for label, value in labels if isinstance(value, str) and value
        )
        observed_at = now_canberra()
        return [
            CommonRecord(
                record_id=f"accommodation:residence:{entity_id}",
                source_id=SOURCE_ID,
                entity_id=entity_id,
                domain=Domain.ACCOMMODATION,
                title=title,
                content=content,
                canonical_url=canonical_url,
                collected_at=observed_at,
                last_seen_at=observed_at,
                content_hash=make_content_hash(content),
                metadata_json=normalized_metadata,
            )
        ]
