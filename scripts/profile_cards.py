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


def language_sizes(repos):
    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name in EXCLUDE:
                continue
            sizes[name] = sizes.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#888888"
    return sizes, colors


def combined_shares(p, w, top=7):
    # Each account gets equal weight; raw bytes would let a few large work
    # repos drown out everything personal
    shares, colors = {}, {"Other": "#565f89"}
    accounts = [language_sizes(a["repos"]) for a in (p, w)]
    accounts = [a for a in accounts if a[0]]
    for sizes, cols in accounts:
        total = sum(sizes.values())
        colors.update(cols)
        for name, v in sizes.items():
            shares[name] = shares.get(name, 0) + v / total / len(accounts)
    ranked = sorted(shares.items(), key=lambda kv: -kv[1])
    langs = ranked[:top]
    rest = sum(v for _, v in ranked[top:])
    if rest:
        langs.append(("Other", rest))
    return [(n, v, colors[n]) for n, v in langs]


def donut(cx, cy, r_out, r_in, shares):
    out, angle = [], -math.pi / 2
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
    return out


RANKS = [("SSS", 16), ("SS", 8), ("S", 4), ("A", 2), ("B", 1), ("C", 0.5)]
TROPHIES = [("Commits", 100), ("Pull Requests", 10), ("Issues", 10), ("Repositories", 10), ("Stars", 10), ("Followers", 10)]
CUP = "M-14,-18 h28 v10 a14,14 0 0 1 -28,0 z M-14,-14 h-7 a7,7 0 0 0 7,10 M14,-14 h7 a7,7 0 0 1 -7,10 M-3,6 h6 v7 h7 v5 h-20 v-5 h7 z"


def rank(value, base):
    for letter, mult in RANKS:
        if value >= base * mult:
            return letter
    return "?"


def overview_card(p, w):
    """Languages donut on the left, 3x2 trophy grid on the right, one image."""
    width, height, lw = 880, 290, 390
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<rect width="{lw}" height="{height}" rx="8" fill="{BG}"/>',
           f'<text x="22" y="34" {FONT} font-size="17" font-weight="600" fill="{TITLE}">Most Used Languages</text>',
           f'<text x="22" y="54" {FONT} font-size="11" fill="{MUTED}">Personal + work, each weighted equally</text>']
    shares = combined_shares(p, w)
    out += donut(110, 170, 78, 50, shares)
    for i, (name, share, color) in enumerate(shares):
        y = 106 + i * 19
        out.append(f'<circle cx="222" cy="{y - 4}" r="5" fill="{color}"/>')
        out.append(f'<text x="234" y="{y}" {FONT} font-size="12.5" fill="{TEXT}">'
                   f'{escape(name)} <tspan fill="{MUTED}">{100 * share:.1f}%</tspan></text>')

    tw, th, gap = 156, 139, 12
    ox = lw + gap
    for i, (name, base) in enumerate(TROPHIES):
        x, y = ox + (i % 3) * (tw + gap), (i // 3) * (th + gap)
        total = p[name] + w[name]
        letter = rank(total, base)
        color = GOLD if letter.startswith("S") else "#9ece6a" if letter == "A" else "#7aa2f7" if letter == "B" else MUTED
        cx = x + tw / 2
        out.append(f'<rect x="{x}" y="{y}" width="{tw}" height="{th}" rx="8" fill="{BG}"/>'
                   f'<text x="{cx}" y="{y + 20}" text-anchor="middle" {FONT} font-size="11" font-weight="700" fill="{color}">{letter}</text>'
                   f'<path transform="translate({cx},{y + 44})" d="{CUP}" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" fill-opacity="0.85"/>'
                   f'<text x="{cx}" y="{y + 86}" text-anchor="middle" {FONT} font-size="13" font-weight="600" fill="{TEXT}">{name}</text>'
                   f'<text x="{cx}" y="{y + 106}" text-anchor="middle" {FONT} font-size="14" font-weight="700" fill="{TEXT}">{total:,}</text>'
                   f'<text x="{cx}" y="{y + 125}" text-anchor="middle" {FONT} font-size="10.5" fill="{MUTED}">{p[name]:,} personal · {w[name]:,} work</text>')
    out.append("</svg>")
    return "".join(out)


STATS = [("Total Stars Earned", "Stars"), ("Total Commits", "Commits"), ("Total PRs", "Pull Requests"),
         ("Total Issues", "Issues"), ("Contributions (last year)", "Contributions (last year)")]
FONT_FILE = os.path.join(os.path.dirname(__file__), "assets", "press-start-2p.woff2")


def stats_card(p, w):
    """Pixel-style card matching the old pixel-profile look, with a personal/work split."""
    import base64
    with open(FONT_FILE, "rb") as f:
        font = base64.b64encode(f.read()).decode()
    cyan, width, row = "#00FFFF", 1226, 40
    height = 250 + len(STATS) * row
    px = 'font-family="Pixel" fill="#00FFFF"'
    cols = [("Personal", 790), ("Work", 960), ("Total", 1130)]
    title = "Mohammad Malik's GitHub Stats"
    tx0, tx1 = 84, 84 + len(title) * 24 + 12
    bottom = height - 46
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           f'<defs><style>@font-face{{font-family:Pixel;src:url(data:font/woff2;base64,{font})}}</style>'
           '<linearGradient id="bg" x1="1" y1="1" x2="0" y2="0">'
           '<stop offset="0" stop-color="#126134"/><stop offset="0.6" stop-color="#231e38" stop-opacity="0.42"/></linearGradient></defs>',
           f'<rect width="{width}" height="{height}" fill="url(#bg)"/>',
           f'<path d="M{tx0},46 H50 V{bottom} H1176 V46 H{tx1}" fill="none" stroke="{cyan}" stroke-width="3"/>',
           f'<text x="{tx0 + 6}" y="58" {px} font-size="24">{escape(title)}</text>']
    for label, x in cols:
        out.append(f'<text x="{x}" y="112" text-anchor="end" {px} font-size="16" fill-opacity="0.7">{label}</text>')
    y = 112
    for label, key in STATS:
        y += row
        out.append(f'<text x="94" y="{y}" {px} font-size="20">{escape(label)}:</text>')
        for (_, x), v in zip(cols, (p[key], w[key], p[key] + w[key])):
            out.append(f'<text x="{x}" y="{y}" text-anchor="end" {px} font-size="20">{v:,}</text>')
    y += 34
    out.append(f'<line x1="94" y1="{y}" x2="1130" y2="{y}" stroke="{cyan}" stroke-width="3" stroke-dasharray="14 6"/>')
    y += 42
    out.append(f'<text x="94" y="{y}" {px} font-size="20">Accounts:</text>')
    out.append(f'<text x="1130" y="{y}" text-anchor="end" {px} font-size="16">@{PERSONAL} + @{WORK}</text>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    p, w = personal_stats(), work_stats()
    for fname, svg in (("overview.svg", overview_card(p, w)), ("stats.svg", stats_card(p, w))):
        with open(fname, "w", encoding="utf-8") as f:
            f.write(svg)
    print("personal:", {k: v for k, v in p.items() if k != "repos"})
    print("work:", {k: v for k, v in w.items() if k != "repos"})
