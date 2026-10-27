"""Kalibrerer fysikkmodellen mot observasjonene (tåler at folk mest er der når det er tørt).

Bruker de eldste 70 % av observasjonene til kalibrering og de nyeste 30 % til å sjekke at det faktisk
ble bedre. Med --write lagres parametrene i config/kalibrert/<felt>.yaml, som load_config bruker
automatisk (timesjobben plukker dem opp når de er pushet).

  python scripts/calibrate.py --config config/ekstraveggen.yaml --weather data/raw/<vær>.csv --labels supabase
  python scripts/calibrate.py ... --write

Simulering viser at kalibrering hjelper tydelig fra et par hundre observasjoner (se docs/MODEL.md).
"""
import argparse

import yaml
from _common import DEFAULT_CONFIG, ROOT
from _labels import get_labels
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.ml.calibrate import PARAMS, calibrate, observation_propensity_weights
from klatreforhold.ml.evaluate import evaluate, format_table
from klatreforhold.physics.wetness import run_model

MIN_OBS = 50


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", required=True)
    ap.add_argument("--labels", nargs="+", required=True, help="etikettfil(er) eller 'supabase'")
    ap.add_argument("--med-dev", action="store_true")
    ap.add_argument("--vekter", action="store_true", help="vekt etter hvor sannsynlig det er å bli observert")
    ap.add_argument("--write", action="store_true", help="lagre i config/kalibrert/ hvis det ble bedre")
    a = ap.parse_args()
    crag, params = load_config(a.config)
    w = load_weather(a.weather).interpolate(limit=3)
    y = get_labels(a.labels, a.config, crag.timezone, a.med_dev)
    y = y[y.index.isin(w.index)].sort_index()
    if len(y) < MIN_OBS:
        raise SystemExit(f"Bare {len(y)} observasjoner. Vent til det er minst {MIN_OBS} (helst flere hundre).")
    cut = y.index[int(len(y) * 0.7)]
    y_tr, y_te = y[y.index < cut], y[y.index >= cut]
    wts = observation_propensity_weights(w, y_tr.index, crag.timezone) if a.vekter else None
    print(f"Kalibrerer på {len(y_tr)} observasjoner ({y_tr.mean():.0%} vått), tester på {len(y_te)}")
    res = calibrate(w, y_tr, crag, params, weights=wts)
    print("\nParameter              før      etter")
    for k in PARAMS:
        print(f"{k:<22} {res.prior_params[k]:7.3f}  {res.params[k]:7.3f}")
    before = evaluate(run_model(w, crag, params)["wet"], y_te, w)
    after = evaluate(run_model(w, crag, {**params, **res.params})["wet"], y_te, w)
    print("\nTest på de nyeste observasjonene:")
    print(format_table({"før": before, "etter": after}))
    b0, b1 = before["etter_regn"]["balansert"], after["etter_regn"]["balansert"]
    better = b1 is not None and (b0 is None or b1 >= b0)
    if a.write:
        if not better:
            print("Ikke lagret: kalibreringen ble ikke bedre etter regn på testdataene.")
            return
        path = ROOT / "config" / "kalibrert" / f"{crag.name.lower()}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Skrevet av scripts/calibrate.py. Overstyrer startverdiene i ../" + path.name + "\n"
                        + yaml.safe_dump({"model": {k: round(v, 4) for k, v in res.params.items()},
                                          "kalibrering": {"observasjoner": len(y), "test_balansert_etter_regn_for": b0,
                                                          "test_balansert_etter_regn_etter": b1}},
                                         allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"Lagret -> {path}  (commit og push, så bruker timesjobben det)")


if __name__ == "__main__":
    main()
