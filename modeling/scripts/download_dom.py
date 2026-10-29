"""Laster ned Kartverkets overflatemodell (DOM1, 1 m, med trær og bygg) rundt feltet.

Bruker Geonorges åpne ATOM-feed (ingen innlogging): finner 15 km-rutene som overlapper
området ±3 km rundt feltet, laster dem ned (opptil ~1.2 GB hver) og setter sammen et utsnitt i data/raw/.

  pip install rasterio pyproj
  python scripts/download_dom.py
  python scripts/horizon_from_dem.py --dem data/raw/dom1_ekstraveggen.tif

Lisens: CC BY 4.0, © Kartverket.
"""
import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from _common import DEFAULT_CONFIG, ROOT

from klatreforhold.config import load_config

FEED = "https://nedlasting.geonorge.no/geonorge/ATOM/hoydedata/datasett/{product}.atom"


def tiles(product: str):
    """Gir (navn, nedlastingslenke, liste av (lat, lon)) for hver rute i feeden."""
    xml = requests.get(FEED.format(product=product), timeout=120).content
    root = ET.fromstring(xml)
    for entry in root.iter():
        if not entry.tag.endswith("entry"):
            continue
        title = link = None
        coords = []
        for el in entry.iter():
            tag = el.tag.split("}")[-1].lower()
            if tag == "title" and el.text:
                title = el.text.strip()
            elif tag == "link" and el.get("href", "").lower().endswith(".tif"):
                link = el.get("href")
            elif tag in ("polygon", "box", "poslist") and el.text:
                nums = [float(x) for x in re.split(r"[\s,]+", el.text.strip()) if x]
                coords = list(zip(nums[0::2], nums[1::2]))  # GeoRSS: "lat lon lat lon ..."
        if link and coords:
            yield title, link, coords


def download(title: str, link: str, raw: Path) -> None:
    print(f"Laster ned {title}: {link}")
    with requests.get(link, stream=True, timeout=600) as r:
        r.raise_for_status()
        size = int(r.headers.get("content-length", 0))
        done = 0
        with open(raw, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if size:
                    print(f"\r  {done / 1e6:.0f} / {size / 1e6:.0f} MB", end="")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--product", default="DOM1", choices=["DOM1", "DTM1"])
    ap.add_argument("--radius-m", type=float, default=3000)
    ap.add_argument("--tile", nargs="+", help="bruk allerede nedlastede ruter i stedet for å laste ned")
    ap.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"),
                    help="mappe for store ruter og utsnitt (f.eks. hovedsjekkens data/raw fra en worktree)")
    a = ap.parse_args()
    crag, _ = load_config(a.config)
    raw_dir = Path(a.raw_dir)

    import rasterio
    from pyproj import Transformer
    from rasterio.merge import merge

    # Alle rutene er UTM 33 (EPSG:25833). Utsnittet kan gå over flere ruter, så vi tar alle som overlapper
    crs = "EPSG:25833"
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(crag.lon, crag.lat)
    box = (x - a.radius_m, y - a.radius_m, x + a.radius_m, y + a.radius_m)

    if a.tile:
        paths = [Path(t) for t in a.tile]
    else:
        to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        paths = []
        for title, link, coords in tiles(a.product):
            xs, ys = to_utm.transform([c[1] for c in coords], [c[0] for c in coords])
            if min(xs) > box[2] or max(xs) < box[0] or min(ys) > box[3] or max(ys) < box[1]:
                continue
            name = link.rsplit("/", 1)[-1]
            # Eldre nedlastinger ble lagret som f.eks. DOM1_Høydedata_DOM1_33-104-120.tif
            old = sorted(raw_dir.glob(f"{a.product}_*{name}"))
            raw = old[0] if old else raw_dir / f"{a.product}_{name}"
            if not raw.exists():
                download(title, link, raw)
            paths.append(raw)
        if not paths:
            raise SystemExit("Fant ingen rute som dekker feltet. Last ned manuelt fra https://hoydedata.no")

    # Utsnittet får navn etter config-fila (slug), ikke feltnavnet, så det blir ASCII
    out = raw_dir / f"{a.product.lower()}_{Path(a.config).stem}.tif"
    srcs = [rasterio.open(p) for p in paths]
    try:
        nodata = srcs[0].nodata if srcs[0].nodata is not None else -9999
        data, transform = merge(srcs, bounds=box, nodata=nodata)
        profile = srcs[0].profile.copy()
        profile.update(width=data.shape[2], height=data.shape[1], count=1, transform=transform,
                       nodata=nodata, compress="deflate", tiled=True, BIGTIFF="IF_SAFER")
    finally:
        for src in srcs:
            src.close()
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(data[0], 1)
    print(f"Lagret utsnitt fra {len(paths)} rute(r) -> {out}")
    print("(De store rutene kan slettes for å spare plass.)")


if __name__ == "__main__":
    main()
