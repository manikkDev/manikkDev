#!/usr/bin/env python3
"""Generate assets/telemetry.svg + assets/contrib.svg from live GitHub data."""
import json, os, sys, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TPL = os.path.join(ROOT, "assets", "telemetry.tpl.svg")
OUT = os.path.join(ROOT, "assets", "telemetry.svg")
OUT_CONTRIB = os.path.join(ROOT, "assets", "contrib.svg")
SEED = os.path.join(ROOT, ".github", "scripts", "telemetry-seed.json")
USER = "manikkDev"

Q = """
query($login:String!){
 user(login:$login){
  contributionsCollection{
   contributionYears
   totalPullRequestContributions
   totalIssueContributions
   totalRepositoriesWithContributedCommits
   contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount date weekday } } }
  }
  repositories(ownerAffiliations:OWNER,isFork:false,first:100,orderBy:{field:PUSHED_AT,direction:DESC}){
   nodes{ stargazerCount languages(first:8,orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color } } } }
  }
 }
}"""

Q_COMMITS_YEAR = """
query($login:String!,$from:DateTime!,$to:DateTime!){
 user(login:$login){
  contributionsCollection(from:$from,to:$to){ totalCommitContributions }
 }
}"""

def gql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "telemetry-gen"})
    return json.load(urllib.request.urlopen(req, timeout=30))

def fetch(token):
    d = gql(Q, {"login": USER}, token)["data"]["user"]
    cc = d["contributionsCollection"]
    commits = 0
    for y in cc["contributionYears"]:
        r = gql(Q_COMMITS_YEAR, {"login": USER,
                "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"}, token)
        commits += r["data"]["user"]["contributionsCollection"]["totalCommitContributions"]
    days = [day for w in cc["contributionCalendar"]["weeks"] for day in w["contributionDays"]]
    longest = run = 0
    lend, lendate = 0, None
    for day in days:
        if day["contributionCount"] > 0:
            run += 1
            longest = max(longest, run)
            if run > lend:
                lend = run
                lendate = day["date"]
        else:
            run = 0
    cur = 0
    for day in reversed(days):
        if day["contributionCount"] > 0:
            cur += 1
        else:
            break
    long_dates = "—"
    if lendate:
        end_d = datetime.date.fromisoformat(lendate)
        start_d = end_d - datetime.timedelta(days=lend - 1)
        long_dates = f"{start_d.strftime('%b %d').upper()}-{end_d.strftime('%b %d').upper()}"
    langs, total_sz, stars = {}, 0, 0
    for repo in d["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
            total_sz += e["size"]
    top = sorted(langs.items(), key=lambda x: -x[1])[:6]
    langs_out = [{"name": n, "pct": round(100 * s / total_sz, 2)} for n, s in top]
    weeks = cc["contributionCalendar"]["weeks"]
    weekly = [sum(dd["contributionCount"] for dd in w["contributionDays"]) for w in weeks[-26:]]
    cal = [[{"c": dd["contributionCount"], "d": dd["date"], "w": dd["weekday"]}
            for dd in w["contributionDays"]] for w in weeks]
    active = sum(1 for day in days if day["contributionCount"] > 0)
    best = max(days, key=lambda x: x["contributionCount"])
    return {
        "stars": stars, "commits": commits,
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "collabs": cc["totalRepositoriesWithContributedCommits"],
        "total": cc["contributionCalendar"]["totalContributions"],
        "cur": cur, "long": longest, "long_dates": long_dates,
        "langs": langs_out, "weekly": weekly, "cal": cal,
        "active": active, "best": best["contributionCount"],
        "best_date": best["date"],
        "since": cc["contributionYears"][-1] if cc["contributionYears"] else 2024,
    }

ACCENTS = ["#00F5FF", "#FF6CF0", "#FFD700", "#39FF14", "#7B8CFF"]
CELLCOLORS = ["#121B2C", "#0C4A57", "#0E8C9B", "#15B8CC", "#00F5FF", "#FF6CF0"]

def _shade(hexv, f):
    r, g, b = int(hexv[1:3], 16), int(hexv[3:5], 16), int(hexv[5:7], 16)
    return f"#{int(r*f):02X}{int(g*f):02X}{int(b*f):02X}"

def render_telemetry(data):
    tpl = open(TPL, encoding="utf-8").read()
    rows = []
    labels = ["TOTAL STARS", "TOTAL COMMITS", "PULL REQUESTS", "ISSUES", "REPO COLLABS"]
    vals = [data["stars"], data["commits"], data["prs"], data["issues"], data["collabs"]]
    for i, (lab, v) in enumerate(zip(labels, vals)):
        y = 122 + i * 40
        a = ACCENTS[i]
        rows.append(f"""    <rect x="40" y="{y - 11}" width="3" height="15" rx="1.5" fill="{a}"/>
    <text class="mono" x="54" y="{y}" font-size="11.5" fill="#93A4BC" letter-spacing="1.2">{lab}</text>
    <text class="mono" x="296" y="{y + 2}" font-size="19" font-weight="800" fill="{a}" text-anchor="end">{v}</text>
    <line x1="40" y1="{y + 14}" x2="296" y2="{y + 14}" stroke="#141B2B" stroke-width="1"/>""")
    combat = "\n".join(rows)
    lrows = []
    for i, l in enumerate(data["langs"][:6]):
        y = 118 + i * 31
        a = ACCENTS[i % len(ACCENTS)]
        filled = max(1, round(l["pct"] / 10))
        segs = "".join(
            f'<rect class="seg" x="{j * 14}" y="0" width="11" height="8" rx="1.5" fill="{a if j < filled else "#16233A"}" '
            f'style="animation-delay:{.2 + i * .1 + j * .04:.2f}s"/>' for j in range(10))
        lrows.append(f"""    <text class="mono" x="652" y="{y}" font-size="11" fill="#C9D1D9">{l["name"].upper()}</text>
    <text class="mono" x="908" y="{y}" font-size="11" font-weight="700" fill="{a}" text-anchor="end">{l["pct"]}%</text>
    <g transform="translate(652,{y + 7})">{segs}</g>""")
    langrows = "\n".join(lrows)
    mx = max(data["weekly"]) or 1
    spark = []
    for i, v in enumerate(data["weekly"]):
        h = max(2, round(v / mx * 13))
        x = 430 + i * 6.7
        spark.append(f'    <rect x="{x:.0f}" y="{302 - h}" width="5" height="{h}" rx="1" '
                     f'fill="{"#00F5FF" if v == mx else "#233146"}" opacity="{0.9 if v else 0.5}"/>')
    spark = "\n".join(spark)
    ring = round(min(data["cur"] / max(data["long"], 1), 1) * 226.2, 1)
    out = (tpl.replace("__COMBAT_ROWS__", combat)
              .replace("__LANG_ROWS__", langrows)
              .replace("__SPARK__", spark)
              .replace("__TOTAL__", str(data["total"]))
              .replace("__CUR__", str(data["cur"]))
              .replace("__LONG__", str(data["long"]))
              .replace("__LONGDATES__", data["long_dates"])
              .replace("__RING_LEN__", str(ring))
              .replace("__SINCE__", str(data["since"]))
              .replace("__SYNC__", datetime.date.today().strftime("%Y-%m-%d")))
    open(OUT, "w", encoding="utf-8", newline="\n").write(out)
    print(f"telemetry.svg - commits:{data['commits']} streak:{data['cur']}/{data['long']}")

def render_contrib(data):
    """Isometric neon skyline of the 53-week contribution calendar."""
    cal = data["cal"]
    counts = sorted(d["c"] for w in cal for d in w if d["c"] > 0)
    def pct(p):
        return counts[int(len(counts) * p)] if counts else 1
    t1, t2, t3, t4 = pct(.30), pct(.60), pct(.85), pct(.97)
    def lvl(c):
        if c <= 0: return 0
        if c >= t4: return 5
        if c >= t3: return 4
        if c >= t2: return 3
        if c >= t1: return 2
        return 1

    OX, OY, CW, CH = 286, 88, 8.0, 4.5
    items = []
    for i, week in enumerate(cal):
        for day in week:
            items.append((i + day["w"], i, day["w"], day["c"]))
    items.sort()

    floor, bars, parts = [], [], []
    for s, i, j, c in items:
        x, y = OX + (i - j) * CW, OY + (i + j) * CH
        floor.append(f'    <polygon points="{x:.1f},{y - CH:.1f} {x + CW:.1f},{y:.1f} {x:.1f},{y + CH:.1f} {x - CW:.1f},{y:.1f}" fill="#0D1424" stroke="#1B2946" stroke-width="0.4"/>')
        if c <= 0:
            continue
        h = 4 + min(c, 20) * 2.6
        l = lvl(c)
        col = CELLCOLORS[l]
        d1, d2 = _shade(col, .55), _shade(col, .30)
        delay = s * .014
        glow = ' filter="url(#sglow)"' if l >= 4 else ''
        bars.append(f'''    <g class="rise" style="animation-delay:{delay:.2f}s"{glow}>
      <polygon points="{x:.1f},{y - CH - h:.1f} {x + CW:.1f},{y - h:.1f} {x:.1f},{y + CH - h:.1f} {x - CW:.1f},{y - h:.1f}" fill="{col}"/>
      <polygon points="{x - CW:.1f},{y - h:.1f} {x:.1f},{y + CH - h:.1f} {x:.1f},{y + CH:.1f} {x - CW:.1f},{y:.1f}" fill="{d1}"/>
      <polygon points="{x + CW:.1f},{y - h:.1f} {x:.1f},{y + CH - h:.1f} {x:.1f},{y + CH:.1f} {x + CW:.1f},{y:.1f}" fill="{d2}"/>
    </g>''')

    stats = [
        ("TOTAL_CONTRIB", data["total"], "#00F5FF"),
        ("ACTIVE_DAYS", data["active"], "#FF6CF0"),
        ("BEST_DAY", f'{data["best"]}c', "#FFD700"),
        ("STREAK_CUR", f'{data["cur"]}d', "#39FF14"),
    ]
    statcol = ""
    for k, (lab, v, a) in enumerate(stats):
        y = 150 + k * 54
        statcol += f'''    <rect x="800" y="{y - 22}" width="3" height="30" rx="1.5" fill="{a}"/>
    <text class="mono" x="814" y="{y - 6}" font-size="9.5" fill="#5C6773" letter-spacing="1.5">{lab}</text>
    <text class="mono" x="814" y="{y + 14}" font-size="21" font-weight="800" fill="{a}">{v}</text>
'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="940" height="430" viewBox="0 0 940 430">
  <defs>
    <linearGradient id="skedge" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#00F5FF" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#00F5FF" stop-opacity="0.85"/>
      <stop offset="1" stop-color="#FF00FF" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="horizon" cx="0.45" cy="0.5" r="0.55">
      <stop offset="0" stop-color="#00F5FF" stop-opacity="0.10"/>
      <stop offset="0.6" stop-color="#FF00FF" stop-opacity="0.05"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="ssweep" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#00F5FF" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#00F5FF" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#00F5FF" stop-opacity="0"/>
    </linearGradient>
    <filter id="sglow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="2.6"/>
    </filter>
    <style><![CDATA[
      .mono  {{ font-family:'Cascadia Code','JetBrains Mono',Consolas,'Courier New',monospace; }}
      .rise  {{ animation: rise .55s cubic-bezier(.2,.8,.3,1.1) backwards; }}
      .pulse {{ animation: pulse 2.2s ease-in-out infinite; }}
      .sweep {{ animation: sweepx 13s linear infinite; }}
      .run   {{ animation: run 8s linear infinite; }}
      .pt    {{ animation-name: prise; animation-timing-function: linear; animation-iteration-count: infinite; opacity:0; }}
      @keyframes rise   {{ 0% {{opacity:0;transform:translateY(16px)}} 100% {{opacity:1;transform:translateY(0)}} }}
      @keyframes pulse  {{ 0%,100% {{opacity:1}} 50% {{opacity:.3}} }}
      @keyframes sweepx {{ 0% {{transform:translateX(0);opacity:0}} 10% {{opacity:1}} 90% {{opacity:1}} 100% {{transform:translateX(900px);opacity:0}} }}
      @keyframes run    {{ 0% {{transform:translateX(-8px);opacity:0}} 12% {{opacity:.9}} 88% {{opacity:.9}} 100% {{transform:translateX(900px);opacity:0}} }}
      @keyframes prise  {{ 0% {{transform:translateY(0);opacity:0}} 15% {{opacity:.7}} 80% {{opacity:.3}} 100% {{transform:translateY(-220px);opacity:0}} }}
    ]]></style>
  </defs>

  <rect x="8" y="8" width="924" height="414" rx="12" fill="#070A12" stroke="#1F2A37" stroke-width="1"/>
  <rect x="8" y="8" width="924" height="2" rx="1" fill="url(#skedge)" opacity="0.8"/>
  <ellipse cx="430" cy="240" rx="380" ry="200" fill="url(#horizon)"/>
  <g stroke="#2A3A54" stroke-width="1.4" fill="none" opacity="0.9">
    <path d="M15 23 V15 H23"/><path d="M917 15 H925 V23"/>
    <path d="M15 407 V415 H23"/><path d="M917 415 H925 V407"/>
  </g>

  <text class="mono" x="26" y="38" font-size="12" fill="#00F5FF" letter-spacing="3">CONTRIBUTION.SKYLINE</text>
  <text class="mono" x="240" y="38" font-size="12" fill="#5C6773" letter-spacing="3">//</text>
  <text class="mono" x="266" y="38" font-size="12" fill="#C9D1D9" letter-spacing="2.5">LAST_365_DAYS</text>
  <circle class="pulse" cx="890" cy="34" r="3" fill="#39FF14"/>
  <text class="mono" x="910" y="38" font-size="11" fill="#5C6773" letter-spacing="1.5" text-anchor="end">ISO-RENDER · AUTO-SYNC DAILY</text>
  <line x1="20" y1="50" x2="920" y2="50" stroke="#1F2A37" stroke-width="1"/>

{"".join(floor)}
{"".join(bars)}

  <rect class="sweep" x="20" y="60" width="30" height="310" fill="url(#ssweep)" opacity="0"/>
  <circle class="pt" cx="300" cy="380" r="1.6" fill="#00F5FF" style="animation-duration:9s;animation-delay:-2s"/>
  <circle class="pt" cx="420" cy="385" r="1.3" fill="#FF00FF" style="animation-duration:11s;animation-delay:-6s"/>
  <circle class="pt" cx="560" cy="382" r="1.7" fill="#00F5FF" style="animation-duration:8s;animation-delay:-4s"/>
  <circle class="pt" cx="680" cy="386" r="1.4" fill="#FFD700" style="animation-duration:12s;animation-delay:-8s"/>

{statcol}
  <line x1="790" y1="80" x2="790" y2="380" stroke="#1F2A37" stroke-width="1"/>

  <line x1="20" y1="392" x2="920" y2="392" stroke="#141B2B" stroke-width="1"/>
  <text class="mono" x="30" y="410" font-size="9.5" fill="#5C6773" letter-spacing="1.5">PEAK <tspan fill="#FFD700" font-weight="700">{data["best"]} CONTRIBUTIONS</tspan> · {data["best_date"]}</text>
  <text class="mono" x="910" y="410" font-size="9.5" fill="#5C6773" letter-spacing="1" text-anchor="end">53 WEEKS · {len(cal) * 7} CELLS · STREAK <tspan fill="#39FF14" font-weight="700">{data["cur"]}D</tspan> / MAX <tspan fill="#FF6CF0" font-weight="700">{data["long"]}D</tspan></text>

  <circle class="run" cx="10" cy="9" r="2.2" fill="#00F5FF" filter="url(#sglow)"/>
</svg>
'''
    open(OUT_CONTRIB, "w", encoding="utf-8", newline="\n").write(svg)
    print(f"contrib.svg skyline - {sum(1 for w in cal for d in w if d['c'] > 0)} bars, thresholds {t1}/{t2}/{t3}/{t4}")

def render(data):
    render_telemetry(data)
    if data.get("cal"):
        render_contrib(data)

def main():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    data = None
    if token:
        try:
            data = fetch(token)
            json.dump(data, open(SEED, "w"))
        except Exception as e:
            print("graphql fetch failed, using seed:", e, file=sys.stderr)
    if data is None:
        if not os.path.exists(SEED):
            sys.exit("no token and no seed - refusing to blank assets")
        data = json.load(open(SEED))
    render(data)

if __name__ == "__main__":
    main()
