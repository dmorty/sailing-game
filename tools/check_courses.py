"""Check course files (courses/<id>/course.json) against their charts.

With no arguments it checks courses/index.json and every location it lists; otherwise the course files given.

For each location:
- the file has every field the game needs, with sensible values (see courses/README.md);
- every course names a known start, finish and marks, rounds each mark to port or starboard, and has exactly one
  shortened-course mark; every wind picks a course that exists in every division;
- the chart exists and matches the course file's boundary;
- every mark, start and finish is on the chart and in open water;
- where a course has a published length (nm), the charted straight-line length is close to it.

Each problem names where it is, such as divisions.2[6].marks[3]. Exits 1 if there are any.

Run from anywhere (standard library only):
    python3 tools/check_courses.py [courses/<id>/course.json ...]
"""
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
COURSES = ROOT / "courses"
TOLERANCE = 0.20  # allowed difference from a published length; the RSYS sheet distances are approximate


class Report:
    def __init__(self):
        self.problems = 0

    def problem(self, where, msg):
        self.problems += 1
        print(f"  PROBLEM {where}: {msg}")


def load_json(path, rep, where):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        rep.problem(where, f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} not found")
    except json.JSONDecodeError as e:
        rep.problem(where, f"not valid JSON: {e}")
    return None


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_index(rep):
    """courses/index.json lists every location folder once, each with a course file. Returns the course files."""
    print("Index (courses/index.json):")
    index = load_json(COURSES / "index.json", rep, "index.json")
    if index is None:
        return []
    locs = index.get("locations")
    if not isinstance(locs, list) or not locs:
        rep.problem("index.json", '"locations" must be a non-empty list')
        return []
    files, seen = [], set()
    for i, loc in enumerate(locs):
        where = f"index.json locations[{i}]"
        lid = loc.get("id") if isinstance(loc, dict) else None
        if not isinstance(lid, str) or not lid:
            rep.problem(where, 'needs an "id"')
            continue
        if lid in seen:
            rep.problem(where, f'id "{lid}" is listed twice')
        seen.add(lid)
        if not loc.get("name"):
            rep.problem(where, f'"{lid}" needs a "name" for the Club picker')
        f = COURSES / lid / "course.json"
        if f.exists():
            files.append(f)
            print(f"  {lid:8} {loc.get('name', '')}")
        else:
            rep.problem(where, f"courses/{lid}/course.json not found")
    for f in sorted(COURSES.glob("*/course.json")):
        if f.parent.name not in seen:
            rep.problem("index.json", f'courses/{f.parent.name}/ has a course file but isn\'t listed, so the game can\'t pick it')
    return files


def check_fields(c, rep):
    """The course file's own structure. Returns False if it's too broken to check against the chart; a course with
    bad references is reported here and left out of the length check."""
    ok = True
    for k in ("club", "title", "chart"):
        if not isinstance(c.get(k), str) or not c.get(k):
            rep.problem(k, "missing (a non-empty string)"); ok = False
    for k in ("blurb", "credits"):
        if not isinstance(c.get(k), str):
            rep.problem(k, "missing (text for the start card)")

    b = c.get("boundary")
    if not isinstance(b, dict) or not all(is_num(b.get(k)) for k in ("north", "south", "west", "east")):
        rep.problem("boundary", "needs numbers north, south, west and east"); ok = False
    elif not (b["north"] > b["south"] and b["east"] > b["west"]):
        rep.problem("boundary", "needs north > south and east > west"); ok = False

    for kind in ("marks", "starts", "finishes"):
        group = c.get(kind)
        if not isinstance(group, dict) or not group:
            rep.problem(kind, "missing (an object of name → position)"); ok = False
            continue
        for name, p in group.items():
            if not isinstance(p, dict) or not (is_num(p.get("lat")) and is_num(p.get("lon"))):
                rep.problem(f"{kind}.{name}", "needs numbers lat and lon"); ok = False
            elif not (-90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180):
                rep.problem(f"{kind}.{name}", f"lat {p['lat']}, lon {p['lon']} is not a GPS position"); ok = False
            if kind == "marks" and isinstance(p, dict) and not p.get("name"):
                rep.problem(f"marks.{name}", 'needs a "name"')
    marks, starts, finishes = (c.get(k) if isinstance(c.get(k), dict) else {} for k in ("marks", "starts", "finishes"))

    divisions = c.get("divisions")
    if not isinstance(divisions, dict) or not divisions:
        rep.problem("divisions", "missing (an object of division → list of courses)")
        return False
    for div, courses in divisions.items():
        if not isinstance(courses, list) or not courses:
            rep.problem(f"divisions.{div}", "needs a non-empty list of courses")
            continue
        for n, crs in enumerate(courses):
            where = f"divisions.{div}[{n}]"
            if not isinstance(crs, dict):
                rep.problem(where, "must be an object")
                continue
            if crs.get("start") not in starts:
                rep.problem(f"{where}.start", f"unknown start {crs.get('start')!r}")
            if crs.get("finish") not in finishes:
                rep.problem(f"{where}.finish", f"unknown finish {crs.get('finish')!r}")
            if "nm" in crs and not (is_num(crs["nm"]) and crs["nm"] > 0):
                rep.problem(f"{where}.nm", "must be a positive number")
            ms = crs.get("marks")
            if not isinstance(ms, list) or not ms:
                rep.problem(f"{where}.marks", "needs a non-empty list of marks")
                continue
            for i, m in enumerate(ms):
                mw = f"{where}.marks[{i}]"
                if not isinstance(m, dict):
                    rep.problem(mw, 'must be an object like { "mark": "KP", "rounding": "port" }')
                    continue
                if m.get("mark") not in marks:
                    rep.problem(mw, f"unknown mark {m.get('mark')!r}")
                if m.get("rounding") not in ("port", "starboard"):
                    rep.problem(mw, f"rounding must be \"port\" or \"starboard\", not {m.get('rounding')!r}")
            shorts = sum(1 for m in ms if isinstance(m, dict) and m.get("shortened"))
            if shorts != 1:
                rep.problem(f"{where}.marks", f"needs exactly one shortened-course mark, has {shorts}")

    winds = c.get("winds")
    fewest = min((len(v) for v in divisions.values() if isinstance(v, list) and v), default=0)
    names = set()
    if not isinstance(winds, list) or not winds:
        rep.problem("winds", "needs a non-empty list")
    else:
        for i, w in enumerate(winds):
            where = f"winds[{i}]"
            if not isinstance(w, dict) or not isinstance(w.get("name"), str):
                rep.problem(where, 'needs a "name"')
                continue
            if w["name"] in names:
                rep.problem(where, f"wind {w['name']!r} is listed twice")
            names.add(w["name"])
            if not (is_num(w.get("bearing")) and 0 <= w["bearing"] < 360):
                rep.problem(f"{where}.bearing", "must be a number of degrees, 0 to 360")
            if not (isinstance(w.get("course"), int) and 0 <= w["course"] < fewest):
                rep.problem(f"{where}.course", f"{w.get('course')!r} isn't a course in every division (0 to {fewest - 1})")

    wind = c.get("wind")
    if not isinstance(wind, dict):
        rep.problem("wind", 'needs "default" and "strength"')
    else:
        if wind.get("default") not in names:
            rep.problem("wind.default", f"{wind.get('default')!r} isn't one of the winds")
        if not (is_num(wind.get("strength")) and wind["strength"] > 0):
            rep.problem("wind.strength", "must be a positive number of knots")

    alt = c.get("altFinish")
    if alt is not None and not (isinstance(alt, dict) and isinstance(alt.get("flag"), str) and alt.get("finish") in finishes):
        rep.problem("altFinish", 'must be { "flag": ..., "finish": <a name from finishes> }')

    for i, lab in enumerate(c.get("labels", [])):
        if not (isinstance(lab, dict) and lab.get("text") and is_num(lab.get("lat")) and is_num(lab.get("lon"))):
            rep.problem(f"labels[{i}]", "needs text, lat and lon")
        elif lab.get("kind", "land") not in ("land", "water"):
            rep.problem(f"labels[{i}].kind", 'must be "land" or "water"')
    if not (isinstance(c.get("osmWater", []), list) and all(isinstance(r, int) for r in c.get("osmWater", []))):
        rep.problem("osmWater", "must be a list of OSM relation ids")
    return ok


def course_ok(c, crs):
    """Every reference in the course resolves, so it can be measured."""
    ms = crs.get("marks") if isinstance(crs, dict) else None
    return (isinstance(ms, list) and bool(ms) and crs.get("start") in c["starts"] and crs.get("finish") in c["finishes"]
            and all(isinstance(m, dict) and m.get("mark") in c["marks"] and m.get("rounding") in ("port", "starboard") for m in ms))


def check_chart(c, chart, rep):
    """The chart has what the game draws with, and was built from this boundary. Returns False if it's unusable."""
    need = ("W", "H", "mPerUnit", "lon0", "latTop", "lonPerUnit", "latPerUnit", "land")
    missing = [k for k in need if k not in chart]
    if missing:
        rep.problem("chart", f"missing {', '.join(missing)}: rebuild it with tools/build_harbour.py")
        return False
    b = c["boundary"]
    east, south = chart["lon0"] + chart["W"] * chart["lonPerUnit"], chart["latTop"] - chart["H"] * chart["latPerUnit"]
    if any(abs(a - e) > 1e-4 for a, e in ((chart["lon0"], b["west"]), (chart["latTop"], b["north"]), (east, b["east"]), (south, b["south"]))):
        rep.problem("chart", f"covers N {chart['latTop']:.4f} S {south:.4f} W {chart['lon0']:.4f} E {east:.4f}, "
                             f"not the boundary: rebuild it with tools/build_harbour.py")
    return True


def check_positions(c, chart, rep):
    m_per_unit = chart["mPerUnit"]

    def xy(p):
        return ((p["lon"] - chart["lon0"]) / chart["lonPerUnit"], (chart["latTop"] - p["lat"]) / chart["latPerUnit"])

    def on_land(x, y):
        inside = False
        for r in chart["land"]:
            n = len(r) // 2
            for i in range(n):
                x1, y1, x2, y2 = r[2 * i], r[2 * i + 1], r[2 * ((i + 1) % n)], r[2 * ((i + 1) % n) + 1]
                if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
        return inside

    def shore_m(x, y):
        """Rough distance to the nearest shoreline vertex, in metres."""
        return min((math.hypot(r[i] - x, r[i + 1] - y) for r in chart["land"] for i in range(0, len(r), 2)), default=0) * m_per_unit

    print(" Positions (distance to nearest shoreline point):")
    for kind in ("marks", "starts", "finishes"):
        for name, p in c[kind].items():
            x, y = xy(p)
            where = "OFF CHART" if not (0 <= x <= chart["W"] and 0 <= y <= chart["H"]) else "ON LAND" if on_land(x, y) else ""
            print(f"  {kind[:-1] if kind != 'finishes' else 'finish':6} {name:16} x{x:6.0f} y{y:6.0f}  {shore_m(x, y):5.0f} m"
                  f"{'  approx' if p.get('approx') else ''}")
            if where:
                rep.problem(f"{kind}.{name}", f"is {where.lower()} (lat {p['lat']}, lon {p['lon']})")

    print(" Courses (charted straight-line length vs published):")
    for div, courses in c["divisions"].items():
        for n, crs in enumerate(courses if isinstance(courses, list) else []):
            if not course_ok(c, crs):
                print(f"  Div {div} course {n}: not measured (see the problems above)")
                continue
            pts = [c["starts"][crs["start"]]] + [c["marks"][m["mark"]] for m in crs["marks"]] + [c["finishes"][crs["finish"]]]
            pts = [xy(p) for p in pts]
            nm = sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) * m_per_unit / 1852
            line = " ".join(("*" if m.get("shortened") else "") + m["mark"] + ("(P)" if m["rounding"] == "port" else "")
                            for m in crs["marks"])
            if "nm" in crs:
                off = nm / crs["nm"] - 1
                print(f"  Div {div} course {n}: {nm:5.1f} nm vs {crs['nm']:5.1f} nm ({off:+.0%})  {line}")
                if abs(off) > TOLERANCE:
                    rep.problem(f"divisions.{div}[{n}]", f"charted {nm:.1f} nm is {off:+.0%} from the published "
                                                         f"{crs['nm']} nm (allowed ±{TOLERANCE:.0%}): check its marks and positions")
            else:
                print(f"  Div {div} course {n}: {nm:5.1f} nm (none published)  {line}")


def check_location(path, rep):
    name = path.parent.name
    print(f"\n{name} ({path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}):")
    c = load_json(path, rep, name)
    if c is None:
        return
    if not isinstance(c, dict):
        rep.problem(name, "must be a JSON object")
        return
    if not check_fields(c, rep):
        print("  (positions and lengths not checked until the problems above are fixed)")
        return
    chart = load_json(path.parent / c["chart"], rep, "chart")
    if chart is None or not check_chart(c, chart, rep):
        return
    check_positions(c, chart, rep)


def main(argv):
    rep = Report()
    files = [pathlib.Path(a).resolve() for a in argv] if argv else check_index(rep)
    for f in files:
        check_location(f, rep)
    print(f"\n{rep.problems} problem(s)")
    return 1 if rep.problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
