# Course files

Each club or harbour area is a folder here holding two files. The game loads them at startup.

`index.json` lists the locations for the Club picker on the start card: `{ "locations": [{ "id", "name", "area" }] }`, where `id` is the folder name. A static site can't list folders, so **add every new location here**. The first entry is the default.

The player's pick is saved in `localStorage` (`location`), and switching reloads the page. Setup and best times are saved per location as `<id>Setup` and `<id>Best`.

## `course.json`

| Field | Meaning |
| --- | --- |
| `club`, `shortName`, `area`, `series` | Who runs the races, where, and which series the courses come from. |
| `source` | Where the data came from and how sure it is. |
| `title`, `blurb`, `credits` | The start card's heading (also the tab title), its intro paragraph and its fine print. |
| `altFinish` | Optional. An alternative finish the race committee can signal, such as `{ "flag": "O", "finish": "Kirribilli" }`; `finish` is a name from `finishes`. It shows as a checkbox on the start card, and the course's best-time key gets `-<flag>`. |
| `chart` | The chart file in this folder (land shapes, projection), from `tools/build_harbour.py`. |
| `boundary` | The chart's edges in GPS degrees: `north`, `south`, `west`, `east`. The chart is 3600 units from north to south, and its width follows from the boundary. |
| `osmWater` | OpenStreetMap relation ids of enclosed water that the OSM coastline doesn't bound, such as a harbour or bay (Port Jackson is 15522136). Used only by `tools/build_harbour.py`. |
| `labels` | Place names drawn on the chart: `{ text, lat, lon, kind }`, where `kind` is `land` or `water` (drawn in italics). Used only by `tools/build_harbour.py`, which projects them into `chart.json`. |
| `wind` | `default`: the wind name picked on a first visit (one of `winds`). `strength`: full-strength wind in knots, as shown on the HUD. |
| `marks` | Mark code → `{ name, lat, lon }`. `"approx": true` means the position has no published source and was placed from a description. |
| `starts`, `finishes` | Name → `{ lat, lon }`, the centre of each start or finish line. |
| `winds` | The wind choices: `name`, `bearing` (degrees the wind blows from) and `course` (index into each division's course list). |
| `divisions` | Division name → list of courses. Each course has a `start` and `finish` (names from above), `nm` (the published length) and `marks` in rounding order. |

Each entry in a course's `marks` is `{ "mark": "KP", "rounding": "port" }`: `rounding` is `port` or `starboard`, the side the mark is left on. Exactly one mark per course has `"shortened": true`, the mark the course finishes after when it's shortened (flag S).

Check a course file against its chart with `python3 tools/check_courses.py`.

## `chart.json`

Generated from the course file's `boundary`, `osmWater` and `labels` by:

    uv run --with shapely --with requests tools/build_harbour.py courses/<location>/course.json

It uses OpenStreetMap data (© OpenStreetMap contributors, ODbL). It holds the world size (`W`, `H`), the projection (`lon0`, `latTop`, `lonPerUnit`, `latPerUnit`, `mPerUnit`), place `labels`, and `land` as flat `[x0, y0, x1, y1, …]` rings in world units.
