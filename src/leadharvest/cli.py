"""LeadHarvest command-line interface.

Commands
--------
    leadharvest collect --from-api  [--base-url URL] [--out raw.json]
    leadharvest collect --from-csv  samples/leads_raw.csv [--out raw.json]
    leadharvest enrich  raw.json -o leads.xlsx [--report rejected.csv]
    leadharvest stats   leads.xlsx

Exit codes: 0 = success, 1 = error, 2 = zero valid leads.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .enrich import compute_stats, enrich_records, format_stats
from .export import export, load_leads, write_rejected
from .sources import API_DEFAULT, fetch_users, load_records, save_raw


def cmd_collect(args: argparse.Namespace) -> int:
    if args.from_api:
        origin = args.base_url
        print(f"LeadHarvest {__version__} — collecting from {origin}")
        records = fetch_users(args.base_url)
        print(f"[ok] fetched {len(records)} records")
    else:
        origin = args.from_csv
        print(f"LeadHarvest {__version__} — reading {origin}")
        records = load_records(Path(args.from_csv))
        print(f"[ok] loaded {len(records)} records")

    if not records:
        print("[warn] no records found", file=sys.stderr)
        return 1
    if args.out:
        save_raw(records, Path(args.out))
        print(f"[ok] saved raw snapshot → {args.out}")
    else:
        print("[hint] pass --out raw.json to keep a snapshot for `enrich`")
    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    source = Path(args.input)
    print(f"LeadHarvest {__version__} — enriching {source}")
    records = load_records(source)
    result = enrich_records(records)
    print(f"[stats] {format_stats(result)}")

    if args.report:
        write_rejected(result.rejected, Path(args.report))
        print(f"[ok] rejected report → {args.report} ({result.rejected_count} rows)")

    if not result.leads:
        print("[warn] zero valid leads — nothing exported", file=sys.stderr)
        return 2

    export(result.leads, Path(args.output))
    print(f"[ok] exported {result.valid_count} leads → {args.output}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    source = Path(args.input)
    print(f"LeadHarvest {__version__} — stats for {source}")
    leads = load_leads(source)
    if not leads:
        print("[warn] zero valid leads in file", file=sys.stderr)
        return 2

    stats = compute_stats(leads)
    print(f"[stats] {stats.total} valid leads")
    print("  by city:")
    for city, count in stats.by_city:
        print(f"    {city:<24} {count}")
    print("  by domain (top 5):")
    for domain, count in stats.by_domain:
        print(f"    {domain:<24} {count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leadharvest",
        description="Collect, enrich and export B2B lead lists.",
    )
    parser.add_argument(
        "--version", action="version", version=f"leadharvest {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("collect", help="fetch leads from a public API or CSV")
    source = c.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--from-api", action="store_true", help="fetch JSON user records"
    )
    source.add_argument("--from-csv", metavar="PATH", help="read leads from CSV")
    c.add_argument(
        "--base-url",
        default=API_DEFAULT,
        help=f"API endpoint (default: {API_DEFAULT})",
    )
    c.add_argument("--out", metavar="PATH", help="save raw snapshot as JSON")
    c.set_defaults(func=cmd_collect)

    e = sub.add_parser("enrich", help="normalize, validate, dedupe and export")
    e.add_argument("input", help="raw records (.json or .csv)")
    e.add_argument(
        "-o",
        "--output",
        required=True,
        help="output file (.csv / .xlsx / .json)",
    )
    e.add_argument("--report", metavar="PATH", help="write rejected rows to CSV")
    e.set_defaults(func=cmd_enrich)

    s = sub.add_parser("stats", help="summarize an exported lead file")
    s.add_argument("input", help="lead file (.xlsx / .csv / .json)")
    s.set_defaults(func=cmd_stats)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[abort] interrupted", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
