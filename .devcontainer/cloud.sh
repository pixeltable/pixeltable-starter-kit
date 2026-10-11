#!/usr/bin/env bash
# Deploy a starter app to Pixeltable Cloud and call it once.
#
#   bash .devcontainer/cloud.sh                          # chat-agent on a free trial (pxt new), no account
#   bash .devcontainer/cloud.sh video-search
#   bash .devcontainer/cloud.sh chat-agent pxt://org:db  # a database you already have, after `pxt login`
#
# Safe to rerun: `pxt new` returns the trial this machine already has, and each update applies only what changed.
set -euo pipefail

app="${1:-chat-agent}"
uri="${2:-}"
case "$app" in
  chat-agent) target=agent ;;
  video-search) target=videointel ;;
  *) echo "usage: bash .devcontainer/cloud.sh [chat-agent|video-search] [pxt://org:db]" >&2; exit 2 ;;
esac
cd "$(dirname "$0")/../$app"

pxt() { uv run --quiet pxt "$@"; }
json() { python3 -c "import json, sys; d = json.load(sys.stdin); print($1)"; }

if [ -z "$uri" ]; then
  if ! trial="$(pxt new --json)"; then
    echo "If pxt new says this machine is signed in, pass one of your databases instead:" >&2
    echo "  bash .devcontainer/cloud.sh $app pxt://<org>:main" >&2
    exit 1
  fi
  uri="pxt://$(json 'd["org"] + ":" + d["db"]' <<<"$trial")"
  claim_url="$(json 'd["claim_url"] or ""' <<<"$trial")"
fi
org="${uri#pxt://}"
org="${org%%:*}"

# The CLI finds a hosted database through its entry in pixeltable.toml.
grep -qF "name = '$uri'" pixeltable.toml || printf "\n[[pixeltable.database]]\nname = '%s'\n" "$uri" >>pixeltable.toml

# A new database refuses updates while it provisions, which takes a minute or two.
for _ in $(seq 60); do
  state="$(pxt db status "$uri" --json | json 'd["current"]["state"]')"
  [ "$state" = AVAILABLE ] && break
  case "$state" in FAILED | STOPPED) echo "$uri is $state; see: pxt db status $uri" >&2; exit 1 ;; esac
  echo "==> $uri is $state, waiting"
  sleep 10
done

if [ "$app" = chat-agent ] && [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  pxt secret set "pxt://$org" "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
fi

echo "==> Uploading $app to $uri"
pxt db update "$uri" -f
echo "==> Creating tables"
pxt schema update app.py "$uri" -f
echo "==> Starting the service"
pxt service update app.py "$uri" -f
endpoint="$(pxt service list "$uri" --json | json "[s['endpoint'] for s in d if s['name'] == '$target'][0]")"
echo "==> $target is live at $endpoint"

if [ "$app" = chat-agent ]; then
  # The trial's key never leaves the CLI's cache; read it here only to make one call.
  api_url="$(pxt whoami --json | json 'd["api_url"]')"
  uv run --quiet python - "$endpoint" "$api_url" <<'EOF'
import os
import sys

import httpx
from pixeltable.service import session_cache

endpoint, api_url = sys.argv[1], sys.argv[2]
key = os.environ.get("PIXELTABLE_API_KEY") or getattr(session_cache.load_credential(api_url), "api_key", None)
if key is None:
    sys.exit("Skipped the test call: set PIXELTABLE_API_KEY to a key for this organization.")
client = httpx.Client(base_url=endpoint, headers={"X-api-key": key}, timeout=120)
doc = {"title": "hello", "source": "cloud.sh", "body": "Pixeltable stores, transforms, and serves data in one app.py."}
inserted = client.post("/api/knowledge", json=doc)
print(f"POST /api/knowledge -> {inserted.status_code} {inserted.text[:200]}")
found = client.get("/api/knowledge/search", params={"query_text": "What does Pixeltable do?", "limit": 1})
print(f"GET /api/knowledge/search -> {found.status_code} {found.text[:200]}")
sys.exit(0 if inserted.is_success and found.is_success else 1)
EOF
fi

if [ -n "${claim_url:-}" ]; then
  echo
  echo "Claim this trial to keep it past 48 hours (one sign-in): $claim_url"
fi
