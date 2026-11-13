"""Natt til 13.11.2026: 503 fra Open-Meteo ga hull i varselet, og lagret tilstand med holds = -3e-24 ble avvist."""
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold import publish  # noqa: E402
from klatreforhold.physics.balance import STORES, _zero_if_tiny_negative, state_at  # noqa: E402


def test_avrundingsfeil_blir_null():
    assert _zero_if_tiny_negative(-3.308722450212111e-24) == 0.0
    assert _zero_if_tiny_negative(-1.7e-18) == 0.0
    assert _zero_if_tiny_negative(0.2) == 0.2
    assert _zero_if_tiny_negative(-0.01) == -0.01          # ekte feil skal fortsatt avvises
    assert math.isnan(_zero_if_tiny_negative(float("nan")))  # NaN skal ikke skjules som 0


def test_state_at_lagrer_ikke_negative_avrundingsfeil():
    t = pd.Timestamp("2026-11-12T23:00Z")
    row = {k + "_mm": 0.0 for k in STORES}
    row.update(holds_mm=-3.3e-24, seep_mm=0.28, rock_temp=-2.9, deep_temp=1.3)
    s = state_at(pd.DataFrame([row], index=[t]), t)
    assert s["holds"] == 0.0 and s["seep"] == 0.28 and s["Ts"] == -2.9


def test_nytt_forsok_for_felt_som_feilet(monkeypatch):
    kall = {"a": 0, "b": 0}

    def fake_publish_one(slug, *args):
        kall[slug] += 1
        if slug == "b" and kall["b"] == 1:
            return {"feil": "503 Server Error: Service Unavailable"}
        return {"timer": 48, "status_na": "tort"}

    monkeypatch.setattr(publish, "list_crags", lambda: [{"slug": "a"}, {"slug": "b"}])
    monkeypatch.setattr(publish, "_publish_one", fake_publish_one)
    monkeypatch.setattr(publish, "collect_bones", lambda *a: ({}, None))
    monkeypatch.setattr(publish, "load_crag", lambda s: (type("C", (), {"frost_station": None})(), {}))
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    res = publish.publish_all(storage=None)
    assert kall == {"a": 1, "b": 2}
    assert "feil" not in res["b"] and res["b"]["forste_feil"].startswith("503")
