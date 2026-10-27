from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


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


def _num(v):
    """YAML leser f.eks. 2.2e6 som tekst; gjør om tall til float, la bool/tekst være."""
    if isinstance(v, bool):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def load_config(path: str | Path) -> tuple[Crag, dict]:
    """Leser en felt-konfig (yaml) og returnerer (Crag, modellparametre)."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    c = cfg["crag"]
    crag = Crag(
        name=c["name"],
        lat=round(float(c["lat"]), 4),
        lon=round(float(c["lon"]), 4),
        face_azimuth_deg=float(c["face_azimuth_deg"]),
        face_tilt_deg=float(c.get("face_tilt_deg", 90)),
        elevation_m=float(c.get("elevation_m", 0)),
        timezone=c.get("timezone", "Europe/Oslo"),
        horizon=c.get("horizon", [[0, 0], [360, 0]]),
        felt_id=c.get("felt_id"),
        rain_sheltered=bool(c.get("rain_sheltered", False)),
        frost_station=c.get("frost_station"),
        frost_bruk=str(c.get("frost_bruk", "kontroll")),
    )
    params = {k: _num(v) for k, v in cfg.get("model", {}).items()}
    # Kalibrerte parametre (scripts/calibrate.py --write) overstyrer startverdiene
    kal = Path(path).parent / "kalibrert" / Path(path).name
    if kal.exists():
        with open(kal, encoding="utf-8") as f:
            params.update({k: _num(v) for k, v in (yaml.safe_load(f) or {}).get("model", {}).items()})
    return crag, params
