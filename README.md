# ntfy Home Assistant App

Home Assistant app (add-on) for the official [ntfy](https://github.com/binwiederhier/ntfy) server. Local-first, authenticated by default (`deny-all`), data persisted in `/data`, LAN port `8093`.

Add `https://github.com/rohanod/ha-addon-ntfy` in Settings → Apps → App Store → Repositories. Usage, options, iOS notes and automation examples: [ntfy/DOCS.md](ntfy/DOCS.md).

## Layout

- `ntfy/config.yaml`, `Dockerfile` (digest-pinned upstream `FROM`), `run.sh` (options → `NTFY_*` env, user provisioning, `exec`s upstream `ntfy serve`), `CHANGELOG.md` (served by Supervisor).
- `scripts/appctl.py`: `update` (find release, check image, rewrite pin/version/changelog, validate, roll back on failure) and `validate`.
- `.github/workflows/update-ntfy.yml`: daily + manual (`packaging_note` input for packaging-only releases); `test.yml`: unit tests + image smoke test.

## Test

```bash
python3 -m unittest discover -s tests -v
python3 scripts/appctl.py validate
```

## Repo setup for auto-merge

Settings → Actions → General → allow Actions to create pull requests; branch protection must not require reviews for `github-actions[bot]`.
