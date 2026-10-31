# ntfy

Self-hosted [ntfy](https://ntfy.sh) server as a Home Assistant app, running the official upstream image.

- LAN port `8093` (HTTP; not exposed to the internet by this app)
- Anonymous access denied by default; users managed in the app options
- Persistent `/data`: message cache, users, attachments (attachments need `base_url`)
- Optional outbound-only iOS wake-ups via `ntfy.sh`
- Upstream release notes appear in the app's Changelog tab on every update

See **Documentation** for setup and limitations.
