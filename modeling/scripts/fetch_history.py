"""Henter historiske timesdata for feltet fra offentlige kilder og lagrer i data/raw/.

Eksempler:
  python scripts/fetch_history.py --start 2023-01-01 --end 2026-10-26
  python scripts/fetch_history.py --source metnordic --start 2025-06-01 --end 2025-06-07   # treg: 1 kall per time
  python scripts/fetch_history.py --source frost --station SN50540 --start 2026-06-01 --end 2026-10-26
"""
import argparse

from _common import DEFAULT_CONFIG, ROOT

from klatreforhold.config import load_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--source", choices=["openmeteo", "metnordic", "frost"], default="openmeteo")
    ap.add_argument("--station", default="SN50540", help="Frost-stasjon (kun --source frost)")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    a = ap.parse_args()
    crag, _ = load_config(a.config)
    out_dir = ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = crag.name.lower()
    if a.source == "openmeteo":
        from klatreforhold.data.openmeteo import fetch_history
        df = fetch_history(crag.lat, crag.lon, a.start, a.end)
        path = out_dir / f"{slug}_openmeteo_metno_{a.start}_{a.end}.csv"
    elif a.source == "metnordic":
        from klatreforhold.data.metnordic_thredds import fetch_history
        df = fetch_history(crag.lat, crag.lon, a.start, a.end)
        path = out_dir / f"{slug}_metnordic_thredds_{a.start}_{a.end}.csv"
    else:
        from klatreforhold.data.frost import fetch_observations
        df = fetch_observations(a.station, a.start, a.end)
        path = out_dir / f"frost_{a.station}_{a.start}_{a.end}.csv"
    df.to_csv(path)
    print(f"Lagret {len(df)} timer -> {path}")
    print(df.isna().mean().round(3).to_string())


if __name__ == "__main__":
    main()
