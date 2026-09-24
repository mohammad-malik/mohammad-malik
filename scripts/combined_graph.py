"""Render a combined personal + work GitHub contribution graph as an SVG.

Each account is fetched with its own token so private contributions are
included as bare daily counts (no repo names or content).
"""
import json
import os
import urllib.request
from datetime import date

for _name in ("PERSONAL_TOKEN", "WORK_TOKEN"):
    if not os.environ.get(_name, "").strip():
        print(f"WARNING: {_name} is empty; falling back to the Actions token, which undercounts")
PERSONAL = ("mohammad-malik", os.environ.get("PERSONAL_TOKEN", "").strip() or os.environ["GITHUB_TOKEN"])
WORK = ("mohammadmalik-avirso", os.environ.get("WORK_TOKEN", "").strip() or os.environ["GITHUB_TOKEN"])
OUT = os.environ.get("OUT_FILE", "combined-graph.svg")

QUERY = """
query($login: String!) {
  viewer { login }
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# (light, dark) palettes, levels 1-4
GREEN = [("#9be9a8", "#0e4429"), ("#40c463", "#006d32"), ("#30a14e", "#26a641"), ("#216e39", "#39d353")]
BLUE = [("#b6d7ff", "#0c2d6b"), ("#6cb2ff", "#1158c7"), ("#2f81f7", "#388bfd"), ("#0a4fb3", "#79c0ff")]


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"{login}: {body['errors']}")
    print(f"{login}: token belongs to {body['data']['viewer']['login']}")
    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def thresholds(counts):
    nz = sorted(c for c in counts.values() if c > 0)
    if not nz:
        return [1, 1, 1]
    return [nz[int(len(nz) * q)] for q in (0.25, 0.5, 0.75)]


def level(count, th):
    if count == 0:
        return 0
    return 1 + sum(count > t for t in th)


def main():
    p, w = fetch(*PERSONAL), fetch(*WORK)
    # The work token can see private days but may be blind to SSO-protected org
    # activity; the public view catches that. Take the larger count per day.
    public_w = fetch(WORK[0], PERSONAL[1])
    w = {d: max(w.get(d, 0), public_w.get(d, 0)) for d in set(w) | set(public_w)}
    days = sorted(set(p) | set(w))
    tp, tw = thresholds(p), thresholds(w)

    cell, gap, left, top = 11, 3, 32, 58
    step = cell + gap
    first = date.fromisoformat(days[0])
    offset = (first.weekday() + 1) % 7  # Sunday = row 0
    ncols = (len(days) + offset + 6) // 7
    width = left + ncols * step + 16
    height = top + 7 * step + 44

    css = [".t{font:600 14px -apple-system,Segoe UI,sans-serif;fill:#1f2328}",
           ".s{font:11px -apple-system,Segoe UI,sans-serif;fill:#59636e}",
           ".e{fill:#ebedf0}"]
    dark = [".t{fill:#e6edf3}", ".s{fill:#9198a1}", ".e{fill:#161b22}"]
    for i, (g, b) in enumerate(zip(GREEN, BLUE), 1):
        css += [f".p{i}{{fill:{g[0]}}}", f".w{i}{{fill:{b[0]}}}"]
        dark += [f".p{i}{{fill:{g[1]}}}", f".w{i}{{fill:{b[1]}}}"]

    sp, sw = sum(p.values()), sum(w.values())
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<style>{''.join(css)}@media (prefers-color-scheme:dark){{{''.join(dark)}}}</style>",
        f'<text class="t" x="{left}" y="20">Combined activity: @{PERSONAL[0]} (personal) + @{WORK[0]} (work)</text>',
        f'<text class="s" x="{left}" y="38">{sp:,} personal · {sw:,} work · {sp + sw:,} total in the last year</text>',
    ]
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text class="s" x="0" y="{top + row * step + 9}">{name}</text>')

    last_month = None
    for i, d in enumerate(days):
        col, row = divmod(i + offset, 7)
        x, y = left + col * step, top + row * step
        dt = date.fromisoformat(d)
        if row == 0 or i == 0:
            if dt.month != last_month and col < ncols - 2:
                out.append(f'<text class="s" x="{x}" y="{top - 6}">{dt.strftime("%b")}</text>')
                last_month = dt.month
        lp, lw = level(p.get(d, 0), tp), level(w.get(d, 0), tw)
        tip = f"<title>{d}: {p.get(d, 0)} personal, {w.get(d, 0)} work</title>"
        if lp and lw:  # split square: personal top-left, work bottom-right
            out.append(f'<g>{tip}<polygon class="p{lp}" points="{x},{y} {x + cell},{y} {x},{y + cell}"/>'
                       f'<polygon class="w{lw}" points="{x + cell},{y} {x + cell},{y + cell} {x},{y + cell}"/></g>')
        else:
            cls = f"p{lp}" if lp else f"w{lw}" if lw else "e"
            out.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2">{tip}</rect>')

    ly = top + 7 * step + 22
    out.append(f'<rect class="p3" x="{left}" y="{ly - 9}" width="{cell}" height="{cell}" rx="2"/>')
    out.append(f'<text class="s" x="{left + 16}" y="{ly}">Personal</text>')
    out.append(f'<rect class="w3" x="{left + 80}" y="{ly - 9}" width="{cell}" height="{cell}" rx="2"/>')
    out.append(f'<text class="s" x="{left + 96}" y="{ly}">Work</text>')
    out.append(f'<text class="s" x="{left + 140}" y="{ly}">Split square = both on the same day · updated {date.today()}</text>')
    out.append("</svg>")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"Wrote {OUT}: {sp} personal, {sw} work")


if __name__ == "__main__":
    main()
