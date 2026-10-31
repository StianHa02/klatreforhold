"""MET Nordic-punktdata via OPeNDAP ASCII; små kall med tidsavbrudd og lokal cache.

Stråling og nedbør gjelder timen før tidsstempelet. Ingen nedlasting av hele grid.
Historikk før 2025-11-01 bruker v4; senere brukes operasjonelt arkiv.
"""
from __future__ import annotations
from functools import lru_cache
from io import StringIO
from pathlib import Path
from urllib.parse import quote
import re
import numpy as np
import pandas as pd
from .http import get
from ..config import ROOT

BASE = "https://thredds.met.no/thredds/dodsC"
PROJ = "+proj=lcc +lat_0=63 +lon_0=15 +lat_1=63 +lat_2=63 +R=6.371e+06"
VARS = {
    "air_temperature_2m": "air_temperature", "relative_humidity_2m": "relative_humidity",
    "precipitation_amount": "precipitation", "wind_speed_10m": "wind_speed",
    "wind_direction_10m": "wind_direction", "cloud_area_fraction": "cloud_cover",
    "integral_of_surface_downwelling_shortwave_flux_in_air_wrt_time": "ghi",
    "integral_of_surface_downwelling_longwave_flux_in_air_wrt_time": "longwave_down",
    "probability_of_snow_phase": "snow_probability",
}


def parse_ascii(text: str) -> dict[str, np.ndarray]:
    """Leser DAPs skalarer, vektorer og punktuttrekk [tid][1][1]."""
    if "---------------------------------------------" not in text:
        raise ValueError("Uventet svar fra OPeNDAP")
    out = {}
    for block in text.split("---------------------------------------------", 1)[1].strip().split("\n\n"):
        lines = block.strip().splitlines()
        if len(lines) == 1 and "," in lines[0]:
            key, number = lines[0].split(",", 1)
            out[key.strip()] = np.array([float(number)])
            continue
        if len(lines) < 2:
            continue
        key = lines[0].split("[")[0]
        payload = ",".join(re.sub(r"^(?:\[\d+\])+,\s*", "", line.strip()) for line in lines[1:])
        values = np.fromstring(payload, sep=",")
        values[np.abs(values) > 1e30] = np.nan
        out[key] = values
    return out


def _read(url, query):
    return parse_ascii(get(url + ".ascii?" + quote(query, safe=""), timeout=20, retries=1).text)


@lru_cache(maxsize=128)
def _metadata(url, hour_key):
    dds = get(url + ".dds", timeout=15, retries=1).text
    variables = [v for v in VARS if re.search(r"\b" + v + r"\[", dds)]
    query = "time,x[0:1:1],y[0:1:1]"
    if "forecast_reference_time" in dds:
        query += ",forecast_reference_time"
    meta = _read(url, query)
    return meta, variables


def _url(t):
    t = pd.Timestamp(t)
    archive = "metpparchivev4" if t < pd.Timestamp("2025-11-01", tz="UTC") else "metpparchive"
    return f"{BASE}/{archive}/{t:%Y/%m/%d}/met_analysis_1_0km_nordic_{t:%Y%m%dT%H}Z.nc"


def _point(url, lat, lon, kind):
    from pyproj import Transformer
    meta, variables = _metadata(url, pd.Timestamp.now(tz="UTC").floor("h").isoformat())
    x, y = Transformer.from_crs("EPSG:4326", PROJ, always_xy=True).transform(lon, lat)
    ix = int(round((x - meta["x"][0]) / np.diff(meta["x"])[0]))
    iy = int(round((y - meta["y"][0]) / np.diff(meta["y"])[0]))
    if ix < 0 or iy < 0:
        raise ValueError("Punktet er utenfor MET Nordic")
    n = len(meta["time"])
    # Et samlet uttrekk av ni variabler over ~60 timer bruker over 20 sekunder
    # hos THREDDS, så prognosen hentes tre variabler om gangen. Analysefilen
    # inneholder bare én time og kan leses samlet.
    batch_size = 3 if kind == "forecast" else max(1, len(variables))
    data = {}
    for offset in range(0, len(variables), batch_size):
        batch = variables[offset:offset + batch_size]
        query = "time," + ",".join(f"{v}[0:1:{n-1}][{iy}:1:{iy}][{ix}:1:{ix}]" for v in batch)
        part = _read(url, query)
        if data and not np.array_equal(data["time"], part["time"]):
            raise ValueError("MET-uttrekkene har forskjellige tidsakser")
        data.update(part)
    index = pd.to_datetime(data["time"], unit="s", utc=True)
    df = pd.DataFrame({VARS[v]: data[f"{v}.{v}"] for v in variables}, index=index)
    df["air_temperature"] -= 273.15
    df["relative_humidity"] *= 100
    for name in ("ghi", "longwave_down"):
        if name in df:
            # Prognosefilene akkumulerer fra modellstart (verifisert mot live data).
            # Analysefilen har én foregående time. Første prognoseintervall er ukjent.
            df[name] = df[name].diff() / 3600 if kind == "forecast" else df[name] / 3600
            # MET kan ha små negative differanser ved skumring (målt −0.14 W/m²).
            # Opptil 1 W/m² behandles som null; større fall kan være en ekte nullstilling.
            if (df[name].dropna() < -1.0).any():
                raise ValueError(f"Uventet nullstilling i strålingsakkumulasjonen for {name}: {df[name].min():.2f} W/m²")
            df[name] = df[name].clip(lower=0)
    df["weather_source"] = "metnordic"
    df["weather_kind"] = kind
    reference = meta.get("forecast_reference_time", meta["time"])[0]
    df["weather_issued"] = pd.to_datetime(reference, unit="s", utc=True).isoformat()
    if kind == "forecast" and df.index[0] == pd.to_datetime(reference, unit="s", utc=True):
        df.iloc[0, df.columns.get_loc("precipitation")] = np.nan
    df.index.name = "time"
    return df


def fetch_forecast(lat, lon):
    url = f"{BASE}/metpplatest/met_forecast_1_0km_nordic_latest.nc"
    meta, _ = _metadata(url, pd.Timestamp.now(tz="UTC").floor("h").isoformat())
    # Lås til én kjøring, slik at en oppdatering mellom kallene ikke blander tidsakser.
    issued = pd.to_datetime(meta["forecast_reference_time"][0], unit="s", utc=True)
    if pd.Timestamp.now(tz="UTC") - issued > pd.Timedelta(hours=6):
        raise ValueError("MET Nordic-kjøringen er for gammel")
    url = url.replace("latest.nc", issued.strftime("%Y%m%dT%HZ.nc"))
    return _point(url, lat, lon, "forecast")


def fetch_history(lat, lon, start, end, cache_dir=None, refresh_hours=2, sleep_s=0):
    cache = Path(cache_dir or ROOT / "data/cache/metnordic")
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"analysis_{lat:.6f}_{lon:.6f}.csv.gz"
    old = pd.read_csv(path, index_col=0, parse_dates=True) if path.exists() else pd.DataFrame()
    if not old.empty:
        old.index = pd.to_datetime(old.index, utc=True)
    times = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="h")
    if times.tz is None:
        times = times.tz_localize("UTC")
    parts = [old]
    now = pd.Timestamp.now(tz="UTC")
    failures = 0
    for t in times:
        if t in old.index and t < now - pd.Timedelta(hours=refresh_hours):
            continue
        try:
            url = (f"{BASE}/metpplatest/met_analysis_1_0km_nordic_{t:%Y%m%dT%H}Z.nc"
                   if t >= now - pd.Timedelta(days=3) else _url(t))
            parts.append(_point(url, lat, lon, "analysis"))
            failures = 0
        except Exception:
            # Eldre cache beholdes, ellers står timen åpen for reservekilden.
            failures += 1
            if failures >= 2:
                break
            continue
    df = pd.concat(parts).sort_index()
    if df.empty:
        return df
    df = df[~df.index.duplicated(keep="last")]
    df = df.loc[df.index >= now - pd.Timedelta(days=120)]
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, compression="gzip")
    tmp.replace(path)
    return df.reindex(times)
