import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.physics.drying import drying_events, summarize_events


def episode(n=100):
    idx = pd.date_range("2026-07-01", periods=n, freq="h", tz="UTC")
    w = pd.DataFrame({"precipitation": 0.}, index=idx)
    w.iloc[6:12] = 1.
    r = pd.DataFrame({"wet": True, "status": "vatt"}, index=idx)
    return w, r


def test_immediate_dry_zero_and_long_events_not_completed():
    w, r = episode()
    r.iloc[11:] = [False, "tort"]
    d = drying_events(w, r)
    assert d.iloc[0].utfall == "tort" and d.iloc[0].timer == 0
    _, r = episode()
    d = drying_events(w, r)
    assert d.iloc[0].utfall == "fortsatt_vatt" and d.iloc[0].timer == 72
    assert summarize_events(d)["fullfort"] is None


def test_new_rain_is_competing_outcome_and_next_event_retained():
    w, r = episode()
    w.iloc[20:23] = 1.
    r.iloc[28:] = [False, "tort"]
    d = drying_events(w, r)
    assert d.utfall.tolist() == ["nytt_regn", "tort"]
    assert d.timer.tolist() == [9, 6]
    s = summarize_events(d)
    assert s["innen_timer"]["6"]["andel"] == .5


def test_incomplete_and_winter_explicit():
    w, r = episode(20)
    d = drying_events(w, r)
    assert d.iloc[0].utfall == "ufullstendig"
    assert summarize_events(d)["innen_timer"]["24"]["andel"] is None
    r.iloc[12] = [True, "is"]
    assert summarize_events(drying_events(w, r))["vinterpaavirket"] == 1
