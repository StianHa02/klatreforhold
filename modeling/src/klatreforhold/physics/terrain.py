"""Horisont fra Kartverket, med asimut relativt sann nord og separat bakkehøyde."""
import numpy as np


def terrain_horizon(crag, dem, ground_elevation, eye_height=1.5, offset_m=3, step_deg=5,
                    min_dist=10, max_dist=3000):
    import rasterio
    from pyproj import Geod, Transformer
    geod = Geod(ellps="GRS80")
    lon, lat, _ = geod.fwd(crag.lon, crag.lat, crag.face_azimuth_deg, offset_m)
    with rasterio.open(dem) as ds:
        heights = ds.read(1, masked=True).astype(float).filled(np.nan)
        transform = Transformer.from_crs(4326, ds.crs, always_xy=True)
        inverse = ~ds.transform
        distances = np.arange(min_dist, max_dist, max(1, abs(ds.transform.a)))
        profile = []
        for bearing in np.arange(0, 360, step_deg):
            lons, lats, _ = geod.fwd(np.full(len(distances), lon), np.full(len(distances), lat),
                                    np.full(len(distances), bearing), distances)
            xs, ys = transform.transform(lons, lats)
            cols, rows = inverse * (xs, ys)
            rows, cols = np.floor(rows).astype(int), np.floor(cols).astype(int)
            valid = (rows >= 0) & (cols >= 0) & (rows < ds.height) & (cols < ds.width)
            if valid.mean() < .95:
                raise ValueError("Høydemodellen dekker ikke horisontens søkeradius")
            z = heights[rows[valid], cols[valid]]
            angle = np.rad2deg(np.arctan2(z - ground_elevation - eye_height, distances[valid]))
            if not np.isfinite(angle).any():
                raise ValueError("Horisonten mangler terrengdata")
            profile.append([float(bearing), round(float(max(0, np.nanmax(angle))), 2)])
    return profile + [[360.0, profile[0][1]]]
