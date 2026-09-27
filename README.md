# LeadHarvest

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#testing)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**B2B lead collection, enrichment and export — dirty lists in, verified `.xlsx` out.**

Pull public company contacts from an API or CSV → normalize, validate and de-duplicate
them → ship a clean Excel sheet plus an auditable rejection report.

```
API/CSV in → raw.json → enrich → leads.xlsx + rejected.csv → stats
```

---

## Why this exists

Lead lists arrive messy: phones in three formats, e-mail in the wrong case,
typos that bounce, copy-pasted duplicates. Cleaning them by hand steals hours
before any outreach even starts. LeadHarvest does the boring half:

- **Collect** from a public JSON API (`--from-api`) or your own CSV (`--from-csv`)
- **Normalize** names, e-mails, phones (BR `+55` aware), websites and cities
- **Validate** e-mail syntax → bad rows land in a `rejected.csv` with a reason
- **Deduplicate** by e-mail (first occurrence wins) with a full pipeline count
- **Export** CSV / JSON / styled Excel (bold header, frozen first row) by suffix
- **Report** totals per city and top domains — **exit code 2 when zero valid
  leads**, so cron/CI fails loudly instead of sending an empty sheet

## Quick start

```bash
pip install -r requirements.txt                      # requests, openpyxl
PYTHONPATH=src python3 -m leadharvest.cli --help     # (or: pip install -e .)
```

Run the bundled pipeline — the same four commands that produced [`demo/`](demo/)
(every line below runs with `PYTHONPATH=src`, or installed via `pip install -e .`):

```bash
# 1) fetch 10 public records → raw snapshot
python3 -m leadharvest.cli collect --from-api --out demo/raw.json

# 2) clean them → Excel + rejection report
python3 -m leadharvest.cli enrich demo/raw.json \
    -o demo/leads.xlsx --report demo/rejected.csv

# 3) summarize the result
python3 -m leadharvest.cli stats demo/leads.xlsx

# 4) same pipeline against a messy local CSV
python3 -m leadharvest.cli enrich samples/leads_raw.csv -o demo/leads_from_csv.csv
```

Real captured output ([`demo/demo_run1.txt`](demo/demo_run1.txt)):

```
$ python3 -m leadharvest.cli collect --from-api --out demo/raw.json
LeadHarvest 1.0.0 — collecting from https://jsonplaceholder.typicode.com/users
[ok] fetched 10 records
[ok] saved raw snapshot → demo/raw.json
[exit 0]
```

Enrichment of that live fetch ([`demo/demo_run2.txt`](demo/demo_run2.txt)):

```
$ python3 -m leadharvest.cli enrich demo/raw.json -o demo/leads.xlsx --report demo/rejected.csv
LeadHarvest 1.0.0 — enriching demo/raw.json
[stats] raw 10 → valid 10 → duplicates 0 → rejected 0
[ok] rejected report → demo/rejected.csv (0 rows)
[ok] exported 10 leads → demo/leads.xlsx
[exit 0]
```

Stats over the exported workbook ([`demo/demo_run3.txt`](demo/demo_run3.txt)):

```
$ python3 -m leadharvest.cli stats demo/leads.xlsx
LeadHarvest 1.0.0 — stats for demo/leads.xlsx
[stats] 10 valid leads
  by city:
    Aliyaview                1
    Bartholomebury           1
    Gwenborough              1
    ...
  by domain (top 5):
    annie.ca                 1
    april.biz                1
    billy.biz                1
    dana.io                  1
    jasper.info              1
[exit 0]
```

The messy sample CSV (`samples/leads_raw.csv`, 15 rows with bad e-mails, three
BR phone formats, duplicates and missing companies) shows the full pipeline
([`demo/demo_run4.txt`](demo/demo_run4.txt)):

```
$ python3 -m leadharvest.cli enrich samples/leads_raw.csv -o demo/leads_from_csv.csv
LeadHarvest 1.0.0 — enriching samples/leads_raw.csv
[stats] raw 15 → valid 9 → duplicates 2 → rejected 4
[ok] exported 9 leads → demo/leads_from_csv.csv
[exit 0]
```

Rejected rows carry an explicit reason, e.g.:

```csv
name,email,reason
João Silva,joao.silva@.com,invalid email format
Sem Email,,missing email
Igor Martins,igor.martins@@mail.com,invalid email format
Pedro Valente,pedro(at)mailinator.com,invalid email format
```

## Full CLI

| Command | Purpose |
|---------|---------|
| `leadharvest collect --from-api` | fetch JSON user records (default `jsonplaceholder.typicode.com/users`) |
| `--base-url URL` | point at any endpoint returning a JSON list |
| `collect --from-csv file.csv` | read leads from a CSV instead |
| `--out raw.json` | save the raw snapshot for a later `enrich` run |
| `leadharvest enrich raw.json -o leads.xlsx` | normalize + validate + dedupe + export |
| `-o out.csv \| out.json \| out.xlsx` | export format chosen by suffix |
| `--report rejected.csv` | write rejected rows with reasons |
| `leadharvest stats leads.xlsx` | totals, per-city counts, top-5 domains |
| `--version` | print version |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | success |
| `1` | error (bad input, network failure, unsupported format) |
| `2` | **zero valid leads** — nothing worth exporting |

## Data quality rules

| Field | Rule | Example |
|-------|------|---------|
| `name` | trim, collapse spaces, title case | ` ana   silva ` → `Ana Silva` |
| `email` | lowercase + regex validation | `ANA@Agencia.com.br` → `ana@agencia.com.br` |
| `email` invalid | row rejected with reason | `joao@.com` → `rejected.csv` |
| `phone` | E.164-ish, `+` kept, BR promoted to `+55` | `(11) 99999-0000` → `+5511999990000` |
| `phone` BR variants | all three forms converge | `11 99999 0000`, `+55 11 99999-0000` → `+5511999990000` |
| `website` | `https://` prefixed when scheme missing | `acme.io` → `https://acme.io` |
| `city` | trimmed, whitespace collapsed | `São   Paulo` → `São Paulo` |
| `company` | carried from record (API `company.name`) | `Romaguera-Crona` |
| `domain` | derived from e-mail | `ana@acme.io` → `acme.io` |
| duplicates | same e-mail → keep first | count reported, not exported |

## Architecture

```
src/leadharvest/
├── cli.py       argparse + commands (collect / enrich / stats)
├── sources.py   API fetch + JSON/CSV readers + raw snapshots (I/O)
├── enrich.py    pure normalization, validation, dedupe, stats
├── export.py    CSV / JSON / XLSX writers + readers
└── models.py    Lead / Rejected / EnrichmentResult / LeadStats dataclasses
```

- **Enrichment is pure** (rows in → leads out) → unit-tested with zero network
- **I/O is isolated** in `sources` / `export` → swapping APIs or formats is cheap
- **Nested API payloads flatten automatically** (`company.name`, `address.city`)
- **Stats re-read the exported file** → the report matches the delivered sheet

## Testing

```bash
PYTHONPATH=src python3 -m pytest -q
```

```
33 passed in 1.46s
```

Coverage: record flattening, API/CSV loading (network monkeypatched), raw
snapshots, every normalization rule (3 BR phone formats, e-mail rejection,
https promotion), dedupe + pipeline counts, stats aggregation, CSV/JSON/XLSX
round-trips, rejected-report format and CLI exit codes `0 / 1 / 2`.
All tests run offline against `samples/users_fixture.json`.

## Use cases

| Who | Uses LeadHarvest for |
|-----|----------------------|
| Freelancers | client lead lists → clean Excel deliverable |
| Sales/SDR | conference or directory exports → de-duplicated outreach lists |
| Agencies | merging CSV extracts from multiple tools into one schema |
| Marketing | domain/city breakdowns before running campaigns |
| Ops | scheduled collection → fail (exit 2) when a source returns junk |

## Data policy

- Public business endpoints only — no login-walled or private/personal data
- Source kept verbatim (`raw.json`) so every rejection is auditable
- Rejected rows are reported, never silently dropped
- Respect each source's Terms of Service and applicable anti-spam law
  (LGPD, GDPR, CAN-SPAM) when using the output for outreach

## License

MIT — see [LICENSE](LICENSE).
