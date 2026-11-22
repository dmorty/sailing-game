# Progress log

One entry per issue or task, newest first. Tasks are GitHub Issues; see the rules in [CLAUDE.md](CLAUDE.md).

<!--
## YYYY-MM-DD — #N Issue title

- **Branch:** `N-short-name`
- **What changed:**
- **To review:**
- **Next steps:**
- **Questions:** (if blocked or unsure; also comment them on the issue and label it needs-input)
-->

## 2026-11-22 — #12 Ingestion: check that every course is sailable

- **Branch:** `12-sailable-courses`
- **What changed:**
  - `tools/check_courses.py` now checks that every course is sailable. That covers every variant the game can build: full and shortened, with and without the alternative finish.
    - **Water map:** the chart's land is drawn onto a 5-unit grid by even-odd scanline fill. Sailable water is any water at least 15 units (39 m) from land, room for the 22-unit hull to turn and tack, and at least 40 units from the chart edge, as `js/boat.js` keeps the boat. Connected areas of sailable water are labelled.
    - **Legs:** a mark, start or finish joins every sailable area it reaches within 60 units (157 m) over open water. A leg is sailable when its two ends share an area.
    - **Roundings:** each mark needs at least 30 units (78 m) of water along its rounding gate. That's the game's own rule from `js/course.js`, with the gate direction copied as `gate_dir()`.
  - **Reporting:** problems are grouped into one line per blocked leg, one per mark and side (with the least water found), and one per point cut off from sailable water. Each line names the courses affected, adding "shortened" or "flag O" only when the problem appears just in that variant. For example: `PROBLEM mark MW: no room to leave it to starboard: as little as 26 m of water on the outside of the turn, needs 78 m (courses divisions.1[0], ...)`.
  - **Fixed:** an invalid `altFinish` no longer crashes the later checks.
  - **`check_courses_test.py`** has three new cases that add land to a copy of the chart:
    - a ring of land fencing off mark BB (blocked legs);
    - BB walled into a pond with no sailable water;
    - a rock on the outside of MW's turn (no room to round).
  - `CLAUDE.md` and the ingestion playbook describe the check.
- **Testing:**
  - RSYS: all 86 different legs and 127 different roundings are sailable, with 0 problems. The tightest rounding is TB, with 55 units of water against the 30 needed.
  - The land grid agrees with the exact polygon test at 3,000 random cell centres.
  - `check_courses_test.py`: all checks pass. The whole check takes about 0.6 s.
  - There are no game changes.
- **To review:**
  - **Connectivity, not a sailed route:** this checks that a water route exists, not that the boat can sail it to windward in the time a player would accept. A long beat up a narrow channel passes.
  - **Tuning:** the 15-unit clearance and 60-unit reach are judgement calls. A mark tucked into a narrow bay more than 157 m from 78 m-wide water would fail.
  - **#4's split is now complete** except #13, which waits on the Greenwich Flying Squadron source document.
- **Next steps:** #13, ingesting Greenwich Flying Squadron, once its source document is in `inbox/`. There are no other `ready` issues.

## 2026-11-22 — #11 Ingestion: browser check that any location loads and every course builds

- **Branch:** `11-location-load-check`
- **What changed:**
  - **New `tools/location_test.py [ID ...]`**, for every location in `courses/index.json` by default. For each location it opens the game and checks:
    - the game loads that location, with no console errors or warnings;
    - a race starts;
    - every division × wind × shortened × alternative-finish course builds, with no error and none of the game's warnings: a mark hard against the shore, a squeezed line, or no room for the start boat;
    - the boat's spawn is in water;
    - the start boat has a water route from the start to the finish.
    Each problem names the course key, such as `2-S: Unknown mark "ZZ"`.
  - **`--self-test`** serves broken copies of RSYS through Playwright routes: an unknown mark in one course, a mark on land, a missing chart file, and an id that isn't in the index. It checks each one fails with a clear message.
  - **`race_test.py`:** its RSYS-only water-route sweep moved into the new test.
  - **Fixed a harness bug from #1.** The "wait until the course is built" step in `browser_harness.py` didn't wait, because Playwright's `wait_for_function` treats a returned Promise as true straight away. I confirmed this with a Promise resolving to `false`. Tests only passed because of the 300 ms pause after it. The new `wait_for_course()` polls with `page.evaluate`, which does await, and both tests use it.
  - `CLAUDE.md` and the ingestion playbook list the new test.
- **Testing:**
  - `location_test.py`: RSYS passes, with all 120 courses built.
  - `--self-test`: all 4 broken cases are reported.
  - `race_test.py` passes, `compare_versions.py` shows 0 of 156 snapshots differ, and there are no game changes.
- **To review:**
  - The number of skipped wrong-side checks in `race_test.py` varies between 2 and 4 from run to run. The race committee's wind pick isn't seeded in that test, so the course it races changes. This was already the case. Seeding it would make runs repeatable.
- **Next steps:** #12, the sailability check: every leg has a water route and room to round each mark.

## 2026-11-22 — #5 Generalise check_courses.py to validate any course file

- **Branch:** `5-check-any-course`
- **What changed:**
  - **`tools/check_courses.py` checks any location.** With no arguments it checks `courses/index.json` and every location listed there; it also accepts course files as arguments.
  - It now checks:
    - **Index:** every listed location has a course file and a name, no id is listed twice, and every `courses/*/course.json` is listed. An unlisted one can't be picked in the game.
    - **Fields:** every field the game needs is present and sensible: club, title, card text, boundary, positions as GPS numbers, the wind default and strength, wind bearings, `altFinish`, labels and `osmWater`.
    - **Courses:** every start, finish and mark is known, every rounding is `port` or `starboard`, and each course has exactly one shortened-course mark.
    - **Winds:** every wind picks a course that exists in every division.
    - **Chart:** it has the projection and land, and was built from the course file's boundary. Otherwise the problem says to rebuild it.
    - **Positions:** as before, every mark, start and finish is on the chart and in open water.
    - **Lengths:** they're compared with published lengths only where a course has `nm`. A course with none is just reported.
  - **Reporting:**
    - Each problem names where it is, for example `PROBLEM divisions.1[0].marks[0]: unknown mark 'ZZ'`.
    - A course with bad references is left out of the length check but doesn't stop the other checks, so a mark on land is still reported alongside it.
    - Only structural breakage stops the chart checks: a bad boundary, positions or chart.
  - **New `tools/check_courses_test.py`** breaks a copy of the RSYS course file in 20 ways, one at a time, such as an unknown mark, a bad rounding, a mark on land, a stale chart or invalid JSON. It checks each is reported with the right location and message, along with three index problems and a combined case. The unbroken copy must pass.
  - `CLAUDE.md`, `courses/README.md` and the ingestion playbook (`inbox/README.md`) describe the new checks.
- **Testing:**
  - On RSYS: 0 problems, with the same positions and lengths as before.
  - `check_courses_test.py`: all 26 checks pass. I confirmed it fails when an expected message is wrong.
  - There are no game changes.
- **To review:** the length tolerance is still ±20% for every location. RSYS's published distances are rough, and another club's might call for a tighter limit.
- **Next steps:** #11, a browser check that any location loads and every course builds. Then #12, sailability, which builds on this checker.

## 2026-11-22 — #10 Ingestion: inbox and processed folders, and the playbook

- **Branch:** `10-inbox-playbook`
- **Split of #4:** #4 (the ingestion workflow) was too big for one run and depends on #5. It's split into:
  - #10: this task;
  - #11: a browser check that any location loads and every course builds;
  - #12: a sailability check, which depends on #5;
  - #13: ingesting Greenwich Flying Squadron. That one is labelled `needs-input`, because it needs the source document in `inbox/`.
  - #4 stays open to track them. Its `ready` label was removed so it isn't picked up again.
- **What changed:**
  - **New `inbox/README.md`:** what goes in the inbox, plus the step-by-step ingestion playbook:
    - choosing the id;
    - writing each `course.json` field from the source;
    - choosing the boundary and finding the `osmWater` relations, with an Overpass query;
    - building and previewing the chart;
    - validating;
    - registering the location in `courses/index.json`;
    - recording uncertain values in both `course.json` and `PROGRESS.md`;
    - moving the source to `inbox/processed/`.
  - **New `.gitignore`:** it ignores everything in `inbox/` except the README, so source documents (including `processed/`) stay out of this public repo. This follows the RSYS sailing instructions, which were kept out of the repo when it moved.
  - The ingestion section of `CLAUDE.md` points to the playbook.
- **Testing:**
  - A dummy PDF in `inbox/` and one in `inbox/processed/` were both ignored by git.
  - The playbook's square-boundary formula reproduces the RSYS `east` exactly (151.301641).
  - There are no game changes.
- **To review:**
  - **Scale:** the playbook says to keep each location's north-south span near RSYS's 9.4 km and the chart square. Boat speeds, gates and line lengths are in world units, and non-square charts haven't been played. A much larger or smaller club area would need the scale handled in code.
  - **Inbox not in git:** because the inbox is ignored, ingestion has to run on the machine where the document was dropped. A cloud agent or another checkout won't see it.
  - **Invented values:** where a source lacks a wind-to-course table or a shortening point, the playbook lets the agent invent one and flag it. You may prefer those to be questions instead.
- **Next steps:** #5, generalising `check_courses.py`, which #12 depends on. #11 can be done any time.

## 2026-11-22 — #3 Add a club/location picker to the start screen

- **Branch:** `3-location-picker`
- **What changed:**
  - **New `courses/index.json`** lists the locations (`id`, `name`, `area`). A static site can't list folders, so every new location must be added here. `courses/README.md` says so.
  - **Start card:** a full-width **Club** select at the top lists every location.
    - Picking one saves it (`localStorage` `location`) and reloads the page, which loads that location's course file and chart. A reload is the simplest correct switch, because the land mask, soundings, start-boat route grid and course marks are all built once at startup.
    - An unknown or missing pick falls back to the first location.
  - **Saved per location:** setup and best times are stored as `<id>Setup` and `<id>Best`. For RSYS these are still `rsysSetup` and `rsysBest`, so existing saved setups and best times carry over.
  - **RSYS-specific text moved into `course.json`:**
    - `title`: the card heading and the tab title;
    - `blurb` and `credits`: the card text and fine print;
    - `altFinish` `{ flag: "O", finish: "Kirribilli" }`, which replaces the hard-coded Kirribilli finish. The checkbox (now `#altfinish`) is labelled from it and hidden for locations without one. Course keys still end in `-O`, so best times are unchanged.
    - A saved setup's old `kirribilli` field is read as `altFinish`.
  - `index.html` holds neutral placeholders ("Harbour Race") until the course file loads.
- **Testing:**
  - `race_test.py` has a new location test. Playwright routes serve a second location, `test`: the RSYS chart and courses under another club name and title, with SW as the default wind and no alternative finish. The test checks that:
    - the picker lists both locations;
    - picking `test` loads its course file and chart, its title, and its default wind, and hides the flag O option;
    - a best time goes to `testBest` and leaves `rsysBest` alone;
    - the pick survives a reload;
    - switching back brings RSYS with its flag O finish, setup and best times.
  - All checks pass, with no console errors.
  - `compare_versions.py`: 0 of 156 snapshots differ from `master`. It now finds the flag O checkbox under either id.
  - `check_courses.py`: 0 problems.
  - Screenshots of the start card at desktop and phone sizes look right.
- **To review:**
  - With only RSYS listed, the picker has one option. It's shown anyway, so the feature is visible. It could be hidden until there's a second location.
  - The page `<title>` and heading show "Harbour Race" for a moment before the course file loads.
  - `check_courses.py` doesn't check `index.json` against the folders yet. That fits #5, generalising it to any course file.
- **Next steps:** #4, the ingestion workflow from an inbox folder.

## 2026-11-22 — #2 Make build_harbour.py take its map boundary from a course file

- **Branch:** `2-chart-from-course-file`
- **What changed:**
  - `tools/build_harbour.py` now takes a course file: `tools/build_harbour.py courses/rsys/course.json`. It writes the chart to the file named by the course's `chart` field, in the same folder.
  - The three Sydney-specific things it had hard-coded now come from the course file:
    - the map box (`LON0`, `LAT_TOP`, `LAT_BOT`), now read from `boundary`;
    - the place labels, now in a new `labels` field;
    - the Port Jackson OSM relation, now in a new `osmWater` list. The tool needs this because natural=coastline doesn't bound the harbour.
  - **Projection:** the world is still 3600 units from north to south. Its width now follows from the boundary's `east`, rather than always being square. For RSYS it's still 3600 × 3600.
  - **Cache:** the Overpass cache file for a relation is now `water_<id>.json`, replacing `port_jackson.json`.
  - `courses/README.md` documents the two new fields and the build command, and `CLAUDE.md` gives the build command.
- **Testing:**
  - I ran `master`'s tool and the new one on the same downloaded OSM data. They produced byte-identical charts.
  - The game is unchanged: `compare_versions.py` shows 0 of 156 snapshots differ, `race_test.py` passes, and `check_courses.py` reports 0 problems.
- **To review:**
  - **OSM has changed since the committed chart was built.** A fresh build today differs by about 5,200 m² of land (0.01%): about 4,600 m² near Vaucluse (x2594 y2664) and about 490 m² near Kirribilli (x715 y2500).
    - I kept the committed `chart.json`, so the game doesn't change here. Rebuild it as a separate change if you want the newer coastline.
  - The tool keeps its old name (`build_harbour.py`), although it now builds any location's chart.
- **Next steps:** #3, a club/location picker on the start screen.

## 2026-11-21 — #1 Convert the RSYS data into the per-location course file format

- **Branch:** `1-course-file-format`
- **What changed:**
  - **New `courses/rsys/course.json`** replaces `rsys-courses.js`. It holds the club and area names, the series, a source note, the map boundary in GPS degrees, the default wind (NE) and its strength (14 kn), and the marks, starts, finishes, wind-to-course table and division courses.
    - Each course's marks are now structured entries, `{ "mark": "KP", "rounding": "port", "shortened": true }`, instead of the sheet's text (`*KP(P)`). The in-game course sheet still shows the sheet notation.
  - **New `courses/rsys/chart.json`** replaces `harbour-data.js`. It holds the same data as plain JSON, with an attribution field.
  - **`courses/README.md`** describes the format.
  - **Game:** `js/chart.js` loads `course.json` and the chart it names with `fetch` and top-level `await`. The `window.RSYS` / `window.HARBOUR` globals and their `<script>` tags are gone.
    - `js/course.js` reads the structured marks (`courseMarks()` replaces `parseMarks()`).
    - `js/ui.js` takes the default wind and the HUD's wind strength from the file.
  - **Tools:**
    - `check_courses.py` reads the JSON files.
    - `build_harbour.py` writes `courses/rsys/chart.json`.
    - `browser_harness.py` waits for the first course to be built, because the game now loads its data asynchronously.
- **Testing:**
  - `compare_versions.py` against `master`: 156 snapshots compared, 0 differ, and both consoles are clean.
  - `race_test.py`: all checks pass. The 2 Point Piper wrong-side skips are as before.
  - `check_courses.py`: 0 problems, and its output is identical to `master`'s.
- **To review:**
  - The mark lines' typos from the sailing instructions (such as `*SM)`) are gone now that marks are structured. The order, sides and shortened marks are unchanged.
  - The location is fixed to `courses/rsys/` in `js/chart.js` until the picker (#3) exists.
  - If the course files fail to load, the game shows only the page with no chart. There's no error message on screen; the error goes to the console.
  - `build_harbour.py` wasn't re-run, because it needs network access. Its output format matches the converted file.
- **Next steps:** #2, making `build_harbour.py` take its map boundary from the course file.

## 2026-11-21 — Move the game into its own repo

- **Branch:** `move-to-own-repo`
- **What changed:**
  - The game moved from `sailing/` in `dmorty/dmorty.github.io` to its own public repo, `dmorty/sailing-game`, with its history kept.
    - The 17 commits that touched `sailing/` were replayed with `sailing/` as the root, using `git subtree split`. Authors, dates and messages are unchanged, but commit hashes are new.
    - It's served by GitHub Pages from the root of `master` at https://dmorty.github.io/sailing-game/. That's the same origin as before, so saved setup, best times and the sound setting carry over.
  - **Paths fixed for the repo root:**
    - The tools' docstrings and run commands drop `sailing/`.
    - `race_test.py` and `compare_versions.py` find the repo one level up.
    - `browser_harness.py` opens the site root.
    - `compare_versions.py` archives the whole tree of the ref.
    - The game itself needed no changes, because it only uses relative paths.
  - Added `.nojekyll`, so Pages serves the files as they are.
  - **Tasks moved to GitHub Issues:**
    - New labels `ready` and `needs-input`.
    - Issues #1-#5 were created from the remaining "Later to-do list" items, all labelled `ready`.
    - `CLAUDE.md` now says to pick the lowest-numbered `ready` issue, branch as `N-short-name`, comment on the issue, and label it `needs-input` when blocked.
- **To review:**
  - The old copy still lives in `sailing/` of the main site repo, and `https://dmorty.github.io/sailing/` still works. Remove it once the new site is confirmed working.
  - The RSYS sailing instructions PDF was untracked and wasn't moved into this public repo.
- **Next steps:** #1, converting the RSYS data into the per-location course file format.

## 2026-11-21 — Auto-trim on by default

- **Branch:** `start-boat-to-finish`. This is a user request outside the to-do list, made while that branch was unmerged.
- **What changed:** auto-trim now starts on: `game.auto` is `true`, and the HUD checkbox starts ticked. At load the checkbox takes its value from `game.auto`, so a browser restoring an old checkbox state can't leave the two disagreeing.
- **Testing:** `race_test.py` checks that auto-trim starts on. All checks pass.
- **To review:** the choice isn't remembered between visits. Every load starts with auto-trim on.

## 2026-11-21 — Start boat moves to the finish line

- **Branch:** `start-boat-to-finish`
- **What changed:**
  - **New `js/committee.js`:** it owns the start boat, which was previously drawn from fixed course data.
    - The boat waits at the start line until 30 seconds after the player crosses it (`WAIT` in `js/committee.js`, added at the user's request). The start line keeps both ends until the player has started.
    - It then motors at about 9 kn to the finish, with a wake. It slows for sharp turns and for the final approach, and stops to give way if the player's boat is close ahead.
    - It anchors in place of one finish pin and swings to lie head to wind.
  - **Route:** A* over a grid of open-water cells at least 30 units from land, built once and then reused. The path is straightened wherever a clear straight run has room for the hull.
  - **Finish position:** `buildCourse()` adds `course.finishBoat`, 22 units beyond end b of the finish line. If the hull doesn't fit in open water there, it tries end a, then moves closer to the line. The 19 finishes where end b is against the shore use one of the fallbacks.
  - **Drawing:**
    - The finish line shows both pins until the boat arrives; then the pin at the boat's end disappears.
    - The "Finish" label sits at the end that stays a pin.
    - On the minimap the boat's dot follows it and no longer fades after the start.
  - The boat stays solid wherever it is: collision moved from `boat.js` to `committee.js`.
- **Testing:**
  - `race_test.py` has three new checks:
    - the boat is still at the start 29 s after the player starts, and under way by 31 s;
    - in a live race it reaches the finish (7 s on that course) without its centre ever crossing land, and anchors at the right spot;
    - every one of the 120 course combinations (division × wind × flag S × flag O) has a water route, with no point along it on land.
  - All checks pass, with no console errors. Checked in screenshots under way and anchored at the finish.
- **To review:**
  - Speed is `SPEED = 110` (about 9 kn) in `js/committee.js`. On most courses it reaches the finish long before the player, so the player rarely sees it arrive.
  - The route check covers the boat's centre line and a hull-width margin on straightened legs, not every point of the hull on turns.
  - The 30 seconds count from when the player crosses the start line, not from the "Go!" signal.
- **Next steps:** the to-do list is complete. The later list starts with converting the RSYS data into the per-location course file format.

## 2026-11-21 — Link to the game from the site's home page

- **Branch:** `link-game-from-home`
- **What changed:** The site home page (`index.md`, outside `sailing/`) keeps its "Welcome to DMORTY" heading. The "Page coming soon......" placeholder is replaced with an "RSYS Harbour Race" section: a one-line description and a **Play the RSYS Harbour Race** link to `sailing/`.
- **Testing:**
  - The link is relative (`sailing/`), so it works from the site root, where this GitHub Pages user site is served.
  - The game answers at `/sailing/` on the local server.
  - Jekyll isn't installed locally, so the rendered home page wasn't previewed. Check it on the live site after merging.
- **To review:** the placeholder line was removed. Put it back if the home page is meant to say more is coming.
- **Note:** the user had added a new to-do item above this one ("Once the race has started make the start boat make its way to the finish line and replace one of the pins"). This task was done out of order, and that item went into this commit unticked.
- **Next steps:** the start boat moving to the finish line, the one remaining to-do item.

## 2026-11-21 — Add a start boat to one end of the start line

- **Branch:** `add-start-boat`
- **What changed:**
  - **Course:** `buildCourse()` now places a start boat (`course.startBoat`) 22 units beyond the starboard end of the start line. That is the right-hand end looking upwind, where the race committee boat usually sits. The other end stays an orange pin buoy, and the "Start" label moved to the pin end.
  - **Drawing (`js/render.js`):** the start boat is drawn as a motor cruiser lying head to wind. It swings with the wind shifts and flies a fluttering orange flag. It also shows as a dot on the minimap, which fades once the race has started.
  - **Physics (`js/boat.js`):** the start boat is solid, an ellipse a little larger than the drawn hull. Hitting it stops the boat like running aground, with a "Hit the start boat!" toast and the aground thud.
  - The new to-do item was added to `CLAUDE.md` by the user.
- **Testing:**
  - On all 60 start configurations (every division, wind and Kirribilli option), no point of the start boat's hull is on land, and every start line keeps its full length.
  - `race_test.py` has a new check: sailing along the start line into the start boat stops the boat outside its hull, with the toast. All checks pass, with no console errors.
  - Checked in a zoomed screenshot of the start area.
- **To review:**
  - The start boat isn't hit by its own wake and doesn't push the player's boat away. Hitting it is the same as touching the shore.
  - There's no penalty for touching it, as there would be under the racing rules.
  - On the default Division 1 NE course, the boat spawns on top of mark N3. This was already the case before this task.
- **Next steps:** link to the game from the site's home page (`index.md`).

## 2026-11-21 — Add simple sound effects

- **Branch:** `add-sound-effects`
- **What changed:**
  - New `js/sound.js` builds every sound in code with the Web Audio API, so there are no audio files and no new dependencies.
  - Sounds:
    - a start horn on "Go!"
    - a ping on crossing the start line
    - a bell for each mark rounded
    - a double buzz for a wrong-side rounding
    - a thud on running aground
    - a finish gun: a short horn, then a long one
  - Browsers block audio until the player interacts, so audio starts on the first key press or tap. The first race's start horn still plays.
  - Mute with the new "Sound effects" checkbox on the start card, or with M during a race. The setting is saved in `localStorage` (`rsysSound`), and the card's help list now shows the M key.
- **Testing:**
  - `race_test.py` now counts the audio sources the game creates. It checks that sounds play during races, that M mutes them and shows "Sound off", that a muted start-line crossing is silent, that the setting survives a reload, and that the checkbox turns sound back on.
  - All checks pass, with no console errors. The races covered every sound.
  - The start card was checked in screenshots at desktop and phone sizes.
- **To review:** listen to the sounds. The tests prove they play, not that they sound good. Volumes and pitches are in the `SOUNDS` table in `js/sound.js`.
- **Next steps:** link to the game from the site's home page (`index.md`).

## 2026-11-21 — Add leeway

- **Branch:** `add-leeway`
- **What changed:**
  - `js/boat.js`: the wind now pushes the boat sideways, away from the wind (`boat.drift`, eased in smoothly).
    - The push is strongest close-hauled, fades to nothing on a run, and fades out head to wind.
    - A stopped boat slips about three times as much as one at full speed.
    - It's tuned by one constant, `LEEWAY = 14`, the sideways speed of a stopped boat close-hauled in full wind.
  - Leeway applies only while racing, so the boat stays still behind the start line while the setup card is showing.
  - Running aground also kills the drift.
  - The start card tips now mention it.
- **Testing:**
  - `race_test.py` has two new checks. Close-hauled from a standstill, the boat slips 6 units to leeward in 1 second; on a run, it slips 0.
  - All the existing race checks still pass, and `check_courses.py` reports 0 problems.
  - Leeway measured at speed with auto-trim: about 10° at 45° to the wind (pinching, 4.6 kn), about 4° at 60° (7.8 kn) and under 1° at 135°.
- **To review:**
  - Is 10° when pinching too much? Real dinghies slip about 5-10° when pinched. Lower `LEEWAY` if it feels punishing.
  - `compare_versions.py` against `master` will now show differences in races. That's expected, because this task changes how the boat moves.
- **Next steps:** add simple sound effects.

## 2026-11-21 — Split index.html into ES modules

- **Branch:** `split-into-modules`
- **What changed:**
  - Moved the game's inline script into 12 ES modules under `js/`:
    - `game` (shared state)
    - `util`
    - `chart`
    - `course`
    - `boat`
    - `wind`
    - `camera`
    - `input`
    - `ui`
    - `render`
    - `minimap`
    - `main` (entry point, race logic and frame loop)
  - `index.html` keeps its markup and CSS, and loads `js/main.js` as a module after the two data scripts.
  - State that changes during play lives on the `game` object in `game.js`; camera and screen state lives on `view` in `camera.js`. Modules can't reassign each other's variables.
  - Updated the modules rule in `CLAUDE.md` and added a note that the game must be served over HTTP.
- **Testing:** a headless Chromium script played the `master` version and this branch side by side. It faked the clock, animation frames and `Math.random`, and sent the same keyboard and mouse input to both.
  - All 156 snapshots matched exactly: canvas pixels, minimap, HUD text and the course sheet for every division, wind and flag combination, plus about 60 seconds of steering, trimming, auto-trim, zooming, panning and recentering.
  - A second script raced Division 2 (SW) and Division 3 (race committee's wind) by placing the boat just before each line and rounding gate. Starts were detected, wrong-side roundings refused and correct ones counted. The finish card, saved best times, the setup after a reload and "Race again" all worked.
  - There were no console errors. The tuning constants are unchanged, and `check_courses.py` reports 0 problems.
- **To review:**
  - `finish()` lives in `ui.js` rather than `main.js` as planned, because it mostly updates the finish card and needs the setup state.
  - The scripts in `js/` are no longer readable by opening `index.html` from disk: use `python3 -m http.server`.
- **Later the same day:** kept both test scripts in `tools/`:
  - `race_test.py` races whole courses. A wrong-side check is skipped when that approach starts on the shore: 4 at Point Piper.
  - `compare_versions.py [REF]` plays the same session against a git ref and the working tree.
  - `browser_harness.py` holds the shared fake clock and browser setup.
- **Next steps:** add leeway, the next to-do item.

## 2026-11-21 — Set up the agent workflow

- **Branch:** none (`master`, before the workflow existed)
- **What changed:** Rewrote `CLAUDE.md` in Markdown with the vision, the rules, the to-do lists and the definition of done. Removed the tasks the game already does: the skeleton and game loop, the harbour chart, steering, wind, the speed polar and no-go zone, buoys rounded in order, the timer and finish screen, best times, shifting wind, the start screen and restart, touch controls, the wake and sail animation, and deployment. Created this log.
- **To review:**
  - `CLAUDE.md` asks for small modules, but the game is still one `index.html`.
  - `CLAUDE.md` still calls touch controls a later goal, but they're already built.
- **Next steps:** Start the to-do list with leeway.
