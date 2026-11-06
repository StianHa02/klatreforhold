"""Kjører modellen for alle felt og lagrer i Supabase. Kjøres hver time (Raspberry Pi, reserve i GitHub Actions).

  $env:SUPABASE_URL = "https://<ref>.supabase.co"; $env:SUPABASE_SERVICE_ROLE_KEY = "<secret key>"
  python scripts/publish_forecast.py            # skriver til Supabase
  python scripts/publish_forecast.py --dry-run  # bare test, skriver ingenting
  python scripts/publish_forecast.py --dry-run --felt uteveggen  # bare ett felt (kan gjentas)
"""
import argparse
import json
import sys

from _common import ROOT  # noqa: F401  (setter opp sys.path)

from klatreforhold.publish import publish_all
from klatreforhold.storage import SupabaseStorage, get_storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--felt", action="append", metavar="SLUG", help="bare dette feltet (kan gjentas)")
    a = ap.parse_args()
    if a.felt:
        from klatreforhold.predict import list_crags
        ukjente = sorted(set(a.felt) - {c["slug"] for c in list_crags()})
        if ukjente:
            sys.exit(f"Ukjent felt: {', '.join(ukjente)}")
    st = get_storage()
    if not a.dry_run and not isinstance(st, SupabaseStorage):
        sys.exit("Sett SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY (eller bruk --dry-run)")
    res = publish_all(st, dry_run=a.dry_run, felter=a.felt)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if any("feil" in r for r in res.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
