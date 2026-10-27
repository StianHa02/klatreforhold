"""Tester kontrollen mot målestasjoner og valget mellom kontroll/erstatt (uten nett)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klatreforhold import predict as P  # noqa: E402
from klatreforhold.config import load_config  # noqa: E402
from klatreforhold.verify import forecast_rows, observation_rows, scores, to_obs_frame  # noqa: E402


def _w(hours=72, rain_every=6):
    idx = pd.date_range("2026-10-20", periods=hours, freq="h", tz="UTC")
    rain = np.where(np.arange(hours) % rain_every == 0, 1.0, 0.0)
    return pd.DataFrame({"air_temperature": 10.0, "relative_humidity": 85.0, "precipitation": rain,
                         "wind_speed": 4.0, "wind_direction": 250.0}, index=idx)


def test_rows_and_scores_perfect_forecast():
    w = _w()
    gen = w.index[10]
    fc = pd.DataFrame(forecast_rows("SN1", w, gen))
    assert fc["ledetid_timer"].iloc[0] == 0 and fc["ledetid_timer"].max() == 48
    obs = pd.DataFrame(observation_rows("SN1", w)).set_index("tid")
    s = scores(fc, obs)
    assert set(s["ledetid"]) >= {"nå", "1-6 t"}
    assert (s["temp_mae"] == 0).all()
    assert (s["traff_regn"].dropna() == 1.0).all() and (s["falsk_regn"].dropna() == 0.0).all()


def test_scores_detect_missed_rain():
    w = _w()
    obs = to_obs_frame(w)
    fc = to_obs_frame(w.assign(precipitation=0.0)).reset_index(names="tid")
    s = scores(fc, obs, by_lead=False)
    assert s["traff_regn"].iloc[0] == 0.0 and s["mm_forhold"].iloc[0] == 0.0


def test_kontroll_does_not_touch_model_input(monkeypatch=None):
    crag, _ = load_config(ROOT / "config" / "ekstraveggen.yaml")
    assert crag.frost_bruk == "kontroll"
    w = _w()
    import klatreforhold.data.openmeteo as om
    om.fetch_forecast = lambda *a, **k: w
    called = {"n": 0}
    orig = P.with_observations
    P.with_observations = lambda ww, c: called.__setitem__("n", called["n"] + 1) or ww
    try:
        out = P.get_weather(crag)
        assert out is w and called["n"] == 0
        crag.frost_bruk = "erstatt"
        P.get_weather(crag)
        assert called["n"] == 1
    finally:
        P.with_observations = orig


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
