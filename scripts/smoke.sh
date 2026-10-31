#!/bin/bash
# Build the app image and exercise it over HTTP: health, deny-all, authed publish, poll.
# Usage: scripts/smoke.sh [arch-label]   (needs docker, curl)
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$(sed -n 's/^version: "\(.*\)"$/\1/p' ntfy/config.yaml)"
docker build -q --build-arg "BUILD_VERSION=$VERSION" --build-arg "BUILD_ARCH=${1:-amd64}" -t ntfy-app-smoke ntfy >/dev/null
D="$(mktemp -d)"; N=ntfy-smoke; U=http://127.0.0.1:18093
trap 'docker rm -f $N >/dev/null 2>&1 || true; rm -rf "$D"' EXIT
cat > "$D/options.json" <<'JSON'
{"base_url":"http://127.0.0.1:18093","auth_default_access":"deny-all","enable_login":true,"enable_signup":false,"cache_duration":"12h","log_level":"info","ios_push_forwarding":false,"users":[{"username":"ha","password":"secret","role":"admin"}]}
JSON
docker rm -f $N >/dev/null 2>&1 || true
docker run -d --name $N -p 127.0.0.1:18093:80 -v "$D:/data" ntfy-app-smoke >/dev/null
fail() { echo "SMOKE FAIL: $1" >&2; docker logs $N >&2; exit 1; }
for _ in $(seq 30); do curl -fs $U/v1/health | grep -q '"healthy":true' && break; sleep 1; done
curl -fs $U/v1/health | grep -q '"healthy":true' || fail "not healthy"
[ "$(curl -s -o /dev/null -w '%{http_code}' -d hi $U/washer)" = 403 ] || fail "anonymous publish not denied"
# users are provisioned just after the health check turns green
for _ in $(seq 15); do curl -fs -u ha:secret -d "wash done" $U/washer >/dev/null && ok=1 && break; sleep 1; done
[ "${ok:-}" = 1 ] || fail "authenticated publish failed"
docker restart $N >/dev/null
for _ in $(seq 30); do curl -fs $U/v1/health >/dev/null && break; sleep 1; done
curl -fs -u ha:secret "$U/washer/json?poll=1&since=all" | grep -q 'wash done' || fail "message lost across restart"
echo "SMOKE OK: health, deny-all, authed publish, persistence across restart"
