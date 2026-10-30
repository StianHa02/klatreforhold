"""Tester rettferdig evaluering og kalibrering på en liten syntetisk serie (uten nett)."""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klatreforhold.config import load_config  # noqa: E402
from klatreforhold.ml.calibrate import calibrate  # noqa: E402
from klatreforhold.ml.evaluate import evaluate, strata  # noqa: E402
from klatreforhold.physics.wetness import run_model  # noqa: E402

CFG = ROOT / "config" / "ekstraveggen.yaml"


def _weather(days=40, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-01", periods=days * 24, freq="h", tz="UTC")
    rain = np.zeros(len(idx))
    for start in rng.choice(len(idx) - 10, size=days // 4, replace=False):
        rain[start:start + 6] = rng.uniform(0.5, 4)
    return pd.DataFrame({"air_temperature": 12 + 4 * np.sin(np.arange(len(idx)) * 2 * np.pi / 24),
                         "relative_humidity": 80.0, "precipitation": rain, "wind_speed": 4.0,
                         "wind_direction": 290.0, "cloud_cover": 0.6}, index=idx)


def test_strata_and_metrics():
    w = _weather()
    s = strata(w)
    assert set(s.unique()) <= {"under_regn", "etter_regn", "torkeperiode"}
    y = pd.Series(True, index=w.index[:100])
    res = evaluate(pd.Series(False, index=w.index), y, w)
    assert res["totalt"]["treff_vatt"] == 0.0 and res["totalt"]["treff_tort"] is None


def test_calibration_moves_towards_truth():
    crag, p = load_config(CFG)
    w = _weather(days=60)
    truth = {"evaporation_efficiency": .4}
    tw = run_model(w, crag, {**p, **truth})["wet"]
    obs = w.index[::7]
    r = calibrate(w, tw.loc[obs], crag, p, maxiter=60)
    assert r.nll_etter < r.nll_for
    assert .25 <= r.params["evaporation_efficiency"] < 1
    assert set(r.params) == {"evaporation_efficiency"}


def test_calibrated_overlay_is_loaded():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "x.yaml"
        base.write_text(CFG.read_text(encoding="utf-8"), encoding="utf-8")
        (Path(d) / "kalibrert").mkdir()
        (Path(d) / "kalibrert" / "x.yaml").write_text("model:\n  holds_capacity_mm: 1.23\n", encoding="utf-8")
        crag, params = load_config(base)
        assert params["holds_capacity_mm"] == .6
        from klatreforhold.version import MODEL_VERSION, config_hash
        import yaml
        (Path(d) / "kalibrert/x.yaml").write_text(yaml.safe_dump({
            "model_version": MODEL_VERSION, "validated": True, "base_config_hash": config_hash(crag, params),
            "model": {"evaporation_efficiency": .7}}), encoding="utf-8")
        assert load_config(base)[1]["evaporation_efficiency"] == .7


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
