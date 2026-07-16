"""Renders the self-contained HTML dashboard from computed team stats.

No external JS/CSS dependencies -- the file this writes can be opened
directly from disk or emailed around.
"""
from __future__ import annotations

import html
import json

ZONE_ORDER = ["Near post", "Central", "Far post", "Short / edge of box"]
ZONE_COLORS_LIGHT = {
    "Near post": "#2a78d6",
    "Central": "#008300",
    "Far post": "#e87ba4",
    "Short / edge of box": "#eda100",
}
ZONE_COLORS_DARK = {
    "Near post": "#3987e5",
    "Central": "#008300",
    "Far post": "#d55181",
    "Short / edge of box": "#c98500",
}


def render_dashboard(meta: dict, teams: list[dict]) -> str:
    teams_sorted = sorted(teams, key=lambda t: t["pct_corners_to_chance"], reverse=True)
    data_json = json.dumps({"meta": meta, "teams": teams_sorted}, ensure_ascii=False)
    zone_legend = "".join(
        f'<span class="legend-item"><i style="--c-light:{ZONE_COLORS_LIGHT[z]};'
        f'--c-dark:{ZONE_COLORS_DARK[z]}"></i>{html.escape(z)}</span>'
        for z in ZONE_ORDER
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Corner analysis — {html.escape(meta.get("competition_name", ""))}</title>
<style>
  .viz-root {{
    color-scheme: light;
    --surface-1:    #fcfcfb;
    --page:         #f9f9f7;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted:   #898781;
    --grid:         #e1e0d9;
    --baseline:     #c3c2b7;
    --border:       rgba(11,11,11,0.10);
    --series-1:     #2a78d6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) .viz-root {{
      color-scheme: dark;
      --surface-1:    #1a1a19;
      --page:         #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted:   #898781;
      --grid:         #2c2c2a;
      --baseline:     #383835;
      --border:       rgba(255,255,255,0.10);
      --series-1:     #3987e5;
    }}
  }}
  :root[data-theme="dark"] .viz-root {{
    color-scheme: dark;
    --surface-1:    #1a1a19;
    --page:         #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:   #898781;
    --grid:         #2c2c2a;
    --baseline:     #383835;
    --border:       rgba(255,255,255,0.10);
    --series-1:     #3987e5;
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--page);
    color: var(--text-primary);
  }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 64px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-secondary); font-size: 14px; margin-bottom: 28px; }}
  .card {{
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 24px;
    overflow-x: auto;
  }}
  .card h2 {{ font-size: 15px; margin: 0 0 4px; }}
  .card .hint {{ color: var(--text-muted); font-size: 12.5px; margin: 0 0 16px; }}

  table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; min-width: 720px; }}
  th, td {{ text-align: right; padding: 8px 10px; white-space: nowrap; }}
  th:first-child, td:first-child {{ text-align: left; }}
  thead th {{
    color: var(--text-muted);
    font-weight: 600;
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    border-bottom: 1px solid var(--grid);
    cursor: pointer;
    user-select: none;
  }}
  thead th:hover {{ color: var(--text-primary); }}
  thead th.sorted::after {{ content: " \\2193"; }}
  thead th.sorted.asc::after {{ content: " \\2191"; }}
  tbody tr {{ border-bottom: 1px solid var(--grid); }}
  tbody tr:hover {{ background: color-mix(in srgb, var(--text-primary) 4%, transparent); }}
  tbody td:first-child {{ font-weight: 600; }}
  tbody, td, th {{ font-variant-numeric: tabular-nums; }}

  .bar-row {{ display: flex; align-items: center; gap: 10px; height: 22px; margin: 6px 0; }}
  .bar-label {{ width: 168px; flex: none; font-size: 12.5px; color: var(--text-secondary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .bar-track {{ flex: 1; background: var(--grid); border-radius: 3px; height: 10px; position: relative; }}
  .bar-fill {{ background: var(--series-1); height: 10px; border-radius: 3px; position: relative; }}
  .bar-value {{ width: 56px; flex: none; font-size: 12.5px; color: var(--text-primary); text-align: right;
    font-variant-numeric: tabular-nums; }}

  .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  @media (max-width: 820px) {{ .charts-row {{ grid-template-columns: 1fr; }} }}

  .legend {{ display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }}
  .legend-item {{ font-size: 12.5px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; }}
  .legend-item i {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; background: var(--c-light); }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) .legend-item i {{ background: var(--c-dark); }}
  }}
  :root[data-theme="dark"] .legend-item i {{ background: var(--c-dark); }}

  .stack-row {{ display: flex; align-items: center; gap: 10px; margin: 8px 0; }}
  .stack-label {{ width: 168px; flex: none; font-size: 12.5px; color: var(--text-secondary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .stack-track {{ flex: 1; display: flex; height: 16px; border-radius: 3px; overflow: hidden;
    background: var(--grid); }}
  .stack-seg {{ height: 100%; position: relative; }}
  .stack-seg + .stack-seg {{ margin-left: 2px; }}
  .tooltip {{
    position: fixed; pointer-events: none; z-index: 50;
    background: var(--text-primary); color: var(--surface-1);
    font-size: 12px; padding: 6px 9px; border-radius: 6px;
    opacity: 0; transform: translateY(4px); transition: opacity .1s ease;
    max-width: 220px;
  }}
  .tooltip.show {{ opacity: 1; }}
  footer {{ color: var(--text-muted); font-size: 11.5px; margin-top: 8px; }}
</style>
</head>
<body>
<div class="viz-root">
<div class="wrap">
  <h1>Corner-kick analysis — <span id="comp-name"></span></h1>
  <p class="subtitle" id="subtitle"></p>

  <div class="card">
    <h2>Team comparison</h2>
    <p class="hint">Click a column header to sort. "Chance" = a corner possession that produced a shot.</p>
    <table id="main-table">
      <thead><tr>
        <th data-key="team_name">Team</th>
        <th data-key="corners_taken">Corners</th>
        <th data-key="chances">Chances</th>
        <th data-key="pct_corners_to_chance" class="sorted">Chance %</th>
        <th data-key="chances_on_target">On target</th>
        <th data-key="goals">Goals</th>
        <th data-key="xg">xG from corners</th>
        <th data-key="xg_per_corner">xG / corner</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="charts-row">
    <div class="card">
      <h2>Corner &rarr; chance conversion</h2>
      <p class="hint">Share of a team's corners that produced a shot.</p>
      <div id="chart-pct"></div>
    </div>
    <div class="card">
      <h2>xG generated from corners</h2>
      <p class="hint">Summed expected goals across all corner-originated possessions.</p>
      <div id="chart-xg"></div>
    </div>
  </div>

  <div class="card">
    <h2>Where deliveries land (first contact)</h2>
    <p class="hint">Landing zone of the corner delivery, as a share of that team's corners.</p>
    <div class="legend">{zone_legend}</div>
    <div id="chart-zones"></div>
  </div>

  <footer>Generated from Wyscout match events. Zone boundaries are a heuristic based on delivery end-location relative to goal center — see README for definitions.</footer>
</div>
</div>
<div class="tooltip" id="tooltip"></div>
<script>
const DATA = {data_json};
const ZONE_ORDER = {json.dumps(ZONE_ORDER)};
const isDark = () => {{
  const t = document.documentElement.getAttribute('data-theme');
  if (t === 'dark') return true;
  if (t === 'light') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}};
const ZONE_COLORS = {{
  light: {json.dumps(ZONE_COLORS_LIGHT)},
  dark: {json.dumps(ZONE_COLORS_DARK)}
}};
function zoneColor(z) {{ return ZONE_COLORS[isDark() ? 'dark' : 'light'][z]; }}

const tooltip = document.getElementById('tooltip');
function showTip(evt, text) {{
  tooltip.textContent = text;
  tooltip.style.left = (evt.clientX + 12) + 'px';
  tooltip.style.top = (evt.clientY + 12) + 'px';
  tooltip.classList.add('show');
}}
function hideTip() {{ tooltip.classList.remove('show'); }}

document.getElementById('comp-name').textContent = DATA.meta.competition_name || '';
document.getElementById('subtitle').textContent =
  (DATA.meta.season_name ? DATA.meta.season_name + ' \\u2022 ' : '') +
  DATA.meta.matches_analyzed + ' matches analyzed \\u2022 ' + DATA.teams.length + ' teams';

let sortKey = 'pct_corners_to_chance';
let sortAsc = false;

function renderTable() {{
  const rows = [...DATA.teams].sort((a, b) => {{
    const av = a[sortKey], bv = b[sortKey];
    const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv;
    return sortAsc ? cmp : -cmp;
  }});
  const tbody = document.querySelector('#main-table tbody');
  tbody.innerHTML = rows.map(t => `
    <tr>
      <td>${{t.team_name}}</td>
      <td>${{t.corners_taken}}</td>
      <td>${{t.chances}}</td>
      <td>${{t.pct_corners_to_chance.toFixed(1)}}%</td>
      <td>${{t.chances_on_target}}</td>
      <td>${{t.goals}}</td>
      <td>${{t.xg.toFixed(2)}}</td>
      <td>${{t.xg_per_corner.toFixed(3)}}</td>
    </tr>
  `).join('');
  document.querySelectorAll('#main-table th').forEach(th => {{
    th.classList.toggle('sorted', th.dataset.key === sortKey);
    th.classList.toggle('asc', th.dataset.key === sortKey && sortAsc);
  }});
}}
document.querySelectorAll('#main-table th').forEach(th => {{
  th.addEventListener('click', () => {{
    if (sortKey === th.dataset.key) {{ sortAsc = !sortAsc; }}
    else {{ sortKey = th.dataset.key; sortAsc = false; }}
    renderTable();
  }});
}});
renderTable();

function renderBarChart(containerId, key, formatter) {{
  const container = document.getElementById(containerId);
  const rows = [...DATA.teams].sort((a, b) => b[key] - a[key]);
  const max = Math.max(...rows.map(r => r[key]), 0.0001);
  container.innerHTML = rows.map(t => `
    <div class="bar-row" data-team="${{t.team_name}}" data-value="${{t[key]}}">
      <div class="bar-label">${{t.team_name}}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${{(100 * t[key] / max).toFixed(1)}}%"></div></div>
      <div class="bar-value">${{formatter(t[key])}}</div>
    </div>
  `).join('');
  container.querySelectorAll('.bar-row').forEach(row => {{
    row.addEventListener('mousemove', evt => showTip(evt, `${{row.dataset.team}}: ${{formatter(+row.dataset.value)}}`));
    row.addEventListener('mouseleave', hideTip);
  }});
}}
renderBarChart('chart-pct', 'pct_corners_to_chance', v => v.toFixed(1) + '%');
renderBarChart('chart-xg', 'xg', v => v.toFixed(2));

function renderZoneChart() {{
  const container = document.getElementById('chart-zones');
  container.innerHTML = DATA.teams.map(t => {{
    const segs = ZONE_ORDER.map(z => {{
      const pct = t.zone_pct[z] || 0;
      return `<div class="stack-seg" data-zone="${{z}}" data-pct="${{pct}}" data-team="${{t.team_name}}"
        style="width:${{pct}}%; background:${{zoneColor(z)}}"></div>`;
    }}).join('');
    return `
      <div class="stack-row">
        <div class="stack-label">${{t.team_name}}</div>
        <div class="stack-track">${{segs}}</div>
      </div>
    `;
  }}).join('');
  container.querySelectorAll('.stack-seg').forEach(seg => {{
    seg.addEventListener('mousemove', evt => showTip(evt,
      `${{seg.dataset.team}} \\u2014 ${{seg.dataset.zone}}: ${{(+seg.dataset.pct).toFixed(1)}}%`));
    seg.addEventListener('mouseleave', hideTip);
  }});
}}
renderZoneChart();
</script>
</body>
</html>
"""
