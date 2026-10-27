"""Laster ned Kartverkets overflatemodell (DOM1, 1 m, med trær og bygg) rundt feltet.

Bruker Geonorges åpne ATOM-feed (ingen innlogging): finner 15 km-ruta som dekker feltet,
laster den ned (kan være flere hundre MB), og klipper ut et område på ±3 km til data/raw/.

  pip install rasterio pyproj
  python scripts/download_dom.py
  python scripts/horizon_from_dem.py --dem data/raw/dom1_ekstraveggen.tif

Lisens: CC BY 4.0, © Kartverket.
"""
import argparse
import re
import xml.etree.ElementTree as ET

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


def covers(coords, lat, lon) -> bool:
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    return min(lats) <= lat <= max(lats) and min(lons) <= lon <= max(lons)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--product", default="DOM1", choices=["DOM1", "DTM1"])
    ap.add_argument("--radius-m", type=float, default=3000)
    a = ap.parse_args()
    crag, _ = load_config(a.config)

    hits = [(t, l) for t, l, c in tiles(a.product) if covers(c, crag.lat, crag.lon)]
    if not hits:
        raise SystemExit("Fant ingen rute som dekker feltet. Last ned manuelt fra https://hoydedata.no")
    title, link = hits[0]
    raw = ROOT / "data" / "raw" / f"{a.product}_{title}.tif".replace(" ", "_")
    if not raw.exists():
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

    import rasterio
    from pyproj import Transformer
    from rasterio.windows import from_bounds

    out = ROOT / "data" / "raw" / f"{a.product.lower()}_{crag.name.lower()}.tif"
    with rasterio.open(raw) as src:
        x, y = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(crag.lon, crag.lat)
        win = from_bounds(x - a.radius_m, y - a.radius_m, x + a.radius_m, y + a.radius_m, src.transform)
        data = src.read(1, window=win, boundless=True, fill_value=src.nodata or -9999)
        profile = src.profile.copy()
        profile.update(width=data.shape[1], height=data.shape[0],
                       transform=src.window_transform(win), compress="deflate")
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(data, 1)
    print(f"Lagret utsnitt -> {out}")
    print(f"(Den store ruta {raw.name} kan slettes for å spare plass.)")


if __name__ == "__main__":
    main()
