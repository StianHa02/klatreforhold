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
    import klatreforhold.data.pipeline as pipeline
    original_fetch = pipeline.fetch_weather
    pipeline.fetch_weather = lambda *a, **k: w
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
        pipeline.fetch_weather = original_fetch
        P.with_observations = orig


def test_rain_windows_tolerate_timing():
    from klatreforhold.verify import rain_windows
    w = _w(hours=96)
    obs = w["precipitation"]
    shifted = obs.shift(1).fillna(0)  # varselet bommer med én time
    hourly = scores(to_obs_frame(w.assign(precipitation=shifted)).reset_index(names="tid"), to_obs_frame(w), by_lead=False)
    win = rain_windows(shifted, obs)
    assert hourly["traff_regn"].iloc[0] == 0.0 and win["traff_regn_24t"] == 1.0


def _years(bias_by_month, amp=0.0, noise=6.0):
    """Tre år der varselet er bias_by_month[m] (+ en døgnsvingning med topp kl 17) for fuktig, pluss tilfeldig feil."""
    idx = pd.date_range("2023-01-01", "2025-12-31 22:00", freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    loc = idx.tz_convert("Europe/Oslo")
    obs = pd.Series(np.clip(78 + 12 * np.sin(np.arange(len(idx)) / 24 * 2 * np.pi) + rng.normal(0, 6, len(idx)), 20, 100), index=idx)
    sys_bias = np.asarray(bias_by_month)[loc.month - 1] + amp * np.cos(2 * np.pi * (loc.hour.to_numpy() - 17) / 24)
    fc = obs + sys_bias + rng.normal(0, noise, len(idx))
    return fc, obs


def test_rh_correction_fit_finds_season_and_daily_cycle():
    from klatreforhold.physics.wetness import rh_correction
    from klatreforhold.verify import rh_bias_by_level, rh_bias_table, rh_bias_year_month, rh_correction_fit
    bias = [0, 1, 3, 4, 4, 4, 3, 3, 2, 1, 0, 0]
    fc, obs = _years(bias, amp=3.0)
    k = rh_correction_fit(fc, obs)
    p = {"rh_korreksjon_maned": k["maned"], "rh_korreksjon_doegn_cos": k["doegn_cos"], "rh_korreksjon_doegn_sin": k["doegn_sin"]}
    t = pd.DatetimeIndex([pd.Timestamp("2025-05-15 17:00", tz="Europe/Oslo"), pd.Timestamp("2025-05-15 05:00", tz="Europe/Oslo"),
                          pd.Timestamp("2025-01-15 12:00", tz="Europe/Oslo")])
    c = rh_correction(t, p)
    assert abs(c[0] + 7) < 0.8 and abs(c[1] + 1) < 0.8 and abs(c[2] - 0) < 1.0  # mai kl 17: -(4+3), kl 05: -(4-3)
    # Tilfeldig feil alene gir "for fuktig når varselet er fuktig" - men ikke etter målt nivå
    lv = rh_bias_by_level(*_years([0] * 12, noise=8.0))
    assert lv["skjevhet_etter_varslet"].iloc[-1] > 2 and lv["skjevhet_etter_malt"].iloc[-1] < 0
    assert list(rh_bias_table(fc, obs, "sesong")["sesong"]) == ["vinter", "vår", "sommer", "høst"]
    ym = rh_bias_year_month(fc, obs)
    assert list(ym.index) == ["2023", "2024", "2025"] and ym.shape[1] == 12


def test_scores_and_windows_by_season():
    from klatreforhold.verify import rain_windows_by, scores_by
    idx = pd.date_range("2024-01-01", "2024-12-31 23:00", freq="h", tz="UTC")
    w = pd.DataFrame({"air_temperature": 8.0, "relative_humidity": 85.0,
                      "precipitation": np.where(np.arange(len(idx)) % 10 == 0, 1.0, 0.0),
                      "wind_speed": 4.0, "wind_direction": 250.0}, index=idx)
    obs = to_obs_frame(w)
    s = scores_by(to_obs_frame(w).reset_index(names="tid"), obs, "sesong")
    assert list(s["sesong"]) == ["vinter", "vår", "sommer", "høst"] and (s["traff_regn"] == 1.0).all()
    v = rain_windows_by(w["precipitation"], w["precipitation"], "maned")
    assert len(v) == 12 and (v["traff_regn_24t"] == 1.0).all()


def test_rh_correction_in_model():
    from klatreforhold.physics.wetness import rh_correction, run_model
    crag, params = load_config(ROOT / "config" / "ekstraveggen.yaml")
    w = _w()
    p0 = {**params, "rh_korreksjon": 0.0, "rh_korreksjon_maned": None}
    a = run_model(w, crag, p0)
    b = run_model(w, crag, {**p0, "rh_korreksjon": -3.0})
    assert np.allclose(b["rh_brukt"], 82.0) and np.allclose(a["rh_brukt"], 85.0)
    # tørrere luft gir mer fordampning totalt
    assert b["evaporation_mm"].sum() > a["evaporation_mm"].sum()
    # målte timer korrigeres ikke
    c = run_model(w.assign(rh_malt=np.arange(len(w)) < 10), crag, {**p0, "rh_korreksjon": -3.0})
    assert np.allclose(c["rh_brukt"].iloc[:10], 85.0) and np.allclose(c["rh_brukt"].iloc[10:], 82.0)
    # månedsverdier glir over årsskiftet uten hopp
    idx = pd.date_range("2025-12-25", "2026-01-08", freq="h", tz="UTC")
    k = rh_correction(idx, {"rh_korreksjon_maned": [-4] + [0] * 10 + [-2]})
    assert np.abs(np.diff(k)).max() < 0.01 and -4 <= k.min() and k.max() <= -2
    assert np.allclose(rh_correction(idx, {"rh_korreksjon_maned": [-4] * 12, "rh_korreksjon_styrke": 0.5}), -2.0)


def test_station_correction_loaded_from_config():
    _, params = load_config(ROOT / "config" / "ekstraveggen.yaml")
    assert "rh_korreksjon" in params or "rh_korreksjon_maned" in params


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
