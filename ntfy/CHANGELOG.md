# Changelog

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

