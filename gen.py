"""Builds profile.svg, a terminal-style GitHub stats card. Run: GH_TOKEN=... python gen.py"""
import json, os, urllib.request
from collections import OrderedDict
from datetime import date, timedelta
from xml.sax.saxutils import escape

LOGIN = "vaibhav375"
NAME = "Vaibhav Handoo"
BIO = ["Builds AI agents that show their work:", "RAG, RL post-training, compliance", "kernels and network tooling."]
SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS"}  # markup/notebook bytes drown out real code
# Shown when portrait.png is absent; drop a square photo in the repo to get the reel's line-art face.
MONOGRAM = [
    "██╗   ██╗██╗  ██╗",
    "██║   ██║██║  ██║",
    "██║   ██║███████║",
    "╚██╗ ██╔╝██╔══██║",
    " ╚████╔╝ ██║  ██║",
    "  ╚═══╝  ╚═╝  ╚═╝",
]

QUERY = """query($login:String!){ user(login:$login){
  repos: repositories(ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC, first:100){ totalCount nodes{
    stargazerCount languages(first:10, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color } } } } }
  all: repositories(ownerAffiliations:OWNER, privacy:PUBLIC){ totalCount }
  contributionsCollection{ totalCommitContributions totalPullRequestContributions
    contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } } } } }"""

GREENS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
FG, DIM, ACC, BG, PANEL = "#c9d1d9", "#8b949e", "#39d353", "#0d1117", "#161b22"
W = 860


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}"},
    )
    body = json.load(urllib.request.urlopen(req))
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def streak(days):
    counts = [d["contributionCount"] for d in days]
    if counts and counts[-1] == 0:  # today not over yet; don't break the streak
        counts = counts[:-1]
    n = 0
    for c in reversed(counts):
        if not c:
            break
        n += 1
    return n


def portrait_lines(path="portrait.png", cols=34, rows=17):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    if not os.path.exists(path):
        return None
    img = ImageOps.autocontrast(ImageOps.grayscale(Image.open(path)).resize((cols, rows)))
    ramp = " .:-=+*#%@"
    px = img.load()
    return ["".join(ramp[(255 - px[x, y]) * (len(ramp) - 1) // 255] for x in range(cols)) for y in range(rows)]


def t(x, y, s, fill=FG, size=13, weight="normal", anchor="start"):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(s))}</text>'


def prompt(y, cmd):
    return (f'<text x="32" y="{y}" fill="{FG}" font-size="13"><tspan fill="{ACC}">vaibhav@github</tspan>'
            f'<tspan fill="{DIM}"> ~ $ </tspan>{escape(cmd)}</text>')


def build(u):
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    nonzero = sorted(d["contributionCount"] for d in days if d["contributionCount"])
    cuts = [nonzero[len(nonzero) * q // 4] for q in (1, 2, 3)] if nonzero else [1, 2, 3]

    def level(c):
        return 0 if not c else 1 + sum(c > k for k in cuts)

    stars = sum(r["stargazerCount"] for r in u["repos"]["nodes"])
    langs = {}
    colors = {}
    for r in u["repos"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            if n in SKIP_LANGS:
                continue
            langs[n] = langs.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or DIM
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    total_bytes = sum(s for _, s in top) or 1

    months = OrderedDict()
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["contributionCount"]
    months = list(months.items())[-12:]

    out = []
    # window chrome
    out.append(f'<rect x="0.5" y="0.5" width="{W-1}" height="H" rx="12" fill="{BG}" stroke="#30363d"/>')
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{22 + i*18}" cy="20" r="6" fill="{c}"/>')
    out.append(t(W // 2, 24, f"{LOGIN} — zsh", DIM, 12, anchor="middle"))
    out.append(f'<line x1="0" y1="38" x2="{W}" y2="38" stroke="#30363d"/>')

    # contributions heatmap
    y = 66
    out.append(prompt(y, "./contributions.sh"))
    gx, gy, cell = 32, y + 16, 15
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            dow = date.fromisoformat(d["date"]).isoweekday() % 7
            out.append(f'<rect x="{gx + wi*cell}" y="{gy + dow*cell}" width="12" height="12" rx="2" fill="{GREENS[level(d["contributionCount"])]}"><title>{d["date"]}: {d["contributionCount"]}</title></rect>')
    y = gy + 7 * cell + 18
    out.append(t(32, y, f'{cal["totalContributions"]:,} contributions in the last year', DIM, 12))
    lx = W - 32 - 5 * 14 - 60
    out.append(t(lx - 6, y, "less", DIM, 11, anchor="end"))
    for i, g in enumerate(GREENS):
        out.append(f'<rect x="{lx + i*14}" y="{y-10}" width="11" height="11" rx="2" fill="{g}"/>')
    out.append(t(lx + 5 * 14 + 2, y, "more", DIM, 11))

    # whoami: portrait/monogram + bio | stats + monthly bars
    y += 40
    out.append(prompt(y, "whoami"))
    top_y = y + 16
    out.append(f'<rect x="32" y="{top_y}" width="300" height="250" rx="8" fill="{PANEL}" stroke="#30363d"/>')
    art = portrait_lines()
    if art:
        for i, line in enumerate(art):
            out.append(t(182, top_y + 22 + i * 9, line, FG, 9, anchor="middle").replace("<text", '<text xml:space="preserve" letter-spacing="1"'))
        ty = top_y + 22 + len(art) * 9 + 14
    else:
        for i, line in enumerate(MONOGRAM):
            out.append(t(182, top_y + 36 + i * 17, line, ACC, 16, anchor="middle").replace("<text", '<text xml:space="preserve"'))
        ty = top_y + 36 + len(MONOGRAM) * 17 + 18
    out.append(t(48, ty, NAME, FG, 15, "bold"))
    out.append(t(48, ty + 18, f"@{LOGIN}", DIM, 12))
    for i, line in enumerate(BIO):
        out.append(t(48, ty + 42 + i * 17, line, FG, 12))

    stats = [
        ("contributions", f'{cal["totalContributions"]:,}'),
        ("commits", f'{cc["totalCommitContributions"]:,}'),
        ("pull requests", f'{cc["totalPullRequestContributions"]:,}'),
        ("public repos", u["all"]["totalCount"]),
        ("stars earned", stars),
        ("day streak", streak(days)),
    ]
    sx, sw, sh = 352, 152, 58
    for i, (label, val) in enumerate(stats):
        x, yy = sx + (i % 3) * (sw + 10), top_y + (i // 3) * (sh + 10)
        out.append(f'<rect x="{x}" y="{yy}" width="{sw}" height="{sh}" rx="8" fill="{PANEL}" stroke="#30363d"/>')
        out.append(t(x + 14, yy + 30, val, ACC, 22, "bold"))
        out.append(t(x + 14, yy + 48, label, DIM, 11))

    by = top_y + 2 * (sh + 10)
    bw_total, bh = 3 * sw + 20, 250 - 2 * (sh + 10)
    out.append(f'<rect x="{sx}" y="{by}" width="{bw_total}" height="{bh}" rx="8" fill="{PANEL}" stroke="#30363d"/>')
    out.append(t(sx + 14, by + 20, "contributions / month", DIM, 11))
    peak = max((c for _, c in months), default=1) or 1
    slot = (bw_total - 28) / len(months)
    base = by + bh - 22
    for i, (m, c) in enumerate(months):
        h = max(2, (bh - 56) * c / peak)
        x = sx + 14 + i * slot
        out.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{slot - 6:.1f}" height="{h:.1f}" rx="2" fill="{ACC}" opacity="{0.45 + 0.55 * c / peak:.2f}"><title>{m}: {c}</title></rect>')
        out.append(t(f"{x + (slot - 6) / 2:.1f}", base + 14, date.fromisoformat(m + "-01").strftime("%b")[0], DIM, 10, anchor="middle"))

    # language bar
    y = top_y + 250 + 40
    out.append(prompt(y, "./stack.sh"))
    y += 16
    x = 32.0
    bar_w = W - 64
    out.append(f'<clipPath id="bar"><rect x="32" y="{y}" width="{bar_w}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">')
    for n, s in top:
        w = bar_w * s / total_bytes
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="10" fill="{colors[n]}"/>')
        x += w
    out.append("</g>")
    y += 32
    col = bar_w / 3
    for i, (n, s) in enumerate(top):
        lx, ly = 32 + (i % 3) * col, y + (i // 3) * 22
        out.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{colors[n]}"/>')
        out.append(t(lx + 16, ly, f"{n}  ", FG, 12).replace("</text>", f'<tspan fill="{DIM}">{100 * s / total_bytes:.1f}%</tspan></text>'))
    y += ((len(top) + 2) // 3) * 22 + 20

    # idle prompt with blinking cursor
    out.append(prompt(y, ""))
    out.append(f'<rect x="{32 + 19 * 7.8:.0f}" y="{y - 12}" width="8" height="15" fill="{ACC}"><animate attributeName="opacity" values="1;0;1" dur="1.1s" repeatCount="indefinite"/></rect>')
    height = y + 26

    svg = "\n".join(out).replace('height="H"', f'height="{height - 1}"')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">\n{svg}\n</svg>\n'
    )


if __name__ == "__main__":
    svg = build(fetch())
    assert svg.count("<svg") == 1 and "NaN" not in svg
    with open("profile.svg", "w") as f:
        f.write(svg)
    print("wrote profile.svg")
