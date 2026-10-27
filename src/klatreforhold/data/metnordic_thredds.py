"""MET Nordic-analyser (1 km) direkte fra thredds.met.no, for lang historikk (fra 2012).

Den eneste gratis kilden med 1 km timesverdier for BÅDE kortbølget og langbølget stråling.
Ingen nøkkel. Én fil per time, så ett år = ~8 760 OPeNDAP-kall (vi leser bare ett gridpunkt).

Arkiver:
  metpparchivev4  2012-09-01 -> 2025-10-31  (rerun, kun analyser, foretrekkes der den finnes)
  metpparchive    2018-03-01 -> i dag       (operasjonelt)
Filnavn: met_analysis_1_0km_nordic_YYYYMMDDTHHZ.nc

Krever: pip install xarray netCDF4 pyproj
NB: ikke testet mot tjenesten ennå (nettverket var blokkert der koden ble skrevet).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BASE = "https://thredds.met.no/thredds/dodsC"
PROJ = "+proj=lcc +lat_0=63 +lon_0=15 +lat_1=63 +lat_2=63 +R=6.371e+06"

VARS = {
    "air_temperature_2m": "air_temperature",               # K
    "relative_humidity_2m": "relative_humidity",           # 0-1
    "precipitation_amount": "precipitation",               # mm siste time
    "wind_speed_10m": "wind_speed",
    "wind_direction_10m": "wind_direction",
    "cloud_area_fraction": "cloud_cover",                  # 0-1
    "integral_of_surface_downwelling_shortwave_flux_in_air_wrt_time": "ghi",          # W s m-2
    "integral_of_surface_downwelling_longwave_flux_in_air_wrt_time": "longwave_down",  # W s m-2
}


def _url(t: pd.Timestamp) -> str:
    archive = "metpparchivev4" if t < pd.Timestamp("2025-11-01", tz="UTC") else "metpparchive"
    return (f"{BASE}/{archive}/{t:%Y/%m/%d}/met_analysis_1_0km_nordic_{t:%Y%m%dT%H}Z.nc")


def grid_index(lat: float, lon: float, sample_time: pd.Timestamp) -> tuple[int, int]:
    """Finner nærmeste gridcelle (y, x) fra koordinatene i en fil."""
    import xarray as xr
    from pyproj import Transformer

    ds = xr.open_dataset(_url(sample_time))
    x, y = Transformer.from_crs("EPSG:4326", PROJ, always_xy=True).transform(lon, lat)
    ix = int(np.abs(ds["x"].values - x).argmin())
    iy = int(np.abs(ds["y"].values - y).argmin())
    ds.close()
    return iy, ix


def fetch_history(lat: float, lon: float, start: str, end: str, sleep_s: float = 0.1) -> pd.DataFrame:
    import time

    import xarray as xr

    times = pd.date_range(start, end, freq="h", tz="UTC")
    iy, ix = grid_index(lat, lon, times[0])
    rows = []
    for t in times:
        try:
            ds = xr.open_dataset(_url(t))
            row = {"time": t}
            for v, name in VARS.items():
                if v in ds:
                    row[name] = float(np.ravel(ds[v].isel(y=iy, x=ix).values)[0])  # dimensjoner: time(,height),y,x
            ds.close()
            rows.append(row)
        except Exception as err:  # manglende fil -> hull i serien
            print(f"Mangler {t}: {err}")
        time.sleep(sleep_s)
    df = pd.DataFrame(rows).set_index("time")
    if "air_temperature" in df:
        df["air_temperature"] -= 273.15
    if "relative_humidity" in df:
        df["relative_humidity"] *= 100.0
    for c in ("ghi", "longwave_down"):
        if c in df:
            df[c] /= 3600.0  # W s m-2 per time -> W/m2 snitt
    return df.asfreq("h")
