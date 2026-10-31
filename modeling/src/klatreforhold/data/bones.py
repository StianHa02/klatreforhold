"""Bønes værstasjon: privat Davis Vantage Pro2 Plus 1,3 km fra Ekstraveggen (weather.kippenbroeck.no).

Stasjonen er ikke vår. API-et gir bare siste femminuttsmåling, så timesjobben lagrer én måling per kjøring
(tabellen bones_maling), og timeverdiene regnes ut her. Se docs/BONES_STASJON.md for hvorfor bare regn og
temperatur brukes: fuktigheten viser for høyt i tørr luft og vinden er skjermet.

- Nedbør per time er differansen i nedbor_i_dag_mm mellom to målinger omtrent en time fra hverandre.
  Over midnatt nullstilles telleren, så den timen er ukjent. Ukjent blir NaN, aldri null.
- Målingen kl. HH:05 (slutten av intervallet) dekker omtrent timen som slutter kl. HH, samme regel som
  modellen (nedbør gjelder timen før tidsstempelet).

Data: Bønes værstasjon, weather.kippenbroeck.no (CC BY 4.0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .http import get

API = "https://weather.kippenbroeck.no/api/naa.php"
KILDE = "Bønes værstasjon, weather.kippenbroeck.no (CC BY 4.0)"
MIN_TEMP_REGN = 2.0  # under dette kan nedbøren være snø, som vippekarmåleren ikke fanger
MIN_GAP = pd.Timedelta(minutes=45)
MAX_GAP = pd.Timedelta(minutes=75)


def fetch_latest() -> dict | None:
    """Siste måling som rad til bones_maling. None hvis målingen er eldre enn 15 minutter (stasjonen henger)."""
    js = get(API, timeout=20).json()
    if not js.get("fersk"):
        return None
    d = js["data"]
    return {
        "tid": pd.Timestamp(js["tidspunkt_utc"]).tz_convert("UTC").isoformat(),
        "lufttemp": d.get("temperatur_c"), "luftfuktighet": d.get("luftfuktighet_pst"),
        "vind_ms": d.get("vind_ms"), "vindkast_ms": d.get("vindkast_ms"), "vindretning": d.get("vindretning_grader"),
        "nedbor_i_dag_mm": d.get("nedbor_i_dag_mm"), "nedbor_dato": js["nedbor_dato"],
        "nedbor_intensitet_mm_t": d.get("nedbor_intensitet_mm_t"),
    }


def hourly(malinger: pd.DataFrame) -> pd.DataFrame:
    """Timeverdier (UTC-indeks) med precipitation og air_temperature fra lagrede målinger.

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


def with_rain(w: pd.DataFrame, malinger: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Bytter modellens nedbør med målt Bønes-regn i passerte timer der den finnes og det er over +2 °C.

    Alt annet beholdes fra modellen. Uten brukbare målinger returneres w uendret, så varselet virker alltid.
    """
    t = hourly(malinger)
    if now is not None:
        t = t.loc[:pd.Timestamp(now).tz_convert("UTC").floor("h")]
    t = t.reindex(w.index)
    temp = t["air_temperature"].where(t["air_temperature"].notna(), w["air_temperature"])
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
