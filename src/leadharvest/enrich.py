"""Pure enrichment pipeline: normalization, validation, dedupe, stats.

Every function here takes data in and returns data out — no network, no
disk, no globals — so the whole pipeline is unit-testable offline.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Mapping

from .models import EnrichmentResult, Lead, LeadStats, Rejected

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
BR_LOCAL_FORMAT = re.compile(r"^\(?\d{2}\)?[\s-]\d{4}[\s-]\d{4}$")

DOMAIN_TOP_N = 5


def normalize_name(value: str) -> str:
    """Trim, collapse whitespace and title-case a personal name."""
    return " ".join(value.split()).title()


def normalize_email(value: str) -> str:
    """Trim and lowercase an email address."""
    return value.strip().lower()


def is_valid_email(value: str) -> bool:
    """Check the address against a pragmatic RFC-ish pattern."""
    return bool(EMAIL_RE.match(value))


def normalize_phone(value: str) -> str:
    """E.164-ish phone normalization (keeps ``+``, drops other formatting).

    Brazilian numbers are promoted to ``+55``:
    - already carries the 55 country code (12–13 digits) → ``+55...``
    - 11 local digits that are not a US NANP ``1 + 10`` shape → ``+55...``
    - 10 digits formatted as a BR landline ``(DD) 3333-4444`` → ``+55...``
    Anything else keeps its digits (prefixed with ``+`` if it had one).
    """
    raw = value.strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if raw.startswith("+"):
        return "+" + digits
    if digits.startswith("55") and len(digits) in (12, 13):
        return "+" + digits
    if len(digits) == 11 and not (digits[0] == "1" and digits[1] != "1"):
        return "+55" + digits
    if len(digits) == 10 and BR_LOCAL_FORMAT.match(raw):
        return "+55" + digits
    return digits


def normalize_website(value: str) -> str:
    """Prefix ``https://`` when the URL has no scheme."""
    site = value.strip()
    if not site:
        return ""
    if site.lower().startswith(("http://", "https://")):
        return site
    return "https://" + site


def normalize_city(value: str) -> str:
    """Trim and collapse whitespace in a city name."""
    return " ".join(value.split())


def domain_from_email(email: str) -> str:
    """Extract the registrable domain part of an email address."""
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1]


def enrich_record(raw: Mapping[str, Any]) -> Lead:
    """Turn one flat source row into a fully normalized :class:`Lead`."""
    email = normalize_email(str(raw.get("email") or ""))
    return Lead(
        name=normalize_name(str(raw.get("name") or "")),
        email=email,
        phone=normalize_phone(str(raw.get("phone") or "")),
        website=normalize_website(str(raw.get("website") or "")),
        company=" ".join(str(raw.get("company") or "").split()),
        city=normalize_city(str(raw.get("city") or "")),
        domain=domain_from_email(email),
    )


def enrich_records(rows: Iterable[Mapping[str, Any]]) -> EnrichmentResult:
    """Normalize, validate and de-duplicate rows (first occurrence wins).

    Invalid/missing emails are moved to the rejected list with a reason;
    later rows repeating a seen email count as duplicates.
    """
    leads: list[Lead] = []
    rejected: list[Rejected] = []
    seen: set[str] = set()
    raw_count = 0
    duplicate_count = 0

    for row in rows:
        raw_count += 1
        raw_email = str(row.get("email") or "").strip()
        email = normalize_email(raw_email)
        display_name = normalize_name(str(row.get("name") or ""))
        if not email:
            rejected.append(Rejected(name=display_name, email="", reason="missing email"))
            continue
        if not is_valid_email(email):
            rejected.append(
                Rejected(name=display_name, email=email, reason="invalid email format")
            )
            continue
        if email in seen:
            duplicate_count += 1
            continue
        seen.add(email)
        leads.append(enrich_record({**dict(row), "email": email}))

    return EnrichmentResult(
        leads=leads,
        rejected=rejected,
        raw_count=raw_count,
        duplicate_count=duplicate_count,
    )


def compute_stats(leads: Iterable[Lead], top_domains: int = DOMAIN_TOP_N) -> LeadStats:
    """Aggregate a lead list: total, per-city counts, top domain counts."""
    materialized = list(leads)
    cities = Counter(lead.city for lead in materialized if lead.city)
    domains = Counter(lead.domain for lead in materialized if lead.domain)
    return LeadStats(
        total=len(materialized),
        by_city=sorted(cities.items(), key=lambda kv: (-kv[1], kv[0])),
        by_domain=sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))[:top_domains],
    )


def format_stats(result: EnrichmentResult) -> str:
    """One-line pipeline summary: raw → valid → duplicates → rejected."""
    return (
        f"raw {result.raw_count} → valid {result.valid_count} → "
        f"duplicates {result.duplicate_count} → rejected {result.rejected_count}"
    )
