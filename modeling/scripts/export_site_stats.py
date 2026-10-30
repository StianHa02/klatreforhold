"""Modellstatistikk med oppvarming, konkurrerende regnhendelser og felles værforsøk."""
import json
import argparse
from datetime import date
import numpy as np
import pandas as pd
from _common import ROOT
from train import load_weather
from klatreforhold.config import load_config
from klatreforhold.physics.wetness import run_model
from klatreforhold.physics.drying import drying_events, summarize_events
from klatreforhold.version import MODEL_VERSION, config_hash

OUT = ROOT.parent / "web/data/modellstatistikk.json"


def drying_times(w, res, min_rain_mm=2., cap_h=72):
    return drying_events(w, res, min_rain_mm, cap_h)


def describe(w, res, crag):
    # Årsserier starter midtvinters; de første 90 døgnene tas aldri med som fasit.
    start = w.index.min() + pd.Timedelta(days=90)
    res, w = res.loc[start:], w.loc[start:]
    local = res.index.tz_convert(crag.timezone)
    day = (local.hour >= 8) & (local.hour <= 20)
    dry = ~res.wet
    monthly = dry.groupby(local.month).mean()
    daytime = dry[day].groupby(local.month[day]).mean()
    sun = res.sun_on_face.groupby(local.month).mean() * 24
    events = drying_events(w, res)
    months = pd.DatetimeIndex(events.slutt).tz_convert(crag.timezone).month if len(events) else np.array([])
    summer = np.isin(months, [4, 5, 6, 7, 8, 9])
    summaries = {"sommer": summarize_events(events[summer]), "vinter": summarize_events(events[~summer])}
    def month_values(series):
        return [round(float(series[m]), 3) if m in series else None for m in range(1, 13)]
    return {
        "navn": crag.name, "orientering": crag.face_azimuth_deg, "helning": crag.face_tilt_deg,
        "periode": [str(local.min().date()), str(local.max().date())],
        "tort_per_maned": month_values(monthly), "tort_dagtid_per_maned": month_values(daytime),
        "soltimer_per_dogn": month_values(sun),
        "torketid_timer": {k: s["fullfort"] for k, s in summaries.items()}, "torkeepisoder": summaries,
        "regn_pa_veggen_mm_per_ar": round(float(res.rain_on_face_mm.sum() / (len(res) / 8766))),
        "nedbor_mm_per_ar": round(float(w.precipitation.sum() / (len(w) / 8766))),
        "vintertimer": int((res.status == "is").sum()),
        "massefeil_maks_mm": float(res.mass_balance_error_mm.abs().max()),
        "energifeil_maks_j_m2": float(res.energy_balance_error_j_m2.abs().max()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-missing", action="store_true", help="hent offentlig værhistorikk for nye felt")
    args = ap.parse_args()
    fields, common = {}, {}
    reference = sorted((ROOT / "data/raw").glob("ekstraveggen_openmeteo_metno_*.csv"))[-1]
    common_weather = load_weather(reference)
    for cfg in sorted((ROOT / "config").glob("*.yaml")):
        files = sorted((ROOT / "data/raw").glob(f"{cfg.stem}_openmeteo_metno_*.csv"))
        crag, params = load_config(cfg)
        if not files and args.fetch_missing:
            from klatreforhold.data.openmeteo import fetch_history
            start, end = str(common_weather.index.min().date()), str(common_weather.index.max().date())
            print(f"Henter {cfg.stem}: {start}–{end}", flush=True)
            try:
                weather = fetch_history(crag.lat, crag.lon, start, end)
                path = ROOT / f"data/raw/{cfg.stem}_openmeteo_metno_{start}_{end}.csv"
                weather.to_csv(path)
                files = [path]
            except Exception as err:
                print(f"Historikk utilgjengelig for {cfg.stem}: {type(err).__name__}. Kun kontrollforsøk med felles vær.", flush=True)
        if not files:
            common[cfg.stem] = describe(common_weather, run_model(common_weather, crag, params), crag)
            continue
        w = load_weather(files[-1])
        r = run_model(w, crag, params)
        fields[cfg.stem] = {**describe(w, r, crag), "konfigurasjon": config_hash(crag, params)}
        # Samme timer og vær fra Ekstraveggen, med de forskjellige veggenes geometri/parametre.
        rr = r if w.equals(common_weather) else run_model(common_weather, crag, params)
        common[cfg.stem] = describe(common_weather, rr, crag)
        print(cfg.stem, fields[cfg.stem]["torketid_timer"], flush=True)
    payload = {"generert": str(date.today()), "modellversjon": MODEL_VERSION, "oppvarming_dogn": 90,
               "felt": fields, "felles_vaer": {"kilde": "Ekstraveggen", "felt": common}, "simulering": None}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
