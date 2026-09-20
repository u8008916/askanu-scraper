"""Parser for public Official ANU Events detail pages."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import CANBERRA_TZ, make_content_hash, normalize_text, now_canberra
from askanu_scraper.common.parser import BaseParser, ParseError

SOURCE_ID = "events_anu_official"
DETAIL_PATH_RE = re.compile(r"/events/([a-z0-9]+(?:-[a-z0-9]+)*)")
EVENT_ID_RE = re.compile(r"[0-9]+")
DATE_PART = r"(?:[A-Z][a-z]{2}\s+)?\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}"
TIME_PART = r"\d{1,2}(?::\d{2})?\s*(?:am|pm)"
DATE_TIME_RE = re.compile(rf"^({DATE_PART})(?:,\s*({TIME_PART}))?$", re.I)


def normalize_event_url(url: str) -> str:
    """Return an exact same-origin public ANU event URL."""
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ParseError("Event canonical URL is malformed") from exc
    path = parsed.path.rstrip("/")
    match = DETAIL_PATH_RE.fullmatch(path)
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != "www.anu.edu.au"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or match is None
        or parsed.query
        or parsed.fragment
    ):
        raise ParseError("Event canonical URL is outside the approved detail boundary")
    if match.group(1) in {"podcasts", "videos", "submit-an-event", "event-submission"}:
        raise ParseError("Event canonical URL targets a non-event content page")
    return urlunsplit(("https", "www.anu.edu.au", path, "", ""))


def _text(node: Tag | None) -> str | None:
    return normalize_text(node.get_text(" ", strip=True)) if node is not None else None


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        value = _text(soup.select_one(selector))
        if value:
            return value
    return None


def _labelled_value(soup: BeautifulSoup, label: str) -> str | None:
    wanted = label.casefold()
    for heading in soup.select("h2, h3, .views-label, dt"):
        heading_text = _text(heading)
        if not heading_text or heading_text.rstrip(":").casefold() != wanted:
            continue
        parent = heading.parent if isinstance(heading.parent, Tag) else None
        if parent is not None:
            for candidate in parent.select(
                ".field-content, .field__item, .field-type-datetime, dd, address"
            ):
                if heading not in candidate.parents:
                    value = _text(candidate)
                    if value and value != heading_text:
                        return value
        sibling = heading.find_next_sibling()
        value = _text(sibling if isinstance(sibling, Tag) else None)
        if value:
            return value
    return None


def _canonical_url(soup: BeautifulSoup, fetched_url: str) -> str:
    fetched = normalize_event_url(fetched_url)
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    if not isinstance(canonical, Tag) or not isinstance(canonical.get("href"), str):
        raise ParseError("Event detail is missing its canonical URL")
    page = normalize_event_url(str(canonical["href"]))
    if page != fetched:
        raise ParseError("Event canonical URL does not match the fetched detail URL")
    return page


def _event_id(soup: BeautifulSoup) -> str:
    article = soup.select_one("article[data-history-node-id]")
    article_id = str(article.get("data-history-node-id", "")).strip() if article else ""
    metadata_ids: set[str] = set()
    for script in soup.select("script"):
        text = script.string or script.get_text(" ", strip=True)
        metadata_ids.update(re.findall(r'["\']entityId["\']\s*:\s*["\']?(\d+)', text))
    if not EVENT_ID_RE.fullmatch(article_id) or not metadata_ids:
        raise ParseError("Event detail is missing cross-checkable numeric identity")
    if metadata_ids != {article_id}:
        raise ParseError("Event article and page metadata identities conflict")
    return article_id


def _parse_endpoint(value: str) -> tuple[date, datetime | None]:
    match = DATE_TIME_RE.fullmatch(normalize_text(value) or "")
    if not match:
        raise ParseError(f"Unsupported displayed Event date/time: {value!r}")
    raw_date, raw_time = match.groups()
    raw_date = re.sub(r"^[A-Z][a-z]{2}\s+", "", raw_date)
    try:
        parsed_date = datetime.strptime(raw_date, "%d %b %Y").date()
    except ValueError as exc:
        raise ParseError(f"Invalid displayed Event date: {value!r}") from exc
    if raw_time is None:
        return parsed_date, None
    normalized_time = re.sub(r"\s+", " ", raw_time.strip().upper())
    fmt = "%I:%M %p" if ":" in normalized_time else "%I %p"
    try:
        parsed_time = datetime.strptime(normalized_time, fmt).time()
    except ValueError as exc:
        raise ParseError(f"Invalid displayed Event time: {value!r}") from exc
    return parsed_date, datetime.combine(parsed_date, parsed_time, CANBERRA_TZ)


def parse_displayed_interval(value: str) -> tuple[date, date, datetime | None, datetime | None]:
    """Parse displayed HTML dates; the source ICS is deliberately not consulted."""
    parts = re.split(r"\s+(?:-|–|—)\s+", normalize_text(value) or "", maxsplit=1)
    if not parts or not parts[0]:
        raise ParseError("Event detail is missing displayed start evidence")
    start_date, start_at = _parse_endpoint(parts[0])
    end_date, end_at = (start_date, start_at) if len(parts) == 1 else _parse_endpoint(parts[1])
    if end_date < start_date or (start_at and end_at and end_at < start_at):
        raise ParseError("Event displayed end precedes its start")
    if (start_at is None) != (end_at is None):
        raise ParseError("Event interval mixes date-only and timed evidence")
    return start_date, end_date, start_at, end_at


def _displayed_intervals(soup: BeautifulSoup) -> tuple[str, date, date, datetime | None, datetime | None]:
    values = [
        value for node in soup.select(".field-type-datetime li, .field--type-datetime li")
        if (value := _text(node))
    ]
    if not values:
        fallback = _labelled_value(soup, "Date and Times") or _first_text(soup, ("time",))
        values = [fallback] if fallback else []
    if not values:
        raise ParseError("Event detail is missing displayed start evidence")
    intervals = [parse_displayed_interval(value) for value in values]
    starts = [item[0] for item in intervals]
    ends = [item[1] for item in intervals]
    timed = [item for item in intervals if item[2] is not None]
    if timed and len(timed) != len(intervals):
        raise ParseError("Event has mixed date-only and timed occurrences")
    start_at = min(item[2] for item in timed) if timed else None
    end_at = max(item[3] for item in timed) if timed else None
    return "; ".join(values), min(starts), max(ends), start_at, end_at


def _list_values(soup: BeautifulSoup, selectors: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for selector in selectors:
        for node in soup.select(selector):
            value = _text(node)
            if value and value not in values:
                values.append(value)
    return values


def _registration_links(soup: BeautifulSoup, canonical_url: str) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        label = _text(link)
        parent_text = _text(link.parent if isinstance(link.parent, Tag) else None)
        evidence = " ".join(filter(None, (label, parent_text))).casefold()
        if not re.search(r"\b(register|registration|book tickets?)\b", evidence):
            continue
        raw_href = link.get("href")
        if not isinstance(raw_href, str):
            continue
        destination = urljoin(canonical_url, raw_href.strip())
        try:
            parsed = urlsplit(destination)
            parsed.port
        except ValueError:
            continue
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or destination in seen
        ):
            continue
        seen.add(destination)
        values.append({"label": label or "Registration", "url": destination})
    return values


class EventsParser(BaseParser):
    """Convert one official ANU Event page into one normalized event record."""

    SOURCE_ID = SOURCE_ID

    def __init__(self, now_func: Callable[[], datetime] | None = None) -> None:
        self._now = now_func or now_canberra

    def parse(self, raw_content: str, url: str) -> list[CommonRecord]:
        soup = BeautifulSoup(raw_content, "lxml")
        for executable in soup.select("style, iframe, object, embed"):
            executable.decompose()
        canonical_url = _canonical_url(soup, url)
        event_id = _event_id(soup)
        title = _first_text(soup, ("h1.page-title span", "h1.page-title", "h1"))
        if not title:
            raise ParseError("Event detail is missing a title")
        date_text, start_date, end_date, start_at, end_at = _displayed_intervals(soup)
        description_node = soup.select_one(
            ".field--name-body.field--type-text-with-summary, .field--name-body"
        )
        description = _text(description_node)
        location = _labelled_value(soup, "Location") or _first_text(
            soup, (".views-field-field-event-location .field-content", ".event-location")
        )
        organiser = _first_text(
            soup,
            (".views-field-field-colleges .field-content", ".field--name-field-colleges"),
        ) or _labelled_value(soup, "Presented by")
        fmt = _labelled_value(soup, "Format") or _first_text(
            soup, (".field--name-field-event-format", ".event-format")
        )
        categories = _list_values(
            soup, (".field--name-field-event-category .field__item", ".event-category a")
        )
        tags = _list_values(
            soup, (".field--name-field-tags .field__item", ".field--name-field-event-tags .field__item")
        )
        cancellation_text = _first_text(
            soup,
            (".field--name-field-event-status", ".event-cancellation", ".cancelled", ".canceled"),
        )
        status = None
        if cancellation_text and re.search(r"\bcancell?ed\b", cancellation_text, re.I):
            status = "cancelled"
        elif re.match(r"^cancell?ed\b", title, re.I):
            status = "cancelled"
            cancellation_text = title
        registration_links = _registration_links(soup, canonical_url)
        category = categories[0] if len(categories) == 1 else None
        registration_url = (
            registration_links[0]["url"] if len(registration_links) == 1 else None
        )
        metadata: dict[str, object] = {
            "entity_type": "event", "source_event_id": event_id,
            "start_at": start_at.isoformat() if start_at else None,
            "end_at": end_at.isoformat() if end_at else None,
            "timezone": "Australia/Canberra",
            "organiser_name": organiser,
            "venue_name": location,
            "address": None,
            "latitude": None,
            "longitude": None,
            "category": category,
            "tags": tags,
            "registration_url": registration_url,
            "source_status": None,
            "cancellation_status": status,
            "audience": None,
        }
        registration_content = "; ".join(
            f"{item['label']}: {item['url']}" for item in registration_links
        ) or None
        labels = (
            ("Title", title), ("Date and times", date_text), ("Location", location),
            ("Format", fmt), ("Categories", "; ".join(categories) or None),
            ("Tags", "; ".join(tags) or None), ("Presented by", organiser),
            ("Description", description),
            ("Registration", registration_content),
            ("Status", status), ("Cancellation", cancellation_text),
        )
        content = "\n".join(f"{label}: {value}" for label, value in labels if value)
        observed_at = self._now()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ParseError("Events parser clock must be timezone-aware")
        return [CommonRecord(
            record_id=f"events:event:{event_id}", source_id=SOURCE_ID,
            entity_id=event_id, domain=Domain.EVENTS, title=title, content=content,
            canonical_url=canonical_url, effective_from=start_at, effective_to=end_at,
            collected_at=observed_at, last_seen_at=observed_at,
            content_hash=make_content_hash(content), metadata_json=metadata,
        )]


__all__ = ["EventsParser", "normalize_event_url", "parse_displayed_interval"]
