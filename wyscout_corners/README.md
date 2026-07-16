# Wyscout corner-kick analysis

Compares every team in a competition/season on:

- how many corners they take
- what share of those corners produce a chance (a shot)
- the xG generated from corner-originated possessions
- where the delivery typically lands (near post / central / far post / short)

## Setup

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

- `wyscout_client.py` — Basic Auth HTTP client with the documented 12 req/s
  rate limit and retry/backoff on 429/5xx.
- `corner_analysis.py` — the corner/possession extraction and per-team
  aggregation logic (no network calls; pure functions over event payloads).
- `report.py` — renders `corner_dashboard.html` from computed team stats.
- `cli.py` — wires it together: resolve competition/season → list matches →
  fetch events concurrently → analyze → write CSV/JSON/HTML.
- `test_fixture.py` — a synthetic events payload (no network) that exercises
  the full pipeline and asserts the arithmetic; run with `python3
  test_fixture.py` any time you change the extraction/aggregation logic.

## Notes

- This session's network egress policy blocked `apirest.wyscout.com`, so the
  pipeline is validated against a synthetic fixture (`test_fixture.py`) and
  the schema in the provided OpenAPI spec, not a live competition. Run it
  against AUS VIC NPL 2026 (or whatever scope you want) from an environment
  that can reach the Wyscout API, and share any error output if something
  doesn't match the spec's shape.
- Wyscout's own `MatchAdvancedStats` endpoint separately exposes a match-level
  `attacks.corners` / `attacks.cornersWithShot` pair per team, which is a
  reasonable cross-check for the "corners taken" / "chances" counts if you
  want one — not used here to keep this to a single API call per match.
