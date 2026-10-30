"""Versjonering av fysikk, tilstand og lærte parametre."""
from dataclasses import asdict
import hashlib
import json

MODEL_VERSION = "2.0.0"


def config_hash(crag, params: dict) -> str:
    payload = {"version": MODEL_VERSION, "crag": asdict(crag), "params": params}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
