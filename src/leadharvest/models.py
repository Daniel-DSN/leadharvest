"""Core data models for leads, rejections and enrichment results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Lead:
    """A single cleaned, ready-to-use B2B lead."""

    name: str
    email: str
    phone: str = ""
    website: str = ""
    company: str = ""
    city: str = ""
    domain: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lead":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass(slots=True)
class Rejected:
    """A source row dropped during enrichment, with the reason why."""

    name: str
    email: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EnrichmentResult:
    """Outcome of an enrichment pass: kept leads, rejects and counts."""

    leads: list[Lead] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    raw_count: int = 0
    duplicate_count: int = 0

    @property
    def valid_count(self) -> int:
        return len(self.leads)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


@dataclass(slots=True)
class LeadStats:
    """Aggregates computed from a list of leads."""

    total: int
    by_city: list[tuple[str, int]] = field(default_factory=list)
    by_domain: list[tuple[str, int]] = field(default_factory=list)
