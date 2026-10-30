import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = "tjorgef"
TOKEN = os.environ["GITHUB_TOKEN"]
OUTPUT = Path("profile")
OUTPUT.mkdir(exist_ok=True)

API = "https://api.github.com/graphql"

BG = "#0d1117"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
ACCENT = "#58a6ff"
GREEN = "#3fb950"


def graphql(query, variables=None):
    payload = json.dumps({
        "query": query,
        "variables": variables or {}
    }).encode()

    request = urllib.request.Request(
        API,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "tjorgef-profile-stats"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(result["errors"])

    return result["data"]


def text(x, y, value, size=14, color=TEXT, weight=400):
    return (
        f'<text x="{x}" y="{y}" '
        f'font-family="Arial, sans-serif" '
        f'font-size="{size}" '
        f'font-weight="{weight}" '
        f'fill="{color}">{escape(str(value))}</text>'
    )


def rect(x, y, width, height, color, radius=0):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" '
        f'height="{height}" rx="{radius}" fill="{color}"/>'
    )


def save_svg(filename, width, height, content):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
        width="{width}" height="{height}"
        viewBox="0 0 {width} {height}">

        <rect width="{width}" height="{height}"
              rx="12" fill="{BG}"
              stroke="{BORDER}"/>

        {content}

    </svg>"""

    (OUTPUT / filename).write_text(svg, encoding="utf-8")


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    name
    followers {
      totalCount
    }
    following {
      totalCount
    }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      privacy: PUBLIC
      isFork: false
    ) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
    contributionsCollection(from: $from, to: $to) {
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


now = datetime.now(timezone.utc)
start = now - timedelta(days=364)

data = graphql(
    QUERY,
    {
        "login": USERNAME,
        "from": start.isoformat(),
        "to": now.isoformat()
    }
)

user = data["user"]

if not user:
    raise RuntimeError(f"User {USERNAME} not found")

repos = user["repositories"]["nodes"]

followers = user["followers"]["totalCount"]
following = user["following"]["totalCount"]
repo_count = user["repositories"]["totalCount"]
stars = sum(repo["stargazerCount"] for repo in repos)

calendar = user["contributionsCollection"]["contributionCalendar"]
contributions = calendar["totalContributions"]


# ---------------------------------
# GitHub Statistics
# ---------------------------------

content = text(
    25, 38,
    "GitHub Statistics",
    20, ACCENT, 700
)

stats = [
    ("Public Repositories", repo_count),
    ("Followers", followers),
    ("Following", following),
    ("Stars Received*", stars),
    ("Contributions (12 months)", contributions)
]

for index, (label, value) in enumerate(stats):
    y = 78 + index * 38

    content += text(25, y, label, 14, MUTED)
    content += text(285, y, value, 17, TEXT, 700)

content += text(
    25, 290,
    "*Stars from the first 100 public, non-fork repositories",
    10, MUTED
)

save_svg("stats.svg", 400, 310, content)


# ---------------------------------
# Language Statistics
# ---------------------------------

languages = {}

for repo in repos:
    for edge in repo["languages"]["edges"]:
        name = edge["node"]["name"]
        size = edge["size"]

        languages[name] = languages.get(name, 0) + size

sorted_languages = sorted(
    languages.items(),
    key=lambda item: item[1],
    reverse=True
)[:6]

total = sum(languages.values())

content = text(
    25, 38,
    "Most Used Languages",
    20, ACCENT, 700
)

palette = [
    "#58a6ff",
    "#3fb950",
    "#d29922",
    "#bc8cff",
    "#f78166",
    "#79c0ff"
]

if total == 0:
    content += text(25, 90, "No language data available", 14, MUTED)

for index, (name, size) in enumerate(sorted_languages):
    y = 78 + index * 39
    percent = size / total * 100 if total else 0

    content += text(25, y, name, 13)
    content += text(
        320, y,
        f"{percent:.1f}%",
        13, MUTED
    )

    content += rect(
        25, y + 8,
        320, 7,
        BORDER, 3
    )

    content += rect(
        25, y + 8,
        320 * percent / 100,
        7,
        palette[index], 3
    )

save_svg("languages.svg", 400, 330, content)


# ---------------------------------
# Contribution Activity
# ---------------------------------

days = []

for week in calendar["weeks"]:
    days.extend(week["contributionDays"])

monthly = {}

for day in days:
    month = day["date"][:7]

    monthly[month] = (
        monthly.get(month, 0)
        + day["contributionCount"]
    )

months = sorted(monthly.keys())

# Keep the most recent 12 months.
months = months[-12:]

values = [monthly[month] for month in months]
maximum = max(values, default=0)

content = text(
    25, 38,
    "Contribution Activity",
    20, ACCENT, 700
)

content += text(
    25, 63,
    f"{contributions} contributions in the last 12 months",
    13, MUTED
)

chart_top = 95
chart_bottom = 245
chart_height = chart_bottom - chart_top

bar_width = 38
gap = 21
start_x = 30

for index, month in enumerate(months):
    value = monthly[month]

    height = (
        value / maximum * chart_height
        if maximum > 0
        else 0
    )

    x = start_x + index * (bar_width + gap)
    y = chart_bottom - height

    content += rect(
        x, y,
        bar_width, height,
        GREEN, 4
    )

    label = datetime.strptime(
        month, "%Y-%m"
    ).strftime("%b")

    content += text(
        x + 3,
        270,
        label,
        11, MUTED
    )

    content += text(
        x + 8,
        max(y - 8, 88),
        value,
        11, TEXT
    )

save_svg("activity.svg", 780, 295, content)

print("Generated:")
print(" - profile/stats.svg")
print(" - profile/languages.svg")
print(" - profile/activity.svg")
