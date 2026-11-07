#!/usr/bin/env bash
# Publish the app version from an exact commit as an immutable lightweight tag
# and a GitHub Release. Safe to rerun after a partial publish.
set -euo pipefail

: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
commit="${1:?usage: publish-release.sh COMMIT_SHA}"
git cat-file -e "${commit}^{commit}"
version="$(git show "${commit}:ntfy/config.yaml" | sed -n 's/^version: "\([^"]*\)"$/\1/p')"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || { echo "Invalid app version: $version" >&2; exit 1; }
tag="v${version}"

# Never put a release tag on a commit whose Dockerfile points to a different ntfy version.
upstream="${version%.*}"
if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then upstream="$version"; fi
git show "${commit}:ntfy/Dockerfile" | grep -Eq "^FROM binwiederhier/ntfy:v${upstream//./\\.}@sha256:[0-9a-f]{64}$" || {
  echo "Dockerfile image version does not match $version" >&2; exit 1;
}

remote_sha="$(gh api "repos/${GITHUB_REPOSITORY}/git/ref/tags/${tag}" --jq '.object.sha' 2>/dev/null || true)"
# Some gh versions return the HTTP 404 JSON body even with --jq.
# Only a genuine Not Found response means a tag is absent.
if [[ "$remote_sha" == *'"message":"Not Found"'* && "$remote_sha" == *'"status":"404"'* ]]; then
  remote_sha=""
elif [[ -n "$remote_sha" && ! "$remote_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Unexpected response while looking up tag: $remote_sha" >&2
  exit 1
fi
if [[ -n "$remote_sha" && "$remote_sha" != "$commit" ]]; then
  echo "Tag ${tag} already exists at ${remote_sha}, expected ${commit}; refusing to move it" >&2
  exit 1
fi
if [[ -z "$remote_sha" ]]; then
  gh api "repos/${GITHUB_REPOSITORY}/git/refs" -f "ref=refs/tags/${tag}" -f "sha=${commit}" >/dev/null
  echo "Created immutable tag ${tag} at ${commit}"
fi

if gh release view "$tag" >/dev/null 2>&1; then
  echo "Release ${tag} already published"
  exit 0
fi

notes="$(mktemp)"
trap 'rm -f "$notes"' EXIT
git show "${commit}:ntfy/CHANGELOG.md" | python3 -c '
import sys
version = sys.argv[1]
text = sys.stdin.read()
marker = "## " + version + "\n"
if marker not in text:
    sys.exit("Changelog missing version " + version)
section = text.split(marker, 1)[1].split("\n## ", 1)[0].strip()
if not section:
    sys.exit("Empty release notes")
print(section)
' "$version" > "$notes"
gh release create "$tag" --target "$commit" --title "ntfy Home Assistant app ${version}" --notes-file "$notes"
echo "Published ${tag} (commit ${commit})"
