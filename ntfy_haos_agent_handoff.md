# Agent handoff — publish ntfy Home Assistant OS app

**Target:** `https://github.com/rohanod/ha-addon-ntfy` (owner `rohanod`).

**Task:** Create the repository if it does not exist and you have permission; otherwise update it, using the full source code below. Push the resulting working Home Assistant OS app to the `main` branch through the connected GitHub tool. Do not modify `rohanod/ha-addon-homebridge`: use it only as a reference for repo structure and upstream update automation. If a repo already exists, review its history and reconcile instead of overwriting user changes. Do not claim to have published anything until the tool confirms it.

## Product requirements

1. **HA OS native app:** Make `ntfy` installable in Settings → Apps/App Store from the custom repository `https://github.com/rohanod/ha-addon-ntfy`, using the official `binwiederhier/ntfy` container as the runtime base. Support `amd64` and `aarch64` at a minimum, only after verifying upstream supports each. Port `8093` on the HA host must serve the ntfy web UI and HTTP API. No port forwarding, external DNS, public proxy, TLS certificate, Docker Compose or separate host is required for LAN access. Document that port exposure is on the LAN, not restricted to loopback by default.
2. **Persistent data:** Keep ntfy message cache, attachments and app options across restarts, version updates and backups. Use Supervisor `/data/options.json` and `/data` storage. Retain sensible defaults and straightforward user configuration.
3. **iPhone caveat:** Default to local-only operation. Provide an opt-in outbound-only `ntfy.sh` upstream wake-up mode for timely iOS background alerts. Do **not** promise fully offline instant iPhone pushes or off-LAN message retrieval. No inbound port forwarding should be added. Verify currently documented upstream behaviour.
4. **Auto-updates:** A daily scheduled and manually dispatchable GitHub Actions workflow must check *stable upstream ntfy GitHub releases* and pin the official image to a specific stable version. Only update after tests, `amd64` Docker build, and an actual HTTP health/publish smoke test pass. Commit/publish successful version changes, so HA OS sees a newer app version. Explain that installing the update automatically requires enabling HA app **Auto update**. Do not use uncontrolled floating `latest` tags.
5. **Proper changelog:** On every version update, append the entire **upstream release body** for **every release skipped** between current and newest version, in reverse chronological order, with version, publication date and clickable upstream link. Include security and maintenance notes; never replace changelog with one-line 'Bump' entries. Preserve older history. A failed upstream query must not silently discard a release. Starting baseline below is ntfy v2.35.0 (observed 2026-10-31); recheck current upstream stable releases before final commit.
6. **Quality/security:** Do not introduce secrets in commits. Preserve upstream licensing notices, document LAN authentication trade-off, no WAN ingress. Validate app metadata, shell/YAML, Python updater tests and multi-architecture release support. Verify GitHub Actions permissions (write content) and repository settings. If protected branch prohibits direct commit, use a safe PR-based workflow rather than bypassing protection. Check for obvious incompatibilities with current HA OS Supervisor.
7. **Deliverable:** Complete functioning source repo, short implementation summary with link to the repo and commit SHA, tests actually run and their results, and any deployment limitations. Do not stop at a proposal. Do not alter unrelated repositories.

## Important notes about the code below

This is the complete previously prepared baseline, not a guarantee of a successful HA OS image build. The Python unit tests and shell/YAML syntax were checked locally, but a Docker/HA OS build has **not** been verified. Review and fix any issues before pushing. You may improve implementation if needed, but keep all functionality and preserve the entire changelog history. The initial workflow deliberately updates `ntfy/config.yaml`, `ntfy/Dockerfile`, and `ntfy/CHANGELOG.md` together.

## Required repository tree

```text
ha-addon-ntfy/
├── .github/workflows/update-ntfy.yml
├── .gitignore
├── README.md
├── repository.yaml
├── ntfy/
│   ├── CHANGELOG.md
│   ├── DOCS.md
│   ├── Dockerfile
│   ├── README.md
│   ├── config.yaml
│   └── run.sh
├── scripts/update_ntfy.py
└── tests/test_update_ntfy.py
```

## Complete file contents

Create each file at its exact relative path. Treat the code blocks below as source file contents (do not put headings or fence markers into the files).


### 1. `repository.yaml`

````yaml
name: Rohan's Home Assistant Apps
url: https://github.com/rohanod/ha-addon-ntfy
maintainer: rohanod
````


### 2. `ntfy/config.yaml`

````yaml
name: ntfy
slug: ntfy
description: Self-hosted ntfy notifications using the official ntfy container
version: "2.35.0"
url: https://github.com/rohanod/ha-addon-ntfy
stage: stable
arch:
  - amd64
  - aarch64
startup: services
boot: auto
init: false
ports:
  80/tcp: 8093
ports_description:
  80/tcp: ntfy web interface and HTTP API (LAN only; do not forward this port)
webui: http://[HOST]:[PORT:80]
watchdog: http://[HOST]:[PORT:80]/v1/health
panel_icon: mdi:bell-ring
options:
  base_url: ""
  ios_instant_notifications: false
schema:
  base_url: str?
  ios_instant_notifications: bool
````


### 3. `ntfy/Dockerfile`

````dockerfile
# Upstream version is deliberately pinned and updated by .github/workflows/update-ntfy.yml.
ARG NTFY_VERSION=2.35.0
FROM binwiederhier/ntfy:v${NTFY_VERSION}

# The upstream image is Alpine-based; jq reads Supervisor's options.json.
RUN apk add --no-cache jq
COPY run.sh /usr/local/bin/start-ntfy
RUN chmod 0755 /usr/local/bin/start-ntfy

ARG BUILD_ARCH
ARG BUILD_VERSION
LABEL io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      io.hass.version="${BUILD_VERSION}"

ENTRYPOINT ["/usr/local/bin/start-ntfy"]
````


### 4. `ntfy/run.sh`

````sh
#!/bin/sh
set -eu

CONFIG=/data/options.json
if [ ! -f "$CONFIG" ]; then
  echo "Error: missing $CONFIG (Supervisor app options)." >&2
  exit 1
fi

# Persist messages/attachments across app re-creations and upgrades.
mkdir -p /data/attachments
export NTFY_LISTEN_HTTP=":80"
export NTFY_CACHE_FILE="/data/cache.db"
export NTFY_ATTACHMENT_CACHE_DIR="/data/attachments"

BASE_URL="$(jq -er '.base_url // "" | strings' "$CONFIG")"
IOS="$(jq -er '.ios_instant_notifications // false | tostring' "$CONFIG")"

if [ -n "$BASE_URL" ]; then
  case "$BASE_URL" in
    http://*|https://*) ;;
    *) echo "Error: base_url must start with http:// or https://" >&2; exit 1 ;;
  esac
  case "$BASE_URL" in
    */) echo "Error: base_url must not have a trailing slash" >&2; exit 1 ;;
  esac
  export NTFY_BASE_URL="$BASE_URL"
fi

if [ "$IOS" = "true" ]; then
  if [ -z "$BASE_URL" ]; then
    echo "Error: Set base_url to the exact LAN URL subscribed to on the iPhone before enabling iOS instant notifications." >&2
    exit 1
  fi
  export NTFY_UPSTREAM_BASE_URL="https://ntfy.sh"
  echo "iOS upstream wake-up requests enabled (outbound ntfy.sh only; no port forwarding)."
else
  unset NTFY_UPSTREAM_BASE_URL || true
  echo "iOS upstream wake-up requests disabled; background iOS notifications may be delayed."
fi

echo "Starting ntfy on TCP 80; message cache stored in /data/cache.db."
exec /usr/bin/ntfy serve
````


### 5. `.github/workflows/update-ntfy.yml`

````yaml
name: Update ntfy upstream and changelog

on:
  schedule:
    - cron: "17 3 * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: ntfy-upstream-update
  cancel-in-progress: false

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout default branch
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.repository.default_branch }}

      - name: Test release synchroniser
        run: python3 -m unittest discover -s tests -v

      - name: Check all stable upstream releases and build changelog
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: python3 scripts/update_ntfy.py

      - name: Detect change
        id: change
        shell: bash
        run: |
          if git diff --quiet -- ntfy/config.yaml ntfy/Dockerfile ntfy/CHANGELOG.md; then
            echo 'updated=false' >> "$GITHUB_OUTPUT"
          else
            echo 'updated=true' >> "$GITHUB_OUTPUT"
          fi

      - name: Build pinned upstream Docker image (amd64)
        if: steps.change.outputs.updated == 'true'
        shell: bash
        run: |
          set -euo pipefail
          VERSION="$(sed -n 's/^version: "\(.*\)"$/\1/p' ntfy/config.yaml)"
          docker build --platform linux/amd64 \
            --build-arg BUILD_ARCH=amd64 \
            --build-arg "BUILD_VERSION=$VERSION" \
            -t ntfy-ha-app:ci ntfy

      - name: Smoke test ntfy HTTP health and publishing
        if: steps.change.outputs.updated == 'true'
        shell: bash
        run: |
          set -euo pipefail
          WORKDIR="$(mktemp -d)"
          trap 'docker rm -f ntfy-ha-ci >/dev/null 2>&1 || true; rm -rf "$WORKDIR"' EXIT
          printf '{"base_url":"","ios_instant_notifications":false}\n' > "$WORKDIR/options.json"
          docker run -d --rm --name ntfy-ha-ci -p 127.0.0.1:18093:80 \
            -v "$WORKDIR:/data" ntfy-ha-app:ci
          for n in $(seq 1 30); do
            if curl -fsS http://127.0.0.1:18093/v1/health >/dev/null; then
              curl -fsS --data 'CI test message' http://127.0.0.1:18093/ci-test >/dev/null
              echo 'ntfy health check and message publish passed'
              exit 0
            fi
            sleep 1
          done
          docker logs ntfy-ha-ci
          exit 1

      - name: Commit validated release update
        if: steps.change.outputs.updated == 'true'
        shell: bash
        run: |
          set -euo pipefail
          VERSION="$(sed -n 's/^version: "\(.*\)"$/\1/p' ntfy/config.yaml)"
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
          git add ntfy/config.yaml ntfy/Dockerfile ntfy/CHANGELOG.md
          git commit -m "chore: update ntfy to v$VERSION with upstream release notes"
          git push origin "HEAD:${{ github.event.repository.default_branch }}"
````


### 6. `scripts/update_ntfy.py`

````python
#!/usr/bin/env python3
"""Sync stable upstream ntfy releases, image pin, and complete HA app changelog.

No third-party Python packages required. Idempotent; fails closed if the
currently pinned release is missing from the upstream release history.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "ntfy/config.yaml"
DOCKERFILE = ROOT / "ntfy/Dockerfile"
CHANGELOG = ROOT / "ntfy/CHANGELOG.md"
API_URL = "https://api.github.com/repos/binwiederhier/ntfy/releases"
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
VERSION_LINE = re.compile(r'(?m)^version: "([0-9]+\.[0-9]+\.[0-9]+)"$')
IMAGE_ARG = re.compile(r'(?m)^ARG NTFY_VERSION=([0-9]+\.[0-9]+\.[0-9]+)$')


def version_tuple(raw: str) -> tuple[int, int, int] | None:
    match = SEMVER.fullmatch(raw)
    return tuple(map(int, match.groups())) if match else None


def http_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ha-addon-ntfy-update-checker",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def releases_since(
    current: str, fetch: Callable[[str], Any] = http_json
) -> list[dict[str, Any]]:
    """Return every *stable* newer release in ascending version order.

    Pagination continues until the pinned release is found, rather than
    assuming the newest N results cover the gap.
    """
    current_tuple = version_tuple(current)
    if current_tuple is None:
        raise ValueError(f"Not a stable semantic version: {current}")

    new: dict[str, dict[str, Any]] = {}
    found_current = False
    for page in range(1, 31):
        url = f"{API_URL}?per_page=100&page={page}"
        data = fetch(url)
        if not isinstance(data, list):
            raise RuntimeError("Invalid GitHub API response: expected a release list")
        for release in data:
            tag = release.get("tag_name", "")
            parsed = version_tuple(tag)
            if release.get("draft") or release.get("prerelease") or parsed is None:
                continue
            if parsed == current_tuple:
                found_current = True
            elif parsed > current_tuple:
                new[tag] = release
        if found_current:
            break
        if len(data) < 100:
            break
    if not found_current:
        raise RuntimeError(
            f"Pinned release v{current} not found in GitHub release history. "
            "Refusing to skip unknown releases; check upstream history manually."
        )
    return sorted(new.values(), key=lambda r: version_tuple(r["tag_name"]))


def replace_once(pattern: re.Pattern[str], contents: str, replacement: str) -> str:
    updated, count = pattern.subn(lambda _match: replacement, contents)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {pattern.pattern!r}, found {count}")
    return updated


def release_section(release: dict[str, Any]) -> str:
    tag = release["tag_name"]
    date = (release.get("published_at") or "").split("T")[0] or "date unknown"
    url = release.get("html_url") or f"https://github.com/binwiederhier/ntfy/releases/tag/{tag}"
    # The upstream GitHub release body is inserted in full, without filtering
    # security, fixes, or maintenance changes. Only whitespace is normalised.
    body = (release.get("body") or "No upstream release description supplied.").strip()
    return f"## {tag} — {date}\n\n[Official upstream release]({url})\n\n{body}\n"


def update_files(root: Path, releases: list[dict[str, Any]]) -> bool:
    if not releases:
        return False
    config = root / "ntfy/config.yaml"
    dockerfile = root / "ntfy/Dockerfile"
    changelog = root / "ntfy/CHANGELOG.md"
    config_text = config.read_text(encoding="utf-8")
    docker_text = dockerfile.read_text(encoding="utf-8")
    old_changelog = changelog.read_text(encoding="utf-8")
    match = VERSION_LINE.search(config_text)
    if not match:
        raise RuntimeError("No valid version in ntfy/config.yaml")
    old_version = match.group(1)
    docker_match = IMAGE_ARG.search(docker_text)
    if not docker_match or docker_match.group(1) != old_version:
        raise RuntimeError("Docker image version and HA app version differ")
    if not old_changelog.startswith("# Changelog\n"):
        raise RuntimeError("Missing changelog heading")
    if any(version_tuple(r["tag_name"]) <= version_tuple(old_version) for r in releases):
        raise RuntimeError("Attempt to apply an already-installed/older release")

    latest = releases[-1]["tag_name"].removeprefix("v")
    new_config = replace_once(VERSION_LINE, config_text, f'version: "{latest}"')
    new_docker = replace_once(IMAGE_ARG, docker_text, f"ARG NTFY_VERSION={latest}")
    new_sections = "\n".join(release_section(r) for r in reversed(releases))
    rest = old_changelog[len("# Changelog\n"):].lstrip("\n")
    new_changelog = f"# Changelog\n\n{new_sections}\n{rest}".rstrip() + "\n"

    # All assertions are complete before writing any files.
    config.write_text(new_config, encoding="utf-8")
    dockerfile.write_text(new_docker, encoding="utf-8")
    changelog.write_text(new_changelog, encoding="utf-8")
    print(f"Updated ntfy: {old_version} -> {latest} ({len(releases)} upstream release(s))")
    return True


def main() -> int:
    config_text = CONFIG.read_text(encoding="utf-8")
    match = VERSION_LINE.search(config_text)
    if not match:
        raise RuntimeError("Unable to parse version from ntfy/config.yaml")
    current = match.group(1)
    releases = releases_since(current)
    if not releases:
        print(f"ntfy v{current}: already up to date")
    else:
        update_files(ROOT, releases)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, urllib.error.URLError) as error:
        print(f"Update failed: {error}", file=sys.stderr)
        sys.exit(1)
````


### 7. `tests/test_update_ntfy.py`

````python
"""Offline tests for the updater, including missed releases and failure safety."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/update_ntfy.py'
SPEC = importlib.util.spec_from_file_location('update_ntfy', SCRIPT)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


def release(v, *, prerelease=False):
    return dict(tag_name=f'v{v}', draft=False, prerelease=prerelease,
                body=f'Full upstream changes for {v}.\n\n**Fixed:**\n\n* A relevant bug.\n',
                published_at='2026-11-01T12:00:00Z',
                html_url=f'https://github.com/binwiederhier/ntfy/releases/tag/v{v}')


class UpdateTests(unittest.TestCase):
    def test_no_update(self):
        self.assertEqual(updater.releases_since('2.35.0', lambda _: [release('2.35.0')]), [])

    def test_multiple_updates_preserved_order(self):
        found = updater.releases_since('2.35.0', lambda _: [release('2.36.0'), release('2.35.1'), release('2.35.0')])
        self.assertEqual([x['tag_name'] for x in found], ['v2.35.1', 'v2.36.0'])

    def test_skip_prereleases(self):
        found = updater.releases_since('2.35.0', lambda _: [release('2.36.0', prerelease=True), release('2.35.0')])
        self.assertEqual(found, [])

    def test_fail_when_current_missing(self):
        with self.assertRaises(RuntimeError):
            updater.releases_since('2.35.0', lambda _: [release('2.36.0')])

    def test_updater_writes_every_release_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'ntfy'
            folder.mkdir()
            (folder / 'config.yaml').write_text('name: ntfy\nversion: "2.35.0"\n')
            (folder / 'Dockerfile').write_text('ARG NTFY_VERSION=2.35.0\nFROM binwiederhier/ntfy:v${NTFY_VERSION}\n')
            (folder / 'CHANGELOG.md').write_text('# Changelog\n\n## v2.35.0\n\nOld notes.\n')
            self.assertTrue(updater.update_files(Path(tmp), [release('2.35.1'), release('2.36.0')]))
            changelog = (folder / 'CHANGELOG.md').read_text()
            self.assertLess(changelog.index('## v2.36.0'), changelog.index('## v2.35.1'))
            self.assertLess(changelog.index('## v2.35.1'), changelog.index('## v2.35.0'))
            self.assertIn('Full upstream changes for 2.36.0.', changelog)
            self.assertIn('Full upstream changes for 2.35.1.', changelog)
            self.assertIn('Old notes.', changelog)
            self.assertIn('version: "2.36.0"', (folder / 'config.yaml').read_text())
            self.assertIn('ARG NTFY_VERSION=2.36.0', (folder / 'Dockerfile').read_text())

    def test_inconsistent_image_version_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'ntfy'
            folder.mkdir()
            (folder / 'config.yaml').write_text('version: "2.35.0"\n')
            (folder / 'Dockerfile').write_text('ARG NTFY_VERSION=2.34.0\n')
            (folder / 'CHANGELOG.md').write_text('# Changelog\n')
            with self.assertRaises(RuntimeError):
                updater.update_files(Path(tmp), [release('2.36.0')])
            self.assertIn('2.35.0', (folder / 'config.yaml').read_text())


if __name__ == '__main__':
    unittest.main()
````


### 8. `ntfy/CHANGELOG.md`

````markdown
# Changelog

## v2.35.0 — 2026-10-30

[Official upstream release](https://github.com/binwiederhier/ntfy/releases/tag/v2.35.0)

This release keeps what a user already spent when their tier changes, and makes a tier's daily email limit a hard cap. It also fixes intermittent 403s under concurrent requests from the same IP, and the Matrix push gateway storing messages under a protected topic on SQLite.

**Security:**

* Reject Matrix push gateway requests whose push key does not name a valid topic. Publishing strips NUL bytes and invalid UTF-8 from the topic after authorization, so an anonymous push key like `/sec%00ret` was authorized against an unmatched topic and then stored under the protected topic `secret` (SQLite only; on PostgreSQL the request was denied; thanks to [Efe Çam](https://github.com/the-arma-of-owl) for reporting)

**Features:**

* A tier change (an upgrade, a downgrade, or a tier edited in place) applies on the user's next request and keeps what was already spent; before, it refilled the request, email and attachment bandwidth limits ([#2104](https://github.com/binwiederhier/ntfy/pull/2104), [#2105](https://github.com/binwiederhier/ntfy/pull/2105))
* A tier's daily email limit is a hard cap; before, the tier's email burst came on top of it, so a user could send more emails a day than the tier allows

**Bug fixes + maintenance:**

* Fix intermittent 403s and panics in the account handlers under concurrent requests from the same IP: a login or logout could change the user under another request, so a request with valid credentials was treated as anonymous, or the other way around. Every request now gets its own visitor ([#1051](https://github.com/binwiederhier/ntfy/issues/1051), [#2113](https://github.com/binwiederhier/ntfy/issues/2113), [#2118](https://github.com/binwiederhier/ntfy/pull/2118), thanks to @ivanetinajero for reporting)
* A tier with a daily email limit of zero sends no emails; before, it could still send the server's email burst (`visitor-email-limit-burst`)
* An attachment upload rejected at a size limit is no longer charged to the attachment bandwidth limit for the part that went over
* Rate limits live in one shared limit service, keyed by `ip:<prefix>` or `user:<id>`, instead of in each visitor, which uses less memory per visitor and takes a global lock off the request path
* Accept terabyte units (e.g. `1T`) in size settings such as attachment and tier limits, matching how sizes are displayed ([#2078](https://github.com/binwiederhier/ntfy/pull/2078), thanks to @cangen185-sudo for the contribution)
````


### 9. `ntfy/DOCS.md`

````markdown
# ntfy for Home Assistant OS

## Start here

1. Install this app from the repository and start it.
2. Open `http://HOME_ASSISTANT_IP:8093` from a device on the same LAN. The app's **Open Web UI** button uses the configured port.
3. Send a test from a terminal on the LAN:

   ```bash
   curl --fail --data 'Washing finished' http://HOME_ASSISTANT_IP:8093/washer
   ```

4. Subscribe to the topic `washer` in the ntfy mobile app, choosing **Use another server** and the same LAN URL.

No port forwarding, DNS records, public HTTPS certificate, or reverse proxy is required. The app publishes HTTP on port 8093 of the HA OS host. This does **not** mean it is firewalled from all LAN clients; use your UniFi firewall to isolate untrusted networks if needed.

## iPhone background notifications

- By default, **iOS instant notifications are off**. iOS restricts background processing, so local-only background delivery may be delayed substantially.
- To enable prompt iPhone notifications with **outbound-only** internet access, set `base_url` to the **exact** URL the iPhone is subscribed to, for example `http://10.72.34.92:8093`, then enable `ios_instant_notifications` in this app's Configuration page and restart it.
- The app will send a minimal wake-up request through `ntfy.sh` and Apple's notification service. The notification content remains on your ntfy server; your phone retrieves it directly.
- **No inbound WAN access is needed**. However, for the iPhone to retrieve the message, it must have a route to the server (home Wi-Fi or VPN). Away from home without a VPN, notifications may be generic or may not load the actual message.
- `base_url` must match the server URL in the iPhone app exactly, including scheme, host and port; do not add a trailing slash.
- Some phone configurations or versions may enforce HTTPS for third-party servers. If the app will not accept your plain HTTP LAN URL, arrange local HTTPS or use Home Assistant's mobile-app notification service instead. Do not open WAN ports.

## Home Assistant integration

The simplest Home Assistant notification sender is a REST command. Add this to `configuration.yaml` only if you want to use REST commands rather than the existing HA ntfy integration:

```yaml
rest_command:
  ntfy_washer:
    url: "http://HOME_ASSISTANT_IP:8093/washer"
    method: POST
    payload: "{{ message }}"
    content_type: "text/plain; charset=utf-8"
```

Replace `HOME_ASSISTANT_IP`, restart Home Assistant, and call `rest_command.ntfy_washer` with `message: Washing finished`. For appliance-complete automation, use a verified washing-machine status entity from the Electrolux integration.

## Security

- This intentionally simple LAN-only setup does not configure ntfy user authentication. Anyone who can reach TCP 8093 can read or publish to known topics. **Never forward TCP 8093 to the internet**.
- If you need access from other VLANs, add explicit UniFi rules for the required clients rather than exposing it generally.
- Outbound-only iOS wake-ups can be disabled at any time in the app configuration.

## Data, updates, and recovery

- `/data/cache.db`, `/data/attachments`, and `/data/options.json` persist across app updates and are included in Home Assistant app backups.
- This repository checks upstream GitHub stable releases daily. When a new release exists, CI first builds and smoke-tests the official tagged Docker image before updating the pinned version, and adds the **complete upstream release body** to `CHANGELOG.md`.
- Home Assistant offers the new version after the app repository refreshes. Enable **Auto update** in the Home Assistant app page if you want installation without manual approval.
- The upstream image is used unmodified except for installing `jq` and adding a tiny Supervisor options startup script.

Official docs: https://docs.ntfy.sh/ and https://github.com/binwiederhier/ntfy/releases
````


### 10. `ntfy/README.md`

````markdown
# ntfy

Self-hosted ntfy server running as a Home Assistant OS app, using the official upstream Docker image.

- Port `8093` on the Home Assistant host (not publicly exposed by this app)
- Persistent `/data` message and attachment storage
- Optional outbound iOS wake-up requests to `ntfy.sh`
- Official release notes included in the app's **Changelog** tab

Read **Documentation** for initial setup and limitations.
````


### 11. `README.md`

````markdown
# ntfy Home Assistant app

Home Assistant OS app (formerly *add-on*) for the official `binwiederhier/ntfy` image, without port forwarding or a separate Docker host.

## Install

1. Create a GitHub repository named **`rohanod/ha-addon-ntfy`**, and upload the contents of this package to its repository root.
2. Open **Settings → Apps → App Store → ⋮ → Repositories** in Home Assistant OS (the exact UI label may also say Add-ons or Add-on Store).
3. Add `https://github.com/rohanod/ha-addon-ntfy` as a custom app repository.
4. Install **ntfy**, start it, and use **Open Web UI**. The default LAN endpoint is `http://YOUR_HA_IP:8093`.
5. Enable **Auto update** in the app information page if you want Home Assistant to install updates automatically.

The app configuration allows the iOS upstream wake-up feature to be enabled without allowing any incoming internet connections. See [ntfy/DOCS.md](ntfy/DOCS.md) for details and the iPhone limitations.

## Update automation

The GitHub Actions workflow `.github/workflows/update-ntfy.yml` runs daily and supports manual dispatch. It:

1. Retrieves all stable upstream ntfy releases after the pinned version (not just the most recent one).
2. Appends **verbatim upstream release notes** for *each* missed release to `ntfy/CHANGELOG.md`, with direct release links and dates.
3. Updates `ntfy/config.yaml` and the upstream image version in `ntfy/Dockerfile` together.
4. Builds and smoke-tests the updated image (on amd64) **before** committing to the default branch.
5. Commits automatically with `GITHUB_TOKEN`, letting Home Assistant detect a new app version.

### GitHub settings

Enable Actions and permit workflows to write repository contents. A protected branch may block the automated commit; configure repository rules appropriately. The workflow never pushes if the image build or smoke test fails.

The updater uses a pinned upstream `vX.Y.Z` Docker tag, not `latest` or a mutable minor-version tag. It only follows stable upstream GitHub releases and does not silently update on a container tag repush.

Run the local updater tests with `python3 -m unittest discover -s tests -v`.

## Source and licence

ntfy is created by Philipp C. Heckel and contributors: https://github.com/binwiederhier/ntfy. Its upstream licensing applies to the upstream image. This repository contains only a thin integration layer and automation.
````


### 12. `.gitignore`

````text
.DS_Store
__pycache__/
.pytest_cache/
*.pyc
````


## Verification and delivery checklist

- `python3 -m unittest discover -s tests -v` succeeds.
- Parse `ntfy/config.yaml`, `repository.yaml`, and workflow YAML correctly; note YAML 1.1 parsers treat GitHub `on` specially.
- `sh -n ntfy/run.sh` succeeds.
- The HA OS app builds for supported CPU architectures and starts under Supervisor with actual `/data/options.json`.
- HTTP GET `/v1/health` succeeds; POST to a new topic returns success and subscribers can read it.
- The update script performs no write if no release or if the upstream API is broken; if multiple missed stable releases, all their original notes appear in `ntfy/CHANGELOG.md`.
- CI validates the candidate before it automatically publishes its changed version to GitHub.
- Document `http://HOME_ASSISTANT_IP:8093` LAN access, optional iOS outbound push, and no port forwarding.
- Commit, push and report the exact GitHub repo URL and commit SHA.
