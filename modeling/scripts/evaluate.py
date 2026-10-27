"""Rettferdig evaluering av fysikkmodellen (og enkle regler) mot observasjoner, delt opp etter værsituasjon.
Viser også treff per ledetid fra varselarkivet hvis observasjonene kommer fra Supabase.

  python scripts/evaluate.py --config config/ekstraveggen.yaml --weather data/raw/<vær>.csv --labels supabase
"""
import argparse
import json

from _common import DEFAULT_CONFIG, ROOT
from _labels import get_labels
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.ml.evaluate import evaluate, forecast_skill_by_lead, format_table, simple_rules
from klatreforhold.physics.wetness import run_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", required=True)
    ap.add_argument("--labels", nargs="+", required=True, help="etikettfil(er) eller 'supabase'")
    ap.add_argument("--med-dev", action="store_true")
    a = ap.parse_args()
    crag, params = load_config(a.config)
    w = load_weather(a.weather).interpolate(limit=3)
    y = get_labels(a.labels, a.config, crag.timezone, a.med_dev)
    y = y[y.index.isin(w.index)]
    if y.empty:
        raise SystemExit("Ingen observasjoner innenfor værserien")
    print(f"{len(y)} observasjoner, {y.mean():.0%} vått/fuktig\n")
    models = {"fysikk (nåværende)": run_model(w, crag, params)["wet"], **simple_rules(w)}
    res = {m: evaluate(p, y, w) for m, p in models.items()}
    print(format_table(res))
    out = {"situasjoner": res}
    if "supabase" in a.labels:
        from pathlib import Path

        from klatreforhold.storage import get_storage
        lead = forecast_skill_by_lead(get_storage().forecast_archive(Path(a.config).stem), y)
        if not lead.empty:
            print("Varselet slik det så ut X timer før (fra arkivet):")
            print(lead.round(2).to_string(index=False))
            out["ledetid"] = lead.to_dict(orient="records")
    path = ROOT / "outputs" / f"evaluering_{crag.name.lower()}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nLagret -> {path}")


if __name__ == "__main__":
    main()
