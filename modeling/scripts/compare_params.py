"""Sammenligner varselet for et felt med og uten endrede parametre, på samme værdata.

  python scripts/compare_params.py --set wdr_coefficient=0.2 --set wind_exposure=0.6
  python scripts/compare_params.py --sweep holds_capacity_mm 0.3 0.6 1.2
  python scripts/compare_params.py --set crag.face_azimuth_deg=300          # også feltgeometri
  python scripts/compare_params.py --weather data/raw/<fil>.csv --set seep_timescale_h=60   # historikk

Værdata hentes fra Open-Meteo første gang og lagres i outputs/<felt>_vaer_cache.csv, så alle
varianter kjøres på nøyaktig samme input. Bruk --refresh for å hente på nytt.
"""
import argparse
import dataclasses

import pandas as pd
from _common import DEFAULT_CONFIG, ROOT
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.physics.wetness import hours_until_dry, run_model

STATUSER = ["tort", "fuktig", "vatt", "is"]


def parse_set(items):
    crag_over, param_over = {}, {}
    for s in items or []:
        key, _, val = s.partition("=")
        if not val:
            raise SystemExit(f"--set må være key=verdi, fikk '{s}'")
        try:
            v = float(val)
        except ValueError:
            v = {"true": True, "false": False}.get(val.lower(), val)
        if key.startswith("crag."):
            crag_over[key[5:]] = v
        else:
            param_over[key] = v
    return crag_over, param_over


def kjor(w, crag, params, crag_over, param_over):
    c = dataclasses.replace(crag, **crag_over) if crag_over else crag
    res = run_model(w, c, {**params, **param_over})
    res["hours_until_dry"] = hours_until_dry(res)
    return res.tz_convert(crag.timezone)


def oppsummer(r, fra):
    v = r.loc[fra:]
    teller = v["status"].value_counts().reindex(STATUSER, fill_value=0)
    hud = v["hours_until_dry"].iloc[0] if len(v) else float("nan")
    return {**{f"t_{s}": int(teller[s]) for s in STATUSER},
            "timer_til_tort_na": hud,
            "maks_vann_mm": round(float(v["water_mm"].max()), 3),
            "regn_pa_vegg_mm": round(float(v["rain_on_face_mm"].sum()), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", help="CSV fra fetch_history.py; ellers hentes varsel fra Open-Meteo")
    ap.add_argument("--set", action="append", metavar="KEY=VERDI", help="overstyr modellparameter (eller crag.<felt>)")
    ap.add_argument("--sweep", nargs="+", metavar=("PARAM", "VERDI"), help="én parameter, flere verdier")
    ap.add_argument("--refresh", action="store_true", help="hent værdata på nytt")
    ap.add_argument("--fra", help="start for sammendrag/tabell (YYYY-MM-DD HH); standard = nå")
    ap.add_argument("--alle-timer", action="store_true", help="vis alle timer, ikke bare de som endres")
    a = ap.parse_args()

    crag, params = load_config(a.config)
    if a.weather:
        w = load_weather(a.weather)
        num = w.select_dtypes("number").columns
        w[num] = w[num].interpolate(limit=3)
    else:
        cache = ROOT / "outputs" / f"{crag.name.lower()}_vaer_cache.csv"
        if a.refresh or not cache.exists():
            from klatreforhold.data.openmeteo import fetch_forecast
            w = fetch_forecast(crag.lat, crag.lon, past_days=5, forecast_days=3)
            cache.parent.mkdir(parents=True, exist_ok=True)
            w.to_csv(cache)
            print(f"Værdata hentet -> {cache}")
        else:
            w = load_weather(cache)
            print(f"Værdata fra {cache} (--refresh for å hente på nytt)")

    varianter = []
    if a.set:
        varianter.append(("variant", *parse_set(a.set)))
    if a.sweep:
        p, *verdier = a.sweep
        for v in verdier:
            varianter.append((f"{p}={v}", *parse_set([f"{p}={v}"])))
    if not varianter:
        raise SystemExit("Angi --set KEY=VERDI og/eller --sweep PARAM V1 V2 ...")

    basis = kjor(w, crag, params, {}, {})
    fra = pd.Timestamp(a.fra, tz=crag.timezone) if a.fra else pd.Timestamp.now(tz=crag.timezone).floor("h")
    if a.weather and not a.fra:
        fra = basis.index[0]

    rader = [{"variant": "basis", **oppsummer(basis, fra)}]
    kolonner = pd.DataFrame({"basis": basis.loc[fra:, "status"]})
    for navn, c_over, p_over in varianter:
        for k in p_over:
            if k not in params:
                print(f"ADVARSEL: '{k}' finnes ikke i modellparametrene for {crag.name}")
        r = kjor(w, crag, params, c_over, p_over)
        s = oppsummer(r, fra)
        s["timer_endret"] = int((r.loc[fra:, "status"] != basis.loc[fra:, "status"]).sum())
        rader.append({"variant": navn, **s})
        kolonner[navn] = r.loc[fra:, "status"]

    print("\nSammendrag fra", fra.strftime("%Y-%m-%d %H:%M"), f"({len(kolonner)} timer):")
    print(pd.DataFrame(rader).set_index("variant").fillna("-").to_string())

    endret = kolonner[(kolonner.ne(kolonner["basis"], axis=0)).any(axis=1)]
    vis = kolonner if a.alle_timer else endret
    if len(vis):
        print(f"\nStatus per time ({'alle' if a.alle_timer else 'kun timer som endres'}):")
        vis = vis.copy()
        vis.index = vis.index.strftime("%a %d.%m %H:%M")
        print(vis.to_string())
    else:
        print("\nIngen timer endrer status.")


if __name__ == "__main__":
    main()
