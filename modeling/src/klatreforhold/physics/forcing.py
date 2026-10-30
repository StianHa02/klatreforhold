"""Validering av timeverdier og skille mellom regn og snø."""
import numpy as np
import pandas as pd

REQUIRED = ["air_temperature", "relative_humidity", "precipitation", "wind_speed", "wind_direction"]


def prepare_weather(weather: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in weather]
    if missing:
        raise ValueError(f"Mangler kolonner: {missing}")
    if weather.empty or weather.index.tz is None or weather.index.has_duplicates:
        raise ValueError("Været må ha unike, tidssonebevisste tidsstempler og minst én time")
    w = weather.sort_index().copy()
    w.index = w.index.tz_convert("UTC")
    if not (w.index == w.index.floor("h")).all():
        raise ValueError("Værdata må være på hele timer")
    w = w.asfreq("h")
    # Interpolerer bare korte, innvendige hull. Nedbør blir aldri interpolert.
    for col in ["air_temperature", "relative_humidity", "wind_speed"]:
        w[col] = w[col].interpolate(limit=3, limit_area="inside")
    angle = np.deg2rad(w["wind_direction"])
    x = np.cos(angle).interpolate(limit=3, limit_area="inside")
    y = np.sin(angle).interpolate(limit=3, limit_area="inside")
    w["wind_direction"] = np.mod(np.rad2deg(np.arctan2(y, x)), 360)
    if not np.isfinite(w[REQUIRED].to_numpy(float)).all():
        raise ValueError("Ufullstendig vær: nedbør eller andre nødvendige timeverdier mangler")
    w["precipitation"] = w["precipitation"].clip(lower=0)
    w["wind_speed"] = w["wind_speed"].clip(lower=0)
    w["relative_humidity"] = w["relative_humidity"].clip(0, 100)
    return w


def precipitation_phase(w: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vannekvivalent mm. Sannsynlighet for snø er ikke en målt snøandel.

    Uten levert vannmengde brukes RoadSurfs kategoriske Ta/RH-regel:
    P(regn)<.3 snø, >.7 regn, ellers sludd (halvparten av hver).
    """
    total = w["precipitation"].to_numpy(float)
    exponent = 22 - 2.7 * w["air_temperature"].to_numpy() - .2 * w["relative_humidity"].to_numpy()
    p_rain = 1 / (1 + np.exp(np.clip(exponent, -100, 100)))
    if "snow_probability" in w:
        p_rain = np.where(w["snow_probability"].notna(), 1 - w["snow_probability"], p_rain)
    snow = total * np.where(p_rain < .3, 1, np.where(p_rain > .7, 0, .5))
    estimated = np.ones(len(w), dtype=bool)
    if "snow_water_mm" in w:
        supplied = w["snow_water_mm"].notna().to_numpy()
        snow = np.where(supplied, np.clip(w["snow_water_mm"].to_numpy(), 0, total), snow)
        estimated[supplied] = False
    return total - snow, snow, estimated
