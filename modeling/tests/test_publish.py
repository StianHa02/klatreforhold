"""Tester timesjobbens arkivrader uten nett: bare ledetider opp til 48 t arkiveres."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.publish import ARKIV_MAKS_LEDETID, FRAM_TIMER, VAER_TIMER, archive_rows, weather_rows  # noqa: E402


def _varsel(timer: int) -> dict:
    na = pd.Timestamp("2026-10-29T21:00:00+01:00")
    timer_ = [{
        "tid": (na + pd.Timedelta(hours=i)).isoformat(), "status": "vatt", "vann_mm": 0.3, "p_vatt": None,
        "bergtemp": 8.0, "duggpunkt": 7.0, "nedbor_mm": 0.0, "regn_mot_veggen_mm": 0.0, "sol_pa_veggen": False,
    } for i in range(timer + 1)]
    return {"na": na.isoformat(), "generert": na.isoformat(), "timer": timer_}


def test_arkiv_kutter_lange_ledetider():
    rows = archive_rows("ekstraveggen", _varsel(FRAM_TIMER))
    ledetider = [r["ledetid_timer"] for r in rows]
    assert ledetider == list(range(ARKIV_MAKS_LEDETID + 1)), ledetider[-3:]
    assert rows[0]["generert"] == "2026-10-29T20:00:00+00:00" and rows[0]["tid"].endswith("+00:00")


def test_fram_rekker_ut_dag_4():
    # verste tilfelle: kjøring rett etter midnatt norsk tid må dekke ut dag +4 (5 døgn minus en time)
    assert FRAM_TIMER >= 5 * 24 - 1


def test_vaer_bare_passerte_timer_og_null_for_tomt():
    idx = pd.date_range("2026-10-26T00:00Z", "2026-10-30T12:00Z", freq="h")
    w = pd.DataFrame({"air_temperature": 10.0, "dni": float("nan"), "weather_kind": "analysis",
                      "weather_issued": ""}, index=idx)
    rows = weather_rows("ekstraveggen", w, "2026-10-30T10:07:00+01:00")  # 09:07 UTC
    assert len(rows) == VAER_TIMER
    assert rows[-1]["tid"] == "2026-10-30T09:00:00+00:00" and rows[-1]["generert"] == "2026-10-30T09:07:00+00:00"
    assert rows[0]["air_temperature"] == 10.0 and rows[0]["dni"] is None and rows[0]["weather_issued"] is None
    assert rows[0]["snow_water_mm"] is None  # kolonne som mangler i været blir null, ikke feil


if __name__ == "__main__":
    test_arkiv_kutter_lange_ledetider()
    test_fram_rekker_ut_dag_4()
    test_vaer_bare_passerte_timer_og_null_for_tomt()
    print("ok")
