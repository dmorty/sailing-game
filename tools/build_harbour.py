"""Build a location's chart (land shapes and projection) from OpenStreetMap data.

Reads the course file for the map boundary, the place labels and the OSM relations of its
enclosed water (harbours, bays and rivers that natural=coastline doesn't bound). Water = those
relations plus the open sea seaward of natural=coastline. Land = everything else in the box.
Everything is projected into the game's world (y down, origin top-left), H units tall, with the
width set by the boundary. The chart is written to the file named by the course's "chart" field.

Run from the repo root:
    uv run --with shapely --with requests tools/build_harbour.py courses/rsys/course.json
Options:
    --cache DIR       reuse/save the raw Overpass responses in DIR
    --preview FILE    also render a PNG preview (needs: --with matplotlib)

Map data © OpenStreetMap contributors, ODbL.
"""
import argparse
import json
import math
import pathlib
import time

import requests
from shapely.geometry import LineString, box
from shapely.ops import linemerge, polygonize, unary_union

OVERPASS = "https://overpass-api.de/api/interpreter"
H = 3600                          # world height in units; the width follows from the boundary
KY = 110574.0                     # metres per degree latitude


class Box:
    """The projection from a course file's boundary: square metres, H units from north to south."""

    def __init__(self, b):
        self.north, self.south, self.west, self.east = b["north"], b["south"], b["west"], b["east"]
        if not (self.north > self.south and self.east > self.west):
            raise SystemExit(f"bad boundary {b}: need north > south and east > west")
        self.kx = math.cos(math.radians((self.north + self.south) / 2)) * 111320.0  # metres per degree longitude
        self.m_per_unit = (self.north - self.south) * KY / H
        self.w = round((self.east - self.west) * self.kx / self.m_per_unit)


BOX = None  # set by main() from the course file


def proj(lon, lat):
    return ((lon - BOX.west) * BOX.kx / BOX.m_per_unit, (BOX.north - lat) * KY / BOX.m_per_unit)


def overpass(query, cache, name):
    path = cache / name if cache else None
    if path and path.exists():
        return json.loads(path.read_text())
    for attempt in range(4):  # the public server often answers 429/504 when busy
        r = requests.post(OVERPASS, data={"data": query}, timeout=180,
                          headers={"User-Agent": "harbour-buoy-race-build/1.0"})
        if r.status_code not in (429, 502, 503, 504):
            break
        time.sleep(10 * (attempt + 1))
    r.raise_for_status()
    if path:
        path.write_text(r.text)
    return r.json()


def way_line(geom):
    return LineString([proj(p["lon"], p["lat"]) for p in geom])


def rings_to_polys(lines):
    return list(polygonize(linemerge(lines)))


def relation_water(rel, cache):
    """An OSM multipolygon relation (such as a harbour) as a water polygon: its outer rings minus its inner ones."""
    d = overpass(f"[out:json][timeout:170];rel({rel});out geom;", cache, f"water_{rel}.json")
    if not d["elements"]:
        raise SystemExit(f"OSM relation {rel} not found")
    members = d["elements"][0]["members"]
    outer = [way_line(m["geometry"]) for m in members if m["type"] == "way" and m["role"] == "outer"]
    inner = [way_line(m["geometry"]) for m in members if m["type"] == "way" and m["role"] == "inner"]
    return unary_union(rings_to_polys(outer)).difference(unary_union(rings_to_polys(inner))).buffer(0)


def sea_water(cache, world):
    """Faces of the box cut by the coastline that lie on the sea side (coastline ways have land on their left)."""
    pad = 0.01
    q = (f'[out:json][timeout:170];way["natural"="coastline"]'
         f'({BOX.south - pad},{BOX.west - pad},{BOX.north + pad},{BOX.east + pad});out geom;')
    ways = [way_line(w["geometry"]) for w in overpass(q, cache, "coastline.json")["elements"]]
    segs = [(a, b) for w in ways for a, b in zip(w.coords, w.coords[1:])]
    noded = unary_union([w.intersection(world) for w in ways] + [world.exterior])
    sea = []
    for face in polygonize(noded):
        p = face.representative_point()
        a, b = min(segs, key=lambda s: LineString(s).distance(p))
        cross = (b[0] - a[0]) * (p.y - a[1]) - (b[1] - a[1]) * (p.x - a[0])
        if cross > 0:  # y is down, so "right of the way" (sea) is a positive cross product
            sea.append(face)
    return unary_union(sea)


def ring_coords(ring):
    pts = [(round(x), round(y)) for x, y in ring.coords[:-1]]
    return [v for xy in pts for v in xy]


def main():
    global BOX
    ap = argparse.ArgumentParser()
    ap.add_argument("course", type=pathlib.Path, help="the location's course.json")
    ap.add_argument("--cache", type=pathlib.Path)
    ap.add_argument("--preview", type=pathlib.Path)
    args = ap.parse_args()
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
    course = json.loads(args.course.read_text())
    BOX = Box(course["boundary"])

    world = box(0, 0, BOX.w, H)
    water = unary_union([relation_water(r, args.cache).buffer(0.5) for r in course.get("osmWater", [])]
                        + [sea_water(args.cache, world).buffer(0.5)])
    land = world.difference(water).simplify(1.5)
    polys = [g for g in getattr(land, "geoms", [land]) if g.area > 30]
    land = unary_union(polys)

    rings = []
    for g in polys:
        rings.append(ring_coords(g.exterior))
        rings += [ring_coords(h) for h in g.interiors]

    labels = [{"text": lab["text"], "x": round(proj(lab["lon"], lab["lat"])[0]),
               "y": round(proj(lab["lon"], lab["lat"])[1]), "kind": lab.get("kind", "land")}
              for lab in course.get("labels", [])]

    data = {
        "attribution": "Generated by tools/build_harbour.py. Map data © OpenStreetMap contributors, ODbL.",
        "W": BOX.w, "H": H, "mPerUnit": round(BOX.m_per_unit, 4),
        "lon0": BOX.west, "latTop": BOX.north,
        "lonPerUnit": BOX.m_per_unit / BOX.kx, "latPerUnit": BOX.m_per_unit / KY,
        "labels": labels, "land": rings,
    }
    out = args.course.parent / course["chart"]
    out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n")
    pts = sum(len(r) // 2 for r in rings)
    print(f"{out.name}: {out.stat().st_size / 1024:.0f} KB, {len(rings)} rings, {pts} points, "
          f"{land.area / world.area:.0%} land, {BOX.w}x{H} units, {BOX.m_per_unit:.2f} m/unit")

    if args.preview:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 10))
        for g in polys:
            ax.fill(*g.exterior.xy, color="#ece3c4", ec="#12323b", lw=0.6)
            for h in g.interiors:
                ax.fill(*h.xy, color="#c4dfe0")
        for lab in labels:
            ax.text(lab["x"], lab["y"], lab["text"], fontsize=7, color="#555",
                    style="italic" if lab["kind"] == "water" else "normal")
        ax.set_facecolor("#c4dfe0")
        ax.set_xlim(0, BOX.w); ax.set_ylim(H, 0); ax.set_aspect(1)
        fig.savefig(args.preview, dpi=90, bbox_inches="tight")


if __name__ == "__main__":
    main()
