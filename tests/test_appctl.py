import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import appctl  # noqa: E402

DIGEST = "sha256:" + "a" * 64
IMG = {"digest": DIGEST, "platforms": ["linux/amd64", "linux/arm64", "linux/arm/v7", "linux/arm/v6"]}


def rel(v, body="Notes for %s.\n\n**Features:**\n\n* thing\n", pre=False, draft=False):
    return {"tag_name": f"v{v}", "prerelease": pre, "draft": draft, "published_at": "2026-01-02T03:04:05Z",
            "html_url": f"https://github.com/binwiederhier/ntfy/releases/tag/v{v}",
            "body": body % v if "%s" in body else body}


RELS = [rel("2.36.1"), rel("2.36.0"), rel("2.35.5", pre=True), rel("2.37.0", draft=True), rel("2.35.1"), rel("2.35.0"), rel("2.34.0")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "ntfy", self.tmp / "ntfy", ignore=shutil.ignore_patterns("run.sh"))
        self.addCleanup(shutil.rmtree, self.tmp)
        # Keep test fixtures independent of the version currently released.
        cfg = self.tmp / "ntfy" / "config.yaml"
        cfg.write_text(re.sub(r'^version: "[^"]+"$', 'version: "2.35.0"', cfg.read_text(), flags=re.M))
        df = self.tmp / "ntfy" / "Dockerfile"
        df.write_text(re.sub(r'^(FROM binwiederhier/ntfy:)v[0-9.]+@', r'\g<1>v2.35.0@', df.read_text(), flags=re.M))
        self.cl = self.tmp / "ntfy" / "CHANGELOG.md"
        self.cl.write_text(
            "# Changelog\n\n"
            "## 2.35.0\n\n"
            "### Home Assistant app\n\n"
            "- Initial ntfy Home Assistant app release.\n\n"
            "### ntfy upstream changes\n\n"
            "#### v2.35.0 (2026-10-30)\n\n"
            "Release page: https://github.com/binwiederhier/ntfy/releases/tag/v2.35.0\n\n"
            "Fix intermittent request failures.\n"
        )

    def files(self):
        return {n: (self.tmp / "ntfy" / n).read_text() for n in ("config.yaml", "Dockerfile", "CHANGELOG.md")}


class RepoState(unittest.TestCase):
    def test_repo_validates(self):
        self.assertEqual(appctl.validate(REPO), [])

    def test_options_match_schema(self):
        cfg = (REPO / "ntfy/config.yaml").read_text()
        opts = set(re.findall(r"^  (\w+):", cfg.split("options:")[1].split("schema:")[0], re.M))
        schema = set(re.findall(r"^  (\w+):", cfg.split("schema:")[1], re.M))
        self.assertTrue(opts <= schema, opts - schema)

    def test_no_latest_anywhere(self):
        for f in ("Dockerfile", "config.yaml"):
            self.assertNotIn(":latest", (REPO / "ntfy" / f).read_text())


class Update(Base):
    def test_no_update(self):
        before = self.files()
        self.assertIsNone(appctl.update(self.tmp, [rel("2.35.0"), rel("2.34.0")], IMG))
        self.assertEqual(before, self.files())

    def test_ignores_prerelease_and_draft(self):
        self.assertIsNone(appctl.update(self.tmp, [rel("2.35.0"), rel("2.36.0", pre=True), rel("2.37.0", draft=True)], IMG))

    def test_new_release(self):
        old = self.files()
        self.assertEqual(appctl.update(self.tmp, RELS[3:], IMG), ("2.35.0", "2.35.1"))
        new = self.files()
        self.assertIn('version: "2.35.1"', new["config.yaml"])
        self.assertIn(f"binwiederhier/ntfy:v2.35.1@{DIGEST}", new["Dockerfile"])
        self.assertTrue(new["CHANGELOG.md"].startswith("# Changelog\n\n## 2.35.1\n"))
        self.assertIn("Notes for 2.35.1.", new["CHANGELOG.md"])
        self.assertTrue(new["CHANGELOG.md"].endswith(old["CHANGELOG.md"][len("# Changelog\n\n"):]))  # history intact
        self.assertEqual(appctl.validate(self.tmp), [])

    def test_skipped_versions_all_included(self):
        appctl.update(self.tmp, RELS, IMG)
        cl = self.files()["CHANGELOG.md"]
        head = cl.split("## 2.35.0")[0]
        self.assertTrue(cl.startswith("# Changelog\n\n## 2.36.1\n"))
        for v in ("2.36.1", "2.36.0", "2.35.1"):
            self.assertIn(f"#### v{v} ", head)
            self.assertIn(f"releases/tag/v{v}", head)
        self.assertNotIn("2.35.5", head)  # prerelease
        self.assertLess(head.index("v2.36.1 "), head.index("v2.36.0 "))
        self.assertIn("## 2.35.0", cl)

    def test_breaking_lines_surfaced(self):
        r = rel("2.36.0", body="### Breaking\n* Breaking: config key renamed, migrate it\n* other\n")
        appctl.update(self.tmp, [r, rel("2.35.0")], IMG)
        cl = self.files()["CHANGELOG.md"]
        self.assertIn("Breaking changes / migration", cl)
        self.assertNotIn("\n### Breaking", cl)  # upstream headings demoted

    def test_missing_notes_stated_not_invented(self):
        appctl.update(self.tmp, [rel("2.36.0", body=""), rel("2.35.0")], IMG)
        self.assertIn(appctl.ABSENT, self.files()["CHANGELOG.md"])
        self.assertEqual(appctl.validate(self.tmp), [])

    def test_failures_leave_files_untouched(self):
        before = self.files()
        cases = [
            ([], IMG),
            ([rel("2.36.0", pre=True)], IMG),
            ([rel("2.36.0"), rel("2.35.0")], {"digest": DIGEST, "platforms": ["linux/amd64"]}),
            ([rel("2.36.0"), rel("2.35.0")], {"digest": "sha256:zz", "platforms": IMG["platforms"]}),
        ]
        for raw, img in cases:
            with self.assertRaises(appctl.Fail):
                appctl.update(self.tmp, raw, img)
            self.assertEqual(before, self.files())

    def test_validation_failure_rolls_back(self):
        before = self.files()
        orig = appctl.render_entry
        appctl.render_entry = lambda *a, **k: "## 2.36.0\n\nbroken\n\n"
        try:
            with self.assertRaises(appctl.Fail):
                appctl.update(self.tmp, [rel("2.36.0"), rel("2.35.0")], IMG)
        finally:
            appctl.render_entry = orig
        self.assertEqual(before, self.files())

    def test_cli_invalid_upstream_response(self):
        before = self.files()
        bad = self.tmp / "bad.json"
        bad.write_text("not json")
        r = subprocess.run([sys.executable, str(REPO / "scripts/appctl.py"), "update", "--root", str(self.tmp),
                            "--releases-json", str(bad)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.files(), before)

    def test_packaging_only(self):
        self.assertEqual(appctl.update(self.tmp, packaging_note="Fix watchdog URL."), ("2.35.0", "2.35.0.1"))
        self.assertEqual(appctl.update(self.tmp, packaging_note="Another."), ("2.35.0.1", "2.35.0.2"))
        cl = self.files()["CHANGELOG.md"]
        self.assertTrue(cl.startswith("# Changelog\n\n## 2.35.0.2\n"))
        self.assertIn("Fix watchdog URL.", cl)
        self.assertEqual(appctl.validate(self.tmp), [])
        self.assertIn("binwiederhier/ntfy:v2.35.0@", self.files()["Dockerfile"])
        # upstream bump after packaging revisions
        self.assertEqual(appctl.update(self.tmp, [rel("2.36.0"), rel("2.35.0")], IMG), ("2.35.0.2", "2.36.0"))

    def test_version_ordering(self):
        self.assertEqual(appctl.next_app_version("2.35.0"), "2.35.0.1")
        self.assertEqual(appctl.next_app_version("2.35.0.9", "2.35.0"), "2.35.0.10")
        self.assertGreater(appctl.vt("2.36.0"), appctl.vt("2.35.0.7"))


class Validate(Base):
    def test_version_mismatch(self):
        p = self.tmp / "ntfy/config.yaml"
        p.write_text(p.read_text().replace('"2.35.0"', '"2.36.0"'))
        self.assertTrue(appctl.validate(self.tmp))

    def test_unpinned_image(self):
        p = self.tmp / "ntfy/Dockerfile"
        p.write_text(re.sub(r"^FROM .*$", "FROM binwiederhier/ntfy:latest", p.read_text(), flags=re.M))
        self.assertTrue(appctl.validate(self.tmp))

    def test_placeholder_changelog(self):
        self.cl.write_text("# Changelog\n\n## 2.35.0\n\n### Home Assistant app\n\n- Updated ntfy to 2.35.0\n")
        self.assertTrue(appctl.validate(self.tmp))

    def test_history_altered(self):
        base = self.cl.read_text()
        self.cl.write_text(base.replace("Fix intermittent", "Fix"))
        self.assertIn("previous changelog history was altered", appctl.validate(self.tmp, base))

    def test_missing_changelog_entry_for_version(self):
        p = self.tmp / "ntfy/config.yaml"
        p.write_text(p.read_text().replace('"2.35.0"', '"2.35.0.1"'))
        self.assertTrue(any("!= config version" in e for e in appctl.validate(self.tmp)))


@unittest.skipUnless(shutil.which("jq"), "jq required")
class RunScript(unittest.TestCase):
    def run_app(self, opts, expect_rc=0):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        (d / "options.json").write_text(json.dumps(opts))
        (d / "bin").mkdir()
        fake = d / "bin" / "ntfy"
        fake.write_text('#!/bin/sh\necho "ntfy $*" >> "$LOG"\nenv | grep "^NTFY_" | sort >> "$LOG"\n')
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        wget = d / "bin" / "wget"
        wget.write_text("#!/bin/sh\nexit 0\n")
        wget.chmod(0o755)
        env = dict(os.environ, PATH=f"{d / 'bin'}:{os.environ['PATH']}", LOG=str(d / "log"),
                   NTFY_APP_OPTIONS=str(d / "options.json"), NTFY_APP_DATA=str(d))
        r = subprocess.run(["sh", str(REPO / "ntfy/run.sh")], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, expect_rc, r.stderr)
        return (d / "log").read_text() if (d / "log").exists() else "", r

    BASE = {"base_url": "", "auth_default_access": "deny-all", "enable_login": True, "enable_signup": False,
            "cache_duration": "12h", "log_level": "info", "ios_push_forwarding": False, "users": []}

    def test_defaults(self):
        log, _ = self.run_app(self.BASE)
        self.assertIn("ntfy serve", log)
        self.assertIn("NTFY_AUTH_DEFAULT_ACCESS=deny-all", log)
        self.assertIn("NTFY_ENABLE_SIGNUP=false", log)
        self.assertRegex(log, r"NTFY_CACHE_FILE=.*/cache.db")
        self.assertRegex(log, r"NTFY_AUTH_FILE=.*/user.db")
        self.assertNotIn("UPSTREAM", log)

    def test_ios_forwarding(self):
        log, _ = self.run_app(dict(self.BASE, ios_push_forwarding=True, base_url="http://192.168.1.2:8093"))
        self.assertIn("NTFY_UPSTREAM_BASE_URL=https://ntfy.sh", log)
        self.assertIn("NTFY_BASE_URL=http://192.168.1.2:8093", log)

    def test_attachments_only_with_base_url(self):
        log, _ = self.run_app(self.BASE)
        self.assertNotIn("ATTACHMENT", log)  # ntfy would refuse to start
        log, _ = self.run_app(dict(self.BASE, base_url="http://10.0.0.2:8093"))
        self.assertRegex(log, r"NTFY_ATTACHMENT_CACHE_DIR=.*/attachments")

    def test_bad_base_url(self):
        for bad in ("10.0.0.2:8093", "http://10.0.0.2:8093/"):
            log, r = self.run_app(dict(self.BASE, base_url=bad), expect_rc=1)
            self.assertIn("base_url", r.stderr)
            self.assertEqual(log, "")

    def test_ios_requires_base_url(self):
        log, r = self.run_app(dict(self.BASE, ios_push_forwarding=True), expect_rc=1)
        self.assertIn("base_url", r.stderr)
        self.assertEqual(log, "")

    def test_users_provisioned(self):
        log, r = self.run_app(dict(self.BASE, users=[{"username": "ha", "password": "p w$1", "role": "admin"}]))
        self.assertIn("ntfy user add --role=admin --ignore-exists ha", log)
        self.assertIn("ntfy user change-pass ha", log)
        self.assertNotIn("p w$1", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
