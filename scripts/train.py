"""Trener og sammenligner fysikk alene, scikit-learn og PyTorch mot etiketter.

  python scripts/train.py --weather data/raw/<vær>.csv --labels data/labels/<etiketter>.csv [--torch]

Vær-CSV: fra fetch_history.py (Open-Meteo/Frost) eller stasjons-CSV med 'referenceTime'.
"""
import argparse
import json
from pathlib import Path

import pandas as pd
from _common import DEFAULT_CONFIG, ROOT

from klatreforhold.config import load_config
from klatreforhold.ml.features import build_features, load_labels
from klatreforhold.ml.train import evaluate_physics, evaluate_simple_rules, time_split, train_sklearn, train_torch
from klatreforhold.physics.wetness import run_model


def load_weather(path):
    head = pd.read_csv(path, nrows=1)
    if "referenceTime" in head:
        from klatreforhold.data.station_csv import load_station_csv
        return load_station_csv(path)[0]
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    return df.asfreq("1h")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", required=True)
    ap.add_argument("--labels", required=True, nargs="+",
                    help="én eller flere etikettfiler, eller 'supabase' for å hente observasjonene direkte")
    ap.add_argument("--med-dev", action="store_true", help="ta med observasjoner registrert fra utvikling (kilde=dev)")
    ap.add_argument("--save", action="store_true", help="lagre modellene i models/ så API-et bruker dem")
    ap.add_argument("--torch", action="store_true", help="tren også GRU-modell (PyTorch, CUDA hvis mulig)")
    a = ap.parse_args()
    crag, params = load_config(a.config)
    w = load_weather(a.weather)
    phys = run_model(w, crag, params)
    X = build_features(w.interpolate(limit=3), phys, crag.timezone)
    X = X[w["air_temperature"].notna()]  # ikke tren på utfylte hull
    def labels(p):
        if p == "supabase":
            from klatreforhold.ml.features import labels_from_frame
            from klatreforhold.storage import SupabaseStorage, get_storage
            st = get_storage()
            if not isinstance(st, SupabaseStorage):
                raise SystemExit("--labels supabase krever SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY (f.eks. i .env)")
            df = st.all_observations(Path(a.config).stem, include_dev=a.med_dev)
            print(f"Hentet {len(df)} observasjoner fra Supabase")
            return labels_from_frame(df, crag.timezone)
        return load_labels(p, crag.timezone)

    y = pd.concat([labels(p) for p in a.labels])
    if y.empty:
        raise SystemExit("Ingen etiketter ennå")
    y = y.groupby(level=0).max().reindex(X.index).dropna().astype(bool)
    tr, te = time_split(X, y)
    print(f"Trening: {tr.min()} -> {tr.max()} ({len(tr)} t), test: {te.min()} -> {te.max()} ({len(te)} t)")
    results = {**evaluate_simple_rules(w.interpolate(limit=3), y, te), "fysikk_alene": evaluate_physics(X, y, te)}
    sk_model, sk_cols, results["sklearn_med_fysikk"] = train_sklearn(X, y, tr, te, use_physics=True)
    _, _, results["sklearn_uten_fysikk"] = train_sklearn(X, y, tr, te, use_physics=False)
    if a.torch:
        torch_model, _, results["torch_gru_med_fysikk"] = train_torch(X, y, tr, te, use_physics=True)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    if a.save:
        import joblib
        from pathlib import Path
        slug = Path(a.config).stem
        import os
        mdir = Path(os.environ.get("KLATREFORHOLD_MODEL_DIR", ROOT / "models"))
        mdir.mkdir(exist_ok=True)
        # Endelig modell trenes på ALLE etiketter (testsplitten over var bare for å måle)
        all_t = y.index
        final_sk = sk_model.__class__(**sk_model.get_params()).fit(X.loc[all_t, sk_cols], y.loc[all_t].astype(int))
        joblib.dump({"model": final_sk, "cols": sk_cols}, mdir / f"{slug}_sklearn.joblib")
        print(f"Lagret -> {mdir / f'{slug}_sklearn.joblib'}")
        if a.torch:
            from klatreforhold.ml.torch_model import GRUWetModel
            GRUWetModel(torch_model.cols, torch_model.window, torch_model.hidden).fit(X, y, all_t, verbose=False) \
                .save(mdir / f"{slug}_torch.pt")
            print(f"Lagret -> {mdir / f'{slug}_torch.pt'}")
    out = ROOT / "outputs" / "train_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Lagret -> {out}")


if __name__ == "__main__":
    main()
