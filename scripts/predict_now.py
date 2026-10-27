"""Varsel for feltet: kjører modellen på siste døgn + varsel og skriver status per time.

  python scripts/predict_now.py              # Open-Meteo (MET Nordic, med stråling)
  python scripts/predict_now.py --source metno   # api.met.no Locationforecast
"""
import argparse

from _common import DEFAULT_CONFIG, ROOT

from klatreforhold.config import load_config
from klatreforhold.physics.wetness import hours_until_dry, run_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--source", choices=["openmeteo", "metno"], default="openmeteo")
    a = ap.parse_args()
    crag, params = load_config(a.config)
    if a.source == "openmeteo":
        from klatreforhold.data.openmeteo import fetch_forecast
        w = fetch_forecast(crag.lat, crag.lon, past_days=5, forecast_days=3)
    else:
        # Locationforecast har ikke historikk: start med tomme vannlagre (mindre presist første døgnet)
        from klatreforhold.data.metno import fetch_locationforecast
        w = fetch_locationforecast(crag.lat, crag.lon)
    res = run_model(w, crag, params)
    res["hours_until_dry"] = hours_until_dry(res)
    local = res.tz_convert(crag.timezone)
    out = ROOT / "outputs" / f"{crag.name.lower()}_varsel.csv"
    local.to_csv(out)
    import pandas as pd
    now = pd.Timestamp.now(tz=crag.timezone).floor("h")
    view = local.loc[now:, ["status", "water_mm", "rock_temp", "dew_point", "rain_on_face_mm", "sun_on_face", "hours_until_dry"]]
    print(view.head(60).round(2).to_string())
    print(f"\nLagret -> {out}")


if __name__ == "__main__":
    main()
