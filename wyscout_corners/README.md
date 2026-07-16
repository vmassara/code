# Wyscout corner-kick analysis

Compares every team in a competition/season on:

- how many corners they take
- what share of those corners produce a chance (a shot)
- the xG generated from corner-originated possessions
- where the delivery typically lands (near post / central / far post / short)

## Two ways to run it

**Option A — no install, just a browser:** open `live_dashboard.html` directly
(double-click it, or drag it into a browser tab). Type in your Wyscout
username/password and a competition, click "Run analysis". It calls the
Wyscout API directly from your browser (the API's OpenAPI spec declares CORS
support on every endpoint) — nothing is installed, nothing is stored, your
credentials never leave your machine except in the HTTPS request to
apirest.wyscout.com. Good default for a one-off look; slower to re-run
repeatedly since it re-fetches everything each time the page loads.

**Option B — Python CLI:** better if you want the CSV/JSON output, want to
automate/schedule runs, or want to re-render without re-fetching. See below.

## Setup (Option B only)

```bash
cd wyscout_corners
pip install -r requirements.txt
export WYSCOUT_USER="you@example.com"
export WYSCOUT_PASS="..."
```

## Run

```bash
python3 cli.py --competition "NPL Victoria" --season 2026 --out-dir out/
```

- `--competition` accepts a name (resolved via `/search?objType=competition`) or
  a numeric `wyId`. If the name matches more than one competition, the tool
  lists the candidates so you can re-run with the specific id.
- `--season` accepts a season name/year or numeric `wyId`; omit it to use the
  competition's current active season.
- `--max-matches N` caps how many matches are processed — useful for a fast
  smoke test before running a full season.
- `--workers N` (default 6) controls how many match-events requests run
  concurrently. Requests are globally rate-limited to Wyscout's documented
  12 req/s per API key regardless of worker count.

Outputs land in `--out-dir`:
- `corner_analysis.json` — full per-team stats
- `corner_analysis.csv` — flat table for a spreadsheet
- `corner_dashboard.html` — a self-contained dashboard (open directly in a
  browser, works offline, no build step)

## How the numbers are computed

Everything comes from one endpoint per match: `/matches/{id}/events`. No other
per-match calls are needed:

- **Corners taken**: count of events with `type.primary == "corner"`,
  attributed to `event.team`.
- **Chance / xG from corners**: each event carries a `possession` object.
  When a possession originates from a corner, `possession.types` includes
  `"corner"`, and `possession.attack` holds that possession's outcome
  (`withShot`, `withShotOnGoal`, `withGoal`, `xg`). Possessions are deduped by
  `possession.id` so a multi-event corner sequence is only counted once. A
  "chance" = a corner possession with `withShot == true`.
- **Delivery / first-contact zone**: for each corner event, `pass.endLocation`
  is where Wyscout recorded the ball ending up — i.e. the delivery's landing
  point, our proxy for first contact. It's classified into one of four zones
  relative to goal center, using the corner-taking side (left/right, from
  `event.location.y`) to tell near post from far post:
  - `Short / edge of box` — lands more than 18 (of 100) pitch-units short of
    the byline
  - `Near post` / `Far post` — inside that range, more than 7 units from
    the goal's horizontal center, on the same/opposite side as the corner flag
  - `Central` — inside that range, within 7 units of center

  These thresholds are a heuristic (constants at the top of
  `corner_analysis.py`) — retune `SHORT_CORNER_DX_THRESHOLD` /
  `CENTRAL_ZONE_HALF_WIDTH` if you want tighter/looser buckets.

Only matches with `status == "Played"` are included.

## Files

- `live_dashboard.html` — the no-install option: a self-contained page that
  calls the Wyscout API straight from the browser and renders the same
  dashboard as Option B. Has its own JS port of the resolution/analysis logic
  below (kept in lockstep with `corner_analysis.py` — same test fixture
  validates both, see Testing below).
- `wyscout_client.py` — Basic Auth HTTP client with the documented 12 req/s
  rate limit and retry/backoff on 429/5xx.
- `corner_analysis.py` — the corner/possession extraction and per-team
  aggregation logic (no network calls; pure functions over event payloads).
- `report.py` — renders `corner_dashboard.html` from computed team stats.
- `cli.py` — wires it together: resolve competition/season → list matches →
  fetch events concurrently → analyze → write CSV/JSON/HTML.
- `test_fixture.py` — a synthetic events payload (no network) that exercises
  the full Python pipeline and asserts the arithmetic; run with `python3
  test_fixture.py` any time you change the extraction/aggregation logic. The
  same fixture values were run through `live_dashboard.html`'s JS in a
  headless browser to confirm both give identical output.

## Notes

- This session's network egress policy blocked `apirest.wyscout.com`, so
  neither path has been exercised against a live competition — both are
  validated against a synthetic fixture and the schema in the provided
  OpenAPI spec. Run either against AUS VIC NPL 2026 (or whatever scope you
  want) and send over any error output if something doesn't match the spec's
  shape (e.g. a 401, or a field named slightly differently than documented).
- Wyscout's own `MatchAdvancedStats` endpoint separately exposes a match-level
  `attacks.corners` / `attacks.cornersWithShot` pair per team, which is a
  reasonable cross-check for the "corners taken" / "chances" counts if you
  want one — not used here to keep this to a single API call per match.
