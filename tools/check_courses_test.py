"""Test tools/check_courses.py on deliberately broken copies of the RSYS course file.

Each case breaks one thing in a copy (in a temporary folder, next to a copy of the chart) and checks that the
checker fails with a message naming the problem and where it is. The unbroken copy must pass.

Run from anywhere (standard library only):
    python3 tools/check_courses_test.py
"""
import contextlib
import copy
import io
import json
import pathlib
import shutil
import sys
import tempfile

import check_courses

RSYS = check_courses.COURSES / "rsys"
ON_LAND = {"lat": -33.8290, "lon": 151.2440}   # Mosman
OFF_CHART = {"lat": -33.70, "lon": 151.2440}   # north of the chart


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = check_courses.main(argv)
    return code, out.getvalue()


def set_in(c, path, value):
    """set_in(c, ['divisions', '1', 0, 'marks', 0, 'mark'], 'ZZ'); value None deletes the key."""
    *parents, last = path
    for k in parents:
        c = c[k]
    if value is None:
        del c[last]
    else:
        c[last] = value


# (description, list of (path, value) edits, text the report must contain)
CASES = [
    ("unknown mark", [(["divisions", "1", 0, "marks", 0, "mark"], "ZZ")], "divisions.1[0].marks[0]: unknown mark 'ZZ'"),
    ("bad rounding", [(["divisions", "2", 3, "marks", 1, "rounding"], "left")], 'divisions.2[3].marks[1]: rounding must be "port" or "starboard"'),
    ("two shortened marks", [(["divisions", "3", 0, "marks", 0, "shortened"], True)], "divisions.3[0].marks: needs exactly one shortened-course mark, has 2"),
    ("no shortened mark", [(["divisions", "1", 0, "marks", 2, "shortened"], None)], "divisions.1[0].marks: needs exactly one shortened-course mark, has 0"),
    ("unknown start", [(["divisions", "1", 1, "start"], "Nowhere")], "divisions.1[1].start: unknown start 'Nowhere'"),
    ("unknown finish", [(["divisions", "1", 1, "finish"], "Nowhere")], "divisions.1[1].finish: unknown finish 'Nowhere'"),
    ("empty course", [(["divisions", "2", 0, "marks"], [])], "divisions.2[0].marks: needs a non-empty list of marks"),
    ("mark on land", [(["marks", "MW"], {"name": "Manly West", **ON_LAND})], "marks.MW: is on land"),
    ("start off the chart", [(["starts", "Kirribilli"], OFF_CHART)], "starts.Kirribilli: is off chart"),
    ("mark without a position", [(["marks", "CP", "lat"], None)], "marks.CP: needs numbers lat and lon"),
    ("length far from published", [(["divisions", "1", 0, "nm"], 5)], "divisions.1[0]: charted 16.0 nm is +220% from the published 5 nm"),
    ("wind picks a missing course", [(["winds", 0, "course"], 8)], "winds[0].course: 8 isn't a course in every division (0 to 7)"),
    ("unknown default wind", [(["wind", "default"], "XYZ")], "wind.default: 'XYZ' isn't one of the winds"),
    ("bad wind bearing", [(["winds", 2, "bearing"], 400)], "winds[2].bearing: must be a number of degrees"),
    ("alternative finish not a finish", [(["altFinish", "finish"], "Nowhere")], "altFinish: must be"),
    ("boundary not the chart's", [(["boundary", "north"], -33.70)], "chart: covers N -33.7900"),
    ("upside-down boundary", [(["boundary", "south"], -33.0)], "boundary: needs north > south"),
    ("missing chart file", [(["chart"], "nope.json")], "chart: courses/"),
    ("missing title", [(["title"], None)], "title: missing"),
]


def main():
    rsys = json.loads((RSYS / "course.json").read_text())
    fails = 0

    def check(cond, msg, report=""):
        nonlocal fails
        print(("ok   " if cond else "FAIL ") + msg)
        if not cond:
            fails += 1
            print("     report was:\n" + "\n".join("       " + line for line in report.splitlines() if "PROBLEM" in line or not line.startswith("  ")))

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        check_courses.ROOT = root  # report paths relative to the temporary folder
        loc = root / "courses" / "test"
        loc.mkdir(parents=True)
        shutil.copy(RSYS / "chart.json", loc / "chart.json")
        f = loc / "course.json"

        f.write_text(json.dumps(rsys))
        code, out = run([str(f)])
        check(code == 0 and "0 problem(s)" in out, "an unbroken copy of RSYS passes", out)

        for desc, edits, expect in CASES:
            c = copy.deepcopy(rsys)
            for path, value in edits:
                set_in(c, path, value)
            f.write_text(json.dumps(c))
            code, out = run([str(f)])
            check(code == 1 and f"PROBLEM {expect}" in out, f"{desc}: reported as \"{expect}\"", out)

        # one broken course doesn't hide other problems: positions and the other courses are still checked
        c = copy.deepcopy(rsys)
        c["divisions"]["1"][0]["marks"][0]["mark"] = "ZZ"
        c["marks"]["SM"].update(ON_LAND)
        f.write_text(json.dumps(c))
        code, out = run([str(f)])
        check(code == 1 and "unknown mark 'ZZ'" in out and "PROBLEM marks.SM: is on land" in out
              and "Div 1 course 0: not measured" in out and "Div 1 course 1:" in out,
              "a course with an unknown mark doesn't stop the position and length checks", out)

        # sailability: change the chart copy around a mark (the course file itself stays valid)
        chart = json.loads((RSYS / "chart.json").read_text())

        def xy(code):
            p = rsys["marks"][code]
            return ((p["lon"] - chart["lon0"]) / chart["lonPerUnit"], (chart["latTop"] - p["lat"]) / chart["latPerUnit"])

        def square(cx, cy, half):
            return [cx - half, cy - half, cx + half, cy - half, cx + half, cy + half, cx - half, cy + half]

        bx, by = xy("BB")
        # MW on division 1 course 0 (start Clarke Island → MW → ME), left to starboard: a rock just outside the turn
        start = rsys["starts"]["Clarke Island"]
        start = ((start["lon"] - chart["lon0"]) / chart["lonPerUnit"], (chart["latTop"] - start["lat"]) / chart["latPerUnit"])
        g = check_courses.gate_dir(start, xy("MW"), xy("ME"), False)
        rock = square(xy("MW")[0] + g[0] * 20, xy("MW")[1] + g[1] * 20, 6)
        chart_cases = [
            ("a mark fenced off by land", [square(bx, by, 50), square(bx, by, 30)], "→ BB: has no water route wide enough to sail"),
            ("a mark cut off from sailable water", [square(bx, by, 50), square(bx, by, 8)], "PROBLEM BB: has no sailable water within"),
            ("no room to round a mark", [rock], "PROBLEM mark MW: no room to leave it to starboard"),
        ]
        f.write_text(json.dumps(rsys))
        for desc, rings, expect in chart_cases:
            (loc / "chart.json").write_text(json.dumps({**chart, "land": chart["land"] + rings}))
            code, out = run([str(f)])
            check(code == 1 and expect in out and "is on land" not in out, f"{desc}: reported as \"{expect}\"", out)
        shutil.copy(RSYS / "chart.json", loc / "chart.json")

        f.write_text('{"club": "Broken",')
        code, out = run([str(f)])
        check(code == 1 and "not valid JSON" in out, "invalid JSON is reported", out)

        # the index: every listed location has a course file, and every course file is listed
        check_courses.COURSES = root / "courses"
        f.write_text(json.dumps(rsys))
        (root / "courses" / "index.json").write_text(json.dumps({"locations": [{"id": "test", "name": "Test"}]}))
        code, out = run([])
        check(code == 0 and "0 problem(s)" in out, "a location listed in the index passes", out)
        (root / "courses" / "index.json").write_text(json.dumps({"locations": [
            {"id": "test", "name": "Test"}, {"id": "test", "name": "Again"}, {"id": "gone", "name": "Gone"}]}))
        (root / "courses" / "extra").mkdir()
        (root / "courses" / "extra" / "course.json").write_text(json.dumps(rsys))
        code, out = run([])
        check(code == 1 and 'id "test" is listed twice' in out, "index: a location listed twice is reported", out)
        check("courses/gone/course.json not found" in out, "index: a listed location with no course file is reported", out)
        check("courses/extra/ has a course file but isn't listed" in out, "index: an unlisted course file is reported", out)

    print(f"{'ALL PASSED' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
