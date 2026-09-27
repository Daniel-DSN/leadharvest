"""Record collection: public API fetch, CSV/JSON readers, raw snapshots.

Collection is the I/O layer — it returns plain dict rows so that the
enrichment pipeline stays pure and testable without network or disk.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

import requests

API_DEFAULT = "https://jsonplaceholder.typicode.com/users"
USER_AGENT = "leadharvest/1.0 (+https://github.com/leadharvest)"
CSV_FIELDS = ["name", "email", "phone", "website", "company", "city"]


def flatten_record(record: Mapping[str, Any]) -> dict[str, str]:
    """Reduce an API or CSV row to the flat lead columns.

    Accepts both nested API payloads (``company.name``, ``address.city``)
    and already-flat CSV rows.
    """
    company = record.get("company") or {}
    if isinstance(company, Mapping):
        company_name = company.get("name") or ""
    else:
        company_name = company
    city = record.get("city") or ""
    if not city:
        address = record.get("address") or {}
        if isinstance(address, Mapping):
            city = address.get("city") or ""
    return {
        "name": str(record.get("name") or "").strip(),
        "email": str(record.get("email") or "").strip(),
        "phone": str(record.get("phone") or "").strip(),
        "website": str(record.get("website") or "").strip(),
        "company": str(company_name).strip(),
        "city": str(city).strip(),
    }


def fetch_users(
    base_url: str = API_DEFAULT, timeout: float = 15.0
) -> list[dict[str, Any]]:
    """GET a public JSON list of user records from ``base_url``."""
    response = requests.get(
        base_url, timeout=timeout, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"expected a JSON list from {base_url}, got {type(data).__name__}")
    return [row for row in data if isinstance(row, Mapping)]


def read_json(path: Path) -> list[dict[str, Any]]:
    """Read raw records from a JSON snapshot (list of objects)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list of records")
    return [flatten_record(row) for row in data if isinstance(row, Mapping)]


def read_csv(path: Path) -> list[dict[str, Any]]:
    """Read raw records from a CSV file with LeadHarvest's column names."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [flatten_record(row or {}) for row in reader]


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Read and flatten records from ``.json`` or ``.csv`` by suffix."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        return read_json(path)
    if suffix == ".csv":
        return read_csv(path)
    raise ValueError(f"unsupported input format: {suffix!r} (use .json or .csv)")


def save_raw(records: list[Mapping[str, Any]], path: str | Path) -> Path:
    """Write records untouched as a pretty-printed JSON snapshot."""
    path = Path(path)
    payload = [dict(record) for record in records]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
