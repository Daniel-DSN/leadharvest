"""Enrichment pipeline tests — pure functions, fully offline."""

from pathlib import Path

from leadharvest.enrich import (
    compute_stats,
    domain_from_email,
    enrich_record,
    enrich_records,
    format_stats,
    is_valid_email,
    normalize_city,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_website,
)
from leadharvest.sources import load_records

ROOT = Path(__file__).parent.parent
CSV_SAMPLE = ROOT / "samples" / "leads_raw.csv"


def test_normalize_name_title_cases_and_collapses_spaces():
    assert normalize_name("  ana   claudia silva ") == "Ana Claudia Silva"


def test_normalize_email_lowercases_and_trims():
    assert normalize_email("  Karla@Agencia.COM.BR ") == "karla@agencia.com.br"


def test_is_valid_email_accepts_and_rejects():
    assert is_valid_email("ana.silva@agencia.com.br")
    assert not is_valid_email("joao.silva@.com")
    assert not is_valid_email("igor.martins@@mail.com")
    assert not is_valid_email("pedro(at)mailinator.com")
    assert not is_valid_email("")


def test_normalize_phone_br_three_formats_converge():
    variants = ["(11) 99999-0000", "11 99999 0000", "+55 11 99999-0000"]
    assert [normalize_phone(v) for v in variants] == ["+5511999990000"] * 3


def test_normalize_phone_br_with_country_code_and_landline():
    assert normalize_phone("55 21 97777-6666") == "+5521977776666"
    assert normalize_phone("(11) 3333-4444") == "+551133334444"
    assert normalize_phone("11 3333 4444") == "+551133334444"


def test_normalize_phone_leaves_us_and_empty_alone():
    assert normalize_phone("1-770-736-8031 x41025") == "1770736803141025"
    assert normalize_phone("1-770-736-8031") == "17707368031"
    assert normalize_phone("+1 770 736 8031") == "+17707368031"
    assert normalize_phone("   ") == ""


def test_normalize_website_adds_https_only_when_missing():
    assert normalize_website("hildegard.org") == "https://hildegard.org"
    assert normalize_website("http://old.shop") == "http://old.shop"
    assert normalize_website(" HTTPS://Acme.io ") == "HTTPS://Acme.io"
    assert normalize_website("") == ""


def test_normalize_city_trims_only():
    assert normalize_city("  São   Paulo ") == "São Paulo"


def test_domain_from_email():
    assert domain_from_email("ana@agencia.com.br") == "agencia.com.br"
    assert domain_from_email("no-at-sign") == ""


def test_enrich_record_normalizes_every_field():
    lead = enrich_record(
        {
            "name": "  ana   silva ",
            "email": "ANA@Agencia.com.br",
            "phone": "(11) 99999-0000",
            "website": "agencia.com.br",
            "company": "  Agência Ponto ",
            "city": " São Paulo ",
        }
    )
    assert lead.name == "Ana Silva"
    assert lead.email == "ana@agencia.com.br"
    assert lead.phone == "+5511999990000"
    assert lead.website == "https://agencia.com.br"
    assert lead.company == "Agência Ponto"
    assert lead.city == "São Paulo"
    assert lead.domain == "agencia.com.br"


def test_enrich_records_counts_pipeline_and_keeps_first_duplicate():
    rows = [
        {"name": "Ana Silva", "email": "ana@x.co"},
        {"name": "Ana Silvana", "email": "ANA@x.co"},
        {"name": "Bad", "email": "nope@"},
        {"name": "NoMail", "email": ""},
        {"name": "Bruno", "email": "bruno@y.io"},
    ]
    result = enrich_records(rows)
    assert result.raw_count == 5
    assert result.valid_count == 2
    assert result.duplicate_count == 1
    assert result.rejected_count == 2
    assert result.leads[0].name == "Ana Silva"
    assert [r.reason for r in result.rejected] == [
        "invalid email format",
        "missing email",
    ]
    assert format_stats(result) == "raw 5 → valid 2 → duplicates 1 → rejected 2"


def test_enrich_records_on_messy_sample_csv():
    result = enrich_records(load_records(CSV_SAMPLE))
    assert result.raw_count == 15
    assert result.valid_count == 9
    assert result.duplicate_count == 2
    assert result.rejected_count == 4
    assert all(lead.email == lead.email.lower() for lead in result.leads)
    assert all(lead.website.startswith("https://") for lead in result.leads)
    assert all(lead.domain for lead in result.leads)


def test_compute_stats_totals_cities_and_top_domains():
    result = enrich_records(load_records(CSV_SAMPLE))
    stats = compute_stats(result.leads, top_domains=2)
    assert stats.total == 9
    assert dict(stats.by_city)["São Paulo"] == 3
    assert dict(stats.by_city)["Curitiba"] == 2
    assert len(stats.by_domain) == 2
    assert stats.by_domain[0] == ("agencia.com.br", 2)
