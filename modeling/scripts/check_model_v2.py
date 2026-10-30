"""Reproduserbar kontroll uten databaseendringer. --live prøver offentlige vær-API-er."""
import argparse
import json
import warnings
import numpy as np
import pandas as pd
from _common import ROOT
from klatreforhold.config import load_config
from klatreforhold.physics.solar import face_irradiance, sky_view_factor
from klatreforhold.physics.wetness import run_model
from klatreforhold.version import MODEL_VERSION


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--forecast", action="store_true", help="kjør hele værkjeden og fem døgn varsel for Ekstraveggen")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=FutureWarning)
    output = {"modellversjon": MODEL_VERSION, "felt": {}}
    for cfg in sorted((ROOT / "config").glob("*.yaml")):
        crag, params = load_config(cfg)
        entry = {"retning": crag.face_azimuth_deg, "helning": crag.face_tilt_deg,
                 "bratthet_id": crag.steepness_id, "himmelsyn": round(sky_view_factor(crag), 4), "sol_mulig": {}}
        for date in ["2026-06-21", "2026-10-30"]:
            # 10-minutters geometri; intervallet vurderes midt i foregående time.
            idx = pd.date_range(date, periods=24*6, freq="10min", tz="Europe/Oslo").tz_convert("UTC")
            w = pd.DataFrame(dict(air_temperature=10., relative_humidity=80., precipitation=0.,
                wind_speed=3., wind_direction=crag.face_azimuth_deg, cloud_cover=0.,
                ghi=100., dhi=0., dni=500.), index=idx)
            r = face_irradiance(w, crag)
            visible = (r.index - pd.Timedelta(minutes=30))[r.sun_possible].tz_convert("Europe/Oslo")
            entry["sol_mulig"][date] = [visible.min().strftime("%H:%M"), visible.max().strftime("%H:%M")] if len(visible) else None
        w = pd.DataFrame(dict(air_temperature=6., relative_humidity=90., precipitation=1.,
            wind_speed=4., wind_direction=crag.face_azimuth_deg, cloud_cover=1.),
            index=pd.date_range("2026-10-30", periods=72, freq="h", tz="UTC"))
        r = run_model(w, crag, params)
        assert r.mass_balance_error_mm.abs().max() < 1e-8
        assert r.energy_balance_error_j_m2.abs().max() < 1e-5
        entry["regn_pa_vegg_mm"] = round(float(r.rain_on_face_mm.sum()), 2)
        output["felt"][cfg.stem] = entry
    if a.live:
        from klatreforhold.data.metnordic_thredds import fetch_forecast
        from klatreforhold.data.nowcast import fetch_nowcast
        crag, _ = load_config(ROOT / "config/ekstraveggen.yaml")
        native = fetch_forecast(crag.lat, crag.lon)
        usable = native.dropna(subset=["precipitation", "longwave_down"])
        print("MET-kontroll:", {"timer": len(native), "brukbare_timer": len(usable),
            "langbolget_første": native.longwave_down.head(3).tolist(),
            "langbolget_spenn": [float(native.longwave_down.min()), float(native.longwave_down.max())]}, flush=True)
        assert len(usable) >= 47 and usable.longwave_down.between(100, 550).all()
        assert native.air_temperature.between(-40, 40).all()
        output["live"] = {"metnordic_timer": len(native), "fra": str(native.index.min()),
                          "til": str(native.index.max()), "langbolget_wm2": [float(native.longwave_down.min()), float(native.longwave_down.max())]}
        radar = fetch_nowcast(crag.lat, crag.lon)
        output["live"]["nowcast_oppdatert"] = radar.get("properties", {}).get("meta", {}).get("updated_at")
    if a.forecast:
        from klatreforhold.predict import predict
        forecast = predict("ekstraveggen", hours=120, history_hours=168)
        output["forecast"] = {"timer": len(forecast["timer"]), "historikk": len(forecast["siste_timer"]),
            "status": forecast["sammendrag"]["status_na"], "kilder": sorted({h["vaerkilde"] for h in forecast["timer"]}),
            "modellversjon": forecast["modellversjon"]}
    path = ROOT / "outputs/model_v2_check.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
