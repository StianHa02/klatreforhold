"""Versjonering av fysikk, tilstand og lærte parametre."""
from dataclasses import asdict
import hashlib
import json

MODEL_VERSION = "2.0.0"


def config_hash(crag, params: dict) -> str:
    c = asdict(crag)
    c.pop("omraade", None)  # bare visning
    # Regnmåleren endrer bare modellen når den erstatter regnet. Ellers holdes den utenfor, så lagret
    # modelltilstand og kalibrering gjelder som før.
    if c.get("regnmaler_bruk") != "erstatt":
        c.pop("regnmaler", None)
        c.pop("regnmaler_bruk", None)
    payload = {"version": MODEL_VERSION, "crag": c, "params": params}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
