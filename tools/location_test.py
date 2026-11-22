"""Load each location in the game and build every one of its courses.

For each location (every one in courses/index.json, or the ids given):
- the game loads it, with its course file and chart, with no console errors or warnings, and a race starts;
- every division x wind x shortened x alternative-finish course builds without an error or warning (the game warns
  about marks hard against the shore, squeezed lines, and no room for the start boat), the boat's spawn is in
  open water, and the start boat has a water route from the start to the finish.

--self-test serves deliberately broken copies of RSYS through the browser and checks each one fails clearly.

Run from the repo root:
    uv run --with playwright tools/location_test.py [ID ...]
    uv run --with playwright tools/location_test.py --self-test
"""
import argparse
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

from browser_harness import FAKE_CLOCK, launch, serve, stepper, wait_for_course

REPO = pathlib.Path(__file__).resolve().parents[1]

# Build every course of the loaded location; returns what went wrong, per course key
SWEEP = """async () => {
  const { RS, buildCourse } = await import('./js/course.js'); const { findPath } = await import('./js/committee.js');
  const { isLand } = await import('./js/chart.js');
  const problems = []; let n = 0;
  const warn = console.warn, warned = [];
  console.warn = (...a) => warned.push(a.join(' '));
  try {
    for (const division of Object.keys(RS.divisions)) for (const w of RS.winds)
      for (const shortened of [false, true]) for (const altFinish of RS.altFinish ? [false, true] : [false]) {
        const key = `${division}-${w.name}${shortened ? '-S' : ''}${altFinish ? '-' + RS.altFinish.flag : ''}`;
        let c; n++; warned.length = 0;
        try { c = buildCourse({ division, wind: w.name, shortened, altFinish }); }
        catch (e) { problems.push(`${key}: ${e.message}`); continue; }
        for (const m of warned) problems.push(`${key}: ${m}`);
        if (isLand(c.spawn.x, c.spawn.y)) problems.push(`${key}: the boat starts on land`);
        const path = findPath(c.startBoat, c.finishBoat);
        let land = !path;
        for (let i = 1; path && i < path.length; i++) {
          const p = path[i - 1], q = path[i], k = Math.ceil(Math.hypot(q.x - p.x, q.y - p.y) / 5);
          for (let j = 0; j <= k; j++) if (isLand(p.x + (q.x - p.x) * j / k, p.y + (q.y - p.y) * j / k)) land = true;
        }
        if (land) problems.push(`${key}: no water route for the start boat from the start to the finish`);
      }
  } finally { console.warn = warn; }
  return { n, problems };
}"""


def check_location(browser, base, lid, routes=()):
    """Load location lid and build all its courses. Returns (number of courses built, list of problems)."""
    page = browser.new_page(viewport={"width": 1000, "height": 700})
    page.route("**/fonts.g*/**", lambda r: r.abort())
    for pattern, handler in routes:
        page.route(pattern, handler)
    page.add_init_script(FAKE_CLOCK)
    page.add_init_script(f"localStorage.setItem('location', {json.dumps(json.dumps(lid))})")
    log = []
    page.on("console", lambda m: m.type in ("error", "warning") and "net::ERR_FAILED" not in m.text and log.append(f"console {m.type}: {m.text}"))
    page.on("pageerror", lambda e: log.append(f"page error: {e}"))
    try:
        page.goto(f"{base}/")
        if not wait_for_course(page, timeout=10):
            return 0, ["the game didn't load"] + log
        page.wait_for_timeout(300)
        loaded = page.evaluate("import('./js/chart.js').then(m => m.LOC_ID)")
        if loaded != lid:
            return 0, [f"the game loaded {loaded!r} instead: is {lid!r} in courses/index.json?"] + log
        step = stepper(page)
        page.click("#start"); step(30)
        if page.evaluate("import('./js/game.js').then(({ game }) => game.state)") != "racing":
            log.append("the race didn't start")
        sweep = page.evaluate(SWEEP)
        return sweep["n"], log + sweep["problems"]
    finally:
        page.close()


def report(lid, n, problems):
    print(f"{'ok  ' if not problems else 'FAIL'} {lid}: {n} courses built" + (f", {len(problems)} problem(s):" if problems else ""))
    for p in problems[:30]:
        print(f"       {p}")
    if len(problems) > 30:
        print(f"       ... and {len(problems) - 30} more")


def self_test(browser, base):
    """Serve broken copies of RSYS as location "broken" and check each fails with the expected message."""
    rsys = json.loads((REPO / "courses/rsys/course.json").read_text())
    index = json.loads((REPO / "courses/index.json").read_text())

    def broken(edit):
        c = json.loads(json.dumps(rsys))
        edit(c)

        def index_route(route):
            route.fulfill(json={"locations": index["locations"] + [{"id": "broken", "name": "Broken"}]})

        def files(route):
            name = route.request.url.rsplit("/", 1)[-1]
            if name == "course.json":
                route.fulfill(json=c)
            elif (REPO / "courses/rsys" / name).exists():
                route.fulfill(path=str(REPO / "courses/rsys" / name))
            else:
                route.fulfill(status=404, body="not found")
        return [("**/courses/index.json", index_route), ("**/courses/broken/*", files)]

    def unknown_mark(c):
        c["divisions"]["2"][4]["marks"][1]["mark"] = "ZZ"

    def mark_on_land(c):
        c["marks"]["SM"].update({"lat": -33.8290, "lon": 151.2440})  # Mosman

    def missing_chart(c):
        c["chart"] = "nope.json"

    cases = [
        ("a course with an unknown mark", "broken", broken(unknown_mark), '2-S: Unknown mark "ZZ"'),
        ("a mark on land", "broken", broken(mark_on_land), "Mark SM is charted on land"),
        ("a missing chart file", "broken", broken(missing_chart), "the game didn't load"),
        ("an id not in the index", "nowhere", [], "the game loaded 'rsys' instead"),
    ]
    fails = 0
    for desc, lid, routes, expect in cases:
        n, problems = check_location(browser, base, lid, routes)
        ok = any(expect in p for p in problems)
        print(f"{'ok  ' if ok else 'FAIL'} {desc} is reported: \"{expect}\"")
        if not ok:
            fails += 1
            report(lid, n, problems)
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="location ids (default: every location in courses/index.json)")
    ap.add_argument("--self-test", action="store_true", help="check that broken locations fail clearly")
    args = ap.parse_args()
    ids = args.ids or [loc["id"] for loc in json.loads((REPO / "courses/index.json").read_text())["locations"]]
    with sync_playwright() as p:
        browser = launch(p)
        base = serve(REPO)
        if args.self_test:
            fails = self_test(browser, base)
        else:
            fails = 0
            for lid in ids:
                n, problems = check_location(browser, base, lid)
                report(lid, n, problems)
                fails += bool(problems)
        browser.close()
    print("ALL PASSED" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
