"""Radar-nedbør de neste to timene, integrert over endestemplede modellintervaller."""
import numpy as np
import pandas as pd
from .http import get


def fetch_nowcast(lat, lon):
    return get("https://api.met.no/weatherapi/nowcast/2.0/complete", params={
        "lat": round(lat, 4), "lon": round(lon, 4)}, timeout=15, retries=1).json()


def apply_nowcast(weather, payload, now=None):
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC"))
    props = payload.get("properties", {})
    meta = props.get("meta", {})
    updated = pd.to_datetime(meta.get("updated_at"), utc=True)
    if updated is None or pd.isna(updated) or now - updated > pd.Timedelta(minutes=20) or updated > now:
        return weather
    coverage = meta.get("radar_coverage")
    if coverage is not None and str(coverage).lower() != "ok":
        return weather
    series = props.get("timeseries", [])
    points = []
    for entry in series:
        details = entry.get("data", {}).get("instant", {}).get("details", {})
        rate = details.get("precipitation_rate")
        if rate is not None and np.isfinite(rate):
            points.append((pd.Timestamp(entry["time"]), max(0., float(rate))))
    points.sort()
    w = weather.copy()
    w["precipitation_source"] = w.get("precipitation_source", w.get("weather_source", "unknown"))
    for end in w.index:
        start = end - pd.Timedelta(hours=1)
        if end <= now or start >= now + pd.Timedelta(hours=2):
            continue
        amount = covered = 0.
        for (t0, r0), (t1, r1) in zip(points, points[1:]):
            # Store hull i radardata må ikke interpoleres til oppdiktet regn.
            if t1 - t0 > pd.Timedelta(minutes=10) or t1 <= t0:
                continue
            a, b = max(start, t0, now), min(end, t1, now + pd.Timedelta(hours=2))
            if b <= a:
                continue
            span = (t1-t0).total_seconds()
            ra = r0 + (r1-r0)*(a-t0).total_seconds()/span
            rb = r0 + (r1-r0)*(b-t0).total_seconds()/span
            hours = (b-a).total_seconds()/3600
            covered += hours
            amount += (ra+rb)*.5*hours
        if covered > 0:
            w.at[end, "precipitation"] = w.at[end, "precipitation"] * (1-covered) + amount
            w.at[end, "precipitation_source"] = "nowcast" if covered >= .999 else "nowcast+base"
            # Levert snømengde tilhører den gamle nedbøren; fase estimeres på nytt.
            if "snow_water_mm" in w:
                w.at[end, "snow_water_mm"] = np.nan
    return w
