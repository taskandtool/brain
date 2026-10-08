"""Unit tests for brain_status.py — stdlib unittest, no deps.

    python3 tests/test_brain_status.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import brain_status as bst  # noqa: E402


class DiffTests(unittest.TestCase):
    def test_new_changed_removed(self):
        d = bst.diff({"raw/a.md": "1", "raw/b.md": "2x", "raw/c.md": "3"},
                     {"raw/b.md": "2", "raw/c.md": "3", "raw/gone.md": "9"})
        self.assertEqual(d["new"], ["raw/a.md"])
        self.assertEqual(d["changed"], ["raw/b.md"])
        self.assertEqual(d["removed"], ["raw/gone.md"])
        self.assertEqual(d["units"], {"raw/a.md": {"new": 1, "changed": 0}, "raw/b.md": {"new": 0, "changed": 1}})

    def test_units_group_the_site_and_external_hosts(self):
        self.assertEqual(bst.unit_of("raw/site/acme.com/pages/services.md"), "raw/site/acme.com")
        self.assertEqual(bst.unit_of("raw/site/acme.com/docs/prices.md"), "raw/site/acme.com")
        self.assertEqual(bst.unit_of("raw/external/competitor.com/pricing.md"), "raw/external/competitor.com")
        self.assertEqual(bst.unit_of("raw/docs/2026-09-02-brochure.md"), "raw/docs/2026-09-02-brochure.md")
        self.assertEqual(bst.unit_of("raw/social/instagram/acmehoses/2026-09-01-post.md"),
                         "raw/social/instagram/acmehoses")
        self.assertEqual(bst.unit_of("raw/places/acme-hose-co.json"), "raw/places/acme-hose-co.json")
        d = bst.diff({"raw/site/a.com/pages/a.md": "1", "raw/site/a.com/pages/b.md": "2", "raw/external/x.com/p.md": "3"},
                     {"raw/site/a.com/pages/b.md": "old"})
        self.assertEqual(d["units"], {"raw/site/a.com": {"new": 1, "changed": 1}, "raw/external/x.com": {"new": 1, "changed": 0}})
        self.assertIn("raw/site/a.com  (1 new, 1 changed)", bst.summarize(d))

    def test_summary_lists_pending_and_caps(self):
        d = bst.diff({f"raw/{i}.md": "1" for i in range(20)}, {})
        s = bst.summarize(d)
        self.assertTrue(s.startswith("brain_status status: 20 new raw file(s) not yet distilled"))
        self.assertIn("5 more: python3 scripts/brain_status.py status --all", s)
        self.assertEqual(len(bst.summarize(d, show_all=True).splitlines()), 23)
        self.assertIn("nothing pending", bst.summarize(bst.diff({}, {})))


class FilesystemTests(unittest.TestCase):
    PAGE = "raw/site/acme.com/pages/index.md"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        self.root = bst.ROOT
        bst.ROOT = os.path.realpath(self.tmp.name)
        os.chdir(self.tmp.name)
        for d in ("pages", "images", "shots/index", "_index", "_cache/pages"):
            os.makedirs("raw/site/acme.com/" + d)
        for path, body in ((self.PAGE, "hello"), ("raw/site/acme.com/images/x.png", "png"),
                           ("raw/site/acme.com/shots/index/01.png", "png"), ("raw/site/acme.com/_index/inventory.md", "t"),
                           ("raw/site/acme.com/_cache/pages/index.json", "{}"), ("raw/site/_sites.json", "{}")):
            with open(path, "w") as f:
                f.write(body)

    def tearDown(self):
        os.chdir(self.cwd)
        bst.ROOT = self.root
        self.tmp.cleanup()

    def test_raw_files_skip_pictures_and_the_crawlers_own_files(self):
        self.assertEqual(list(bst.raw_files()), [self.PAGE])

    def test_a_file_ingested_before_it_was_skipped_is_not_reported_removed(self):
        bst.save_manifest({self.PAGE: bst.sha(self.PAGE), "raw/site/acme.com/images/x.png": "old", "raw/site/acme.com/gone.md": "old"})
        self.assertEqual(bst.status()["removed"], ["raw/site/acme.com/gone.md"])

    def test_the_manifest_is_moved_into_place_whole(self):
        bst.mark()
        self.assertFalse(os.path.exists(bst.manifest_path() + ".tmp"))
        with open(bst.manifest_path()) as f:
            self.assertIn(self.PAGE, json.load(f))

    def test_status_then_mark_then_change(self):
        self.assertEqual(bst.status()["new"], [self.PAGE])
        self.assertEqual(bst.mark(), (1, 0, 0))
        self.assertEqual(bst.mark(), (0, 1, 0))
        self.assertEqual(bst.status(), {"new": [], "changed": [], "removed": [], "units": {}})
        with open(self.PAGE, "w") as f:
            f.write("hello again")
        self.assertEqual(bst.status()["changed"], [self.PAGE])
        with open("raw/docs.md", "w") as f:
            f.write("doc")
        # marking one path leaves the other pending
        bst.mark(["raw/docs.md"])
        st = bst.status()
        self.assertEqual((st["new"], st["changed"], st["removed"]), ([], [self.PAGE], []))
        self.assertEqual(st["units"], {"raw/site/acme.com": {"new": 0, "changed": 1}})

    def test_mark_a_folder_marks_every_file_under_it(self):
        with open("raw/site/acme.com/pages/about.md", "w") as f:
            f.write("about")
        self.assertEqual(bst.mark(["raw/site/acme.com"]), (2, 0, 0))
        self.assertEqual(bst.status()["new"], [])
        with self.assertRaises(ValueError):
            bst.mark(["raw/site/nope.com"])
        with self.assertRaises(ValueError):
            bst.mark(["raw/site/acme.com/images"])

    def main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = bst.main(list(args))
        return code, out.getvalue()

    def test_a_removed_file_is_cleared_by_marking_its_path(self):
        bst.mark()
        bst.save_manifest({**bst.load_manifest(), "raw/docs/2026-09-01-old.md": "old", "raw/transcripts/a.md": "old"})
        code, out = self.main("status")
        self.assertEqual(code, 1)
        self.assertIn("2 raw file(s) removed since they were distilled", out)
        self.assertIn("raw/docs/2026-09-01-old.md  (1 removed)", out)
        self.assertIn("mark <path>", out.splitlines()[-1])
        code, out = self.main("mark", "raw/docs/2026-09-01-old.md")
        self.assertEqual(code, 0, out)
        self.assertIn("1 removed from raw/ recorded as removed", out)
        # the other removal stays until its own path is marked
        self.assertEqual(bst.status()["removed"], ["raw/transcripts/a.md"])
        self.assertEqual(self.main("mark", "raw/transcripts")[0], 0)
        self.assertEqual(self.main("status")[0], 0)

    def test_a_crawl_in_passes_marks_and_checks_one_section(self):
        for name in ("services-boilers", "services-heat-pumps", "about"):
            with open(f"raw/site/acme.com/pages/{name}.md", "w") as f:
                f.write(name)
        section = ["raw/site/acme.com/pages/services-boilers.md", "raw/site/acme.com/pages/services-heat-pumps.md"]
        code, out = self.main("status", *section)
        self.assertEqual(code, 1)
        self.assertIn("2 new raw file(s) under", out)
        self.assertIn("new      raw/site/acme.com/pages/services-boilers.md", out)
        self.assertEqual(self.main("mark", *section)[0], 0)
        code, out = self.main("status", *section)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing pending under", out)
        # the rest of the site is still pending, counted on the site's line
        code, out = self.main("status")
        self.assertEqual(code, 1)
        self.assertIn("raw/site/acme.com  (2 new, 0 changed)", out)
        self.assertEqual(self.main("status", "raw/site/nope.com")[0], 2)


class CommandTests(unittest.TestCase):
    SCRIPT = os.path.join(SCRIPTS, "brain_status.py")

    def run_it(self, *args):
        return subprocess.run([sys.executable, self.SCRIPT, *args], capture_output=True, text=True)

    def test_help_and_misuse(self):
        self.assertEqual(self.run_it("--help").returncode, 0)
        self.assertEqual(self.run_it("status", "--help").returncode, 0)
        for bad in (("frobnicate",), ("status", "--bogus"), ("status", "raw/nope"), ("mark",),
                    ("mark", "--all", "raw"), ("mark", "raw/nope")):
            r = self.run_it(*bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertEqual(r.stdout, "", bad)
            self.assertIn("Try: ", r.stderr, bad)
        self.assertEqual(self.run_it("-h").returncode, 0)
        r = self.run_it("status", "--json", "--bogus")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stderr)["try"], "python3 scripts/brain_status.py status --help")

    def test_the_app_root_is_found_from_any_directory(self):
        with tempfile.TemporaryDirectory() as app:
            os.makedirs(os.path.join(app, "scripts"))
            os.makedirs(os.path.join(app, "raw", "docs"))
            os.makedirs(os.path.join(app, "elsewhere"))
            for name in ("brain_status.py", "cli.py"):
                with open(os.path.join(SCRIPTS, name)) as src, \
                        open(os.path.join(app, "scripts", name), "w") as dst:
                    dst.write(src.read())
            with open(os.path.join(app, "raw", "docs", "a.md"), "w") as f:
                f.write("a")
            script = os.path.join(app, "scripts", "brain_status.py")

            def run(*a):
                return subprocess.run([sys.executable, script, *a], capture_output=True, text=True,
                                      cwd=os.path.join(app, "elsewhere"))

            r = run("status")
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("raw/docs/a.md", r.stdout)
            self.assertEqual(run("mark", "raw/docs/a.md").returncode, 0)
            self.assertTrue(os.path.exists(os.path.join(app, "brain", ".ingested.json")))
            self.assertEqual(run("status").returncode, 0)


if __name__ == "__main__":
    unittest.main()
