# Inbox: new course sources

Put a new source document here, such as a club's sailing instructions (PDF or text) or a list of marks with GPS coordinates. The agent turns it into a location under `courses/` by following the playbook below. When it's done, it moves the document to `inbox/processed/`.

Source documents aren't committed: this repo is public and sailing instructions are the clubs' own documents. `.gitignore` keeps everything in `inbox/` except this README out of git, so the documents stay on the machine that ingests them.

## Ingestion playbook

Work on a branch for the ingestion's issue, as usual (see `CLAUDE.md`). The course file format is in [`courses/README.md`](../courses/README.md); use `courses/rsys/course.json` as the worked example.

### 1. Read the source and choose an id

- Read the whole document. Note which pages hold the marks list, the course list and the start and finish areas.
- Pick the location id: the club's short name in lowercase letters, such as `gfs` or `cyca`. The id is also the folder name and the prefix for saved setup and best times, so it can't change once it's published.

### 2. Write `courses/<id>/course.json`

Take every value from the source. Where the source doesn't give one, make a sensible choice and record it in `source` (see "Recording uncertainty" below).

- **`club`, `shortName`, `area`, `series`**, plus **`title`**, **`blurb`** and **`credits`** for the start card. Follow the RSYS wording, and keep "Unofficial fan game" in `credits`.
- **`marks`:** use the codes the source uses. Copy coordinates exactly and convert them to decimal degrees: south and west are negative, and 33° 50.123′ S is -33.83538.
  - A mark with no published position is placed from its description (for example "off X Point", or a chart feature) with `"approx": true`.
- **`starts` and `finishes`:** use the centre of each line or area. Sailing instructions usually give these only as "in the vicinity of", so place them in open water and say so in `source`.
- **`divisions`:** copy each course's marks in order. Set each mark's `rounding` (`port` or `starboard`) from the sailing instructions' default rule and its per-mark exceptions. Mark the shortened-course mark with `"shortened": true`; there must be exactly one per course. If the source gives no shortening point, choose about halfway and record it. Set `nm` when the source gives a distance.
- **`winds`:** if the source picks courses by wind direction, copy that table. Otherwise list the wind directions that make sense for the area, with `course` pointing to the course each one gets, and record that the mapping is invented.
  - **`wind.default`** names one entry of `winds`. **`wind.strength`** is 14 unless the club states a typical breeze.
- **`altFinish`:** include it only if the source has an alternative finish signalled by a flag.
- **`boundary`:** a box around every mark, start and finish, with at least 500 m of margin.
  - Keep `north` - `south` close to RSYS's 0.085° (about 9.4 km), so the chart is about 2.6 m per unit. Boat speeds, mark gates and start lines are in world units, so a very different span changes the game's scale.
  - Make the box square in metres. Set `east = west + (north - south) × 110574 / (111320 × cos(mid-latitude))`. The world's width follows from it, and only square charts have been played so far.
- **`osmWater`:** the OSM multipolygon relations for enclosed water inside the box that isn't bounded by `natural=coastline`, such as harbours, rivers and lakes. Sydney's Port Jackson (15522136) is tagged `natural=water` + `water=harbour`.
  - Find candidates with this Overpass query (south, west, north, east), then keep the ones that cover the racing water:

        [out:json];rel["natural"="water"]["type"="multipolygon"](S,W,N,E);out tags;

  - Open sea and bays inside the coastline need no relation.
- **`labels`:** 8-15 place names that help the player find their way: headlands, suburbs and bays (`"kind": "water"` for water names).
- **`chart`:** `"chart.json"`.

### Recording uncertainty

Every value that isn't read directly from the source gets written down twice:

- in `course.json`, as `"approx": true` on marks, plus a sentence in `source`;
- in the `PROGRESS.md` entry, under **To review**.

Never invent a mark that the source doesn't name.

### 3. Build the chart

```
uv run --with shapely --with requests --with matplotlib tools/build_harbour.py courses/<id>/course.json --cache /tmp/<id>-osm --preview /tmp/<id>-chart.png
```

Look at the preview. The water should be where the racing is, with no missing harbour or river and no land across the course area. If water is missing, add its relation to `osmWater` and rebuild.

### 4. Validate

- `python3 tools/check_courses.py`: every mark, start and finish is in open water, every course uses known marks with one shortened mark, and charted lengths are near published ones. It checks RSYS only until #5 generalises it to any course file.
  - Move any mark that lands on the chart's land into the nearest open water, with `"approx": true` and a note.
- Add the location to `courses/index.json` (`id`, `name`, `area`). RSYS stays first, because it's the default.
- Serve the site (`python3 -m http.server`), pick the new club on the start card, and check that:
  - every division and wind shows a course sheet with no console errors or warnings;
  - a race can be started.
  A browser check for any location (#11) and a sailability check (#12) will automate this.
- Run `uv run --with playwright tools/race_test.py` to make sure RSYS is unaffected.

### 5. Log and file away

- Add a `PROGRESS.md` entry. Include the source document's title and date, what was extracted (counts of marks and courses), every uncertain value, and the validation results.
- Comment the same summary on the issue.
- Move the document to `inbox/processed/` (`mkdir -p inbox/processed` first).
