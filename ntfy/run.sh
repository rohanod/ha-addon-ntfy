#!/bin/sh
# Maps Supervisor options (/data/options.json) to ntfy env config, then runs the
# unmodified upstream `ntfy serve`. Paths overridable for tests.
set -eu

OPTS="${NTFY_APP_OPTIONS:-/data/options.json}"
DATA="${NTFY_APP_DATA:-/data}"
PORT="${NTFY_APP_PORT:-80}"

opt() { jq -r --arg k "$1" 'if .[$k] == null then empty else .[$k] | tostring end' "$OPTS"; }

BASE_URL="$(opt base_url)"
IOS="$(opt ios_push_forwarding)"

if [ "$IOS" = "true" ] && [ -z "$BASE_URL" ]; then
  echo "ERROR: ios_push_forwarding requires base_url (the URL your iPhone uses, e.g. http://192.168.1.10:8093)" >&2
  exit 1
fi

export NTFY_LISTEN_HTTP=":$PORT"
export NTFY_CACHE_FILE="$DATA/cache.db"
export NTFY_AUTH_FILE="$DATA/user.db"
export NTFY_AUTH_DEFAULT_ACCESS="$(opt auth_default_access)"
export NTFY_ENABLE_LOGIN="$(opt enable_login)"
export NTFY_ENABLE_SIGNUP="$(opt enable_signup)"
export NTFY_CACHE_DURATION="$(opt cache_duration)"
export NTFY_LOG_LEVEL="$(opt log_level)"
[ -n "$BASE_URL" ] && export NTFY_BASE_URL="$BASE_URL"
if [ "$IOS" = "true" ]; then
  export NTFY_UPSTREAM_BASE_URL="https://ntfy.sh"
  TOKEN="$(opt upstream_access_token)"
  [ -n "$TOKEN" ] && export NTFY_UPSTREAM_ACCESS_TOKEN="$TOKEN"
fi

ntfy serve &
PID=$!
trap 'kill -TERM "$PID" 2>/dev/null' TERM INT

# Users can only be managed once the server has created the auth database.
if [ "$(jq '.users // [] | length' "$OPTS")" -gt 0 ]; then
  i=0
  until wget -q -O /dev/null "http://127.0.0.1:$PORT/v1/health"; do
    kill -0 "$PID" 2>/dev/null || { echo "ntfy exited during startup" >&2; exit 1; }
    i=$((i + 1)); [ "$i" -le 60 ] || { echo "ntfy not healthy after 60s" >&2; exit 1; }
    sleep 1
  done
  jq -r '.users[] | [.username, .role] | @tsv' "$OPTS" | while IFS="$(printf '\t')" read -r name role; do
    pw="$(jq -r --arg u "$name" '.users[] | select(.username == $u) | .password' "$OPTS")"
    NTFY_PASSWORD="$pw" ntfy user add --role="$role" --ignore-exists "$name" >/dev/null
    NTFY_PASSWORD="$pw" ntfy user change-pass "$name" >/dev/null
    ntfy user change-role "$name" "$role" >/dev/null
    echo "user provisioned: $name ($role)"
  done
fi

rc=0; wait "$PID" || rc=$?
# a TERM trap interrupts the first wait; wait again for the real exit
if kill -0 "$PID" 2>/dev/null; then wait "$PID" || rc=$?; fi
exit "$rc"
