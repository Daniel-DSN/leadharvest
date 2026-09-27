"""Collection layer tests — offline; network is monkeypatched."""

from pathlib import Path

import pytest

from leadharvest.cli import main
from leadharvest.sources import (
    API_DEFAULT,
    fetch_users,
    flatten_record,
    load_records,
    save_raw,
)

ROOT = Path(__file__).parent.parent
SAMPLES = ROOT / "samples"
FIXTURE = SAMPLES / "users_fixture.json"
CSV_SAMPLE = SAMPLES / "leads_raw.csv"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_flatten_record_nested_api_payload():
    users = load_records(FIXTURE)
    row = users[0]
    assert row["name"] == "Leanne Graham"
    assert row["email"] == "Sincere@april.biz"
    assert row["company"] == "Romaguera-Crona"
    assert row["city"] == "Gwenborough"
    assert row["phone"].startswith("1-770-736-8031")
    assert row["website"] == "hildegard.org"


def test_flatten_record_flat_row_passes_through():
    flat = {"name": " Ana ", "email": "a@b.co", "company": "Acme", "city": "Lima"}
    assert flatten_record(flat) == {
        "name": "Ana",
        "email": "a@b.co",
        "phone": "",
        "website": "",
        "company": "Acme",
        "city": "Lima",
    }


def test_load_records_json_fixture_returns_ten_flattened():
    records = load_records(FIXTURE)
    assert len(records) == 10
    assert all("company" in row and "city" in row for row in records)
    assert all(isinstance(row["company"], str) for row in records)


def test_load_records_csv_sample_returns_fifteen_rows():
    records = load_records(CSV_SAMPLE)
    assert len(records) == 15
    assert records[0]["name"] == "Ana Silva"
    assert records[5]["email"] == ""


def test_load_records_rejects_unsupported_suffix(tmp_path):
    bad = tmp_path / "leads.txt"
    bad.write_text("name\nAna\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported input format"):
        load_records(bad)


def test_save_raw_roundtrip(tmp_path):
    records = load_records(CSV_SAMPLE)[:3]
    out = save_raw(records, tmp_path / "raw.json")
    reloaded = load_records(out)
    assert [r["email"] for r in reloaded] == [r["email"] for r in records]


def test_fetch_users_returns_list(monkeypatch):
    payload = [{"name": "Ana", "email": "a@b.co", "company": {"name": "Acme"}}]
    captured = {}

    def fake_get(url, timeout=None, headers=None):
        captured.update(url=url, timeout=timeout, headers=headers)
        return FakeResponse(payload)

    monkeypatch.setattr("leadharvest.sources.requests.get", fake_get)
    users = fetch_users()
    assert users == payload
    assert captured["url"] == API_DEFAULT
    assert captured["timeout"] == 15.0
    assert "leadharvest" in captured["headers"]["User-Agent"]


def test_fetch_users_rejects_non_list_payload(monkeypatch):
    monkeypatch.setattr(
        "leadharvest.sources.requests.get",
        lambda *a, **k: FakeResponse({"oops": True}),
    )
    with pytest.raises(ValueError, match="expected a JSON list"):
        fetch_users("https://example.test/api")


def test_collect_cli_from_csv_writes_snapshot(tmp_path):
    out = tmp_path / "raw.json"
    code = main(["collect", "--from-csv", str(CSV_SAMPLE), "--out", str(out)])
    assert code == 0
    assert out.exists()
    assert len(load_records(out)) == 15


def test_collect_cli_missing_input_returns_error(tmp_path):
    code = main(["collect", "--from-csv", str(tmp_path / "nope.csv")])
    assert code == 1
