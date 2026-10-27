"""Open-Meteo: MET Nordic-data (1 km, MET Norway) uten API-nøkkel.

- Historikk: Historical Forecast API (arkiverte MET Nordic-kjøringer)
- Varsel:    Forecast API med models=metno_seamless (MET Nordic de første ~2.5 døgn, deretter ECMWF)

Gratis for ikke-kommersiell bruk. Data: MET Norway (CC BY 4.0) via Open-Meteo (CC BY 4.0).
"""
from __future__ import annotations

import pandas as pd

from .http import get

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

HOURLY = [
    "temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation",
    "cloud_cover", "shortwave_radiation", "direct_normal_irradiance", "diffuse_radiation",
    "wind_speed_10m", "wind_direction_10m",
]

RENAME = {
    "temperature_2m": "air_temperature",
    "relative_humidity_2m": "relative_humidity",
    "dew_point_2m": "dew_point_2m",
    "precipitation": "precipitation",
    "cloud_cover": "cloud_cover",
    "shortwave_radiation": "ghi",
    "direct_normal_irradiance": "dni",
    "diffuse_radiation": "dhi",
    "wind_speed_10m": "wind_speed",
    "wind_direction_10m": "wind_direction",
}


def _to_frame(js: dict) -> pd.DataFrame:
    h = js["hourly"]
    idx = pd.to_datetime(h["time"], utc=True)
    df = pd.DataFrame({k: h[k] for k in h if k != "time"}, index=idx)
    df = df.rename(columns=RENAME)
    if "cloud_cover" in df:
        df["cloud_cover"] = df["cloud_cover"] / 100.0
    # Open-Meteo: stråling og nedbør er snitt/sum for timen FØR tidsstempelet (samme som modellen antar)
    df.index.name = "time"
    return df


def fetch_history(lat: float, lon: float, start: str, end: str, model: str = "metno_seamless") -> pd.DataFrame:
    """Timesdata fra arkiverte varsler. start/end: 'YYYY-MM-DD'. Henter i biter på 3 måneder.

    MET Nordic finnes i Historical Forecast API fra 2022-11-15. For lengre historikk: bruk
    data/metnordic_thredds.py (analyser fra 2012). Gratis-grense: 10 000 kall/døgn, ikke-kommersielt.
    """
    parts = []
    for s, e in _chunks(start, end, months=3):
        js = get(HISTORICAL_URL, params={
            "latitude": round(lat, 4), "longitude": round(lon, 4),
            "start_date": s, "end_date": e, "hourly": ",".join(HOURLY),
            "models": model, "timezone": "GMT", "wind_speed_unit": "ms",
        }).json()
        parts.append(_to_frame(js))
    df = pd.concat(parts)
    return df[~df.index.duplicated()].sort_index()


def fetch_forecast(lat: float, lon: float, past_days: int = 3, forecast_days: int = 3,
                   model: str = "metno_seamless") -> pd.DataFrame:
    """Varsel + siste døgn (past_days) slik at modellen kan 'varme opp' vannlagrene."""
    js = get(FORECAST_URL, params={
        "latitude": round(lat, 4), "longitude": round(lon, 4), "hourly": ",".join(HOURLY),
        "models": model, "timezone": "GMT", "wind_speed_unit": "ms",
        "past_days": past_days, "forecast_days": forecast_days,
    }).json()
    return _to_frame(js)


def _chunks(start: str, end: str, months: int):
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    while s <= e:
        nxt = min(s + pd.DateOffset(months=months) - pd.Timedelta(days=1), e)
        yield s.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")
        s = nxt + pd.Timedelta(days=1)
