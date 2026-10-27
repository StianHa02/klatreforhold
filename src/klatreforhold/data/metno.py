"""api.met.no Locationforecast 2.0 (complete). Ingen nøkkel, men krever User-Agent med kontaktinfo,
maks 4 desimaler i koordinater, og at man respekterer Expires/If-Modified-Since (caching).
Lisens: CC BY 4.0, krediter "Data fra MET Norway".
Har ikke stråling: modellen beregner klarværsstråling og skalerer med skydekke.
"""
from __future__ import annotations

import pandas as pd

from .http import get

URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"


def fetch_locationforecast(lat: float, lon: float) -> pd.DataFrame:
    js = get(URL, params={"lat": round(lat, 4), "lon": round(lon, 4)}).json()
    rows = []
    for ts in js["properties"]["timeseries"]:
        d = ts["data"]
        inst = d["instant"]["details"]
        n1 = d.get("next_1_hours", {}).get("details", {})
        if not n1:  # etter ~60 timer kommer bare 6-timersverdier; vi bruker kun timesdelen
            continue
        rows.append({
            "time": pd.Timestamp(ts["time"]),
            "air_temperature": inst.get("air_temperature"),
            "relative_humidity": inst.get("relative_humidity"),
            "wind_speed": inst.get("wind_speed"),
            "wind_direction": inst.get("wind_from_direction"),
            "cloud_cover": (inst.get("cloud_area_fraction") or 0) / 100.0,
            "dew_point_2m": inst.get("dew_point_temperature"),
            # precipitation_amount i next_1_hours gjelder timen ETTER tidsstempelet:
            # flyttes en time fram så det matcher "timen før" som resten av prosjektet bruker
            "precipitation_next": n1.get("precipitation_amount", 0.0),
        })
    df = pd.DataFrame(rows).set_index("time").sort_index()
    df["precipitation"] = df["precipitation_next"].shift(1).fillna(0.0)
    return df.drop(columns="precipitation_next")
