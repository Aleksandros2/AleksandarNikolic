#!/usr/bin/env python3
import base64
import datetime as dt
import json
import os
import pathlib
import random
import re
import urllib.error
import urllib.request
from typing import Any


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_contribution_calendar(login: str, token: str) -> dict[str, Any]:
    payload = json.dumps({"query": QUERY, "variables": {"login": login}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "arcade-contrib-generator",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8")
    data = json.loads(body)

    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    user = data.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user '{login}' not found or not accessible.")

    return user["contributionsCollection"]["contributionCalendar"]


def level_for_count(count: int, max_count: int) -> int:
    if count <= 0:
        return 0
    if max_count <= 1:
        return 4
    ratio = count / max_count
    if ratio < 0.25:
        return 1
    if ratio < 0.5:
        return 2
    if ratio < 0.75:
        return 3
    return 4


def load_image_data_uri(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def render_svg(login: str, calendar: dict[str, Any], out_path: pathlib.Path) -> None:
    weeks = calendar.get("weeks", [])
    total = int(calendar.get("totalContributions", 0))

    cell = 11
    gap = 4
    grid_x = 195
    grid_y = 90
    grid_w = max(len(weeks), 52) * (cell + gap)
    grid_h = 7 * (cell + gap)

    width = grid_x + grid_w + 44
    height = grid_y + grid_h + 130

    palette = ["#1a2030", "#30476e", "#3e6aa7", "#5f95dd", "#90c2ff"]

    cells: list[dict[str, Any]] = []
    max_count = 0
    for wi, week in enumerate(weeks):
        days = week.get("contributionDays", [])
        for di, day in enumerate(days):
            count = int(day.get("contributionCount", 0))
            max_count = max(max_count, count)
            x = grid_x + wi * (cell + gap)
            y = grid_y + di * (cell + gap)
            cells.append(
                {
                    "x": x,
                    "y": y,
                    "count": count,
                    "date": str(day.get("date", "")),
                }
            )

    non_zero = [c for c in cells if c["count"] > 0]
    hot_cells = sorted(non_zero, key=lambda c: c["count"], reverse=True)[:4]

    # If there are no contributions, we still animate toward symbolic targets.
    if not hot_cells:
        fallback_positions = [12, 23, 35, 47]
        for idx, col in enumerate(fallback_positions):
            hot_cells.append(
                {
                    "x": grid_x + col * (cell + gap),
                    "y": grid_y + (idx % 7) * (cell + gap),
                    "count": 0,
                    "date": "",
                }
            )

    title = f"{login}'s Arcade Contribution Arena"
    generated_on = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    donkey_data_uri = load_image_data_uri(pathlib.Path("assets/donkeyK.png"))

    pieces = []
    pieces.append(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#060b16" />
      <stop offset="100%" stop-color="#0f1a2f" />
    </linearGradient>
    <linearGradient id="panel" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#1d2f50" stop-opacity="0.65" />
      <stop offset="100%" stop-color="#2e4b7b" stop-opacity="0.15" />
    </linearGradient>
    <style>
      .t-main {{ font: 700 22px 'Segoe UI', 'Trebuchet MS', sans-serif; fill: #e8f0ff; }}
      .t-sub {{ font: 500 12px 'Segoe UI', 'Trebuchet MS', sans-serif; fill: #9db9e7; }}
      .t-mini {{ font: 500 10px 'Consolas', 'Courier New', monospace; fill: #7fa0d3; }}
      .grid-cell {{ rx: 2; ry: 2; }}
      .scanline {{
        animation: scan 5s linear infinite;
      }}
      @keyframes scan {{
        0% {{ transform: translateY(-85px); opacity: 0; }}
        7% {{ opacity: .32; }}
        50% {{ opacity: .08; }}
        100% {{ transform: translateY(210px); opacity: 0; }}
      }}
      .barrel {{
        filter: drop-shadow(0 0 4px rgba(232, 167, 96, 0.45));
      }}
      .barrel-band {{
        fill: #6d3f22;
      }}
      .impact {{
        transform-origin: center;
      }}
      .gorilla {{
        animation: hop 2s ease-in-out infinite;
      }}
      @keyframes hop {{
        0%,100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-3px); }}
      }}
    </style>
  </defs>

  <rect width="{width}" height="{height}" fill="url(#bg)" rx="16" />
  <rect x="18" y="18" width="{width - 36}" height="{height - 36}" rx="12" stroke="#294268" stroke-opacity="0.6" />

  <text x="28" y="42" class="t-main">{title}</text>
  <text x="28" y="61" class="t-sub">Total contributions (last year): {total}</text>
  <text x="{width - 205}" y="{height - 20}" class="t-mini">auto-generated: {generated_on}</text>

  <rect x="{grid_x - 12}" y="{grid_y - 14}" width="{grid_w + 24}" height="{grid_h + 28}" fill="url(#panel)" rx="10" stroke="#355784" stroke-opacity="0.5"/>
"""
    )

    for c in cells:
        fill = palette[level_for_count(c["count"], max_count)]
        pieces.append(
            f'  <rect class="grid-cell" x="{c["x"]}" y="{c["y"]}" width="{cell}" height="{cell}" fill="{fill}" />\n'
        )

    pieces.append(
        f"""  <g class="scanline">
    <rect x="{grid_x - 10}" y="{grid_y - 10}" width="{grid_w + 20}" height="8" fill="#8cc1ff" fill-opacity="0.18" />
  </g>

  <g transform="translate(34 105)">
    <rect x="0" y="78" width="132" height="10" fill="#2a456d" rx="4"/>
"""
    )

    if donkey_data_uri:
        pieces.append(
            f"""    <g class="gorilla" transform="translate(4 0)">
      <image href="{donkey_data_uri}" x="0" y="0" width="124" height="92" preserveAspectRatio="xMidYMid meet"/>
    </g>
"""
        )
    else:
        pieces.append(
            """    <g class="gorilla" transform="translate(8 10)">
      <ellipse cx="45" cy="50" rx="24" ry="18" fill="#6b4732"/>
      <circle cx="43" cy="26" r="15" fill="#6b4732"/>
      <circle cx="36" cy="24" r="3" fill="#f5d6ba"/>
      <circle cx="49" cy="24" r="3" fill="#f5d6ba"/>
      <ellipse cx="43" cy="31" rx="7" ry="5" fill="#f0cba5"/>
      <rect x="15" y="43" width="14" height="8" rx="4" fill="#7d563f"/>
      <rect x="61" y="43" width="14" height="8" rx="4" fill="#7d563f"/>
      <rect x="28" y="63" width="12" height="14" rx="5" fill="#5d3d2d"/>
      <rect x="48" y="63" width="12" height="14" rx="5" fill="#5d3d2d"/>
    </g>
"""
        )

    pieces.append(
        """    <text x="0" y="106" class="t-mini">gorilla barrel smash mode</text>
  </g>
"""
    )

    throw_start_x = 132
    throw_start_y = 123
    durations = [6.4, 6.4, 6.4, 6.4]
    begins = [0.0, 1.3, 2.8, 4.1]

    for idx, target in enumerate(hot_cells):
        tx = target["x"] + cell // 2
        ty = target["y"] + cell // 2
        cx1 = throw_start_x + (tx - throw_start_x) * 0.35
        cy1 = throw_start_y - 44
        cx2 = throw_start_x + (tx - throw_start_x) * 0.7
        cy2 = ty - 26
        path_id = f"p{idx}"
        pieces.append(
            f"""  <path id="{path_id}" d="M {throw_start_x} {throw_start_y} C {cx1:.1f} {cy1:.1f}, {cx2:.1f} {cy2:.1f}, {tx} {ty}" fill="none" stroke="none"/>
  <g class="barrel" opacity="0">
    <g>
      <ellipse cx="0" cy="0" rx="8" ry="5.4" fill="#8a4f2b"/>
      <ellipse cx="0" cy="-2.2" rx="8" ry="2.2" fill="#b57243"/>
      <rect x="-8" y="-2.2" width="16" height="4.4" fill="#ad6a3d"/>
      <rect class="barrel-band" x="-8" y="-1.8" width="16" height="1"/>
      <rect class="barrel-band" x="-8" y="0.8" width="16" height="1"/>
      <ellipse cx="0" cy="2.2" rx="8" ry="2.2" fill="#91542f"/>
      <animateTransform attributeName="transform" type="rotate" values="0;360" dur="0.65s" repeatCount="indefinite"/>
    </g>
    <animateMotion dur="{durations[idx]}s" begin="{begins[idx]}s;{begins[idx]}s+{durations[idx]}s" repeatCount="indefinite" rotate="auto">
      <mpath href="#{path_id}" />
    </animateMotion>
    <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.04;0.9;1" dur="{durations[idx]}s" begin="{begins[idx]}s;{begins[idx]}s+{durations[idx]}s" repeatCount="indefinite"/>
  </g>

  <g class="impact" transform="translate({tx} {ty})" opacity="0">
    <circle r="1" fill="#ffe8a6">
      <animate attributeName="r" values="1;10;15" keyTimes="0;0.5;1" dur="0.45s" begin="{begins[idx] + durations[idx] * 0.88:.2f}s;{begins[idx] + durations[idx] * 0.88:.2f}s+{durations[idx]}s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0;1;0" keyTimes="0;0.3;1" dur="0.45s" begin="{begins[idx] + durations[idx] * 0.88:.2f}s;{begins[idx] + durations[idx] * 0.88:.2f}s+{durations[idx]}s" repeatCount="indefinite"/>
    </circle>
    <line x1="-8" y1="-8" x2="8" y2="8" stroke="#ffd89a" stroke-width="1.2">
      <animate attributeName="opacity" values="0;1;0" dur="0.45s" begin="{begins[idx] + durations[idx] * 0.88:.2f}s;{begins[idx] + durations[idx] * 0.88:.2f}s+{durations[idx]}s" repeatCount="indefinite"/>
    </line>
    <line x1="8" y1="-8" x2="-8" y2="8" stroke="#ffd89a" stroke-width="1.2">
      <animate attributeName="opacity" values="0;1;0" dur="0.45s" begin="{begins[idx] + durations[idx] * 0.88:.2f}s;{begins[idx] + durations[idx] * 0.88:.2f}s+{durations[idx]}s" repeatCount="indefinite"/>
    </line>
  </g>
"""
        )

    pieces.append("</svg>\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(pieces), encoding="utf-8")


def render_error_svg(login: str, error_text: str, out_path: pathlib.Path) -> None:
    safe_error = error_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="220" viewBox="0 0 1100 220" fill="none" role="img" aria-label="Arcade contribution graphic unavailable">
  <rect width="1100" height="220" rx="16" fill="#0c1528"/>
  <rect x="14" y="14" width="1072" height="192" rx="12" stroke="#385b90" stroke-opacity="0.5"/>
  <text x="30" y="56" style="font:700 24px 'Segoe UI',sans-serif;fill:#e7f0ff;">{login}'s Arcade Contribution Arena</text>
  <text x="30" y="95" style="font:500 14px 'Segoe UI',sans-serif;fill:#abc2e8;">Could not load contribution data right now.</text>
  <text x="30" y="128" style="font:500 12px 'Consolas',monospace;fill:#7fa0d3;">{safe_error}</text>
</svg>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")


def build_mock_calendar(login: str) -> dict[str, Any]:
    rng = random.Random(login)
    start = dt.date.today() - dt.timedelta(days=370)
    start = start - dt.timedelta(days=(start.weekday() + 1) % 7)

    weeks = []
    total = 0
    for week_idx in range(53):
        days = []
        for day_idx in range(7):
            date = start + dt.timedelta(days=(week_idx * 7 + day_idx))
            band = 0.12 + (week_idx / 70.0)
            active = rng.random() < min(0.62, band)
            count = rng.randint(1, 10) if active else 0
            total += count
            days.append({"date": date.isoformat(), "contributionCount": count})
        weeks.append({"contributionDays": days})

    return {"totalContributions": total, "weeks": weeks}


def detect_owner_from_git_remote() -> str:
    config_path = pathlib.Path(".git/config")
    if not config_path.exists():
        return ""

    content = config_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"url\s*=\s*(.+)", content)
    if not match:
        return ""

    url = match.group(1).strip()
    https_match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if https_match:
        return https_match.group(1)
    return ""


def main() -> None:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    owner = repository.split("/", 1)[0] if "/" in repository else ""
    detected_owner = detect_owner_from_git_remote()
    login = os.environ.get("PROFILE_USERNAME", owner or detected_owner or "octocat")
    token = os.environ.get("GITHUB_TOKEN", "")
    out_file = pathlib.Path("assets/arcade-contrib.svg")

    if not token:
        render_svg(login, build_mock_calendar(login), out_file)
        return

    try:
        calendar = fetch_contribution_calendar(login, token)
        render_svg(login, calendar, out_file)
    except (RuntimeError, urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        render_svg(login, build_mock_calendar(login), out_file)
        render_error_svg(login, str(exc), pathlib.Path("assets/arcade-contrib-error.svg"))


if __name__ == "__main__":
    main()
