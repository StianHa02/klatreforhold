"""Kjører simuleringen fra simulate_bias.py for flere frø og antall observasjoner, og skriver ett sammendrag.

  python scripts/simulate_sweep.py --weather <vær>.csv --seeds 1 2 3 --n 150 400
Resultater legges til i outputs/simulering_sweep.csv (kan kjøres i flere omganger).
"""
import argparse

import numpy as np
import pandas as pd
from _common import DEFAULT_CONFIG, ROOT
from simulate_bias import SANN, sample_biased, sample_uniform_daytime
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.ml.calibrate import calibrate, observation_propensity_weights
from klatreforhold.ml.evaluate import evaluate
from klatreforhold.physics.wetness import run_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--n", type=int, nargs="+", default=[150])
    a = ap.parse_args()
    crag, prior = load_config(a.config)
    w = load_weather(a.weather).interpolate(limit=3)
    truth = run_model(w, crag, {**prior, **SANN})
    prior_wet = run_model(w, crag, prior)["wet"]
    train_idx = w.loc["2025-04-01":"2025-10-31"].index
    test_idx = w.loc["2026-04-01":"2026-10-25"].index
    out = ROOT / "outputs" / "simulering_sweep.csv"
    for seed in a.seeds:
        for n in a.n:
            rng = np.random.default_rng(seed)
            flip = rng.random(len(truth)) < 0.05
            tw = pd.Series(truth["wet"].to_numpy() ^ flip, index=truth.index)
            obs_tr = sample_biased(tw, prior_wet, train_idx, n, rng)
            obs_un = sample_uniform_daytime(test_idx, 400, rng)
            y = tw.loc[obs_tr]
            rows = []
            for navn, wts in [("kalibrert", None),
                              ("kalibrert+vekter", observation_propensity_weights(w.loc[train_idx], obs_tr, crag.timezone))]:
                r = calibrate(w, y, crag, prior, weights=wts)
                pred = run_model(w, crag, {**prior, **r.params})["wet"]
                ev = evaluate(pred, tw.loc[obs_un], w)
                rows.append({"seed": seed, "n": n, "modell": navn, **{f"p_{k}": v for k, v in r.params.items()},
                             "bal_etter_regn": ev["etter_regn"]["balansert"], "bal_totalt": ev["totalt"]["balansert"]})
            ev0 = evaluate(prior_wet, tw.loc[obs_un], w)
            rows.append({"seed": seed, "n": n, "modell": "startverdier",
                         "bal_etter_regn": ev0["etter_regn"]["balansert"], "bal_totalt": ev0["totalt"]["balansert"]})
            df = pd.DataFrame(rows)
            df.to_csv(out, mode="a", header=not out.exists(), index=False)
            print(df[["seed", "n", "modell", "bal_etter_regn", "bal_totalt"]].round(3).to_string(index=False, header=False))


if __name__ == "__main__":
    main()
