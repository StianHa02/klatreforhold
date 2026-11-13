import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.backfill import endringer, skriverader, spill_om, sammenhengende_slutt
from klatreforhold.version import config_hash
from klatreforhold.predict import load_crag


def _vaer(timer=240, start="2026-11-01"):
    idx = pd.date_range(start, periods=timer, freq="h", tz="UTC", name="time")
    return pd.DataFrame({"air_temperature": 8.0, "relative_humidity": 80.0, "precipitation": 0.0,
                         "wind_speed": 2.0, "wind_direction": 180.0, "cloud_cover": 50.0, "ghi": 0.0,
                         "dni": 0.0, "dhi": 0.0, "longwave_down": 300.0}, index=idx)


def test_hull_kutter_innkjoringen():
    w = _vaer()
    w.loc[w.index[50], "precipitation"] = np.nan
    assert sammenhengende_slutt(w).index[0] == w.index[51]


def test_spill_og_endringer():
    analyse, info = spill_om("ekstraveggen", _vaer())
    assert len(analyse) == 240 and not info["innkjoring_fullstendig"]
    crag, params = load_crag("ekstraveggen")
    ny = config_hash(crag, params)
    arkiv = pd.DataFrame({"felt": "ekstraveggen", "generert": [analyse.index[5]] * 2,
                          "tid": [analyse.index[5], analyse.index[8]], "ledetid_timer": [0, 3],
                          "status": "vatt", "konfigurasjon": ["gammel", ny]})
    e = endringer(arkiv, analyse, ny)
    assert len(e) == 1  # raden med dagens konfigurasjon røres ikke
    rader = skriverader("ekstraveggen", e, ny)
    assert len(rader) == 1 and rader[0]["konfigurasjon"] == ny and rader[0]["ledetid_timer"] == 0
