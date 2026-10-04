#!/usr/bin/env bash
# Regenerates assets/statusbar.svg from assets/statusbar.tpl.svg with live stats.
# Fail-safe: if any fetch fails, keeps the previous generated file.
set -u

cd "$(dirname "$0")/../.."
TPL="assets/statusbar.tpl.svg"
OUT="assets/statusbar.svg"
USER="manikkDev"

fetch() { curl -fsS --max-time 20 -H "Accept: application/vnd.github+json" "$1"; }

# followers + repo count
USER_JSON="$(fetch "https://api.github.com/users/$USER")" || exit 0
FOLLOWERS="$(printf '%s' "$USER_JSON" | python -c 'import sys,json;print(json.load(sys.stdin)["followers"])')"
REPOS="$(printf '%s' "$USER_JSON" | python -c 'import sys,json;print(json.load(sys.stdin)["public_repos"])')"

# total stars across owned public repos
STARS="$(fetch "https://api.github.com/users/$USER/repos?per_page=100&type=owner" | python -c 'import sys,json;print(sum(r["stargazers_count"] for r in json.load(sys.stdin)))')"

# komarev profile-views count (SVG text nodes: number duplicated for mask)
VIEWS="$(curl -fsS --max-time 20 "https://komarev.com/ghpvc/?username=$USER" | python -c '
import sys, re
s = sys.stdin.read()
texts = re.findall(r">([^<]+)<", s)
digits = [t.strip() for t in texts if t.strip().isdigit()]
n = len(digits)
count = "".join(digits[: n // 2]) if n >= 2 and digits[: n // 2] == digits[n // 2 :] else (digits[-1] if digits else "")
print(count)')"

# fail-safe: require all four values
if [ -z "${FOLLOWERS:-}" ] || [ -z "${REPOS:-}" ] || [ -z "${STARS:-}" ] || [ -z "${VIEWS:-}" ]; then
  echo "missing a value — keeping existing $OUT"
  exit 0
fi

sed -e "s/{{VIEWS}}/$VIEWS/g" \
    -e "s/{{FOLLOWERS}}/$FOLLOWERS/g" \
    -e "s/{{STARS}}/$STARS/g" \
    -e "s/{{REPOS}}/$REPOS/g" \
    "$TPL" > "$OUT"

echo "views=$VIEWS followers=$FOLLOWERS stars=$STARS repos=$REPOS"
