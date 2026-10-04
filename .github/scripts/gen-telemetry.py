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
    X0, Y0, P = 64, 86, 15.5
    cells, months = [], []
    prev_month = None
    for wi, week in enumerate(cal):
        x = X0 + wi * P
        m = week[0]["d"][5:7]
        if m != prev_month:
            months.append(f'    <text class="mono" x="{x:.0f}" y="80" font-size="9" fill="#5C6773" letter-spacing="1">{datetime.date.fromisoformat(week[0]["d"]).strftime("%b").upper()}</text>')
            prev_month = m
        for day in week:
            r = day["w"]
            y = Y0 + r * P
            l = lvl(day["c"])
            delay = wi * .022 + r * .008
            glow = ' filter="url(#cglow)"' if l >= 4 else ''
            cells.append(f'    <rect class="cell" x="{x:.0f}" y="{y:.0f}" width="13" height="13" rx="2.5" fill="{CELLCOLORS[l]}"{glow} style="animation-delay:{delay:.2f}s"/>')
    daylabels = ""
    for r, name in ((1, "MON"), (3, "WED"), (5, "FRI")):
        daylabels += f'    <text class="mono" x="58" y="{Y0 + r * P + 11:.0f}" font-size="9" fill="#5C6773" text-anchor="end" letter-spacing="1">{name}</text>\n'
    legend = '    <text class="mono" x="30" y="222" font-size="9.5" fill="#5C6773" letter-spacing="1.5">LESS</text>\n'
    for i, c in enumerate(CELLCOLORS):
        legend += f'    <rect x="{62 + i * 16}" y="211" width="12" height="12" rx="2.5" fill="{c}"/>\n'
    legend += '    <text class="mono" x="168" y="222" font-size="9.5" fill="#5C6773" letter-spacing="1.5">MORE</text>\n'
    cells_s = "".join(cells)
    months_s = "".join(months)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="940" height="244" viewBox="0 0 940 244">
  <defs>
    <linearGradient id="cedge" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#00F5FF" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#00F5FF" stop-opacity="0.85"/>
      <stop offset="1" stop-color="#FF00FF" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#00F5FF" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#00F5FF" stop-opacity="0.35"/>
      <stop offset="1" stop-color="#00F5FF" stop-opacity="0"/>
    </linearGradient>
    <filter id="cglow" x="-120%" y="-120%" width="340%" height="340%">
      <feGaussianBlur stdDeviation="3"/>
    </filter>
    <style><![CDATA[
      .mono  {{ font-family:'Cascadia Code','JetBrains Mono',Consolas,'Courier New',monospace; }}
      .cell  {{ animation: cellin .4s ease-out backwards; transform-box: fill-box; transform-origin: center; }}
      .pulse {{ animation: pulse 2.2s ease-in-out infinite; }}
      .sweep {{ animation: sweepx 14s linear infinite; }}
      .run   {{ animation: run 8s linear infinite; }}
      @keyframes cellin {{ 0% {{opacity:0;transform:scale(.4)}} 100% {{opacity:1;transform:scale(1)}} }}
      @keyframes pulse  {{ 0%,100% {{opacity:1}} 50% {{opacity:.3}} }}
      @keyframes sweepx {{ 0% {{transform:translateX(0);opacity:0}} 8% {{opacity:.6}} 92% {{opacity:.6}} 100% {{transform:translateX(830px);opacity:0}} }}
      @keyframes run    {{ 0% {{transform:translateX(-8px);opacity:0}} 12% {{opacity:.9}} 88% {{opacity:.9}} 100% {{transform:translateX(900px);opacity:0}} }}
    ]]></style>
  </defs>

  <rect x="8" y="8" width="924" height="228" rx="12" fill="#070A12" stroke="#1F2A37" stroke-width="1"/>
  <rect x="8" y="8" width="924" height="2" rx="1" fill="url(#cedge)" opacity="0.8"/>
  <g stroke="#2A3A54" stroke-width="1.4" fill="none" opacity="0.9">
    <path d="M15 23 V15 H23"/><path d="M917 15 H925 V23"/>
    <path d="M15 221 V229 H23"/><path d="M917 229 H925 V221"/>
  </g>

  <text class="mono" x="26" y="38" font-size="12" fill="#00F5FF" letter-spacing="3">CONTRIBUTION.GRID</text>
  <text class="mono" x="204" y="38" font-size="12" fill="#5C6773" letter-spacing="3">//</text>
  <text class="mono" x="230" y="38" font-size="12" fill="#C9D1D9" letter-spacing="2.5">LAST_365_DAYS</text>
  <circle class="pulse" cx="890" cy="34" r="3" fill="#39FF14"/>
  <text class="mono" x="910" y="38" font-size="11" fill="#5C6773" letter-spacing="1.5" text-anchor="end"><tspan fill="#00F5FF" font-weight="700">{data["total"]}</tspan> CONTRIBUTIONS · <tspan fill="#FF6CF0" font-weight="700">{data["active"]}</tspan> ACTIVE DAYS</text>
  <line x1="20" y1="50" x2="920" y2="50" stroke="#1F2A37" stroke-width="1"/>

{daylabels}{months_s}
{cells_s}

  <rect class="sweep" x="64" y="70" width="26" height="130" fill="url(#sweep)" opacity="0"/>

{legend}  <text class="mono" x="910" y="222" font-size="9.5" fill="#5C6773" letter-spacing="1" text-anchor="end">BEST DAY <tspan fill="#FFD700" font-weight="700">{data["best"]}</tspan> · {data["best_date"]} · AUTO-SYNC DAILY</text>

  <circle class="run" cx="10" cy="9" r="2.2" fill="#00F5FF" filter="url(#cglow)"/>
</svg>
'''
    open(OUT_CONTRIB, "w", encoding="utf-8", newline="\n").write(svg)
    print(f"contrib.svg - {sum(len(w) for w in cal)} cells, thresholds {t1}/{t2}/{t3}/{t4}")

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
