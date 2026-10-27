"""Leser stasjons-CSV eksportert fra Frost (referenceTime + elementnavn som kolonner) til standard værformat."""
from __future__ import annotations

import pandas as pd

RENAME = {
    "air_temperature": "air_temperature",
    "sum(precipitation_amount PT1H)": "precipitation",
    "relative_humidity": "relative_humidity",
    "wind_speed": "wind_speed",
    "wind_from_direction": "wind_direction",
}


def load_station_csv(path) -> tuple[pd.DataFrame, pd.Series | None]:
    """Returnerer (vær, etiketter). Etiketter er kolonnen 'forhold' hvis den finnes."""
    df = pd.read_csv(path)
    df["referenceTime"] = pd.to_datetime(df["referenceTime"], utc=True)
    df = df.set_index("referenceTime").sort_index()
    weather = df[[c for c in RENAME if c in df]].rename(columns=RENAME)
    weather = weather.asfreq("1h")  # tydeliggjør hull
    labels = df["forhold"].astype(bool).reindex(weather.index) if "forhold" in df else None
    return weather, labels
