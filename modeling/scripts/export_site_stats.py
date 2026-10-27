"""Lager statistikken som vises på "Om modellen"-siden (web/data/modellstatistikk.json).

Kjører fysikkmodellen over hele værhistorikken for hvert felt (MET Nordic via Open-Meteo) og regner ut:
  - andel tørre timer per måned (hele døgnet og dagtid 08-20)
  - timer med sol på veggen per døgn, per måned
  - tørketid etter regn (timer fra regnet stopper til modellen sier tørt), sommer og vinter
og tar med resultatene fra simuleringen av skjeve observasjoner (outputs/simulering_sweep.csv).

  python scripts/export_site_stats.py
"""
import json
from datetime import date

import numpy as np
import pandas as pd
from _common import ROOT
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.physics.wetness import run_model

OUT = ROOT.parent / "web" / "data" / "modellstatistikk.json"


def drying_times(w: pd.DataFrame, res: pd.DataFrame, min_rain_mm=2.0, cap_h=72):
    """Timer fra regnet stopper (>= min_rain_mm siste 12 t, så 3 t opphold) til modellen sier tørt."""
    p = w["precipitation"].fillna(0).to_numpy()
    wet = res["wet"].to_numpy()
    sum12 = pd.Series(p).rolling(12, min_periods=1).sum().to_numpy()
    out = []
    i, n = 0, len(p)
    while i < n - 4:
        if p[i] >= 0.2 and p[i + 1:i + 4].max() < 0.2 and sum12[i] >= min_rain_mm:
            j = i + 1
            while j < n and wet[j] and j - i <= cap_h and p[j] < 0.2:
                j += 1
            if j < n and p[j] < 0.2:  # bare episoder som tørket før neste regn
                out.append((w.index[i], j - i))
            i = j
        i += 1
    return pd.DataFrame(out, columns=["slutt", "timer"])


def main():
    crags = {}
    for cfg in sorted((ROOT / "config").glob("*.yaml")):
        crag, params = load_config(cfg)
        slug = cfg.stem
        files = sorted((ROOT / "data" / "raw").glob(f"{slug}_openmeteo_metno_*.csv"))
        if not files:
            print(f"Hopper over {slug}: mangler værhistorikk")
            continue
        w = load_weather(files[-1]).interpolate(limit=3)
        res = run_model(w, crag, params)
        local = res.index.tz_convert(crag.timezone)
        dry = ~res["wet"]
        day = (local.hour >= 8) & (local.hour <= 20)
        mnd = local.month
        tort_mnd = dry.groupby(mnd).mean()
        tort_dag_mnd = dry[day].groupby(mnd[day]).mean()
        sol_mnd = res["sun_on_face"].astype(float).groupby(mnd).mean() * 24
        dt = drying_times(w, res)
        sommer = dt[dt["slutt"].dt.tz_convert(crag.timezone).dt.month.isin([4, 5, 6, 7, 8, 9])]["timer"]
        vinter = dt[~dt["slutt"].dt.tz_convert(crag.timezone).dt.month.isin([4, 5, 6, 7, 8, 9])]["timer"]

        def q(s):
            return None if s.empty else {"median": float(s.median()), "q25": float(s.quantile(.25)),
                                         "q75": float(s.quantile(.75)), "n": int(len(s))}

        crags[slug] = {
            "navn": crag.name, "orientering": crag.face_azimuth_deg, "helning": crag.face_tilt_deg,
            "periode": [str(local.min().date()), str(local.max().date())],
            "tort_per_maned": [round(float(tort_mnd.get(m, np.nan)), 3) for m in range(1, 13)],
            "tort_dagtid_per_maned": [round(float(tort_dag_mnd.get(m, np.nan)), 3) for m in range(1, 13)],
            "soltimer_per_dogn": [round(float(sol_mnd.get(m, 0)), 2) for m in range(1, 13)],
            "torketid_timer": {"sommer": q(sommer), "vinter": q(vinter)},
            "regn_pa_veggen_mm_per_ar": round(float(res["rain_on_face_mm"].sum() / (len(res) / 8766)), 0),
            "nedbor_mm_per_ar": round(float(w["precipitation"].sum() / (len(w) / 8766)), 0),
        }
        print(slug, crags[slug]["torketid_timer"], crags[slug]["periode"])

    sim = None
    sweep = ROOT / "outputs" / "simulering_sweep.csv"
    if sweep.exists():
        df = pd.read_csv(sweep)
        g = df.groupby(["n", "modell"])["bal_etter_regn"]
        sim = [{"n": int(n), "modell": m, "snitt": round(float(v.mean()), 3), "min": round(float(v.min()), 3),
                "maks": round(float(v.max()), 3), "frø": int(len(v))} for (n, m), v in g]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generert": str(date.today()), "felt": crags, "simulering": sim},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Lagret -> {OUT}")


if __name__ == "__main__":
    main()
