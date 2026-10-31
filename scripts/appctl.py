#!/usr/bin/env python3
"""Update + validate the ntfy Home Assistant app. stdlib only.

  appctl.py update   [--packaging-note TEXT] [--releases-json F] [--image-json F]
  appctl.py validate [--base-changelog F]

App version: "X.Y.Z" tracks upstream ntfy vX.Y.Z; "X.Y.Z.N" is packaging-only revision N.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = "ntfy"
REPO = "binwiederhier/ntfy"
SUPPORTED_ARCH = {"amd64", "aarch64", "armv7"}
REQUIRED_PLATFORMS = {"linux/amd64", "linux/arm64", "linux/arm/v7"}  # = amd64, aarch64, armv7
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(\.\d+)?$")
FROM_RE = re.compile(r"^FROM binwiederhier/ntfy:v(\d+\.\d+\.\d+)@(sha256:[0-9a-f]{64})$", re.M)
CFG_VER_RE = re.compile(r'^version: "([^"]+)"$', re.M)
HEAD_RE = re.compile(r"^## (\S+)\s*$", re.M)
UP_HDR = "### ntfy upstream changes"
HA_HDR = "### Home Assistant app"
ABSENT = "_Upstream published no release notes for this version._"
BREAKING_RE = re.compile(r"breaking|migrat|deprecat|incompatib|upgrade note", re.I)
CHANGELOG_PREAMBLE = "# Changelog\n\n"


class Fail(Exception):
    pass


# ---- versions -------------------------------------------------------------
def vt(v):
    return tuple(int(x) for x in v.split("."))


def upstream_of(app_version):
    return ".".join(app_version.split(".")[:3])


def next_app_version(current, new_upstream=None):
    if new_upstream and vt(new_upstream) > vt(upstream_of(current)):
        return new_upstream
    parts = current.split(".")
    return ".".join(parts[:3] + [str(int(parts[3]) + 1 if len(parts) == 4 else 1)])


# ---- network (injectable) ---------------------------------------------------
def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    return urllib.request.urlopen(req, timeout=30)


def fetch_releases(floor):
    """All GitHub releases, paging until one <= floor is seen."""
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    out = []
    for page in range(1, 11):
        with _get(f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}", headers) as r:
            batch = json.load(r)
        out += batch
        if not batch or any(stable_version(x) and vt(stable_version(x)) <= vt(floor) for x in batch):
            break
    return out


def fetch_image(tag):
    """-> {"digest": sha256:..., "platforms": ["linux/amd64", ...]} for the multi-arch index."""
    tok = json.load(_get(f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{REPO}:pull"))["token"]
    h = {"Authorization": "Bearer " + tok, "Accept": "application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json"}
    with _get(f"https://registry-1.docker.io/v2/{REPO}/manifests/{tag}", h) as r:
        digest = r.headers["Docker-Content-Digest"]
        idx = json.load(r)
    plats = {"/".join(filter(None, ["linux", m["platform"]["architecture"], m["platform"].get("variant")])) for m in idx["manifests"]}
    return {"digest": digest, "platforms": sorted(plats)}


# ---- release handling -------------------------------------------------------
def stable_version(rel):
    if rel.get("draft") or rel.get("prerelease"):
        return None
    m = re.fullmatch(r"v(\d+\.\d+\.\d+)", rel.get("tag_name", ""))
    return m.group(1) if m else None


def pending_releases(raw, prev, new):
    """Stable releases with prev < v <= new, newest first."""
    sel = [(vt(v), r) for r in raw if (v := stable_version(r)) and vt(prev) < vt(v) <= vt(new)]
    return [r for _, r in sorted(sel, key=lambda x: x[0], reverse=True)]


def demote(body):
    """Turn markdown headings in upstream notes into bold lines so our heading tree stays intact."""
    return re.sub(r"^#{1,6}\s+(.*)$", r"**\1**", body.replace("\r\n", "\n").strip(), flags=re.M)


def render_entry(app_version, releases, notes):
    out = [f"## {app_version}\n", f"{HA_HDR}\n"]
    out += [f"- {n}" for n in notes] + [""]
    if releases:
        out.append(f"{UP_HDR}\n")
        for r in releases:
            v = stable_version(r)
            body = demote(r.get("body") or "") or ABSENT
            out.append(f"#### v{v} ({(r.get('published_at') or 'unknown date')[:10]})\n")
            out.append(f"Release page: {r['html_url']}\n")
            flagged = [l.strip() for l in body.splitlines() if BREAKING_RE.search(l) and l.strip()]
            if flagged:
                out.append("**Breaking changes / migration (lines from the upstream notes):**\n")
                out += [l if l.startswith(("-", "*")) else f"- {l}" for l in flagged] + [""]
            out.append(body + "\n")
    return "\n".join(out).rstrip() + "\n\n"


# ---- repo files ---------------------------------------------------------------
def read_state(root):
    cfg = (root / APP / "config.yaml").read_text()
    df = (root / APP / "Dockerfile").read_text()
    return cfg, df, (root / APP / "CHANGELOG.md").read_text()


def update(root, raw_releases=None, image=None, packaging_note=None):
    """Returns (old_version, new_version) or None if up to date. Writes nothing unless valid."""
    cfg, df, cl = read_state(root)
    cur = CFG_VER_RE.search(cfg).group(1)
    cur_up = upstream_of(cur)
    if packaging_note is None:
        raw = raw_releases if raw_releases is not None else fetch_releases(cur_up)
        stable = sorted((vt(v) for r in raw if (v := stable_version(r))), reverse=True)
        if not stable:
            raise Fail("no stable upstream releases found")
        latest = ".".join(map(str, stable[0]))
        if vt(latest) <= vt(cur_up):
            return None
        rels = pending_releases(raw, cur_up, latest)
        if not rels or stable_version(rels[0]) != latest:
            raise Fail(f"release v{latest} missing from fetched release list")
        image = image if image is not None else fetch_image(f"v{latest}")
        missing = REQUIRED_PLATFORMS - set(image["platforms"])
        if missing:
            raise Fail(f"image v{latest} lacks platforms: {sorted(missing)}")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image["digest"]):
            raise Fail("bad image digest")
        new = latest
        entry = render_entry(new, rels, [f"Updated ntfy from v{cur_up} to v{latest} (official `binwiederhier/ntfy` image, pinned by digest)."])
        df = FROM_RE.sub(f"FROM binwiederhier/ntfy:v{latest}@{image['digest']}", df)
    else:
        if not packaging_note.strip():
            raise Fail("empty packaging note")
        new = next_app_version(cur)
        entry = render_entry(new, [], [packaging_note.strip()])
    if f"## {new}\n" in cl:
        raise Fail(f"changelog already has {new}")
    cfg = CFG_VER_RE.sub(f'version: "{new}"', cfg, count=1)
    cl = CHANGELOG_PREAMBLE + entry + cl[len(CHANGELOG_PREAMBLE):]
    # stage -> validate -> commit to disk
    originals = {n: (root / APP / n).read_text() for n in ("config.yaml", "Dockerfile", "CHANGELOG.md")}
    base = originals["CHANGELOG.md"]
    try:
        for n, t in (("config.yaml", cfg), ("Dockerfile", df), ("CHANGELOG.md", cl)):
            (root / APP / n).write_text(t)
        errs = validate(root, base_changelog=base)
        if errs:
            raise Fail("validation failed: " + "; ".join(errs))
    except BaseException:
        for n, t in originals.items():
            (root / APP / n).write_text(t)
        raise
    return cur, new


def validate(root, base_changelog=None):
    errs = []
    try:
        cfg, df, cl = read_state(root)
    except OSError as e:
        return [f"missing file: {e}"]
    m = CFG_VER_RE.search(cfg)
    ver = m.group(1) if m else ""
    if not VERSION_RE.match(ver):
        return [f"config.yaml version {ver!r} invalid"]
    am = re.search(r"^arch:\n((?:  - \w+\n)+)", cfg, re.M)
    arch = set(re.findall(r"\w+", am.group(1))) if am else set()
    if not arch or not arch <= SUPPORTED_ARCH:
        errs.append(f"unsupported arch set {sorted(arch)}")
    fm = FROM_RE.search(df)
    if not fm:
        errs.append("Dockerfile FROM must be binwiederhier/ntfy:vX.Y.Z@sha256:<digest>")
    elif fm.group(1) != upstream_of(ver):
        errs.append(f"Dockerfile tag v{fm.group(1)} != app version upstream part {upstream_of(ver)}")
    if re.search(r"latest", "\n".join(l for l in df.splitlines() if l.startswith("FROM"))):
        errs.append("unpinned latest image")
    if not cl.startswith(CHANGELOG_PREAMBLE):
        errs.append("CHANGELOG.md must start with '# Changelog'")
    heads = [(h.group(1), h.start(), ) for h in HEAD_RE.finditer(cl)]
    if not heads:
        return errs + ["CHANGELOG.md has no entries"]
    if heads[0][0] != ver:
        errs.append(f"latest changelog entry {heads[0][0]} != config version {ver}")
    names = [h[0] for h in heads]
    if len(set(names)) != len(names):
        errs.append("duplicate changelog headings")
    if any(not VERSION_RE.match(n) for n in names):
        errs.append("non-version changelog heading")
    else:
        if [vt(n) for n in names] != sorted((vt(n) for n in names), reverse=True):
            errs.append("changelog not newest-first")
    bounds = [h[1] for h in heads] + [len(cl)]
    for i, (name, _) in enumerate(heads):
        sec = cl[bounds[i]:bounds[i + 1]]
        if HA_HDR not in sec or not re.search(r"^- \S", sec.split(HA_HDR)[1].split("###")[0], re.M):
            errs.append(f"{name}: missing '{HA_HDR}' bullets")
        if len(name.split(".")) == 3:
            if UP_HDR not in sec:
                errs.append(f"{name}: upstream entry lacks '{UP_HDR}'")
            elif f"https://github.com/{REPO}/releases/tag/v{name}" not in sec:
                errs.append(f"{name}: missing upstream release link")
            if re.search(r"TODO|placeholder|lorem", sec, re.I):
                errs.append(f"{name}: placeholder text")
        if UP_HDR in sec:
            for rel in sec.split("#### v")[1:]:
                if f"https://github.com/{REPO}/releases/tag/v" not in rel or len(rel.strip().splitlines()) < 3:
                    errs.append(f"{name}: upstream release block empty/linkless")
    if base_changelog is not None:
        old = base_changelog[len(CHANGELOG_PREAMBLE):] if base_changelog.startswith(CHANGELOG_PREAMBLE) else base_changelog
        if not cl.endswith(old):
            errs.append("previous changelog history was altered")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update")
    u.add_argument("--packaging-note")
    u.add_argument("--releases-json")
    u.add_argument("--image-json")
    u.add_argument("--root", default=str(ROOT))
    v = sub.add_parser("validate")
    v.add_argument("--base-changelog")
    v.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root)
    try:
        if a.cmd == "validate":
            base = Path(a.base_changelog).read_text() if a.base_changelog else None
            errs = validate(root, base)
            for e in errs:
                print("ERROR:", e, file=sys.stderr)
            return 1 if errs else 0
        raw = json.loads(Path(a.releases_json).read_text()) if a.releases_json else None
        img = json.loads(Path(a.image_json).read_text()) if a.image_json else None
        res = update(root, raw, img, a.packaging_note)
    except Fail as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    except Exception as e:  # network / parse failures must fail the run, never publish
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    out = os.environ.get("GITHUB_OUTPUT")
    lines = ["updated=false"] if res is None else [f"updated=true", f"old={res[0]}", f"new={res[1]}"]
    print("\n".join(lines))
    if out:
        with open(out, "a") as f:
            f.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
