"""Features for ML: rå vær + fysikkmodellens tilstand. Fysikken gjør ML-modellen datasnill:
den trenger færre etiketter fordi den får 'vann på veggen' ferdig beregnet."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..physics.solar import saturation_vapour_pressure_hpa


def hours_since(mask: pd.Series) -> pd.Series:
    """Timer siden sist mask var True (stor verdi hvis aldri)."""
    idx = np.arange(len(mask))
    last = pd.Series(np.where(mask.to_numpy(), idx, np.nan), index=mask.index).ffill()
    return pd.Series(idx, index=mask.index) - last.fillna(-10_000)


def build_features(weather: pd.DataFrame, physics: pd.DataFrame | None = None,
                   timezone: str = "Europe/Oslo") -> pd.DataFrame:
    w = weather.sort_index()
    f = pd.DataFrame(index=w.index)
    p = w["precipitation"].fillna(0)
    for h in [3, 6, 12, 24, 48, 72, 168]:
        f[f"precip_sum_{h}h"] = p.rolling(h, min_periods=1).sum()
    f["hours_since_rain_0.2"] = hours_since(p >= 0.2).clip(upper=500)
    f["hours_since_rain_2"] = hours_since(p >= 2.0).clip(upper=500)
    f["air_temperature"] = w["air_temperature"]
    f["relative_humidity"] = w["relative_humidity"]
    es = saturation_vapour_pressure_hpa(w["air_temperature"])
    f["vpd_hpa"] = es * (1 - w["relative_humidity"].clip(0, 100) / 100)
    f["vpd_mean_12h"] = f["vpd_hpa"].rolling(12, min_periods=1).mean()
    f["wind_speed"] = w["wind_speed"]
    f["wind_speed_mean_12h"] = w["wind_speed"].rolling(12, min_periods=1).mean()
    rad = np.deg2rad(w["wind_direction"])
    f["wind_u"] = np.sin(rad) * w["wind_speed"]
    f["wind_v"] = np.cos(rad) * w["wind_speed"]
    if "cloud_cover" in w:
        f["cloud_cover"] = w["cloud_cover"]
    local = w.index.tz_convert(timezone)
    f["hour_sin"] = np.sin(2 * np.pi * local.hour / 24)
    f["hour_cos"] = np.cos(2 * np.pi * local.hour / 24)
    f["doy_sin"] = np.sin(2 * np.pi * local.dayofyear / 365.25)
    f["doy_cos"] = np.cos(2 * np.pi * local.dayofyear / 365.25)
    if physics is not None:
        ph = physics.reindex(w.index)
        for c in ["water_mm", "film_mm", "holds_mm", "seep_mm", "rock_minus_dewpoint", "rock_temp",
                  "rain_on_face_mm", "sw_face"]:
            f[f"phys_{c}"] = ph[c]
        f["phys_rain_face_24h"] = ph["rain_on_face_mm"].rolling(24, min_periods=1).sum()
        f["phys_evap_pot_24h"] = ph["evap_potential_mm"].rolling(24, min_periods=1).sum()
        f["phys_sun_hours_24h"] = ph["sun_on_face"].astype(float).rolling(24, min_periods=1).sum()
        f["phys_wet"] = ph["wet"].astype(float)
    return f


def load_labels(path, timezone: str = "Europe/Oslo") -> pd.Series:
    """Etikettfil: CSV med kolonnene 'time' og enten 'wet' (0/1) eller 'status' (tort/fuktig/vatt).

    'time' uten tidssone tolkes som lokal tid. Returnerer bool-serie (True = vått/fuktig) på hele timer i UTC.
    """
    return labels_from_frame(pd.read_csv(path), timezone)


def labels_from_frame(df: pd.DataFrame, timezone: str = "Europe/Oslo") -> pd.Series:
    if "time" not in df and "tid" in df:
        df = df.rename(columns={"tid": "time"})
    if df.empty:
        return pd.Series(dtype=bool, name="wet")
    t = pd.to_datetime(df["time"])
    if t.dt.tz is None:
        t = t.dt.tz_localize(timezone, ambiguous="NaT", nonexistent="shift_forward")
    t = t.dt.tz_convert("UTC").dt.ceil("h")  # observasjonen hører til intervallet som slutter her
    if "wet" in df:
        y = df["wet"].astype(bool)
    else:
        y = df["status"].str.lower().isin(["vatt", "vått", "fuktig", "wet", "damp", "is", "ice", "snow"])
    return pd.Series(y.to_numpy(), index=t, name="wet").groupby(level=0).max()
