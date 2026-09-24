"""Render the Top Languages and Trophies cards as SVGs.

Replaces the public github-readme-stats and github-profile-trophy services,
which are no longer online.
"""
import json
import math
import os
import urllib.request
from html import escape

LOGIN = "mohammad-malik"
TOKEN = os.environ.get("PERSONAL_TOKEN", "").strip() or os.environ["GITHUB_TOKEN"]

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection { totalCommitContributions restrictedContributionsCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Tokyo Night, to match the rest of the profile
BG, TITLE, TEXT, MUTED, GOLD = "#1a1b27", "#70a5fd", "#c0caf5", "#8a93b8", "#e0af68"


def gql(after=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN, "after": after}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def collect():
    user, repos, after = None, [], None
    while True:
        page = gql(after)
        user = user or page
        repos += page["repositories"]["nodes"]
        info = page["repositories"]["pageInfo"]
        if not info["hasNextPage"]:
            break
        after = info["endCursor"]
    return user, repos


# Notebook files embed plot and output data, which swamps real code size
EXCLUDE = {"Jupyter Notebook"}


def languages_card(repos, top=8):
    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in EXCLUDE:
                continue
            sizes[name] = sizes.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#888888"
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])
    langs = ranked[:top]
    rest = sum(v for _, v in ranked[top:])
    if rest:
        langs.append(("Other", rest))
        colors["Other"] = "#565f89"
    total = sum(v for _, v in langs)

    w, h, cx, cy, r_out, r_in = 360, 210, 95, 115, 70, 44
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           f'<rect width="{w}" height="{h}" rx="6" fill="{BG}"/>',
           f'<text x="20" y="30" font-family="Segoe UI,sans-serif" font-size="17" font-weight="600" fill="{TITLE}">Most Used Languages</text>']
    angle = -math.pi / 2
    for name, v in langs:
        sweep = 2 * math.pi * v / total
        if sweep >= 2 * math.pi - 1e-6:
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{(r_out + r_in) / 2}" fill="none" stroke="{colors[name]}" stroke-width="{r_out - r_in}"/>')
        else:
            a2 = angle + sweep
            large = 1 if sweep > math.pi else 0
            p = lambda rad, a: (cx + rad * math.cos(a), cy + rad * math.sin(a))
            x1, y1 = p(r_out, angle); x2, y2 = p(r_out, a2)
            x3, y3 = p(r_in, a2); x4, y4 = p(r_in, angle)
            out.append(f'<path fill="{colors[name]}" d="M{x1:.2f},{y1:.2f} A{r_out},{r_out} 0 {large} 1 {x2:.2f},{y2:.2f} '
                       f'L{x3:.2f},{y3:.2f} A{r_in},{r_in} 0 {large} 0 {x4:.2f},{y4:.2f} Z"/>')
        angle += sweep
    for i, (name, v) in enumerate(langs):
        y = 58 + i * 17
        out.append(f'<circle cx="200" cy="{y - 4}" r="5" fill="{colors[name]}"/>')
        out.append(f'<text x="212" y="{y}" font-family="Segoe UI,sans-serif" font-size="12" fill="{TEXT}">'
                   f'{escape(name)} <tspan fill="{MUTED}">{100 * v / total:.1f}%</tspan></text>')
    out.append("</svg>")
    return "".join(out)


RANKS = [("SSS", 16), ("SS", 8), ("S", 4), ("A", 2), ("B", 1), ("C", 0.5)]


def rank(value, base):
    for letter, mult in RANKS:
        if value >= base * mult:
            return letter
    return "?"


def trophies_card(user):
    c = user["contributionsCollection"]
    stars = sum(r["stargazerCount"] for r in REPOS)
    items = [
        ("Commits", c["totalCommitContributions"] + c["restrictedContributionsCount"], 100),
        ("Pull Requests", user["pullRequests"]["totalCount"], 10),
        ("Issues", user["issues"]["totalCount"], 10),
        ("Repositories", user["repositories"]["totalCount"], 10),
        ("Stars", stars, 10),
        ("Followers", user["followers"]["totalCount"], 10),
    ]
    tw, gap = 110, 10
    w, h = len(items) * (tw + gap) - gap, 120
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    cup = "M-14,-18 h28 v10 a14,14 0 0 1 -28,0 z M-14,-14 h-7 a7,7 0 0 0 7,10 M14,-14 h7 a7,7 0 0 1 -7,10 M-3,6 h6 v7 h7 v5 h-20 v-5 h7 z"
    for i, (name, value, base) in enumerate(items):
        x = i * (tw + gap)
        letter = rank(value, base)
        color = GOLD if letter.startswith("S") else "#9ece6a" if letter == "A" else "#7aa2f7" if letter == "B" else MUTED
        out.append(f'<g transform="translate({x},0)"><rect width="{tw}" height="{h}" rx="6" fill="{BG}"/>'
                   f'<path transform="translate({tw / 2},38)" d="{cup}" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" fill-opacity="0.85"/>'
                   f'<text x="{tw / 2}" y="16" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="11" font-weight="700" fill="{color}">{letter}</text>'
                   f'<text x="{tw / 2}" y="84" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="13" font-weight="600" fill="{TEXT}">{name}</text>'
                   f'<text x="{tw / 2}" y="104" text-anchor="middle" font-family="Segoe UI,sans-serif" font-size="12" fill="{MUTED}">{value:,}</text></g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    USER, REPOS = collect()
    with open("top-langs.svg", "w", encoding="utf-8") as f:
        f.write(languages_card(REPOS))
    with open("trophies.svg", "w", encoding="utf-8") as f:
        f.write(trophies_card(USER))
    print(f"Wrote top-langs.svg and trophies.svg from {len(REPOS)} repos")
