"""MEPS-ensemblet uten nett: lesing av OPeNDAP-svaret og sannsynlighet for tørt berg."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.config import ROOT, load_config  # noqa: E402
from klatreforhold.data.meps_ensemble import parse_precip  # noqa: E402
from klatreforhold.physics.forcing import prepare_weather  # noqa: E402
from klatreforhold.physics.wetness import run_model  # noqa: E402
from klatreforhold.predict import ensemble_p_tort  # noqa: E402


def weather(n=72, **kw):
    values = dict(air_temperature=10., relative_humidity=60., precipitation=0., wind_speed=3.,
                  wind_direction=270., cloud_cover=.5, ghi=0., dni=0., dhi=0., longwave_down=320.)
    values.update(kw)
    return pd.DataFrame(values, index=pd.date_range("2026-06-01", periods=n, freq="h", tz="UTC"))


def test_parse_precip_fyllverdier_blir_nan():
    text = ("precipitation_amount_acc.precipitation_amount_acc[2][1][2][1][1]\n"
            "[0][0][0][0], 0.0\n[0][0][1][0], 9.96921E36\n[1][0][0][0], 1.5\n[1][0][1][0], 0.25\n")
    a = parse_precip(text, 2, 2)
    assert a[0, 0] == 0 and np.isnan(a[0, 1]) and a[1, 0] == 1.5 and a[1, 1] == .25
    # første gyldige time per medlem har ingen forrige akkumulasjon
    hourly = np.diff(a, axis=0, prepend=np.nan)
    assert np.isnan(hourly[0]).all() and hourly[1, 0] == 1.5 and np.isnan(hourly[1, 1])


def test_ensemble_regn_gir_lav_p_tort():
    crag, params = load_config(ROOT / "config/ekstraveggen.yaml")
    raw = weather()
    res = run_model(prepare_weather(raw), crag, params)
    now = raw.index[48]
    assert (res.loc[now:, "status"] == "tort").all()
    idx = raw.index[40:]
    dry = pd.DataFrame(0., index=idx, columns=range(12))
    wet = dry.copy()
    wet.iloc[10:14, :6] = 5.  # halvparten av medlemmene gir kraftig regn noen timer etter nå
    assert (ensemble_p_tort(raw, res, crag, params, now, dry) == 1).all()
    p = ensemble_p_tort(raw, res, crag, params, now, wet)
    assert p.iloc[0] == 1 and p.min() == .5, p.round(2).tolist()
    # for få medlemmer gir ingen sannsynlighet
    assert ensemble_p_tort(raw, res, crag, params, now, dry.iloc[:, :3]) is None


def test_radartimer_beholdes():
    crag, params = load_config(ROOT / "config/ekstraveggen.yaml")
    raw = weather()
    raw["precipitation_source"] = "metnordic"
    now = raw.index[48]
    raw.loc[now, "precipitation_source"] = "nowcast"
    res = run_model(prepare_weather(raw), crag, params)
    members = pd.DataFrame(0., index=raw.index[40:], columns=range(12))
    members.loc[now] = 5.  # ensemblet sier regn, radaren sier tørt: radaren vinner
    assert ensemble_p_tort(raw, res, crag, params, now, members).iloc[0] == 1


if __name__ == "__main__":
    test_parse_precip_fyllverdier_blir_nan()
    test_ensemble_regn_gir_lav_p_tort()
    test_radartimer_beholdes()
    print("ok")
