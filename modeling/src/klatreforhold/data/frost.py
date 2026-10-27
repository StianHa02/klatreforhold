"""Frost (frost.met.no): målte stasjonsdata fra MET og Statens vegvesen.

Krever gratis klient-ID: registrer på https://frost.met.no/auth/requestCredentials.html
og sett miljøvariabelen FROST_CLIENT_ID.
"""
from __future__ import annotations

import os

import pandas as pd
import requests

from .http import get

OBS_URL = "https://frost.met.no/observations/v0.jsonld"
SOURCES_URL = "https://frost.met.no/sources/v0.jsonld"
AVAILABLE_URL = "https://frost.met.no/observations/availableTimeSeries/v0.jsonld"

ELEMENTS = {
    "air_temperature": "air_temperature",
    "relative_humidity": "relative_humidity",
    "sum(precipitation_amount PT1H)": "precipitation",
    "wind_speed": "wind_speed",
    "wind_from_direction": "wind_direction",
    "mean(surface_downwelling_shortwave_flux_in_air PT1H)": "ghi",
    "dew_point_temperature": "dew_point_2m",
    "cloud_area_fraction": "cloud_cover_okta",
}
# Merk: elementnavn for veibanetemperatur/føre på Statens vegvesens stasjoner (f.eks. SN50710 E39 Eidsvåg)
# er ikke verifisert. Sjekk med available_elements("SN50710") og søk etter "surface"/"road".


def _auth():
    cid = os.environ.get("FROST_CLIENT_ID")
    if not cid:
        raise RuntimeError("Sett FROST_CLIENT_ID (gratis på frost.met.no)")
    return (cid, "")


def nearby_stations(lat: float, lon: float, n: int = 15) -> pd.DataFrame:
    """Nærmeste stasjoner, inkludert hvem som eier dem (stationHolders)."""
    js = get(SOURCES_URL, params={"geometry": f"nearest(POINT({lon} {lat}))", "nearestmaxcount": n},
             auth=_auth()).json()
    rows = [{"id": s["id"], "name": s.get("name"), "holders": ",".join(s.get("stationHolders", [])),
             "lat": s["geometry"]["coordinates"][1], "lon": s["geometry"]["coordinates"][0],
             "masl": s.get("masl"), "distance_km": s.get("distance")} for s in js["data"]]
    return pd.DataFrame(rows)


def available_elements(station: str) -> pd.DataFrame:
    js = get(AVAILABLE_URL, params={"sources": station}, auth=_auth()).json()
    return pd.DataFrame(js["data"])[["elementId", "timeResolution", "validFrom"]].drop_duplicates()


def fetch_observations(station: str, start: str, end: str, elements: list[str] | None = None) -> pd.DataFrame:
    """Timesobservasjoner for én stasjon (f.eks. 'SN50540' Florida). Henter månedsvis."""
    elements = elements or list(ELEMENTS)
    frames = []
    for s, e in _months(start, end):
        try:
            r = get(OBS_URL, params={"sources": station, "referencetime": f"{s}/{e}",
                                     "elements": ",".join(elements), "timeresolutions": "PT1H"},
                    auth=_auth())
        except requests.HTTPError as err:  # 404 = ingen data i perioden
            if err.response is not None and err.response.status_code == 404:
                continue
            raise
        rows = []
        for item in r.json().get("data", []):
            for ob in item["observations"]:
                rows.append({"time": item["referenceTime"], "element": ob["elementId"], "value": ob["value"]})
        if rows:
            frames.append(pd.DataFrame(rows))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    wide = df.pivot_table(index="time", columns="element", values="value", aggfunc="mean")
    wide = wide.rename(columns=ELEMENTS).asfreq("1h")
    if "cloud_cover_okta" in wide:
        wide["cloud_cover"] = (wide.pop("cloud_cover_okta") / 8.0).clip(0, 1)
    return wide


def _months(start, end):
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    while s < e:
        nxt = min(s + pd.DateOffset(months=1), e)
        yield s.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")
        s = nxt
