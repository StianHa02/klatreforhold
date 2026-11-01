"""Importerer weewx-databasen fra værstasjonen på Bønes (Davis Vantage Pro2 Plus) til timesverdier i modellens format.

  python scripts/import_bones.py --db "C:/.../weewx-2026-10-31.sdb" --start 2021-11-01
  python scripts/import_bones.py --db ... --start 2021-11-01 --sammenlign    # mot Open-Meteo-historikk

Skriver data/raw/bones_stasjon_<start>_<slutt>.csv med kolonnene modellen bruker (SI-enheter, UTC, timen som
slutter ved tidsstempelet). Filen kan brukes direkte med run_history.py, compare_params.py --weather og
sensitivity.py --weather. Se https://weather.kippenbroeck.no/database.md for skjema og forbehold.
"""
import argparse
import sqlite3

import numpy as np
import pandas as pd
from _common import ROOT

from klatreforhold.data.bones import hourly_from_raw

F_TO_C = lambda f: (f - 32) * 5 / 9
MPH = 0.44704
INCH = 25.4


def les_archive(db: str, start: str, slutt: str | None) -> pd.DataFrame:
    q = ("select dateTime, outTemp, outHumidity, dewpoint, rain, windSpeed, windDir, windGust, radiation, barometer "
         "from archive where dateTime > strftime('%s', ?)")
    args = [start]
    if slutt:
        q += " and dateTime <= strftime('%s', ?)"
        args.append(slutt)
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
        df = pd.read_sql(q, con, params=args)
    df.index = pd.to_datetime(df.pop("dateTime"), unit="s", utc=True)
    return df


def til_metrisk(raw: pd.DataFrame) -> pd.DataFrame:
    """US-enheter i weewx -> samme metriske kolonner som API-et gir (data/bones.py)."""
    return pd.DataFrame({
        "air_temperature": F_TO_C(raw["outTemp"]), "relative_humidity": raw["outHumidity"],
        "dew_point_2m": F_TO_C(raw["dewpoint"]), "precipitation": raw["rain"] * INCH,
        "wind_speed": raw["windSpeed"] * MPH, "wind_gust": raw["windGust"] * MPH, "wind_direction": raw["windDir"],
        "ghi": raw["radiation"], "pressure_hpa": raw["barometer"] * 33.8639,
    }, index=raw.index)


def til_timer(raw: pd.DataFrame) -> pd.DataFrame:
    out = hourly_from_raw(til_metrisk(raw))
    out["weather_source"] = "bones_stasjon"
    out["weather_kind"] = "observation"
    return out


def sammenlign(st: pd.DataFrame, lat: float, lon: float, start: str, slutt: str) -> None:
    from klatreforhold.data.openmeteo import fetch_history
    om = fetch_history(lat, lon, start, slutt).reindex(st.index)
    felles = ["air_temperature", "relative_humidity", "precipitation", "wind_speed", "ghi"]
    print("\nOpen-Meteo (MET Nordic) minus stasjon, per måned (bias) og samlet RMSE:")
    rows = []
    for c in felles:
        d = (om[c] - st[c]).dropna()
        if c == "precipitation":
            # nedbør: sum per måned, ikke timevis bias
            s = pd.DataFrame({"om": om[c], "st": st[c]}).dropna().resample("MS").sum()
            rows.append({"variabel": c, "bias": f"{(s['om'].sum() / s['st'].sum() - 1) * 100:+.0f} % total",
                         "rmse": f"{np.sqrt(((s['om'] - s['st']) ** 2).mean()):.0f} mm/mnd", "n": len(d)})
        else:
            rows.append({"variabel": c, "bias": f"{d.mean():+.2f}", "rmse": f"{np.sqrt((d ** 2).mean()):.2f}", "n": len(d)})
    print(pd.DataFrame(rows).to_string(index=False))
    rh = (om["relative_humidity"] - st["relative_humidity"]).dropna()
    print("\nRF-bias (Open-Meteo minus stasjon) per måned i året:")
    print(rh.groupby(rh.index.month).mean().round(1).to_string())
    dag = om["ghi"].notna() & st["ghi"].notna() & (st.index.hour >= 6) & (st.index.hour <= 18)
    r = (om.loc[dag, "ghi"] / st.loc[dag, "ghi"].where(st.loc[dag, "ghi"] > 20)).dropna()
    print(f"\nStråling: Open-Meteo / stasjon (median, dagtimer med >20 W/m²): {r.median():.2f}  "
          f"sum-forhold: {om.loc[dag, 'ghi'].sum() / st.loc[dag, 'ghi'].sum():.2f}")
    stille = (st["wind_speed"] == 0).mean()
    print(f"Vind: stasjon snitt {st['wind_speed'].mean():.2f} m/s, Open-Meteo {om['wind_speed'].mean():.2f} m/s; "
          f"stasjonen viser 0 m/s i {stille:.0%} av timene")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--start", default="2021-11-01")
    ap.add_argument("--slutt", default=None, help="YYYY-MM-DD, standard = siste måling")
    ap.add_argument("--sammenlign", action="store_true", help="sammenlign med Open-Meteo-historikk for Ekstraveggen")
    a = ap.parse_args()
    raw = les_archive(a.db, a.start, a.slutt)
    st = til_timer(raw)
    slutt = st.index[-1].strftime("%Y-%m-%d")
    out = ROOT / "data" / "raw" / f"bones_stasjon_{a.start}_{slutt}.csv"
    st.to_csv(out)
    hull = st["air_temperature"].isna().mean()
    print(f"{len(raw)} målinger -> {len(st)} timer ({hull:.1%} hull) -> {out}")
    print(st[["air_temperature", "relative_humidity", "precipitation", "wind_speed", "ghi"]].describe().round(2).to_string())
    if a.sammenlign:
        from klatreforhold.config import load_config
        crag, _ = load_config(ROOT / "config" / "ekstraveggen.yaml")
        sammenlign(st, crag.lat, crag.lon, a.start, slutt)


if __name__ == "__main__":
    main()
