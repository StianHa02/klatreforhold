"""Henter brukernes observasjoner fra Supabase til data/labels/ for trening.

  $env:SUPABASE_URL = "https://<ref>.supabase.co"
  $env:SUPABASE_SERVICE_ROLE_KEY = "<service role / secret key>"
  python scripts/export_observations.py
  python scripts/train.py --weather <vær>.csv --labels data/labels/ekstraveggen_observasjoner_supabase.csv --torch --save
"""
import argparse

from _common import ROOT

from klatreforhold.predict import list_crags
from klatreforhold.storage import SupabaseStorage, get_storage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--felt", default=None, help="slug, standard alle")
    ap.add_argument("--med-dev", action="store_true", help="ta med observasjoner fra utvikling (kilde=dev)")
    a = ap.parse_args()
    st = get_storage()
    if not isinstance(st, SupabaseStorage):
        raise SystemExit("Sett SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY først")
    slugs = [a.felt] if a.felt else [c["slug"] for c in list_crags()]
    out_dir = ROOT / "data" / "labels"
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        df = st.all_observations(slug, include_dev=a.med_dev)
        path = out_dir / f"{slug}_observasjoner_supabase.csv"
        if df.empty:
            print(f"{slug}: ingen observasjoner")
            continue
        df.rename(columns={"tid": "time"})[["time", "status", "predikert_status", "riktig", "kommentar", "kilde",
                                            "registrert"]].to_csv(path, index=False)
        print(f"{slug}: {len(df)} observasjoner -> {path}")


if __name__ == "__main__":
    main()
