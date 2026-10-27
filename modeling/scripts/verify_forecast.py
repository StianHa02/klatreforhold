"""Hvor godt treffer værvarselet? Sammenligner med målestasjoner i Frost (krever FROST_CLIENT_ID i .env).

To moduser:
  python scripts/verify_forecast.py
      Fra arkivet i Supabase: varselet for stasjonens koordinater, slik det så ut 0-48 timer før,
      mot det stasjonen faktisk målte. Vokser for hver time timesjobben kjører.

  python scripts/verify_forecast.py --historikk [START SLUTT] [--skriv-rh]
      Flere år tilbake (standard fra 2023-01-01 til i går), også per sesong, år, måned og tid på døgnet: MET Nordic-historikk ved stasjonen mot målingene (hvor godt modellen
      treffer på samme sted), og værseriene for hvert felt mot samme stasjon (hvor forskjellig været er
      på feltet og ved stasjonen, altså hvor mye man ville bommet ved å bruke stasjonen for feltet).
      --skriv-rh skriver en fuktighetskorreksjon per måned med døgnsvingning til config/stasjoner/rh_korreksjon.yaml (brukes av modellen).
      Hentingene lagres i data/raw, så neste kjøring på samme periode går raskt.
"""
import argparse

import numpy as np
import pandas as pd
from _common import ROOT
from train import load_weather

from klatreforhold.predict import list_crags, load_crag
from klatreforhold.verify import MANEDER, TZ, rain_windows, scores, to_obs_frame

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
        tid = pd.to_datetime(fc["tid"], utc=True)
        if tid.max() - tid.min() > pd.Timedelta(days=60):
            from klatreforhold.verify import scores_by
            kort = fc[fc["ledetid_timer"] <= 24]
            print("\nPer måned, ledetid 0-24 t:")
            print(scores_by(kort, obs.set_index("tid"), "maned").to_string(**PD))
        res.to_csv(ROOT / "outputs" / f"kontroll_{station}_arkiv.csv", index=False)


HIST_START = "2023-01-01"  # hele kalenderår; MET Nordic finnes i Open-Meteo fra 2022-11-15
RAW = ROOT / "data" / "raw"


def _cached(path, fetch):
    """Lagrer store hentinger i data/raw, så en ny kjøring på samme periode går raskt."""
    if path.exists():
        return load_weather(path)
    df = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return df


def _crag_weather(slug, crag, start, end):
    from klatreforhold.data.openmeteo import fetch_history
    s, e = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    for f in sorted(RAW.glob(f"{slug}_openmeteo_metno_*.csv"), reverse=True):
        w = load_weather(f)
        if w.index.min() <= s and w.index.max() >= e - pd.Timedelta(days=1):
            return w.loc[s:e]
    return _cached(RAW / f"{slug}_openmeteo_metno_{start}_{end}.csv",
                   lambda: fetch_history(crag.lat, crag.lon, start, end))


def _show(title, df):
    print(f"\n{title}")
    print(df.to_string(**PD))


def history(start, end, skriv_rh=False):
    from klatreforhold.data.frost import RECENT_ELEMENTS, fetch_observations, station_info
    from klatreforhold.data.openmeteo import fetch_history
    from klatreforhold.physics.wetness import rh_correction
    from klatreforhold.verify import (rain_windows_by, rh_bias_by_level, rh_bias_table, rh_bias_year_month,
                                      rh_correction_fit, rh_quantiles, scores_by)

    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    for station, slugs in stations_for_crags().items():
        info = station_info(station)
        print(f"\n=== {station} {info.get('navn')} ({info['lat']:.4f}, {info['lon']:.4f}), {start} – {end} ===")
        frost = _cached(RAW / f"frost_{station}_{start}_{end}.csv",
                        lambda: fetch_observations(station, start, end, elements=RECENT_ELEMENTS))
        obs = to_obs_frame(frost)
        print(f"{obs.dropna(how='all').shape[0]} timer med målinger")
        met = _cached(RAW / f"stasjon_{station}_openmeteo_metno_{start}_{end}.csv",
                      lambda: fetch_history(info["lat"], info["lon"], start, end))
        series = {"MET Nordic ved stasjonen": met}
        for slug in slugs:
            crag, _ = load_crag(slug)
            series[f"MET Nordic ved {slug}"] = _crag_weather(slug, crag, start, end)

        # 1) Hele perioden, alle værserier
        rows, vinduer = [], []
        for navn, w in series.items():
            r = scores(to_obs_frame(w).reset_index(names="tid"), obs, by_lead=False)
            r.insert(0, "værserie", navn)
            rows.append(r)
            vinduer.append({"værserie": navn, **rain_windows(w["precipitation"], obs["nedbor_mm"])})
        res = pd.concat(rows).drop(columns="ledetid")
        vin = pd.DataFrame(vinduer)
        _show("Hele perioden, time for time:", res)
        _show("Regn over lengre vinduer (>= 0.5 mm i vinduet), og korrelasjon for døgnsum:", vin)
        res.to_csv(out / f"kontroll_{station}_historikk.csv", index=False)
        vin.to_csv(out / f"kontroll_{station}_historikk_vinduer.csv", index=False)

        # 2) Sesong, år og døgn for MET Nordic ved stasjonen (ren modellfeil, ikke stedsforskjell)
        fc = to_obs_frame(met).reset_index(names="tid")
        sesong = scores_by(fc, obs, "sesong")
        aar = scores_by(fc, obs, "aar")
        vin_s = rain_windows_by(met["precipitation"], obs["nedbor_mm"], "sesong")
        vin_a = rain_windows_by(met["precipitation"], obs["nedbor_mm"], "aar")
        _show("Per sesong (MET Nordic ved stasjonen):", sesong)
        _show("Regnvinduer per sesong:", vin_s)
        _show("Per år:", aar)
        _show("Regnvinduer per år:", vin_a)

        rh_v, rh_m = met["relative_humidity"], obs["luftfuktighet"]
        rh_mnd = rh_bias_table(rh_v, rh_m, "maned")
        rh_doegn = rh_bias_table(rh_v, rh_m, "doegn")
        rh_niva = rh_bias_by_level(rh_v, rh_m)
        rh_aar_mnd = rh_bias_year_month(rh_v, rh_m)
        _show("Luftfuktighet per måned (varsel - målt, prosentpoeng, alle timer):", rh_mnd)
        _show("Luftfuktighet per tid på døgnet (lokal tid):", rh_doegn)
        _show("Fordelingen, varsel og målt (prosentiler):", rh_quantiles(rh_v, rh_m).reset_index(names="serie"))
        _show("Etter nivå. Snur fortegnet mellom kolonnene, er det mest tilfeldig feil, ikke skjevhet:", rh_niva)
        _show("Skjevhet år x måned (går mønsteret igjen hvert år?):", rh_aar_mnd.reset_index())

        korr = rh_correction_fit(rh_v, rh_m)
        p = {"rh_korreksjon_maned": korr["maned"], "rh_korreksjon_doegn_cos": korr["doegn_cos"],
             "rh_korreksjon_doegn_sin": korr["doegn_sin"]}
        rettet = (rh_v + rh_correction(rh_v.index, p)).clip(0, 100)
        print(f"\nForeslått korreksjon (legges til varselet), fra {korr['timer']} timer:")
        print("  maned:    " + "  ".join(f"{m} {v:+.1f}" for m, v in zip(MANEDER, korr["maned"])))
        kl = np.arange(0, 24, 3)
        tid = pd.DatetimeIndex([pd.Timestamp(f"2025-{mm:02d}-15 {h:02d}:00", tz=TZ) for mm in (1, 4, 7, 10) for h in kl])
        eks = rh_correction(tid, p).reshape(4, -1).round(1)
        _show("Korreksjonen gjennom døgnet (15. i måneden, lokal tid):",
              pd.DataFrame(eks, index=["jan", "apr", "jul", "okt"], columns=[f"kl {h:02d}" for h in kl]).reset_index(names="dag"))
        _show("Etter korreksjon, per sesong (skjevhet bør være nær 0):", rh_bias_table(rettet, rh_m, "sesong"))
        _show("Etter korreksjon, per tid på døgnet:", rh_bias_table(rettet, rh_m, "doegn"))

        pd.concat({"sesong": sesong, "aar": aar}).to_csv(out / f"kontroll_{station}_sesong_aar.csv")
        pd.concat({"sesong": vin_s, "aar": vin_a}).to_csv(out / f"kontroll_{station}_vinduer_sesong_aar.csv")
        rh_mnd.to_csv(out / f"kontroll_{station}_rh_maned.csv", index=False)
        rh_niva.to_csv(out / f"kontroll_{station}_rh_niva.csv", index=False)
        rh_aar_mnd.to_csv(out / f"kontroll_{station}_rh_aar_maned.csv")
        if skriv_rh:
            write_rh_correction(station, korr)


def write_rh_correction(station, korr):
    import yaml
    f = ROOT / "config" / "stasjoner" / "rh_korreksjon.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    data = (yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else None) or {}
    data[station] = {"kilde": f"MET Nordic mot {station}, alle timer, {korr['fra']} – {korr['til']}",
                     "timer": korr["timer"], "konstant": korr["konstant"], "maned": korr["maned"],
                     "doegn_cos": korr["doegn_cos"], "doegn_sin": korr["doegn_sin"]}
    head = ("# Korreksjon av luftfuktigheten i MET Nordic (prosentpoeng som legges til), per Frost-stasjon.\n"
            "# Gjelder alle felt med denne frost_station. Skrevet av:\n"
            "#   python scripts/verify_forecast.py --historikk --skriv-rh\n"
            "# maned (jan-des) brukes når den finnes, ellers konstant. Glatt overgang mellom månedene.\n"
            "# doegn_cos/doegn_sin: døgnsvingning per måned, b*cos(2 pi t/24) + c*sin(2 pi t/24), t = lokal time.\n")
    f.write_text(head + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=None),
                 encoding="utf-8")
    print(f"\nSkrev korreksjonen for {station} til {f.relative_to(ROOT)}. Gjelder fra neste timesjobb etter push.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--historikk", nargs="*", metavar="DATO",
                    help=f"START SLUTT (standard {HIST_START} til i går)")
    ap.add_argument("--skriv-rh", action="store_true",
                    help="skriv foreslått fuktighetskorreksjon til config/stasjoner/rh_korreksjon.yaml")
    a = ap.parse_args()
    if a.historikk is not None:
        if len(a.historikk) not in (0, 2):
            ap.error("--historikk tar enten ingen datoer eller START SLUTT")
        start, end = a.historikk or (HIST_START, (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        history(start, end, skriv_rh=a.skriv_rh)
    else:
        live()


if __name__ == "__main__":
    main()
