#!/usr/bin/env python3
"""Generate assets/telemetry.svg from telemetry.tpl.svg + live GitHub data.

Data source: GitHub GraphQL API (contributionsCollection, repo languages).
Auth: GH_TOKEN env (GITHUB_TOKEN in Actions). If the fetch fails, falls back
to telemetry-seed.json so the asset is never blanked.
"""
import json, os, sys, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TPL = os.path.join(ROOT, "assets", "telemetry.tpl.svg")
OUT = os.path.join(ROOT, "assets", "telemetry.svg")
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
   contributionCalendar{ totalContributions weeks{ contributionDays{ contributionCount date } } }
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

    weeks = cc["contributionCalendar"]["weeks"][-26:]
    weekly = [sum(dd["contributionCount"] for dd in w["contributionDays"]) for w in weeks]

    return {
        "stars": stars, "commits": commits,
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "collabs": cc["totalRepositoriesWithContributedCommits"],
        "total": cc["contributionCalendar"]["totalContributions"],
        "cur": cur, "long": longest, "long_dates": long_dates,
        "langs": langs_out, "weekly": weekly,
        "since": cc["contributionYears"][-1] if cc["contributionYears"] else 2024,
    }

ACCENTS = ["#00F5FF", "#FF6CF0", "#FFD700", "#39FF14", "#7B8CFF"]

def render(data):
    tpl = open(TPL, encoding="utf-8").read()

    rows = []
    labels = ["TOTAL STARS", "TOTAL COMMITS", "PULL REQUESTS", "ISSUES", "REPO COLLABS"]
    vals = [data["stars"], data["commits"], data["prs"], data["issues"], data["collabs"]]
    for i, (lab, v) in enumerate(zip(labels, vals)):
        y = 122 + i * 40
        a = ACCENTS[i]
        rows.append(f'''    <rect x="40" y="{y - 11}" width="3" height="16" rx="1.5" fill="{a}"/>
    <text class="mono" x="54" y="{y}" font-size="11.5" fill="#93A4BC" letter-spacing="1.5">{lab}</text>
    <text class="mono" x="296" y="{y + 2}" font-size="19" font-weight="800" fill="{a}" text-anchor="end">{v}</text>
    <line x1="40" y1="{y + 14}" x2="296" y2="{y + 14}" stroke="#141B2B" stroke-width="1"/>''')
    combat = "\n".join(rows)

    lrows = []
    for i, l in enumerate(data["langs"][:6]):
        y = 118 + i * 31
        a = ACCENTS[i % len(ACCENTS)]
        filled = max(1, round(l["pct"] / 10))
        segs = "".join(
            f'<rect class="seg" x="{j * 17}" y="0" width="14" height="9" rx="1.5" fill="{a if j < filled else "#16233A"}" '
            f'style="animation-delay:{.2 + i * .12 + j * .04:.2f}s"/>' for j in range(10))
        lrows.append(f'''    <text class="mono" x="652" y="{y}" font-size="11" fill="#C9D1D9">{l["name"].upper()}</text>
    <text class="mono" x="908" y="{y}" font-size="11" font-weight="700" fill="{a}" text-anchor="end">{l["pct"]}%</text>
    <g transform="translate(652,{y + 7})">{segs}</g>''')
    langrows = "\n".join(lrows)

    mx = max(data["weekly"]) or 1
    spark = []
    for i, v in enumerate(data["weekly"]):
        h = max(2, round(v / mx * 13))
        x = 430 + i * 6.7
        spark.append(f'    <rect x="{x}" y="{302 - h}" width="5" height="{h}" rx="1" '
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
    print(f"telemetry.svg written - commits:{data['commits']} prs:{data['prs']} streak:{data['cur']}/{data['long']}")

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
            sys.exit("no token and no seed - refusing to blank telemetry.svg")
        data = json.load(open(SEED))
    render(data)

if __name__ == "__main__":
    main()
