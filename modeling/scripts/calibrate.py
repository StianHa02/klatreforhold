"""Kalibrerer fysikkmodellen mot observasjonene (tåler at folk mest er der når det er tørt).

Deler kronologisk etter regnepisoder (omtrent 70/30) for å sjekke at det faktisk
ble bedre. Med --write lagres parametrene i config/kalibrert/<felt>.yaml, som load_config bruker
automatisk (timesjobben plukker dem opp når de er pushet).

  python scripts/calibrate.py --config config/ekstraveggen.yaml --weather data/raw/<vær>.csv --labels supabase
  python scripts/calibrate.py ... --write

V2 krever minst 50 observasjoner og 10 uavhengige regnepisoder før tilpasningen kan vurderes.
Se docs/MODELL_V2.md for krav til kontroll på andre episoder.
"""
import argparse
from pathlib import Path
import numpy as np

import yaml
from _common import DEFAULT_CONFIG, ROOT
from _labels import get_labels
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.ml.calibrate import PARAMS, calibrate, observation_propensity_weights, _p_wet
from klatreforhold.ml.evaluate import evaluate, format_table, event_split, rain_event_ids, simple_rules
from klatreforhold.physics.wetness import run_model
from klatreforhold.version import MODEL_VERSION, config_hash

MIN_OBS = 50


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", required=True, nargs="+", help="vær-CSV(er) og/eller 'supabase'")
    ap.add_argument("--labels", nargs="+", required=True, help="etikettfil(er) eller 'supabase'")
    ap.add_argument("--med-dev", action="store_true")
    ap.add_argument("--vekter", action="store_true", help="vekt etter hvor sannsynlig det er å bli observert")
    ap.add_argument("--write", action="store_true", help="lagre i config/kalibrert/ hvis det ble bedre")
    a = ap.parse_args()
    crag, params = load_config(a.config, apply_calibration=False)
    w = load_weather(a.weather, Path(a.config).stem)
    y = get_labels(a.labels, a.config, crag.timezone, a.med_dev)
    y = y[y.index.isin(w.index)].sort_index()
    if len(y) < MIN_OBS:
        raise SystemExit(f"Bare {len(y)} observasjoner. Vent til det er minst {MIN_OBS} (helst flere hundre).")
    try:
        train, test = event_split(w, y)
    except ValueError as err:
        raise SystemExit(str(err))
    y_tr, y_te = y.loc[train], y.loc[test]
    wts = observation_propensity_weights(w, y_tr.index, crag.timezone) if a.vekter else None
    print(f"Kalibrerer på {len(y_tr)} observasjoner ({y_tr.mean():.0%} vått), tester på {len(y_te)}")
    res = calibrate(w, y_tr, crag, params, weights=wts)
    print("\nParameter              før      etter")
    for k in PARAMS:
        print(f"{k:<22} {res.prior_params[k]:7.3f}  {res.params[k]:7.3f}")
    r0 = run_model(w, crag, params)
    r1 = run_model(w, crag, {**params, **res.params})
    before, after = evaluate(r0.wet, y_te, w), evaluate(r1.wet, y_te, w)
    print("\nTest på de nyeste observasjonene:")
    print(format_table({"før": before, "etter": after}))
    b0, b1 = before["etter_regn"]["balansert"], after["etter_regn"]["balansert"]
    def brier(result):
        amount = np.maximum(result.water_mm, result.ice_mm + result.snow_mm).loc[test]
        errors = (_p_wet(amount, params.get("damp_threshold_mm", .01)) - y_te.astype(float))**2
        return float(errors.groupby(rain_event_ids(w).reindex(test)).mean().mean())
    score0, score1 = brier(r0), brier(r1)
    better = (score1 < score0 and after["totalt"]["falskt_tort"] <= before["totalt"]["falskt_tort"]
              and b1 is not None and (b0 is None or b1 >= b0))
    print(format_table({name: evaluate(pred, y_te, w) for name, pred in simple_rules(w).items()}))
    print(f"Brier, lik vekt per regnepisode: {score0:.4f} -> {score1:.4f}")
    if a.write:
        if not better:
            print("Ikke lagret: kalibreringen ble ikke bedre etter regn på testdataene.")
            return
        path = Path(a.config).parent / "kalibrert" / Path(a.config).name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Skrevet av scripts/calibrate.py. Overstyrer startverdiene i ../" + path.name + "\n"
                        + yaml.safe_dump({"model_version": MODEL_VERSION, "validated": True,
                                          "base_config_hash": config_hash(crag, params),
                                          "model": {k: round(v, 4) for k, v in res.params.items()},
                                          "kalibrering": {"observasjoner": len(y), "test_balansert_etter_regn_for": b0,
                                                          "test_balansert_etter_regn_etter": b1,
                                                          "brier_for": score0, "brier_etter": score1}},
                                         allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"Lagret -> {path}  (commit og push, så bruker timesjobben det)")


if __name__ == "__main__":
    main()
