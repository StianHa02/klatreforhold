 """MEPS-ensemblet (30 medlemmer, 2.5 km) fra THREDDS: bare nedbør, for usikkerheten i varselet.

Filen er «lagged»: medlemmene kommer fra de siste kjøringene, og noen mangler de første
timene. Nedbør er akkumulert per medlem; vi gjør den om til mm for timen før tidsstempelet.
"""
from __future__ import annotations
import re
from urllib.parse import quote
import numpy as np
import pandas as pd
from .http import get

URL = "https://thredds.met.no/thredds/dodsC/mepslatest/meps_lagged_6_h_latest_2_5km_latest.nc"
PROJ = "+proj=lcc +lat_0=63.3 +lon_0=15 +lat_1=63.3 +lat_2=63.3 +R=6371000"
MAKS_ALDER = pd.Timedelta(hours=9)  # nyeste kjøring i filen; eldre ensemble gir mer støy enn nytte


def _ascii(query: str) -> str:
    return get(URL + ".ascii?" + quote(query, safe=""), timeout=30, retries=1).text


def _vector(text: str, name: str) -> np.ndarray:
    m = re.search(r"^" + re.escape(name) + r"\[\d+\]\n([^\n]+)", text, re.M)
    if not m:
        raise ValueError(f"Fant ikke {name} i OPeNDAP-svaret")
    return np.array([float(v) for v in m.group(1).split(",")])


def parse_precip(text: str, n_time: int, n_member: int) -> np.ndarray:
    """Leser linjer «[t][0][m][0], verdi» til en matrise tid × medlem. Fyllverdier blir NaN."""
    out = np.full((n_time, n_member), np.nan)
    for t, m, v in re.findall(r"^\[(\d+)\]\[0\]\[(\d+)\]\[0\], (\S+)$", text, re.M):
        out[int(t), int(m)] = float(v)
    out[np.abs(out) > 1e30] = np.nan
    return out


def fetch_precip_ensemble(lat: float, lon: float, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Timenedbør (mm) per medlem, kolonner 0..29, indeks UTC slutten av timen."""
    from pyproj import Transformer
    meta = _ascii("time,x[0:1:1],y[0:1:1],forecast_reference_time,ensemble_member")
    times = pd.to_datetime(_vector(meta, "time"), unit="s", utc=True)
    issued = pd.to_datetime(float(re.search(r"^forecast_reference_time, (\S+)$", meta, re.M).group(1)), unit="s", utc=True)
    if pd.Timestamp(now or pd.Timestamp.now(tz="UTC")) - issued > MAKS_ALDER:
        raise ValueError("MEPS-ensemblet er for gammelt")
    xs, ys = _vector(meta, "x"), _vector(meta, "y")
    n_member = len(_vector(meta, "ensemble_member"))
    x, y = Transformer.from_crs("EPSG:4326", PROJ, always_xy=True).transform(lon, lat)
    ix, iy = int(round((x - xs[0]) / (xs[1] - xs[0]))), int(round((y - ys[0]) / (ys[1] - ys[0])))
    if ix < 0 or iy < 0:
        raise ValueError("Punktet er utenfor MEPS")
    n = len(times)
    text = _ascii(f"precipitation_amount_acc[0:1:{n-1}][0:1:0][0:1:{n_member-1}][{iy}:1:{iy}][{ix}:1:{ix}]")
    acc = parse_precip(text, n, n_member)
    # Første gyldige time per medlem har ingen forrige akkumulasjon: den blir NaN, ikke null.
    hourly = np.diff(acc, axis=0, prepend=np.nan)
    # Små negative differanser er avrunding i akkumulasjonen.
    hourly = np.where(hourly < 0, 0., hourly)
    df = pd.DataFrame(hourly, index=times)
    df.index.name = "time"
    df.attrs["issued"] = issued
    return df
