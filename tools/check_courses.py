"""Sanity-check the RSYS course file (courses/rsys/course.json) against its chart.

For every division and course: every mark is a known mark with a port or starboard rounding and one is the shortened-course mark,
every mark and start/finish position is in open water, and the straight-line course
length is compared with the distance printed on the course sheet.

Run from anywhere (standard library only):
    python3 tools/check_courses.py
"""
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOLERANCE = 0.20  # allowed difference; the sheet distances are approximate and not fully consistent with each other


def load(path):
    return json.loads(path.read_text())


def parse(marks):
    """[{'mark': 'DB', 'rounding': 'port'}, ...] -> [{'code': 'DB', 'port': True, 'short': False}, ...]"""
    out = []
    for m in marks:
        if m.get("rounding") not in ("port", "starboard"):
            raise ValueError(f"mark {m.get('mark')!r}: rounding must be port or starboard")
        out.append({"code": m["mark"], "port": m["rounding"] == "port", "short": bool(m.get("shortened"))})
    return out


def main():
    location = ROOT / "courses" / "rsys"
    rsys = load(location / "course.json")
    chart = load(location / rsys["chart"])
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
        return min(math.hypot(r[i] - x, r[i + 1] - y) for r in chart["land"] for i in range(0, len(r), 2)) * m_per_unit

    problems = 0
    print("Positions (distance to nearest shoreline point):")
    for kind in ("marks", "starts", "finishes"):
        for name, p in rsys[kind].items():
            x, y = xy(p)
            inside = 0 <= x <= chart["W"] and 0 <= y <= chart["H"]
            bad = not inside or on_land(x, y)
            problems += bad
            print(f"  {kind[:-1]:6} {name:16} x{x:6.0f} y{y:6.0f}  {shore_m(x, y):5.0f} m"
                  f"{'  approx' if p.get('approx') else ''}{'  ON LAND / OFF CHART' if bad else ''}")

    print("\nCourses (charted straight-line length vs course sheet):")
    for div, courses in rsys["divisions"].items():
        for num, c in enumerate(courses):
            try:
                marks = parse(c["marks"])
                pts = [rsys["starts"][c["start"]]] + [rsys["marks"][m["code"]] for m in marks] + [rsys["finishes"][c["finish"]]]
            except (ValueError, KeyError) as e:
                problems += 1
                print(f"  Div {div} course {num}: {e!r}")
                continue
            pts = [xy(p) for p in pts]
            nm = sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) * m_per_unit / 1852
            shorts = sum(m["short"] for m in marks)
            off = nm / c["nm"] - 1
            bad = abs(off) > TOLERANCE or shorts != 1
            problems += bad
            print(f"  Div {div} course {num}: {nm:5.1f} nm vs {c['nm']:5.1f} nm ({off:+.0%})"
                  f"{'' if shorts == 1 else f'  {shorts} shortened-course marks'}{'  CHECK' if bad else ''}"
                  f"  {' '.join(('*' if m['short'] else '') + m['code'] + ('(P)' if m['port'] else '') for m in marks)}")

    print(f"\n{problems} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
