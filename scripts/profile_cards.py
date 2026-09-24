"""Render Top Languages, Trophies and Statistics cards for personal + work.

Replaces the public github-readme-stats, github-profile-trophy and
pixel-profile services. Work data comes from WORK_TOKEN, which must be
authorized for the employer's SSO; only totals are shown, never repo names.
"""
import json
import math
import os
import urllib.request
from html import escape

PERSONAL = "mohammad-malik"
WORK = "mohammadmalik-avirso"
PERSONAL_TOKEN = os.environ.get("PERSONAL_TOKEN", "").strip() or os.environ["GITHUB_TOKEN"]
WORK_TOKEN = os.environ.get("WORK_TOKEN", "").strip()

# Tokyo Night, to match the rest of the profile
BG, TITLE, TEXT, MUTED, GOLD = "#1a1b27", "#70a5fd", "#c0caf5", "#8a93b8", "#e0af68"
FONT = 'font-family="Segoe UI,sans-serif"'

# Notebook files embed plot and output data, which swamps real code size
EXCLUDE = {"Jupyter Notebook"}

LANGS = "languages(first: 20, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }"
PERSONAL_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection { contributionCalendar { totalContributions } }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount %s }
    }
  }
}
""" % LANGS
# viewer, not user(login): only the account's own token sees its SSO-protected org work
WORK_QUERY = """
query($after: String) {
  viewer {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first: 100, after: $after, includeUserRepositories: true,
                              contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { %s }
    }
  }
}
""" % LANGS
CALENDAR_QUERY = "query($login: String!) { user(login: $login) { contributionsCollection { contributionCalendar { totalContributions } } } }"


def call(url, token, payload=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body


def gql(token, query, **variables):
    return call("https://api.github.com/graphql", token, {"query": query, "variables": variables})["data"]


def paged(token, query, root, conn, **variables):
    first, nodes, after = None, [], None
    while True:
        page = gql(token, query, after=after, **variables)[root]
        first = first or page
        nodes += page[conn]["nodes"]
        info = page[conn]["pageInfo"]
        if not info["hasNextPage"]:
            return first, nodes
        after = info["endCursor"]


def commit_count(login, token):
    return call(f"https://api.github.com/search/commits?q=author:{login}", token)["total_count"]


def personal_stats():
    user, repos = paged(PERSONAL_TOKEN, PERSONAL_QUERY, "user", "repositories", login=PERSONAL)
    return {
        "repos": repos,
        "Commits": commit_count(PERSONAL, PERSONAL_TOKEN),
        "Pull Requests": user["pullRequests"]["totalCount"],
        "Issues": user["issues"]["totalCount"],
        "Repositories": user["repositories"]["totalCount"],
        "Stars": sum(r["stargazerCount"] for r in repos),
        "Followers": user["followers"]["totalCount"],
        "Contributions (last year)": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
    }


def work_stats():
    # The public view carries private daily counts that the work token may not
    public = gql(PERSONAL_TOKEN, CALENDAR_QUERY, login=WORK)["user"]
    calendar = public["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    if not WORK_TOKEN:
        print("WARNING: WORK_TOKEN is empty; work cards will only show public totals")
        return {"repos": [], "Commits": 0, "Pull Requests": 0, "Issues": 0, "Repositories": 0,
                "Stars": 0, "Followers": 0, "Contributions (last year)": calendar}
    viewer, repos = paged(WORK_TOKEN, WORK_QUERY, "viewer", "repositoriesContributedTo")
    return {
        "repos": repos,
        "Commits": commit_count(WORK, WORK_TOKEN),
        "Pull Requests": viewer["pullRequests"]["totalCount"],
        "Issues": viewer["issues"]["totalCount"],
        "Repositories": viewer["repositoriesContributedTo"]["totalCount"],
        "Stars": 0,  # stars on employer repos aren't this person's
        "Followers": viewer["followers"]["totalCount"],
        "Contributions (last year)": calendar,
    }


def language_shares(repos, top=6):
    sizes, colors = {}, {"Other": "#565f89"}
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
    total = sum(v for _, v in langs) or 1
    return [(n, v / total, colors[n]) for n, v in langs]


def donut(ox, label, shares):
    cx, cy, r_out, r_in = ox + 80, 125, 62, 40
    out = [f'<text x="{cx}" y="58" text-anchor="middle" {FONT} font-size="13" font-weight="600" fill="{MUTED}">{label}</text>']
    if not shares:
        out.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" {FONT} font-size="12" fill="{MUTED}">No data</text>')
        return out
    angle = -math.pi / 2
    for name, share, color in shares:
        sweep = 2 * math.pi * share
        if sweep >= 2 * math.pi - 1e-6:
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{(r_out + r_in) / 2}" fill="none" stroke="{color}" stroke-width="{r_out - r_in}"/>')
        else:
            a2 = angle + sweep
            large = 1 if sweep > math.pi else 0
            p = lambda rad, a: (cx + rad * math.cos(a), cy + rad * math.sin(a))
            x1, y1 = p(r_out, angle); x2, y2 = p(r_out, a2)
            x3, y3 = p(r_in, a2); x4, y4 = p(r_in, angle)
            out.append(f'<path fill="{color}" d="M{x1:.2f},{y1:.2f} A{r_out},{r_out} 0 {large} 1 {x2:.2f},{y2:.2f} '
                       f'L{x3:.2f},{y3:.2f} A{r_in},{r_in} 0 {large} 0 {x4:.2f},{y4:.2f} Z"/>')
        angle += sweep
    for i, (name, share, color) in enumerate(shares):
        y = 80 + i * 17
        out.append(f'<circle cx="{ox + 172}" cy="{y - 4}" r="5" fill="{color}"/>')
        out.append(f'<text x="{ox + 184}" y="{y}" {FONT} font-size="12" fill="{TEXT}">'
                   f'{escape(name)} <tspan fill="{MUTED}">{100 * share:.1f}%</tspan></text>')
    return out


def languages_card(p, w):
    width, height = 700, 215
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<rect width="{width}" height="{height}" rx="6" fill="{BG}"/>',
           f'<text x="20" y="30" {FONT} font-size="17" font-weight="600" fill="{TITLE}">Most Used Languages</text>',
           f'<line x1="350" y1="50" x2="350" y2="195" stroke="#2a2e45"/>']
    out += donut(10, f"Personal · @{PERSONAL}", language_shares(p["repos"]))
    out += donut(360, f"Work · @{WORK}", language_shares(w["repos"]))
    out.append("</svg>")
    return "".join(out)


RANKS = [("SSS", 16), ("SS", 8), ("S", 4), ("A", 2), ("B", 1), ("C", 0.5)]
TROPHIES = [("Commits", 100), ("Pull Requests", 10), ("Issues", 10), ("Repositories", 10), ("Stars", 10), ("Followers", 10)]


def rank(value, base):
    for letter, mult in RANKS:
        if value >= base * mult:
            return letter
    return "?"


def trophies_card(p, w):
    tw, gap, h = 110, 10, 132
    width = len(TROPHIES) * (tw + gap) - gap
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h}" viewBox="0 0 {width} {h}">']
    cup = "M-14,-18 h28 v10 a14,14 0 0 1 -28,0 z M-14,-14 h-7 a7,7 0 0 0 7,10 M14,-14 h7 a7,7 0 0 1 -7,10 M-3,6 h6 v7 h7 v5 h-20 v-5 h7 z"
    for i, (name, base) in enumerate(TROPHIES):
        x, total = i * (tw + gap), p[name] + w[name]
        letter = rank(total, base)
        color = GOLD if letter.startswith("S") else "#9ece6a" if letter == "A" else "#7aa2f7" if letter == "B" else MUTED
        out.append(f'<g transform="translate({x},0)"><rect width="{tw}" height="{h}" rx="6" fill="{BG}"/>'
                   f'<path transform="translate({tw / 2},38)" d="{cup}" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" fill-opacity="0.85"/>'
                   f'<text x="{tw / 2}" y="16" text-anchor="middle" {FONT} font-size="11" font-weight="700" fill="{color}">{letter}</text>'
                   f'<text x="{tw / 2}" y="82" text-anchor="middle" {FONT} font-size="13" font-weight="600" fill="{TEXT}">{name}</text>'
                   f'<text x="{tw / 2}" y="101" text-anchor="middle" {FONT} font-size="13" font-weight="600" fill="{TEXT}">{total:,}</text>'
                   f'<text x="{tw / 2}" y="119" text-anchor="middle" {FONT} font-size="10" fill="{MUTED}">{p[name]:,} personal · {w[name]:,} work</text></g>')
    out.append("</svg>")
    return "".join(out)


STATS = ["Contributions (last year)", "Commits", "Pull Requests", "Issues", "Repositories", "Stars", "Followers"]


def stats_card(p, w):
    width, row = 700, 26
    height = 78 + len(STATS) * row
    cols = [("Personal", 430), ("Work", 540), ("Total", 650)]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<rect width="{width}" height="{height}" rx="6" fill="{BG}"/>',
           f'<text x="20" y="30" {FONT} font-size="17" font-weight="600" fill="{TITLE}">GitHub Statistics · @{PERSONAL} + @{WORK}</text>']
    for label, x in cols:
        out.append(f'<text x="{x}" y="60" text-anchor="end" {FONT} font-size="12" font-weight="600" fill="{MUTED}">{label}</text>')
    for i, name in enumerate(STATS):
        y = 88 + i * row
        if i % 2 == 0:
            out.append(f'<rect x="12" y="{y - 17}" width="{width - 24}" height="{row}" rx="4" fill="#20223a"/>')
        out.append(f'<text x="24" y="{y}" {FONT} font-size="13" fill="{TEXT}">{name}</text>')
        for (label, x), v in zip(cols, (p[name], w[name], p[name] + w[name])):
            weight = ' font-weight="700"' if label == "Total" else ""
            out.append(f'<text x="{x}" y="{y}" text-anchor="end" {FONT} font-size="13"{weight} fill="{TEXT}">{v:,}</text>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    p, w = personal_stats(), work_stats()
    for fname, svg in (("top-langs.svg", languages_card(p, w)), ("trophies.svg", trophies_card(p, w)),
                       ("stats.svg", stats_card(p, w))):
        with open(fname, "w", encoding="utf-8") as f:
            f.write(svg)
    print("personal:", {k: v for k, v in p.items() if k != "repos"})
    print("work:", {k: v for k, v in w.items() if k != "repos"})
