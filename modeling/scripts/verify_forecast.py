"""Hvor godt treffer værvarselet? Sammenligner med målestasjoner i Frost (krever FROST_CLIENT_ID i .env).

To moduser:
  python scripts/verify_forecast.py
      Fra arkivet i Supabase: varselet for stasjonens koordinater, slik det så ut 0-48 timer før,
      mot det stasjonen faktisk målte. Vokser for hver time timesjobben kjører.

  python scripts/verify_forecast.py --historikk 2025-01-01 2026-10-26
      Flere år tilbake med en gang: MET Nordic-historikk ved stasjonen mot målingene (hvor godt modellen
      treffer på samme sted), og værseriene for hvert felt mot samme stasjon (hvor forskjellig været er
      på feltet og ved stasjonen, altså hvor mye man ville bommet ved å bruke stasjonen for feltet).
"""
import argparse

import pandas as pd
from _common import ROOT
from train import load_weather

from klatreforhold.predict import list_crags, load_crag
from klatreforhold.verify import scores, to_obs_frame

PD = dict(index=False)


def stations_for_crags():
    out = {}
    for c in list_crags():
        crag, _ = load_crag(c["slug"])
        if crag.frost_station:
            out.setdefault(crag.frost_station, []).append(c["slug"])
    return out


def live():
    from klatreforhold.storage import SupabaseStorage, get_storage
    st = get_storage()
    if not isinstance(st, SupabaseStorage):
        raise SystemExit("Trenger SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY")
    for station, slugs in stations_for_crags().items():
        fc, obs = st.station_forecasts(station), st.station_observations(station)
        print(f"\n=== {station} (brukes av {', '.join(slugs)}): {len(fc)} varseltimer, {len(obs)} målinger ===")
        if fc.empty or obs.empty:
            print("For lite data ennå. Timesjobben samler inn hver time.")
            continue
        res = scores(fc, obs.set_index("tid"))
        print(res.to_string(**PD))
        res.to_csv(ROOT / "outputs" / f"kontroll_{station}_arkiv.csv", index=False)


def history(start, end):
    from klatreforhold.data.frost import RECENT_ELEMENTS, fetch_observations, station_info
    from klatreforhold.data.openmeteo import fetch_history

    for station, slugs in stations_for_crags().items():
        info = station_info(station)
        print(f"\n=== {station} {info.get('navn')} ({info['lat']:.4f}, {info['lon']:.4f}), {start} – {end} ===")
        obs = to_obs_frame(fetch_observations(station, start, end, elements=RECENT_ELEMENTS))
        print(f"{obs.dropna(how='all').shape[0]} timer med målinger")
        rows = []
        met = fetch_history(info["lat"], info["lon"], start, end)
        r = scores(to_obs_frame(met).reset_index(names="tid"), obs, by_lead=False)
        r.insert(0, "værserie", "MET Nordic ved stasjonen")
        rows.append(r)
        for slug in slugs:
            files = sorted((ROOT / "data" / "raw").glob(f"{slug}_openmeteo_metno_*.csv"))
            if not files:
                continue
            w = load_weather(files[-1]).loc[start:end]
            r = scores(to_obs_frame(w).reset_index(names="tid"), obs, by_lead=False)
            r.insert(0, "værserie", f"MET Nordic ved {slug}")
            rows.append(r)
        res = pd.concat(rows).drop(columns="ledetid")
        print(res.to_string(**PD))
        print("\nLes: traff_regn = andel av timene med målt regn der serien også hadde regn. Forskjellen mellom\n"
              "første rad og feltradene viser hvor mye lokalt vær betyr: hvis feltradene treffer stasjonen dårligere,\n"
              "er stasjonen en dårlig erstatning for feltets eget vær.")
        res.to_csv(ROOT / "outputs" / f"kontroll_{station}_historikk.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--historikk", nargs=2, metavar=("START", "SLUTT"))
    a = ap.parse_args()
    if a.historikk:
        history(*a.historikk)
    else:
        live()


if __name__ == "__main__":
    main()
