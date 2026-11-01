"""Bønes værstasjon: privat Davis Vantage Pro2 Plus 1,3 km fra Ekstraveggen (weather.kippenbroeck.no).

Stasjonen er ikke vår. API-et gir femminuttsmålinger for inntil 168 timer bakover (siste-dogn.php?timer=168),
og timeverdiene regnes ut her. Se docs/BONES_STASJON.md for hvorfor bare regn og temperatur brukes:
fuktigheten viser for høyt i tørr luft og vinden er skjermet.

- En måling merket HH:05 er slutten av intervallet 14:00–14:05 og hører til timen som slutter HH+1,
  samme regel som modellen (nedbør gjelder timen før tidsstempelet).
- Timer med færre enn 10 av 12 målinger får ukjent nedbør (NaN), aldri null.
- Siste måling lagres fortsatt i bones_maling (én rad per kjøring) som reserve hvis historikk-endepunktet
  faller bort; hourly() regner timeverdier fra slike snapshot.

Data: Bønes værstasjon, weather.kippenbroeck.no (CC BY 4.0).
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from .http import get

API_HISTORIKK = "https://weather.kippenbroeck.no/api/siste-dogn.php"
API_HISTORIKK_MAKS_TIMER = 168
KILDE = "Bønes værstasjon, weather.kippenbroeck.no (CC BY 4.0)"
MIN_TEMP_REGN = 2.0  # under dette kan nedbøren være snø, som vippekarmåleren ikke fanger
MIN_MALINGER_PER_TIME = 10
FERSK = pd.Timedelta(minutes=15)
MIN_GAP = pd.Timedelta(minutes=45)
MAX_GAP = pd.Timedelta(minutes=75)

RAW_KOLONNER = {
    "temperatur_c": "air_temperature", "duggpunkt_c": "dew_point_2m", "luftfuktighet_pst": "relative_humidity",
    "vind_ms": "wind_speed", "vindkast_ms": "wind_gust", "vindretning_grader": "wind_direction",
    "lufttrykk_hpa": "pressure_hpa", "nedbor_mm": "precipitation", "straling_wm2": "ghi",
}


def fetch_raw(hours: int = API_HISTORIKK_MAKS_TIMER) -> pd.DataFrame:
    """Femminuttsmålinger (metriske enheter, UTC-indeks = slutten av intervallet) for de siste `hours` timene."""
    hours = max(1, min(int(hours), API_HISTORIKK_MAKS_TIMER))
    r = get(API_HISTORIKK, params={"timer": hours, "format": "csv"}, timeout=30)
    return parse_raw_csv(r.text)


def parse_raw_csv(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    df.index = pd.to_datetime(df.pop("unix"), unit="s", utc=True)
    df.index.name = "tid"
    return df.drop(columns=["tidspunkt", "intervall_minutter"], errors="ignore").rename(columns=RAW_KOLONNER).sort_index()


def latest_row(raw: pd.DataFrame, now: pd.Timestamp | None = None) -> dict | None:
    """Siste måling som rad til bones_maling. None hvis den er eldre enn 15 minutter (stasjonen henger)."""
    if raw.empty:
        return None
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC")).tz_convert("UTC")
    t = raw.index[-1]
    if now - t > FERSK:
        return None
    r = raw.iloc[-1]
    lokal = t.tz_convert("Europe/Oslo")
    # målingen kl. 00:00 hører til døgnet før, slik stasjonen selv teller
    dato = (lokal - pd.Timedelta(seconds=1)).strftime("%Y-%m-%d")
    dag = raw.loc[(raw.index > pd.Timestamp(dato, tz="Europe/Oslo")) & (raw.index <= t), "precipitation"]

    def tall(k):
        v = r.get(k)
        return None if v is None or pd.isna(v) else float(v)
    return {
        "tid": t.isoformat(), "lufttemp": tall("air_temperature"), "luftfuktighet": tall("relative_humidity"),
        "vind_ms": tall("wind_speed"), "vindkast_ms": tall("wind_gust"), "vindretning": tall("wind_direction"),
        "nedbor_i_dag_mm": None if dag.isna().all() else float(dag.sum()), "nedbor_dato": dato,
        "nedbor_intensitet_mm_t": tall("nedbor_intensitet_mm_t"),
    }


def hourly_from_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """Timeverdier (UTC-indeks, timen som slutter ved tidsstempelet) fra femminuttsmålinger."""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["precipitation", "air_temperature"], dtype=float)
    r = raw.copy()
    bins = (r.index - pd.Timedelta(seconds=1)).ceil("h")
    g = r.groupby(bins)
    out = pd.DataFrame(index=g.size().index)
    out["n_malinger"] = g.size()
    for c in ("air_temperature", "relative_humidity", "dew_point_2m", "wind_speed", "ghi", "pressure_hpa"):
        if c in r:
            out[c] = g[c].mean()
    if "precipitation" in r:
        out["precipitation"] = g["precipitation"].sum(min_count=1)
    if "wind_gust" in r:
        out["wind_gust"] = g["wind_gust"].max()
    if {"wind_speed", "wind_direction"}.issubset(r.columns):
        ang = np.deg2rad(r["wind_direction"])
        wx = (np.sin(ang) * r["wind_speed"]).fillna(0).groupby(bins).sum()
        wy = (np.cos(ang) * r["wind_speed"]).fillna(0).groupby(bins).sum()
        out["wind_direction"] = np.mod(np.rad2deg(np.arctan2(wx, wy)), 360)
        out.loc[(wx == 0) & (wy == 0), "wind_direction"] = np.nan
    ufullstendig = out["n_malinger"] < MIN_MALINGER_PER_TIME
    for c in ("precipitation", "ghi"):
        if c in out:
            out.loc[ufullstendig, c] = np.nan
    out = out.asfreq("h")
    out.index.name = "time"
    return out


def hourly(malinger: pd.DataFrame) -> pd.DataFrame:
    """Timeverdier fra lagrede snapshot i bones_maling (reserve når historikk-API-et ikke svarer).

    Én måling per time (den nærmest hel time). Nedbør bare når forrige time også har en måling 45-75 min før,
    fra samme døgn, og telleren ikke har gått ned.
    """
    if malinger is None or malinger.empty:
        return pd.DataFrame(columns=["precipitation", "air_temperature"], dtype=float)
    m = malinger.copy()
    m["tid"] = pd.to_datetime(m["tid"], utc=True)
    m["time"] = m["tid"].dt.round("h")
    m["avstand"] = (m["tid"] - m["time"]).abs()
    m = m.sort_values(["time", "avstand"]).drop_duplicates("time").sort_values("time").set_index("time")
    forrige = m.shift()
    ok = ((m.index.to_series().diff() == pd.Timedelta(hours=1))
          & (m["tid"] - forrige["tid"]).between(MIN_GAP, MAX_GAP)
          & (m["nedbor_dato"].astype(str) == forrige["nedbor_dato"].astype(str)))
    mm = m["nedbor_i_dag_mm"].astype(float) - forrige["nedbor_i_dag_mm"].astype(float)
    ok &= mm >= 0
    out = pd.DataFrame({"precipitation": mm.where(ok), "air_temperature": m["lufttemp"].astype(float)})
    out.index.name = "time"
    return out


def with_rain(w: pd.DataFrame, timer: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Bytter modellens nedbør med målt Bønes-regn i passerte timer der den finnes og det er over +2 °C.

    `timer` er timeverdier fra hourly_from_raw() eller hourly(). Alt annet beholdes fra modellen.
    Uten brukbare målinger returneres w uendret, så varselet virker alltid.
    """
    if timer is None or timer.empty or "precipitation" not in timer:
        w.attrs["bones_timer"] = 0
        return w
    t = timer
    if now is not None:
        t = t.loc[:pd.Timestamp(now).tz_convert("UTC").floor("h")]
    t = t.reindex(w.index)
    temp = t["air_temperature"].where(t["air_temperature"].notna(), w["air_temperature"]) if "air_temperature" in t else w["air_temperature"]
    bruk = t["precipitation"].notna() & (temp > MIN_TEMP_REGN)
    w.attrs["bones_timer"] = int(bruk.sum())
    if not bruk.any():
        return w
    w = w.copy()
    w.loc[bruk, "precipitation"] = t.loc[bruk, "precipitation"].to_numpy()
    if "snow_water_mm" in w:  # levert snømengde hører til modellens nedbør, ikke den målte
        w.loc[bruk, "snow_water_mm"] = np.nan
    # samme standard som nowcast.apply_nowcast: timer uten egen nedbørkilde har værkilden
    if "precipitation_source" not in w:
        w["precipitation_source"] = w.get("weather_source", "unknown")
    w["precipitation_source"] = w["precipitation_source"].astype(object)
    w.loc[bruk, "precipitation_source"] = "bones"
    return w
