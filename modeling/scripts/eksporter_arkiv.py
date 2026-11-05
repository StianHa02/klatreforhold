"""Eksporterer varselarkivet (varsel, stasjon_varsel) til Parquet, én fil per UTC-døgn, og laster det opp
til Storage-bøtta `arkiv` i Supabase. Kjøres hver natt av klatreforhold-arkiv.timer på Raspberry Pi-en.
Se docs/ARKIV.md.

  python scripts/eksporter_arkiv.py              # alle ferdige døgn uten kvittering: last opp, kontroller, kvitter
  python scripts/eksporter_arkiv.py --dry-run    # skriver bare filer i data/arkiv/, ingenting til Supabase
  python scripts/eksporter_arkiv.py --hent       # laster ned hele arkivet til data/arkiv/ (analyse lokalt)
"""
import argparse
import datetime as dt
import sys

from _common import ROOT  # noqa: F401  (setter opp sys.path)

from klatreforhold.arkiv import LOKAL, TABELLER, eksporter, hent
from klatreforhold.storage import SupabaseStorage, get_storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="skriv bare lokale filer")
    ap.add_argument("--hent", action="store_true", help="last ned kvitterte filer til data/arkiv/")
    ap.add_argument("--til", type=dt.date.fromisoformat, default=None, help="siste døgn (UTC), standard i går")
    ap.add_argument("--tabell", choices=sorted(TABELLER), action="append", help="standard begge")
    a = ap.parse_args()
    st = get_storage()
    if not isinstance(st, SupabaseStorage):
        sys.exit("Sett SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY først")
    if a.hent:
        print(f"{hent(st)} filer hentet til {LOKAL}")
        return
    ut = eksporter(st, til=a.til, tabeller=a.tabell, dry_run=a.dry_run)
    n = [k for k in ut if k["rader"]]
    print(f"{len(n)} døgn eksportert" + (" (dry-run, ingenting lastet opp)" if a.dry_run else "")
          + (f", {sum(k['rader'] for k in n)} rader, {sum(k['bytes'] for k in n) / 1024:.0f} kB" if n else ""))


if __name__ == "__main__":
    main()
