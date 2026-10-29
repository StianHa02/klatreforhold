"""Prediksjon for ett felt: status nå og for hver time de neste 24 timene.

Fysikkmodellen kjøres på ~7 døgn historikk + varsel, slik at vannlagrene (tak/sprekker, siging)
er "varmet opp" når vi kommer til nå. Hvis det finnes en trent ML-modell i models/, legges
sannsynligheten for vått ved (p_vatt).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ROOT, Crag, load_config
from .physics.wetness import hours_until_dry, run_model

CONFIG_DIR = ROOT / "config"
MODEL_DIR = Path(os.environ.get("KLATREFORHOLD_MODEL_DIR", ROOT / "models"))
STATUS_TEKST = {"tort": "Tørt", "fuktig": "Fuktig", "vatt": "Vått", "is": "Is"}


def list_crags() -> list[dict]:
    out = []
    for p in sorted(CONFIG_DIR.glob("*.yaml")):
        crag, _ = load_config(p)
        out.append({"slug": p.stem, "navn": crag.name, "felt_id": crag.felt_id, "lat": crag.lat, "lon": crag.lon,
                    "orientering": crag.face_azimuth_deg})
    return out


def load_crag(slug: str) -> tuple[Crag, dict]:
    path = CONFIG_DIR / f"{slug}.yaml"
    if not path.exists():
        raise KeyError(slug)
    return load_config(path)


def get_weather(crag: Crag, source: str = "openmeteo") -> pd.DataFrame:
    """Henter siste 14 døgn + 2 døgn varsel (7 døgn vises, 7 til oppvarming av vannlagrene). Kan overstyres med KLATREFORHOLD_OFFLINE_WEATHER (CSV) for testing."""
    offline = os.environ.get("KLATREFORHOLD_OFFLINE_WEATHER")
    if offline:
        df = pd.read_csv(offline, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True)
        return df.asfreq("h")
    if source == "metno":
        from .data.metno import fetch_locationforecast
        return fetch_locationforecast(crag.lat, crag.lon)
    from .data.openmeteo import fetch_forecast
    w = fetch_forecast(crag.lat, crag.lon, past_days=14, forecast_days=3)
    if crag.frost_bruk == "erstatt":
        return with_observations(w, crag)
    return w  # "kontroll": stasjonen sammenlignes i timesjobben (verify.py), modellen bruker værdata for feltet


def with_observations(w: pd.DataFrame, crag: Crag) -> pd.DataFrame:
    """Bytter ut historikken i w med målinger fra feltets Frost-stasjon der de finnes.

    Varseltimene (etter siste måling) og stråling/skydekke beholdes fra modellen. Uten
    FROST_CLIENT_ID, stasjon eller nett brukes w som den er, så varselet virker alltid.
    """
    w.attrs["frost_station"] = None
    if not crag.frost_station or not os.environ.get("FROST_CLIENT_ID"):
        return w
    from .data.frost import fetch_recent
    try:
        obs = fetch_recent(crag.frost_station, hours=len(w.loc[:pd.Timestamp.now(tz="UTC")]) + 1)
    except Exception as err:  # Frost nede skal ikke ta ned varselet
        print(f"Frost feilet, bruker modellhistorikk: {err}")
        return w
    if obs.empty:
        return w
    w = w.copy()
    obs = obs.reindex(w.index)
    for col in obs.columns.intersection(w.columns):
        w[col] = obs[col].where(obs[col].notna(), w[col])
    if "relative_humidity" in obs:  # målt fuktighet korrigeres ikke i run_model
        w["rh_malt"] = obs["relative_humidity"].notna()
    if "dew_point_2m" in w:  # ikke la et modell-duggpunkt henge igjen ved siden av målt temp/fuktighet
        w = w.drop(columns="dew_point_2m")
    w.attrs["frost_station"] = crag.frost_station
    w.attrs["frost_last_obs"] = obs.dropna(how="all").index.max()
    return w


def _reasons(row: pd.Series, res: pd.DataFrame, t) -> list[str]:
    """Korte forklaringer på norsk for hvorfor modellen sier det den sier."""
    r = []
    last24 = res.loc[t - pd.Timedelta(hours=23):t]
    rain_wall = last24["rain_on_face_mm"].sum()
    if row["status"] == "tort":
        if rain_wall > 0.1:
            r.append(f"Tørket opp etter {rain_wall:.1f} mm regn mot veggen siste døgn")
        if row["sun_on_face"]:
            r.append("Sol på veggen")
        if row["rock_minus_dewpoint"] > 3:
            r.append("God margin til duggpunktet")
        elif row["rock_minus_dewpoint"] < 1.5:
            r.append("Nær duggpunktet, kan bli fuktig")
        return r
    if row["status"] == "is":
        r.append("Berget er under 0 °C")
    if row["rain_on_face_mm"] > 0.02:
        r.append(f"Regn mot veggen nå ({row['rain_on_face_mm']:.1f} mm/t)")
    elif rain_wall > 0.1:
        r.append(f"{rain_wall:.1f} mm regn mot veggen siste døgn")
    if row["condensation_mm"] > 0.001:
        r.append("Kondens: berget er kaldere enn duggpunktet")
    if row["seep_flux_mm"] > 0:
        r.append("Siging etter mye regn de siste dagene")
    if row["holds_mm"] > 0.05 and row["rain_on_face_mm"] <= 0.02:
        r.append("Vann igjen i tak og sprekker")
    return r


def _ml_probability(slug: str, crag: Crag, weather: pd.DataFrame, physics: pd.DataFrame) -> pd.Series | None:
    """Sannsynlighet for vått fra trent modell, hvis den finnes (torch foretrekkes, så sklearn)."""
    torch_path = MODEL_DIR / f"{slug}_torch.pt"
    sk_path = MODEL_DIR / f"{slug}_sklearn.joblib"
    if not torch_path.exists() and not sk_path.exists():
        return None
    from .ml.features import build_features
    X = build_features(weather.interpolate(limit=3), physics, crag.timezone)
    if torch_path.exists():
        try:
            from .ml.torch_model import GRUWetModel
            return GRUWetModel.load(torch_path).predict_proba(X)
        except ImportError:
            pass  # torch er ikke installert (f.eks. på Vercel): bruk sklearn-modellen
        except Exception as err:
            print(f"Torch-modell feilet: {err}")
    if sk_path.exists():
        try:
            import joblib
            bundle = joblib.load(sk_path)
            p = bundle["model"].predict_proba(X[bundle["cols"]].astype(float))[:, 1]
            return pd.Series(p, index=X.index)
        except Exception as err:  # en ødelagt modellfil skal ikke ta ned varselet
            print(f"sklearn-modell feilet: {err}")
    return None


def _format_hours(frame: pd.DataFrame, res: pd.DataFrame, w: pd.DataFrame, p_ml, crag: Crag) -> list[dict]:
    timer = []
    for t, row in frame.iterrows():
        timer.append({
            "tid": t.tz_convert(crag.timezone).isoformat(),
            "status": row["status"],
            "status_tekst": STATUS_TEKST[row["status"]],
            "tort": bool(row["status"] == "tort"),
            "p_vatt": None if p_ml is None or pd.isna(p_ml.get(t, np.nan)) else round(float(p_ml[t]), 3),
            "vann_mm": round(float(row["water_mm"]), 3),
            "bergtemp": round(float(row["rock_temp"]), 1),
            "duggpunkt": round(float(row["dew_point"]), 1),
            "lufttemp": round(float(w.loc[t, "air_temperature"]), 1),
            "luftfuktighet": round(float(w.loc[t, "relative_humidity"]), 0),
            "nedbor_mm": round(float(w.loc[t, "precipitation"]), 2),
            "regn_mot_veggen_mm": round(float(row["rain_on_face_mm"]), 2),
            "vind_ms": round(float(w.loc[t, "wind_speed"]), 1),
            "vindretning": round(float(w.loc[t, "wind_direction"]), 0),
            "sol_pa_veggen": bool(row["sun_on_face"]),
            "sol_wm2": round(float(row["sw_face"])),  # all kortbølget stråling på flaten
            "timer_til_tort": None if pd.isna(row["hours_until_dry"]) else int(row["hours_until_dry"]),
            "grunner": _reasons(row, res, t),
        })

    return timer


def _kilde(source: str, w: pd.DataFrame) -> str:
    if source != "openmeteo":
        return "MET Norway Locationforecast"
    if w.attrs.get("frost_station"):
        return f"Målinger fra MET ({w.attrs['frost_station']}) + MET Nordic-varsel via Open-Meteo"
    return "MET Norway (MET Nordic) via Open-Meteo"


def predict(slug: str, now: pd.Timestamp | None = None, hours: int = 24, source: str = "openmeteo",
            weather: pd.DataFrame | None = None, history_hours: int = 12) -> dict:
    crag, params = load_crag(slug)
    w = weather if weather is not None else get_weather(crag, source)
    w = w.sort_index()
    res = run_model(w, crag, params)
    res["hours_until_dry"] = hours_until_dry(res)
    p_ml = _ml_probability(slug, crag, w, res)

    now = (now or pd.Timestamp.now(tz="UTC")).tz_convert("UTC").ceil("h")  # tidsstempel = slutten av timen
    now = min(max(now, res.index[0]), res.index[-1])
    window = res.loc[now: now + pd.Timedelta(hours=hours)]

    timer = _format_hours(window, res, w, p_ml, crag)
    siste = _format_hours(res.loc[now - pd.Timedelta(hours=history_hours): now - pd.Timedelta(hours=1)], res, w, p_ml, crag)

    first = timer[0] if timer else None
    dry_idx = [i for i, h in enumerate(timer) if h["tort"]]
    wet_idx = [i for i, h in enumerate(timer) if not h["tort"]]
    sammendrag = {
        "status_na": first["status"] if first else None,
        "status_na_tekst": first["status_tekst"] if first else None,
        "tort_na": first["tort"] if first else None,
        "tort_om_24t": timer[-1]["tort"] if timer else None,
        "tørre_timer_neste_24": len(dry_idx),
        "neste_torre_time": timer[dry_idx[0]]["tid"] if dry_idx else None,
        "neste_vate_time": timer[wet_idx[0]]["tid"] if wet_idx else None,
        "grunner_na": first["grunner"] if first else [],
    }
    return {
        "felt": {"slug": slug, "navn": crag.name, "felt_id": crag.felt_id, "lat": crag.lat, "lon": crag.lon,
                 "orientering": crag.face_azimuth_deg},
        "generert": pd.Timestamp.now(tz=crag.timezone).isoformat(),
        "na": now.tz_convert(crag.timezone).isoformat(),
        "kilde": _kilde(source, w),
        "ml_modell": p_ml is not None,
        "sammendrag": sammendrag,
        "timer": timer,
        "siste_timer": siste,
        "forbehold": "Fysisk modell med ukalibrerte parametre. Si fra om varselet stemmer, så blir den bedre.",
    }
