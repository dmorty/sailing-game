# Sailing game

The RSYS Harbour Race, played at https://dmorty.github.io/sailing-game/ (GitHub Pages, served from the root of `master`).

## Vision

A simple, satisfying 2D sailing game playable in the browser. The player steers a small sailboat around a course of buoys in a harbour, racing the clock. Sailing should feel believable: the boat's speed depends on its angle to the wind, and it cannot sail directly into the wind (it must tack).

## Tech choices

- Plain HTML, CSS and JavaScript using the Canvas API. No build step and no frameworks unless clearly justified.
- Everything must run as static files so it deploys to GitHub Pages. `.nojekyll` makes Pages serve the files as they are.
- Keep code split into ES modules by concern (chart, course, boat, wind, camera, input, rendering, UI). Don't create tiny files: a module should own one clear job.
- Modules don't load from `file://`. Test through a local server: `python3 -m http.server` from the repo root, then open http://localhost:8000/.
- Browser tests use Playwright and run from the repo root:
  - `uv run --with playwright tools/race_test.py` races whole courses: start, rounding each mark (the wrong way is refused), finish, best times, reload.
  - `uv run --with playwright tools/location_test.py [ID ...]` loads every location (or those given) and builds every course: no console errors or warnings, the spawn is in water, and the start boat has a water route. `--self-test` checks that broken locations fail clearly.
  - `uv run --with playwright tools/compare_versions.py [REF]` plays the same session against a git ref (default `master`) and the working tree, and reports any difference. Use it for refactors that must not change behaviour.
- Course data lives in `courses/<location>/`: `course.json` (club, marks, courses, wind) and `chart.json` (land from OpenStreetMap). The format is described in `courses/README.md`. Rebuild a chart from its course file with `uv run --with shapely --with requests tools/build_harbour.py courses/<location>/course.json`.
- `python3 tools/check_courses.py` checks every location's course file against its chart (or the course files given as arguments), including that every course is sailable. `python3 tools/check_courses_test.py` checks that it catches broken course files.
- Works with keyboard on desktop; touch controls are a later goal.

## Tasks: GitHub Issues

Tasks are tracked as [GitHub Issues](https://github.com/dmorty/sailing-game/issues) (`gh issue list --label ready`):

- `ready`: ready for the agent to pick up.
- `needs-input`: blocked on a question for the owner.

## How to work (rules for the agent)

1. Each run, pick the lowest-numbered open issue labelled `ready`. Do only that one issue.
2. Work on a new git branch named `<issue number>-<short-name>`, such as `3-location-picker`. Never commit directly to master. Mention the issue in commit messages, with `Fixes #<number>` on the commit that completes it.
3. Keep changes small and focused. If an issue is too big, split it into smaller new issues labelled `ready`, link them from the original issue, and do the first one.
4. After finishing, make sure the game still loads in a browser with no console errors.
5. Comment a short summary on the issue: what changed, anything to review, and suggested next steps. Also add an entry to `PROGRESS.md`, the running work log: date, issue, what changed, anything to review, and next steps.
6. Do not add new dependencies, delete files outside the project, or change deployment settings without noting it clearly on the issue for review.
7. If blocked or unsure, comment the question on the issue, replace its `ready` label with `needs-input`, and stop.

## Later: multiple clubs, maps and courses

Courses are data, not code. Each sailing club or harbour area gets its own course file that the game loads, so new locations can be added without touching game logic.

- **Course file per location (JSON)** holding:
  - club or area name
  - map boundary as GPS coordinates
  - buoy marks with names and GPS positions
  - course order and rounding side (port or starboard)
  - default wind direction and strength
- **Coastlines and land shapes** come from OpenStreetMap data for the map boundary, converted into simple shapes the game can draw and use for collisions.
- **GPS to screen:** the game converts GPS coordinates to screen positions, so real-world mark positions just work.
- **Course picker:** the start screen lists every available course file.

### Club roadmap

1. Royal Sydney Yacht Squadron (existing functionality; convert to the course file format first)
2. Greenwich Flying Squadron
3. Cruising Yacht Club of Australia

### Ingestion workflow (agent task)

Follow the step-by-step playbook in [`inbox/README.md`](inbox/README.md). Source documents in `inbox/` aren't committed.

1. A new source document goes into an inbox folder, such as a club's sailing instructions or a list of marks with coordinates.
2. The agent extracts the marks, positions and course order, and writes a new course file.
3. The agent fetches the coastline for that area and saves it with the course.
4. The agent validates the course: every mark is on water, the course is sailable, and the game loads it with no errors.
5. The agent logs the new course in `PROGRESS.md`, noting anything uncertain for review, and moves the source document to a processed folder.

## Definition of done for each task

- The game runs from `index.html` with no errors.
- The change is visible or testable by playing.
- The issue has a summary comment, and `PROGRESS.md` is updated.
- The issue is closed by the merge (`Fixes #<number>`).
