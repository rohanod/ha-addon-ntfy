# ntfy

Self-hosted [ntfy](https://docs.ntfy.sh/) server built on the official `binwiederhier/ntfy` image (pinned by version and digest in the Dockerfile; runs `ntfy serve`).

## Install

1. Settings → Apps → App Store → ⋮ → Repositories → add `https://github.com/rohanod/ha-addon-ntfy`.
2. Install **ntfy**, set at least one admin user (below), start it.
3. Open `http://<HA-IP>:8093`.

No port forwarding, domain, reverse proxy or TLS is required. Traffic on the LAN is plain HTTP; keep the port off the internet.

## Options

| Option | Default | Meaning |
|---|---|---|
| `base_url` | empty | URL your clients use, e.g. `http://192.168.1.10:8093`. **Required for iOS forwarding.** |
| `auth_default_access` | `deny-all` | Access for anonymous users. `deny-all` means every publisher/subscriber needs a user. |
| `enable_login` / `enable_signup` | `true` / `false` | Web login / self-registration. |
| `cache_duration` | `12h` | How long messages are cached for offline subscribers. |
| `log_level` | `info` | |
| `ios_push_forwarding` | `false` | Forward poll requests to `https://ntfy.sh` (see iOS). |
| `upstream_access_token` | empty | Optional ntfy.sh token, only if you hit upstream rate limits. |
| `users` | `[]` | `username`, `password`, `role` (`admin`/`user`). Created or updated on every start. Removing a user from this list does **not** delete it; run `ntfy user remove` inside the container or delete `user.db`. |

With `deny-all` and no users nobody can publish; add an admin first.

## Data and backups

Everything lives in the app's `/data`: `cache.db` (messages) and `user.db` (users, tokens, ACLs). It survives restarts and updates and is included in Home Assistant backups (backup mode is `cold`, so the app is stopped briefly for a consistent SQLite copy).

## iOS notifications: what is and is not supported

ntfy's iOS app cannot keep a connection to your server in the background; Apple only allows APNs push. For self-hosted servers ntfy solves this by sending a *poll request* (message ID + hash of the topic, not the content) to `https://ntfy.sh`, which triggers an APNs push that makes the iPhone fetch the message from your server.

- Enable `ios_push_forwarding` and set `base_url` to the address your iPhone uses to reach this server. Also set the same server URL in the iOS app. The server only needs outbound HTTPS to ntfy.sh.
- The iPhone must be able to reach `base_url` (same LAN/VLAN, or VPN) at the moment it fetches. If it is away from the LAN without VPN, the push wakes the app but the message cannot be fetched until it can reach the server.
- Without forwarding, upstream docs say delivery to iOS can take hours. **Fully offline, reliable iOS background delivery is not supported**; APNs always goes through ntfy.sh (or another APNs-connected server). This was not verified against a physical iPhone as part of this repo.
- Instant-delivery (priority) behaviour depends on iOS and is not guaranteed.

## Home Assistant examples

Official ntfy integration: Settings → Devices & services → add **ntfy**, URL `http://<HA-IP>:8093` (or `http://homeassistant.local:8093`), then use `notify.send_message` on the created entity.

Without the integration, via `rest_command`:

```yaml
# configuration.yaml
rest_command:
  ntfy_washer:
    url: "http://localhost:8093/washer"   # use the host IP if HA cannot reach itself on 8093
    method: post
    headers:
      Authorization: !secret ntfy_basic_auth   # "Basic <base64 of user:password>"
      Title: "Washing machine"
      Tags: "tada"
    payload: "The cycle has finished."
```

```yaml
# automation
alias: Washer finished
triggers:
  - trigger: numeric_state
    entity_id: sensor.washer_power
    below: 3
    for: "00:02:00"
actions:
  - action: rest_command.ntfy_washer
```

Subscribe on the iPhone to topic `washer` on your server (log in with the user you created).

## Updates and the native changelog

A daily GitHub Actions workflow tracks the newest stable ntfy release, checks the image exists for amd64/arm64/armv7, rewrites the digest-pinned `FROM`, bumps the app version and prepends the upstream release notes of every skipped version to `ntfy/CHANGELOG.md` — the file Supervisor serves in the app's update view. Versions: `X.Y.Z` follows ntfy `vX.Y.Z`; `X.Y.Z.N` is a packaging-only revision.
