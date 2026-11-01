# Changelog

## 2.36.0

### Home Assistant app

- Updated ntfy from v2.35.0 to v2.36.0 (official `binwiederhier/ntfy` image, pinned by digest).

### ntfy upstream changes

#### v2.36.0 (2026-10-31)

Release page: https://github.com/binwiederhier/ntfy/releases/tag/v2.36.0

**Breaking changes / migration (lines from the upstream notes):**

**Upgrade notes:**

This release keeps the daily limits across restarts and, with PostgreSQL, shares them between servers, so a visitor gets one daily allowance in total. Each visitor's day now starts at its own time instead of midnight UTC. It also adds an experimental local admin socket.

**Features:**

* Daily limits (messages, e-mails, phone calls) are stored in the user database, so they survive restarts; with PostgreSQL, all servers share them. Each visitor's day starts at its own time instead of midnight UTC, and the account page and `/v1/account` (`stats.reset_at`) show when it resets ([#2131](https://github.com/binwiederhier/ntfy/pull/2131), see [message limits](https://docs.ntfy.sh/config/#message-limits))
* Experimental local admin socket (`experimental-listen-admin-unix`, off by default) that serves the admin API without credentials to whoever can open it; the shipped systemd unit sets `RuntimeDirectory=ntfy` for it (see [admin socket](https://docs.ntfy.sh/config/#admin-socket))
* Export `ntfy_db_up` per PostgreSQL pool, and health-check the primary like the replicas ([#2133](https://github.com/binwiederhier/ntfy/pull/2133))

**Upgrade notes:**

* Everyone's daily counts start over at the upgrade: the `stats_*` columns of the user table are zeroed and no longer used
* Servers that share a PostgreSQL database must keep their clocks in sync (NTP)
* Visitors without a tier have a daily e-mail limit again (24h / `visitor-email-limit-replenish`)
* The whole server config is checked again when `base-url` or a `message-size-limit` above 4K is set, so an invalid config that used to start now fails at startup ([#1969](https://github.com/binwiederhier/ntfy/pull/1969), thanks to @mikejgray for the contribution)

**Bug fixes + maintenance:**

* Web app: Messages replayed by a poll or a reconnect no longer bring back deleted notifications, lose their read state or notify again ([#2098](https://github.com/binwiederhier/ntfy/issues/2098), [#2090](https://github.com/binwiederhier/ntfy/issues/2090), thanks to @mattford63, @arminus and @tobykaspar79 for reporting)
* CLI: `ntfy pub --wait-pid` now waits for processes owned by other users instead of failing with "not running" ([#1710](https://github.com/binwiederhier/ntfy/pull/1710), thanks to @bekoeppel for the contribution)
* Admin API (internal): manage other users' tokens, tiers and password reset links, return 4xx instead of 500 for invalid input, and remove a deleted user's web push subscriptions

## 2.35.0

### Home Assistant app

- Initial release of the ntfy Home Assistant app, packaging ntfy v2.35.0 (official `binwiederhier/ntfy` image, pinned by digest).
- Server on LAN port `8093`, persistent data in `/data`, access control defaulting to `deny-all`, optional iOS upstream forwarding.

### ntfy upstream changes

#### v2.35.0 (2026-10-30)

Release page: https://github.com/binwiederhier/ntfy/releases/tag/v2.35.0

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

