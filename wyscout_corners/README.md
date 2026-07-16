# Wyscout corner-kick analysis

Compares every team in a competition/season on:

- how many corners they take
- what share of those corners produce a chance (a shot)
- the xG generated from corner-originated possessions
- where the delivery typically lands (near post / central / far post / short)

## Running it

Use the Python CLI (`cli.py`). There's also a `live_dashboard.html` that calls
the API directly from a browser with no install — **it doesn't work**:
Wyscout's API doesn't send the `Access-Control-Allow-Origin` header a browser
requires for a cross-origin request, so every call fails with a CORS error
before credentials are even checked, regardless of how the page is hosted.
That's a decision on Wyscout's server, not something fixable client-side.
Confirmed against a real account on 2026-07-16 (browser console:
`Access to fetch at 'https://apirest.wyscout.com/v3/search?...' from origin
'null' has been blocked by CORS policy: No 'Access-Control-Allow-Origin'
header is present`). Kept in the repo as-is (now with a warning banner) in
case Wyscout ever adds CORS support, or in case someone runs it from a domain
Wyscout has separately allowlisted — otherwise, ignore it.

CORS is purely a browser mechanism, so it doesn't affect `cli.py` at all —
that's a direct HTTPS call, same as `curl` or Postman.

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

- `live_dashboard.html` — browser-only version; **doesn't work**, see above.
  Kept for reference. Has its own JS port of the resolution/analysis logic
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
  `cli.py` hasn't been exercised end-to-end against a live competition from
  here — it's validated against a synthetic fixture and the schema in the
  provided OpenAPI spec. Run it against AUS VIC NPL 2026 (or whatever scope
  you want) and send over any error output if something doesn't match the
  spec's shape (e.g. a 401, or a field named slightly differently than
  documented).
- Wyscout's own `MatchAdvancedStats` endpoint separately exposes a match-level
  `attacks.corners` / `attacks.cornersWithShot` pair per team, which is a
  reasonable cross-check for the "corners taken" / "chances" counts if you
  want one — not used here to keep this to a single API call per match.
