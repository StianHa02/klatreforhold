"""Simulering: virker kalibreringen når brukerne mest er der når det er tørt?

1. Lager en "sann" vegg med kjente parametre (tørker saktere enn startverdiene våre).
2. Trekker observasjoner slik brukere faktisk oppfører seg: dagtid, mest i helger, og mest når
   VÅRT varsel sier tørt (tilbakekoblingen). Når det faktisk er vått, rapporterer de sjeldnere.
3. Kalibrerer på én sesong og tester på neste, både på skjeve og på jevnt fordelte observasjoner.

  python scripts/simulate_bias.py --weather data/raw/ekstraveggen_openmeteo_metno_2023-01-01_2026-10-27.csv
"""
import argparse
import json

import numpy as np
import pandas as pd
from _common import DEFAULT_CONFIG, ROOT
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.ml.calibrate import PARAMS, calibrate, observation_propensity_weights
from klatreforhold.ml.evaluate import evaluate, format_table, simple_rules
from klatreforhold.physics.wetness import run_model

SANN = {"wdr_coefficient": 0.07, "holds_capacity_mm": 1.4, "holds_drying_factor": 0.2}


def sample_biased(truth_wet, prior_wet, idx, n, rng, tz="Europe/Oslo"):
    local = idx.tz_convert(tz)
    day = (local.hour >= 10) & (local.hour <= 20)
    weekend = local.dayofweek >= 5
    p = np.where(day, 1.0, 0.0) * np.where(weekend, 3.0, 1.0)
    p = p * np.where(prior_wet.reindex(idx).to_numpy(), 0.15, 1.0)   # drar når varselet sier tørt
    p = p * np.where(truth_wet.reindex(idx).to_numpy(), 0.4, 1.0)    # rapporterer sjeldnere når det er vått
    p = p / p.sum()
    return pd.DatetimeIndex(np.sort(rng.choice(idx, size=n, replace=False, p=p)))


def sample_uniform_daytime(idx, n, rng, tz="Europe/Oslo"):
    local = idx.tz_convert(tz)
    cand = idx[(local.hour >= 10) & (local.hour <= 20)]
    return pd.DatetimeIndex(np.sort(rng.choice(cand, size=n, replace=False)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", required=True)
    ap.add_argument("--n-train", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    crag, prior = load_config(a.config)
    w = load_weather(a.weather).interpolate(limit=3)

    truth = run_model(w, crag, {**prior, **SANN})
    flip = rng.random(len(truth)) < 0.05                                 # folk tar feil av og til
    truth_wet = pd.Series(truth["wet"].to_numpy() ^ flip, index=truth.index)
    prior_res = run_model(w, crag, prior)
    prior_wet = prior_res["wet"]

    train_idx = w.loc["2025-04-01":"2025-10-31"].index
    test_idx = w.loc["2026-04-01":"2026-10-25"].index
    obs_tr = sample_biased(truth_wet, prior_wet, train_idx, a.n_train, rng)
    obs_te = sample_biased(truth_wet, prior_wet, test_idx, 300, rng)
    obs_un = sample_uniform_daytime(test_idx, 300, rng)
    y_tr = truth_wet.loc[obs_tr]
    print(f"Treningsobservasjoner: {len(obs_tr)}, andel vått {y_tr.mean():.2f} "
          f"(sann andel vått på dagtid i perioden: {truth_wet.loc[train_idx].mean():.2f})")

    res = calibrate(w, y_tr, crag, prior)
    wts = observation_propensity_weights(w.loc[train_idx], obs_tr, crag.timezone)
    res_w = calibrate(w, y_tr, crag, prior, weights=wts)

    print("\nParameter              prior    kalibrert  kalibrert+vekter  SANN")
    for k in PARAMS:
        print(f"{k:<22} {res.prior_params[k]:7.3f}  {res.params[k]:9.3f}  {res_w.params[k]:16.3f}  {SANN[k]:5.3f}")

    models = {
        "startverdier": prior_wet,
        "kalibrert": run_model(w, crag, {**prior, **res.params})["wet"],
        "kalibrert+vekter": run_model(w, crag, {**prior, **res_w.params})["wet"],
        **simple_rules(w),
    }
    out = {}
    for navn, obs in [("TEST, skjeve observasjoner (slik data faktisk kommer inn)", obs_te),
                      ("TEST, jevnt fordelte observasjoner på dagtid (fasit)", obs_un)]:
        print(f"\n=== {navn} ===")
        y = truth_wet.loc[obs]
        r = {m: evaluate(p, y, w) for m, p in models.items()}
        print(format_table(r))
        out[navn] = r
    out["parametre"] = {"sann": SANN, "prior": res.prior_params, "kalibrert": res.params, "kalibrert_vekter": res_w.params}
    (ROOT / "outputs" / "simulering_skjevhet.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
