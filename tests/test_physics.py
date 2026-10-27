"""Enkle fornuftstester for fysikkmodellen: python -m pytest tests  (eller python tests/test_physics.py)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.config import load_config  # noqa: E402
from klatreforhold.physics.wetness import run_model  # noqa: E402

CFG = Path(__file__).resolve().parents[1] / "config" / "ekstraveggen.yaml"


def _weather(hours=96, **over):
    idx = pd.date_range("2026-07-01", periods=hours, freq="h", tz="UTC")
    d = dict(air_temperature=15.0, relative_humidity=70.0, precipitation=0.0, wind_speed=3.0,
             wind_direction=300.0, cloud_cover=0.3)
    d.update(over)
    return pd.DataFrame({k: np.full(hours, v, dtype=float) for k, v in d.items()}, index=idx)


def test_dry_weather_stays_dry():
    crag, p = load_config(CFG)
    r = run_model(_weather(), crag, p)
    assert (r["status"] == "tort").mean() > 0.95


def test_rain_into_face_makes_wet_then_dries():
    crag, p = load_config(CFG)
    w = _weather(hours=24 * 5)
    w.iloc[10:16, w.columns.get_loc("precipitation")] = 3.0
    r = run_model(w, crag, p)
    assert r["wet"].iloc[15]
    assert not r["wet"].iloc[-1], "veggen bør være tørr 4 døgn etter regn i fint vær"


def test_wind_from_behind_gives_less_wall_rain():
    crag, p = load_config(CFG)
    a = _weather(precipitation=2.0, wind_direction=300.0)
    b = _weather(precipitation=2.0, wind_direction=120.0)
    ra, rb = run_model(a, crag, p), run_model(b, crag, p)
    assert rb["wind_driven_rain_mm"].sum() == 0, "vind bakfra gir ikke slagregn"
    assert ra["rain_on_face_mm"].sum() > 2 * rb["rain_on_face_mm"].sum()


def test_condensation_when_warm_humid_air_after_cold():
    crag, p = load_config(CFG)
    w = _weather(hours=24 * 4, air_temperature=2.0, relative_humidity=80.0, cloud_cover=1.0)
    w.iloc[72:, w.columns.get_loc("air_temperature")] = 12.0
    w.iloc[72:, w.columns.get_loc("relative_humidity")] = 98.0
    r = run_model(w, crag, p)
    assert r["condensation_mm"].iloc[72:84].sum() > 0, "kaldt berg + varm fuktig luft skal gi kondens"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
