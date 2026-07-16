"""Corner-kick analysis built on top of the Wyscout Events endpoint.

Core idea (see README for the full reasoning): a single call to
`/matches/{id}/events` carries everything needed —

  * every corner kick itself (`type.primary == "corner"`), with the
    delivery's actual end point in `pass.endLocation`
  * the "possession" each event belongs to, which is tagged with
    `"corner"` in `possession.types` when it originates from a corner,
    and carries the outcome of that possession in `possession.attack`
    (`withShot`, `withShotOnGoal`, `withGoal`, `xg`)

So corner counts, chance conversion, and xG all come from one place,
per match, per team — no extra endpoint calls needed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from wyscout_client import WyscoutClient

CORNER_PRIMARY_TYPE = "corner"
PLAYED_STATUS = "Played"

# How far in from the byline a delivery can land and still count as an
# in-box zone rather than a short corner / recycled possession.
SHORT_CORNER_DX_THRESHOLD = 18
CENTRAL_ZONE_HALF_WIDTH = 7


@dataclass
class TeamCornerStats:
    team_id: int
    team_name: str
    corners_taken: int = 0
    corner_possessions: int = 0
    chances: int = 0
    chances_on_target: int = 0
    goals: int = 0
    xg: float = 0.0
    zone_counts: Counter = field(default_factory=Counter)
    deliveries: list = field(default_factory=list)  # for the pitch plot

    def as_summary(self) -> dict:
        pct_to_chance = (100.0 * self.chances / self.corners_taken) if self.corners_taken else 0.0
        xg_per_corner = (self.xg / self.corners_taken) if self.corners_taken else 0.0
        total_zoned = sum(self.zone_counts.values())
        zone_pct = {
            zone: (100.0 * count / total_zoned if total_zoned else 0.0)
            for zone, count in self.zone_counts.items()
        }
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "corners_taken": self.corners_taken,
            "corner_possessions": self.corner_possessions,
            "chances": self.chances,
            "chances_on_target": self.chances_on_target,
            "goals": self.goals,
            "xg": round(self.xg, 3),
            "pct_corners_to_chance": round(pct_to_chance, 1),
            "xg_per_corner": round(xg_per_corner, 3),
            "zone_pct": {z: round(p, 1) for z, p in zone_pct.items()},
            "deliveries": self.deliveries,
        }


def resolve_competition(client: WyscoutClient, name_or_id: str) -> dict:
    """Returns {"wyId": int, "name": str} for a competition name or numeric id."""
    if str(name_or_id).isdigit():
        comp = client.competition(name_or_id)
        return {"wyId": comp["wyId"], "name": comp["name"]}
    results = client.search(name_or_id, "competition")
    if not results:
        raise ValueError(f"No competition found matching {name_or_id!r}")
    if len(results) > 1:
        options = ", ".join(f"{r['name']} (#{r['wyId']})" for r in results[:10])
        raise ValueError(
            f"Multiple competitions matched {name_or_id!r}: {options}. "
            "Re-run with the numeric wyId."
        )
    match = results[0]
    return {"wyId": match["wyId"], "name": match["name"]}


def resolve_season(client: WyscoutClient, competition_id: int, season_name_or_id: str | None) -> dict:
    """Returns {"wyId": int, "name": str} for a season name/year, numeric id, or
    the active season if season_name_or_id is None."""
    seasons = client.competition_seasons(competition_id)["seasons"]
    if season_name_or_id is None:
        for entry in seasons:
            if entry["season"].get("active"):
                return {"wyId": entry["seasonId"], "name": entry["season"]["name"]}
        raise ValueError("No active season found; specify one explicitly.")
    if str(season_name_or_id).isdigit() and any(
        str(e["seasonId"]) == str(season_name_or_id) for e in seasons
    ):
        entry = next(e for e in seasons if str(e["seasonId"]) == str(season_name_or_id))
        return {"wyId": entry["seasonId"], "name": entry["season"]["name"]}
    for entry in seasons:
        if entry["season"]["name"] == str(season_name_or_id):
            return {"wyId": entry["seasonId"], "name": entry["season"]["name"]}
    available = ", ".join(e["season"]["name"] for e in seasons)
    raise ValueError(f"Season {season_name_or_id!r} not found. Available: {available}")


def list_played_matches(client: WyscoutClient, season_id: int) -> list[dict]:
    matches = client.season_matches(season_id)["matches"]
    return [m for m in matches if m.get("status") == PLAYED_STATUS]


def _classify_delivery_zone(corner_location: dict, delivery_location: dict) -> tuple[str, str]:
    """Returns (zone, side). `side` is which flag the corner was taken from,
    using the fixed pitch orientation where y=0..100 spans one touchline to
    the other (attack is always toward x=100, per the API's coordinate spec)."""
    side = "left" if corner_location["y"] < 50 else "right"
    ex, ey = delivery_location["x"], delivery_location["y"]
    dx = 100 - ex
    if dx > SHORT_CORNER_DX_THRESHOLD:
        return "Short / edge of box", side
    diff = ey - 50
    if abs(diff) <= CENTRAL_ZONE_HALF_WIDTH:
        return "Central", side
    near_offset = diff if side == "right" else -diff
    return ("Near post", side) if near_offset > 0 else ("Far post", side)


def analyze_match(events_payload: dict) -> dict[int, TeamCornerStats]:
    """Processes one match's /events payload into per-team TeamCornerStats
    (keyed by team id), covering just that match."""
    elements = events_payload.get("elements") or [events_payload]
    stats: dict[int, TeamCornerStats] = {}
    seen_possession_ids: set[int] = set()

    def team_stats(team_id: int, team_name: str) -> TeamCornerStats:
        if team_id not in stats:
            stats[team_id] = TeamCornerStats(team_id=team_id, team_name=team_name)
        return stats[team_id]

    for element in elements:
        for event in element.get("events", []):
            team = event.get("team") or {}
            team_id, team_name = team.get("id"), team.get("name")
            if team_id is None:
                continue

            event_type = event.get("type") or {}
            if event_type.get("primary") == CORNER_PRIMARY_TYPE:
                ts = team_stats(team_id, team_name)
                ts.corners_taken += 1
                pass_info = event.get("pass")
                location = event.get("location")
                if pass_info and pass_info.get("endLocation") and location:
                    zone, side = _classify_delivery_zone(location, pass_info["endLocation"])
                    ts.zone_counts[zone] += 1
                    ts.deliveries.append({
                        "x": pass_info["endLocation"]["x"],
                        "y": pass_info["endLocation"]["y"],
                        "zone": zone,
                        "side": side,
                    })

            possession = event.get("possession")
            if not possession:
                continue
            poss_id = possession.get("id")
            poss_types = possession.get("types") or []
            if poss_id is None or poss_id in seen_possession_ids or CORNER_PRIMARY_TYPE not in poss_types:
                continue
            seen_possession_ids.add(poss_id)
            poss_team = possession.get("team") or {}
            poss_team_id, poss_team_name = poss_team.get("id"), poss_team.get("name")
            if poss_team_id is None:
                continue
            ts = team_stats(poss_team_id, poss_team_name)
            ts.corner_possessions += 1
            attack = possession.get("attack") or {}
            if attack.get("withShot"):
                ts.chances += 1
            if attack.get("withShotOnGoal"):
                ts.chances_on_target += 1
            if attack.get("withGoal"):
                ts.goals += 1
            ts.xg += float(attack.get("xg") or 0)

    return stats


def merge_match_stats(match_stats_list: list[dict[int, TeamCornerStats]]) -> dict[int, TeamCornerStats]:
    merged: dict[int, TeamCornerStats] = {}
    for match_stats in match_stats_list:
        for team_id, ts in match_stats.items():
            if team_id not in merged:
                merged[team_id] = TeamCornerStats(team_id=team_id, team_name=ts.team_name)
            m = merged[team_id]
            m.corners_taken += ts.corners_taken
            m.corner_possessions += ts.corner_possessions
            m.chances += ts.chances
            m.chances_on_target += ts.chances_on_target
            m.goals += ts.goals
            m.xg += ts.xg
            m.zone_counts.update(ts.zone_counts)
            m.deliveries.extend(ts.deliveries)
    return merged
