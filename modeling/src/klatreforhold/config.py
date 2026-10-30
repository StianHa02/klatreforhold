from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from .version import MODEL_VERSION, config_hash

ROOT = Path(__file__).resolve().parents[2]
STEEPNESS_TILT = {1: 70.0, 2: 90.0, 3: 100.0, 4: 110.0}


def _load_dotenv(path: Path | None = None) -> None:
    """Leser KEY=verdi fra .env i prosjektroten inn i miljøet (overstyrer ikke det som allerede er satt)."""
    paths = [path] if path else [ROOT / ".env", ROOT.parent / ".env"]  # modeling/.env, så repo-roten
    for p in paths:
        if p.exists():
            _read_env(p)


def _read_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass
class Crag:
    name: str
    lat: float
    lon: float
    face_azimuth_deg: float
    face_tilt_deg: float = 90.0
    elevation_m: float = 0.0
    timezone: str = "Europe/Oslo"
    horizon: list = field(default_factory=lambda: [[0, 0], [360, 0]])
    felt_id: int | None = None
    rain_sheltered: bool = False
    frost_station: str | None = None  # målestasjon i Frost som feltet sammenlignes med
    # "kontroll": stasjonen brukes bare til å sjekke varselet (standard). "erstatt": målingene erstatter
    # historikken modellen kjører på. Bruk "erstatt" bare hvis stasjonen står nær feltet (1-2 km).
    frost_bruk: str = "kontroll"
    geology: str = "ukjent"
    geometry_source: str = ""
    geometry_checked: str = ""
    steepness_id: int | None = None


def _num(v):
    """YAML leser f.eks. 2.2e6 som tekst; gjør om tall til float, la bool/tekst være."""
    if isinstance(v, bool):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def rh_correction_for_station(station: str | None, config_dir: Path) -> dict:
    f = config_dir / "stasjoner" / "rh_korreksjon.yaml"
    if not station or not f.exists():
        return {}
    with open(f, encoding="utf-8") as fh:
        st = (yaml.safe_load(fh) or {}).get(station) or {}
    if st.get("maned"):
        out = {"rh_korreksjon_maned": [float(v) for v in st["maned"]]}
        if st.get("doegn_cos") and st.get("doegn_sin"):
            out["rh_korreksjon_doegn_cos"] = [float(v) for v in st["doegn_cos"]]
            out["rh_korreksjon_doegn_sin"] = [float(v) for v in st["doegn_sin"]]
        return out
    if st.get("konstant") is not None:
        return {"rh_korreksjon": float(st["konstant"])}
    return {}


def load_config(path: str | Path, apply_calibration: bool = True) -> tuple[Crag, dict]:
    """Leser en felt-konfig (yaml) og returnerer (Crag, modellparametre)."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    c = cfg["crag"]
    crag = Crag(
        name=c["name"],
        lat=float(c["lat"]),
        lon=float(c["lon"]),
        face_azimuth_deg=float(c["face_azimuth_deg"]),
        face_tilt_deg=float(c.get("face_tilt_deg", STEEPNESS_TILT.get(c.get("steepness_id"), 90))),
        elevation_m=float(c.get("elevation_m", 0)),
        timezone=c.get("timezone", "Europe/Oslo"),
        horizon=c.get("horizon", [[0, 0], [360, 0]]),
        felt_id=c.get("felt_id"),
        rain_sheltered=bool(c.get("rain_sheltered", False)),
        frost_station=c.get("frost_station"),
        frost_bruk=str(c.get("frost_bruk", "kontroll")),
        geology=c.get("geology", "ukjent"),
        geometry_source=c.get("geometry_source", ""),
        geometry_checked=str(c.get("geometry_checked", "")),
        steepness_id=c.get("steepness_id"),
    )
    if not 0 <= crag.face_tilt_deg <= 180 or not 0 <= crag.face_azimuth_deg < 360:
        raise ValueError("Helning må være 0–180°, asimut 0–359.999° fra sann nord")
    params = {k: _num(v) for k, v in cfg.get("model", {}).items()}
    # Fuktighetskorreksjon for værvarselet, målt mot feltets Frost-stasjon over flere år
    # (scripts/verify_forecast.py --historikk --skriv-rh). Står den i feltets egen konfig, vinner den.
    if "rh_korreksjon" not in params and "rh_korreksjon_maned" not in params:
        params.update(rh_correction_for_station(crag.frost_station, Path(path).parent))
    params.setdefault("rh_correction_source", "openmeteo")
    # Kalibrerte parametre (scripts/calibrate.py --write) overstyrer startverdiene
    kal = Path(path).parent / "kalibrert" / Path(path).name
    if apply_calibration and kal.exists():
        with open(kal, encoding="utf-8") as f:
            fitted = yaml.safe_load(f) or {}
        if (fitted.get("model_version") == MODEL_VERSION and fitted.get("validated") is True
                and fitted.get("base_config_hash") == config_hash(crag, params)):
            params.update({k: _num(v) for k, v in fitted.get("model", {}).items()})
    return crag, params
