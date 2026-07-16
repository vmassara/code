"""Synthetic fixture exercising analyze_match/merge/report without network
access, to sanity-check the pipeline end to end. Not a real pytest suite —
just a quick harness run with `python3 test_fixture.py`.
"""
import json
import os

from corner_analysis import analyze_match, merge_match_stats
from report import render_dashboard

TEAM_A = {"id": 1, "name": "Hume City FC"}
TEAM_B = {"id": 2, "name": "South Melbourne"}


def corner_event(eid, team, corner_y, end_x, end_y, poss_id, with_shot, with_sot, with_goal, xg):
    return {
        "id": eid,
        "team": team,
        "opponentTeam": TEAM_B if team is TEAM_A else TEAM_A,
        "location": {"x": 100, "y": corner_y},
        "type": {"primary": "corner", "secondary": ["corner"]},
        "pass": {
            "accurate": True,
            "endLocation": {"x": end_x, "y": end_y},
        },
        "possession": {
            "id": poss_id,
            "team": team,
            "types": ["corner"],
            "attack": {
                "flank": "right",
                "withShot": with_shot,
                "withShotOnGoal": with_sot,
                "withGoal": with_goal,
                "xg": xg,
            },
        },
    }


def followup_event(eid, team, poss_id):
    # second event of the same possession -- must be deduped, not double counted
    return {
        "id": eid,
        "team": team,
        "location": {"x": 95, "y": 50},
        "type": {"primary": "shot", "secondary": ["shot_after_corner"]},
        "shot": {"xg": 0.2, "isGoal": False, "onTarget": True},
        "possession": {
            "id": poss_id,
            "team": team,
            "types": ["corner"],
            "attack": {"withShot": True, "withShotOnGoal": True, "withGoal": False, "xg": 0.2},
        },
    }


def build_match(match_id, corners_a, corners_b):
    events = []
    eid = match_id * 1000
    for i, (corner_y, end_x, end_y, shot, sot, goal, xg) in enumerate(corners_a):
        events.append(corner_event(eid, TEAM_A, corner_y, end_x, end_y, eid, shot, sot, goal, xg))
        if shot:
            events.append(followup_event(eid + 1, TEAM_A, eid))
        eid += 2
    for i, (corner_y, end_x, end_y, shot, sot, goal, xg) in enumerate(corners_b):
        events.append(corner_event(eid, TEAM_B, corner_y, end_x, end_y, eid, shot, sot, goal, xg))
        if shot:
            events.append(followup_event(eid + 1, TEAM_B, eid))
        eid += 2
    return {"elements": [{"events": events}]}


def main():
    # Team A: 6 corners, varied delivery zones, 3 lead to shots
    corners_a = [
        (2, 96, 44, True, True, False, 0.18),   # near post (left corner -> near = low y)
        (2, 90, 50, False, False, False, 0),    # central-ish but far in -> edge of box
        (2, 97, 60, False, False, False, 0),    # far post
        (2, 96, 40, True, False, False, 0.05),  # near post
        (2, 80, 50, False, False, False, 0),    # short/edge of box
        (2, 96, 63, True, True, True, 0.42),    # far post, goal
    ]
    # Team B: 4 corners, 1 leads to a shot, taken from the right side
    corners_b = [
        (98, 96, 58, True, True, False, 0.11),  # right corner, near post (near = high y)
        (98, 90, 50, False, False, False, 0),
        (98, 97, 40, False, False, False, 0),
        (98, 94, 50, False, False, False, 0),
    ]

    per_match = [
        analyze_match(build_match(1, corners_a[:3], corners_b[:2])),
        analyze_match(build_match(2, corners_a[3:], corners_b[2:])),
    ]
    merged = merge_match_stats(per_match)
    summaries = [ts.as_summary() for ts in merged.values()]
    for s in summaries:
        print(json.dumps(s, indent=2))

    meta = {"competition_name": "Test League", "season_name": "2026", "matches_analyzed": 2}
    html = render_dashboard(meta, summaries)
    out_path = os.path.join(os.path.dirname(__file__), "test_dashboard.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"\nwrote {out_path}")

    # --- assertions ---
    by_name = {s["team_name"]: s for s in summaries}
    a = by_name["Hume City FC"]
    b = by_name["South Melbourne"]
    assert a["corners_taken"] == 6, a
    assert a["chances"] == 3, a
    assert abs(a["pct_corners_to_chance"] - 50.0) < 1e-6, a
    assert abs(a["xg"] - (0.18 + 0.05 + 0.42)) < 1e-6, a
    assert a["goals"] == 1, a
    assert b["corners_taken"] == 4, b
    assert b["chances"] == 1, b
    assert b["pct_corners_to_chance"] == 25.0, b
    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
