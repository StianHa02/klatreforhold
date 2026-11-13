"""Etterfyller arkivet med dagens konfigurasjon, ved å spille lagret vær (`vaer`) gjennom modellen.

  python scripts/etterfyll_varsel.py                      # alle felt: skriver bare lokale filer + rapport
  python scripts/etterfyll_varsel.py --felt ekstraveggen  # ett felt (kan gjentas)
  python scripts/etterfyll_varsel.py --skriv              # oppdaterer også ledetid 0 i varsel (se under)

Lokalt (modeling/data/etterfylt/<felt>.parquet): analysen for hver time med dagens parametre.
Med --skriv overskrives bare rader med ledetid 0 og gammel konfigurasjon i `varsel`. Ledetider over 0 lar seg ikke
gjenskape (værprognosene lagres ikke) og beholder sin opprinnelige konfigurasjon.
Kjør helst etter at arkivet er eksportert (eksporter_arkiv.py), siden Parquet-kopien ikke endres av dette.
"""
import argparse
import sys

import pandas as pd
from _common import ROOT

from klatreforhold.backfill import endringer, innkjoring, skriverader, spill_om
from klatreforhold.predict import list_crags
from klatreforhold.storage import SupabaseStorage, _paged, get_storage

UT = ROOT / "data" / "etterfylt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--felt", action="append", metavar="SLUG")
    ap.add_argument("--skriv", action="store_true", help="oppdater ledetid 0 i varsel (standard: bare lokale filer)")
    ap.add_argument("--uten-innkjoring", action="store_true", help="ikke hent Open-Meteo-innkjøring før første lagrede time")
    a = ap.parse_args()
    st = get_storage()
    if not isinstance(st, SupabaseStorage):
        sys.exit("Sett SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY")
    alle = [c["slug"] for c in list_crags()]
    ukjente = sorted(set(a.felt or []) - set(alle))
    if ukjente:
        sys.exit(f"Ukjent felt: {', '.join(ukjente)}")
    UT.mkdir(parents=True, exist_ok=True)
    totalt = skrevet = 0
    for slug in a.felt or alle:
        try:
            vaer = st.weather(slug)
            if vaer.empty:
                print(f"{slug}: ingen lagret vær"); continue
            spin = None if a.uten_innkjoring else innkjoring(slug, vaer.index.min())
            analyse, info = spill_om(slug, vaer, spin)
            analyse.to_parquet(UT / f"{slug}.parquet")
            arkiv = _paged(st, "varsel", {"felt": f"eq.{slug}", "order": "generert.asc,tid.asc",
                                          "select": "felt,generert,tid,ledetid_timer,status,konfigurasjon"})
            endret = endringer(arkiv, analyse, info["konfigurasjon"])
            n0 = int((endret["ledetid_timer"] == 0).sum()) if not endret.empty else 0
            flip = int(endret["status_endret"].sum()) if not endret.empty else 0
            print(f"{slug}: {len(analyse)} timer analyse (innkjøring {info['innkjoring_timer']} t"
                  f"{'' if info['innkjoring_fullstendig'] else ', UFULLSTENDIG'}); {len(endret)} arkivrader med gammel "
                  f"konfigurasjon, {flip} med annen status, {n0} med ledetid 0")
            totalt += len(endret)
            if a.skriv and n0:
                rader = skriverader(slug, endret, info["konfigurasjon"], info["modellversjon"])
                for i in range(0, len(rader), 500):
                    st._upsert("varsel", rader[i:i + 500], "felt,generert,tid")
                skrevet += len(rader)
        except Exception as err:  # ett felt skal ikke stoppe resten
            print(f"{slug}: FEIL {type(err).__name__}: {err}")
    print(f"Ferdig: {totalt} rader har gammel konfigurasjon; {skrevet} skrevet" + ("" if a.skriv else " (ingen skriving uten --skriv)"))


if __name__ == "__main__":
    main()
