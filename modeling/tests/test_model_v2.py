"""Regresjoner for stråling, nedbør, faseoverganger og tilstandskontinuitet."""
import sys
from pathlib import Path
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.config import Crag, load_config
from klatreforhold.physics.solar import sky_view_factor, face_irradiance, horizon_elevation
from klatreforhold.physics.forcing import prepare_weather
from klatreforhold.physics.wetness import run_model
from klatreforhold.physics.balance import _phase_change, LF, state_at


def weather(n=96, **kw):
    values = dict(air_temperature=8., relative_humidity=80., precipitation=0., wind_speed=3.,
                  wind_direction=270., cloud_cover=1., ghi=0., dni=0., dhi=0., longwave_down=350.)
    values.update(kw)
    return pd.DataFrame(values, index=pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC"))


def test_tilted_sky_and_circular_horizon():
    for tilt in [0, 70, 90, 110, 135, 180]:
        c = Crag("test", 60, 5, 270, face_tilt_deg=tilt)
        assert abs(sky_view_factor(c) - (1 + np.cos(np.deg2rad(tilt))) / 2) < .0001
    c = Crag("test", 60, 5, 270, horizon=[[10, 20], [180, 0], [350, 20]])
    np.testing.assert_allclose(horizon_elevation(c, [359, 0, 1]), 20)


def test_diffuse_sky_blocking_and_no_double_reflection():
    c = Crag("test", 60, 5, 270)
    w = weather(1, ghi=100., dhi=100.)
    a = face_irradiance(w, c).iloc[0]
    b = face_irradiance(w, replace(c, horizon=[[0, 90], [360, 90]])).iloc[0]
    assert a.sw_face_diffuse == pytest.approx(50, abs=.01)
    assert b.sw_face_diffuse == 0
    assert a.sw_face == pytest.approx(57.5, abs=.01)
    assert b.sw_face == pytest.approx(15)


def test_missing_rain_rejected_and_wind_crosses_north():
    w = weather(3)
    w.loc[w.index[1], "precipitation"] = np.nan
    with pytest.raises(ValueError, match="Ufullstendig"):
        prepare_weather(w)
    w.precipitation = 0.
    w.wind_direction = [350., np.nan, 10.]
    middle = prepare_weather(w).wind_direction.iloc[1]
    assert min(middle, 360-middle) < 1e-10


def test_mass_energy_and_checkpoint_resume():
    w = weather(72, air_temperature=-4., precipitation=.5, relative_humidity=95., longwave_down=270.)
    w.loc[w.index[24:], "air_temperature"] = 8.
    w.loc[w.index[24:], "precipitation"] = 0.
    c = Crag("test", 60, 5, 270, face_tilt_deg=70)
    whole = run_model(w, c)
    assert whole.mass_balance_error_mm.abs().max() < 1e-9
    assert whole.energy_balance_error_j_m2.abs().max() < 1e-6
    assert whole.snow_mm.max() > .1 and whole.melt_mm.sum() > .1
    assert whole.catchment_melt_mm.sum() > 0
    assert (whole.select_dtypes("number").filter(regex="^(film|holds|seep|ice|snow|catchment_snow)_mm$") >= -1e-10).all().all()
    first = run_model(w.iloc[:35], c)
    last = run_model(w.iloc[35:], c, init_state=state_at(first, first.index[-1]))
    np.testing.assert_allclose(last.water_mm, whole.water_mm.iloc[35:], atol=1e-10)
    np.testing.assert_allclose(last.rock_temp, whole.rock_temp.iloc[35:], atol=1e-10)


def test_phase_energy_is_used_once_and_ice_persists():
    s = dict(Ts=0., film=1., holds=0., ice_film=0., ice_holds=0., snow=0.)
    frozen, melted = _phase_change(s, -LF/2, 100000)
    assert frozen == .5 and melted == 0 and s["Ts"] == 0
    _phase_change(s, LF/4, 100000)
    assert s["film"] == .75 and s["ice_film"] == .25
    r = run_model(weather(12, air_temperature=-8., relative_humidity=100., longwave_down=250.),
                  Crag("test", 60, 5, 270), init_state={"ice_film": 2., "Ts": -8., "Tdeep": -8.})
    assert (r.status == "is").all() and r.ice_mm.iloc[-1] > 1
    assert r.evaporation_mm.sum() == 0


def test_shelter_and_overhangs_reduce_rain_but_allow_seepage():
    w = weather(12, precipitation=2., wind_speed=8.)
    c = Crag("test", 60, 5, 270)
    amounts = [run_model(w, replace(c, face_tilt_deg=t)).rain_on_face_mm.sum() for t in [70, 90, 110, 135]]
    assert amounts == sorted(amounts, reverse=True)
    assert amounts[-1] < amounts[1] * .1
    calm = weather(2, precipitation=2., wind_speed=0.)
    a = run_model(calm, c, {"runoff_from_above": 0})
    b = run_model(calm, replace(c, rain_sheltered=True), {"runoff_from_above": 0})
    assert b.rain_on_face_mm.sum() == pytest.approx(a.rain_on_face_mm.sum()*.1)
    assert run_model(w, replace(c, face_tilt_deg=135), init_state={"seep": 5.}).seep_flux_mm.sum() > 0


def test_ekstraveggen_no_morning_direct_sun_and_dst():
    c, _ = load_config(Path(__file__).resolve().parents[1] / "config/ekstraveggen.yaml")
    for date in ["2026-06-21", "2026-10-24", "2026-10-25", "2026-10-30"]:
        w = weather(24, ghi=200., dni=500., dhi=50.)
        w.index = pd.date_range(date, periods=24, freq="h", tz="UTC")
        r = face_irradiance(w, c)
        local = r.index.tz_convert("Europe/Oslo")
        assert not r.sun_on_face[(local.hour >= 8) & (local.hour <= 11)].any()
        assert not r.sun_on_face[r.sun_elevation <= 0].any()
        # Én times sommertidsskifte, aldri tre timers forskyvning.
        expected = 2 if date < "2026-10-25" else 1
        assert local[12].utcoffset().total_seconds() == expected * 3600


def test_every_config_has_finite_balances_and_steepness():
    configs = Path(__file__).resolve().parents[1] / "config"
    found = set()
    for path in configs.glob("*.yaml"):
        c, p = load_config(path)
        found.add(path.stem)
        assert c.steepness_id in (1, 2, 3, 4)
        r = run_model(weather(24, precipitation=2.), c, p)
        assert r.mass_balance_error_mm.abs().max() < 1e-8
        assert r.energy_balance_error_j_m2.abs().max() < 1e-5
    assert {'ekstraveggen', 'helleneset', 'sandviken', 'neseveggen', 'bolstadoyri',
            'trollkona', 'loddefjord', 'bymuren', 'fabrikkveggen'} <= found


def test_winter_timestep_convergence():
    w = weather(96, air_temperature=-5., relative_humidity=90., longwave_down=260.)
    w.loc[w.index[:12], 'precipitation'] = 1.
    w.loc[w.index[36:], 'air_temperature'] = 8.
    w.loc[w.index[36:], 'longwave_down'] = 350.
    c = Crag('test', 60, 5, 270, face_tilt_deg=70)
    coarse, fine = run_model(w, c), run_model(w, c, substeps=120)
    assert (coarse.rock_temp-fine.rock_temp).abs().max() < .5
    assert (coarse.water_mm-fine.water_mm).abs().max() < .05
    assert (coarse.status != fine.status).sum() <= 2
