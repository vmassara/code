#!/usr/bin/env python3
"""CLI entrypoint: fetch a competition/season from Wyscout, compute
corner-kick analytics per team, and write CSV/JSON/HTML outputs.

Usage:
  export WYSCOUT_USER=you@example.com
  export WYSCOUT_PASS='...'
  python cli.py --competition "NPL Victoria" --season 2026 --out-dir out/

Credentials can also be passed with --username/--password instead of env vars.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from corner_analysis import (
    analyze_match,
    list_played_matches,
    merge_match_stats,
    resolve_competition,
    resolve_season,
)
from report import render_dashboard
from wyscout_client import WyscoutClient, WyscoutError


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--competition", required=True, help="Competition name or numeric wyId")
    p.add_argument("--season", default=None, help="Season name/year or numeric wyId (default: active season)")
    p.add_argument("--username", default=None, help="Wyscout username (default: $WYSCOUT_USER)")
    p.add_argument("--password", default=None, help="Wyscout password (default: $WYSCOUT_PASS)")
    p.add_argument("--out-dir", default="out", help="Directory to write outputs into")
    p.add_argument("--max-matches", type=int, default=None, help="Cap on matches processed (for a quick test run)")
    p.add_argument("--workers", type=int, default=6, help="Concurrent requests for fetching match events")
    return p.parse_args()


def fetch_all_events(client: WyscoutClient, matches: list[dict], workers: int) -> list[dict]:
    results = [None] * len(matches)

    def fetch_one(i, match):
        return i, client.match_events(match["matchId"])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_one, i, m) for i, m in enumerate(matches)]
        done = 0
        for future in as_completed(futures):
            i, payload = future.result()
            results[i] = payload
            done += 1
            print(f"\r  fetched {done}/{len(matches)} matches' events", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return results


def main():
    args = parse_args()
    try:
        client = WyscoutClient(username=args.username, password=args.password)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Resolving competition {args.competition!r}...", file=sys.stderr)
    competition = resolve_competition(client, args.competition)
    print(f"  -> {competition['name']} (#{competition['wyId']})", file=sys.stderr)

    season = resolve_season(client, competition["wyId"], args.season)
    print(f"Season: {season['name']} (#{season['wyId']})", file=sys.stderr)

    matches = list_played_matches(client, season["wyId"])
    if args.max_matches:
        matches = matches[: args.max_matches]
    print(f"{len(matches)} played matches to analyze", file=sys.stderr)
    if not matches:
        print("No played matches found for this scope.", file=sys.stderr)
        sys.exit(1)

    try:
        events_payloads = fetch_all_events(client, matches, args.workers)
    except WyscoutError as e:
        print(f"error fetching events: {e}", file=sys.stderr)
        sys.exit(1)

    per_match_stats = [analyze_match(payload) for payload in events_payloads]
    merged = merge_match_stats(per_match_stats)
    team_summaries = [ts.as_summary() for ts in merged.values() if ts.corners_taken > 0]
    team_summaries.sort(key=lambda t: t["pct_corners_to_chance"], reverse=True)

    meta = {
        "competition_name": competition["name"],
        "competition_id": competition["wyId"],
        "season_name": season["name"],
        "season_id": season["wyId"],
        "matches_analyzed": len(matches),
    }

    os.makedirs(args.out_dir, exist_ok=True)

    json_path = os.path.join(args.out_dir, "corner_analysis.json")
    with open(json_path, "w") as f:
        json.dump({"meta": meta, "teams": team_summaries}, f, indent=2)

    csv_path = os.path.join(args.out_dir, "corner_analysis.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "team", "corners_taken", "corner_possessions", "chances", "chances_on_target",
            "goals", "xg", "pct_corners_to_chance", "xg_per_corner",
            "zone_near_post_pct", "zone_central_pct", "zone_far_post_pct", "zone_short_edge_pct",
        ])
        for t in team_summaries:
            zp = t["zone_pct"]
            writer.writerow([
                t["team_name"], t["corners_taken"], t["corner_possessions"], t["chances"],
                t["chances_on_target"], t["goals"], t["xg"], t["pct_corners_to_chance"], t["xg_per_corner"],
                zp.get("Near post", 0), zp.get("Central", 0), zp.get("Far post", 0),
                zp.get("Short / edge of box", 0),
            ])

    html_path = os.path.join(args.out_dir, "corner_dashboard.html")
    with open(html_path, "w") as f:
        f.write(render_dashboard(meta, team_summaries))

    print(f"\nWrote:\n  {json_path}\n  {csv_path}\n  {html_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
