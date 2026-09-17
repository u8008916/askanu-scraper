"""Parser for approved ANUSA Student Assistance category pages."""
from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from askanu_scraper.common.models import CommonRecord, Domain
from askanu_scraper.common.normalizer import make_content_hash, normalize_text, now_canberra
from askanu_scraper.common.parser import BaseParser, ParseError


SOURCE_ID = "support_anusa_student_assistance"
DETAIL_PATH_RE = re.compile(r"/student-assistance/([a-z0-9]+(?:-[a-z0-9]+)*)/")
TOPIC_PATH_RE = re.compile(
    r"/student-assistance/[a-z0-9]+(?:-[a-z0-9]+)*/"
    r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*/?"
)
INTERNAL_ANUSA_HOSTS = {"anusa.com.au", "www.anusa.com.au"}


def normalize_support_url(url: str) -> str:
    """Return a canonical top-level ANUSA Student Assistance category URL."""
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ParseError("Support canonical URL is malformed") from exc
    path = f"{parsed.path.rstrip('/')}/"
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != "anusa.com.au"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or DETAIL_PATH_RE.fullmatch(path) is None
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise ParseError("Support URL is outside the approved category boundary")
    return urlunsplit(("https", "anusa.com.au", path, "", ""))


def _is_approved_topic_url(url: str) -> bool:
    """Return whether a URL is an internal Student Assistance topic."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() in INTERNAL_ANUSA_HOSTS
        and parsed.username is None
        and parsed.password is None
        and port is None
        and TOPIC_PATH_RE.fullmatch(parsed.path) is not None
        and not parsed.query
        and not parsed.fragment
    )


def _is_external_referral_url(url: str) -> bool:
    """Return whether a published URL is safe external referral evidence."""
    try:
        parsed = urlsplit(url)
        parsed.port
    except (TypeError, ValueError):
        return False
    host = (parsed.hostname or "").casefold()
    return (
        parsed.scheme.casefold() in {"http", "https"}
        and bool(host)
        and host not in INTERNAL_ANUSA_HOSTS
        and parsed.username is None
        and parsed.password is None
    )


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
    fetched = normalize_support_url(fetched_url)
    node = soup.find("link", rel=lambda value: value and "canonical" in value)
    if isinstance(node, Tag) and isinstance(node.get("href"), str):
        source = normalize_support_url(str(node["href"]))
        if source != fetched:
            raise ParseError("Support canonical URL does not match fetched URL")
    return fetched


def _contact(
    main: Tag, registry_email: str | None
) -> tuple[dict[str, str | None], str | None]:
    contact_widget = main.select_one(".elementor-global-2660")
    if contact_widget is None:
        contact_widget = next(
            (
                node
                for node in main.select(".elementor-widget-text-editor")
                if "contact" in (_text(node) or "").casefold()
            ),
            None,
        )
    text = _text(contact_widget) if isinstance(contact_widget, Tag) else ""
    text = text or ""
    email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    phone_match = re.search(r"(?:\+?61\s*)?0?2\s*\d{4}\s*\d{4}", text)
    location = None
    if isinstance(contact_widget, Tag):
        for item in contact_widget.stripped_strings:
            value = normalize_text(str(item))
            if value and re.match(r"(?:Level\s+\d+|Building\s+\d+)", value, re.I):
                location = value
                break
    if location is None:
        location_match = re.search(
            r"((?:Level\s+\d+|Building\s+\d+),?\s*[^.]+?)(?=\.|$)",
            text,
            re.IGNORECASE,
        )
        location = normalize_text(location_match.group(1)) if location_match else None
    return (
        {
            "email": email_match.group(0) if email_match else registry_email,
            "phone": normalize_text(phone_match.group(0)) if phone_match else None,
            "location": location,
        },
        text or None,
    )


def _published_hours(text: str) -> str | None:
    patterns = (
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^.;]{0,100}(?:am|pm)",
        r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*(?:-|–|to)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalize_text(match.group(0))
    return None


class SupportParser(BaseParser):
    """Convert one category page into one sanitized support service record."""

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
            raise ParseError("Support category identity is missing")
        entity_id = entity_match.group(1)
        main = soup.select_one("main#content, main")
        if main is None:
            raise ParseError("Support detail has no main content")
        title = _text(
            main.select_one(".elementor-widget-heading h1, .elementor-widget-heading h2")
        )
        if not title:
            raise ParseError("Support detail is missing a title")

        first_heading_widget = main.select_one(".elementor-widget-heading")
        purpose = None
        if isinstance(first_heading_widget, Tag):
            column = first_heading_widget.find_parent(
                class_=lambda value: value and "elementor-column" in value
            )
            if isinstance(column, Tag):
                purpose = _text(column.select_one(".elementor-widget-text-editor"))
        purpose = purpose or _mapping_text(metadata, "listing_description")

        topics: list[dict[str, str | None]] = []
        referrals: list[dict[str, str]] = []
        seen_referrals: set[str] = set()
        for card in main.select("a.elementor-cta[href]"):
            topic_title = _text(card.select_one(".elementor-cta__title"))
            if not topic_title:
                continue
            topic_url = urljoin(canonical_url, str(card.get("href", "")))
            if not _is_approved_topic_url(topic_url):
                if not _is_external_referral_url(topic_url):
                    continue
                if topic_url not in seen_referrals:
                    seen_referrals.add(topic_url)
                    referrals.append({"label": topic_title, "url": topic_url})
                continue
            topics.append(
                {
                    "title": topic_title,
                    "description": _text(card.select_one(".elementor-cta__description")),
                    "url": topic_url,
                }
            )

        for anchor in main.select('a[href]'):
            href = urljoin(canonical_url, str(anchor.get("href", "")))
            if not _is_external_referral_url(href):
                continue
            label = _text(anchor)
            if not label or href in seen_referrals:
                continue
            seen_referrals.add(href)
            referrals.append({"label": label, "url": href})

        access = None
        for node in main.select("p, li"):
            value = _text(node)
            if value and re.search(
                r"\b(?:book(?:ing)? an appointment|make an appointment|drop[- ]?in|walk[- ]?in)\b",
                value,
                re.IGNORECASE,
            ):
                access = value
                break
        contact, contact_text = _contact(
            main, _mapping_text(metadata, "registry_email")
        )
        normalized_metadata: dict[str, object] = {
            "entity_type": "support_service",
            "category": _mapping_text(metadata, "category"),
            "purpose": purpose,
            "audiences": _mapping_list(metadata, "audiences"),
            "contact": contact,
            "hours": _published_hours(contact_text or ""),
            "access": access,
            "cost": _mapping_text(metadata, "cost"),
            "topics": topics,
            "referrals": referrals,
        }
        labels: list[tuple[str, object]] = [
            ("Service", title),
            ("Category", normalized_metadata["category"]),
            ("Purpose", purpose),
            ("Audience", "; ".join(normalized_metadata["audiences"])),
            ("Contact email", contact["email"]),
            ("Contact phone", contact["phone"]),
            ("Location", contact["location"]),
            ("Published hours", normalized_metadata["hours"]),
            ("Access", normalized_metadata["access"]),
            ("Cost", normalized_metadata["cost"]),
        ]
        for topic in topics:
            labels.append(
                (
                    f"Topic {topic['title']}",
                    "; ".join(
                        value for key, value in topic.items() if key != "title" and value
                    ),
                )
            )
        for referral in referrals:
            labels.append((f"Referral {referral['label']}", referral["url"]))
        content = "\n".join(
            f"{label}: {value}" for label, value in labels if isinstance(value, str) and value
        )
        observed_at = now_canberra()
        return [
            CommonRecord(
                record_id=f"support:support_service:{entity_id}",
                source_id=SOURCE_ID,
                entity_id=entity_id,
                domain=Domain.SUPPORT,
                title=title,
                content=content,
                canonical_url=canonical_url,
                collected_at=observed_at,
                last_seen_at=observed_at,
                content_hash=make_content_hash(content),
                metadata_json=normalized_metadata,
            )
        ]
