"""
Normalisation helpers for the AskANU scraper.

Rules from DATA_SCHEMA.md:
- Timezone: Australia/Canberra
- content_hash: SHA-256 of canonical content
- stable record ID: "{domain}:{entity_id}"
- Never invent missing fields
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

CANBERRA_TZ = ZoneInfo("Australia/Canberra")


# ---------------------------------------------------------------------------
# ID / hash helpers
# ---------------------------------------------------------------------------

def make_record_id(domain: str, entity_id: str) -> str:
    """Return the stable record ID in the form ``{domain}:{entity_id}``."""
    return f"{domain}:{entity_id}"


def make_content_hash(content: str) -> str:
    """Return SHA-256 hex digest of the canonical content string (UTF-8)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace into single spaces and strip edges."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str | None) -> str | None:
    """
    Normalise a text field:
    - Return None as-is (never invent content).
    - Strip leading/trailing whitespace.
    - Normalize Unicode to NFC.
    - Collapse internal whitespace.
    """
    if text is None:
        return None
    text = unicodedata.normalize("NFC", text)
    return normalize_whitespace(text)


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------

def now_canberra() -> datetime:
    """Return the current datetime in Australia/Canberra timezone."""
    return datetime.now(tz=CANBERRA_TZ)


def to_canberra(dt: datetime) -> datetime:
    """Convert an aware datetime to Australia/Canberra, or attach tz if naive."""
    if dt.tzinfo is None:
        # Assume UTC if naive — document any source-specific assumption at call site
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CANBERRA_TZ)


def parse_date_safe(raw: str | None) -> datetime | None:
    """
    Attempt to parse a date string from a source page.
    Returns None if raw is None or unparseable — never invent a date.
    """
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=CANBERRA_TZ)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def normalize_url(url: str | None) -> str | None:
    """Strip trailing slashes and whitespace from a URL. Return None if empty."""
    if not url:
        return None
    return url.strip().rstrip("/")
