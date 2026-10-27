"""Kjører fysikkmodellen over en historisk periode og lager figur + CSV i outputs/.

  python scripts/run_history.py --weather data/raw/<fil>.csv [--labels data/labels/<fil>.csv]
"""
import argparse

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import DEFAULT_CONFIG, ROOT
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.ml.features import load_labels
from klatreforhold.physics.wetness import run_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", required=True)
    ap.add_argument("--labels")
    ap.add_argument("--name", default=None, help="navn på utfiler")
    ap.add_argument("--start", help="plott fra dato (YYYY-MM-DD); modellen kjøres likevel på hele serien")
    ap.add_argument("--end", help="plott til dato (YYYY-MM-DD)")
    a = ap.parse_args()
    crag, params = load_config(a.config)
    w = load_weather(a.weather)
    gaps = w["air_temperature"].isna()
    res = run_model(w, crag, params)
    res["data_mangler"] = gaps
    name = a.name or crag.name.lower() + "_historikk"
    res.tz_convert(crag.timezone).to_csv(ROOT / "outputs" / f"{name}.csv")

    tz = crag.timezone
    r = res.tz_convert(tz)
    if a.start or a.end:
        r = r.loc[a.start:a.end]
    w = w.loc[res.index.min():res.index.max()]
    fig, ax = plt.subplots(4, 1, figsize=(15, 11), sharex=True)
    ax[0].bar(r.index, w["precipitation"].reindex(r.index.tz_convert("UTC")).fillna(0).to_numpy(), width=1 / 24, color="#3b6fb6", label="nedbør (mm/t)")
    ax[0].bar(r.index, r["rain_on_face_mm"], width=1 / 24, color="#e0732c", label="regn som treffer veggen")
    ax[0].set_ylabel("mm/t"); ax[0].legend(loc="upper right")
    ax[1].plot(r.index, r["film_mm"], lw=0.8, label="vannfilm")
    ax[1].plot(r.index, r["holds_mm"], lw=0.8, label="tak/sprekker")
    ax[1].plot(r.index, r["seep_mm"], lw=0.8, ls="--", label="sigereservoar")
    ax[1].set_ylabel("mm"); ax[1].legend(loc="upper right")
    ax[2].plot(r.index, r["rock_temp"], lw=0.7, label="bergtemperatur (modell)")
    ax[2].plot(r.index, r["dew_point"], lw=0.7, label="duggpunkt")
    ax[2].set_ylabel("°C"); ax[2].legend(loc="upper right")
    colors = {"tort": "#4caf50", "fuktig": "#ffc107", "vatt": "#2b62c4", "is": "#9c27b0"}
    for st, c in colors.items():
        m = r["status"] == st
        ax[3].fill_between(r.index, 0, 1, where=m.to_numpy(), color=c, step="mid", label=f"modell: {st}", lw=0)
    if r["data_mangler"].any():
        ax[3].fill_between(r.index, 0, 1, where=r["data_mangler"].to_numpy(), color="white", alpha=0.6, step="mid", lw=0, label="mangler værdata")
    if a.labels:
        y = load_labels(a.labels, tz).tz_convert(tz)
        y = y.loc[r.index.min():r.index.max()]
        ax[3].scatter(y.index[~y], [1.1] * int((~y).sum()), s=4, color="#4caf50", label="etikett: tørt")
        ax[3].scatter(y.index[y], [1.2] * int(y.sum()), s=4, color="#2b62c4", label="etikett: vått")
    ax[3].set_ylim(0, 1.3); ax[3].set_yticks([])
    ax[3].legend(loc="upper right", ncol=3, fontsize=8)
    fig.suptitle(f"{crag.name}: modellert vann på veggen")
    fig.tight_layout()
    png = ROOT / "outputs" / f"{name}.png"
    fig.savefig(png, dpi=110)
    print(r["status"].value_counts(normalize=True).round(3).to_string())
    print(f"Lagret -> {png}")


if __name__ == "__main__":
    main()
