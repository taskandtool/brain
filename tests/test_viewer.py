"""Unit tests for viewer.py — stdlib unittest, no deps, no Quartz.

    python3 tests/test_viewer.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import viewer as vw  # noqa: E402


class AppTest(unittest.TestCase):
    """A throwaway app root with the given files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.saved = vw.ROOT
        vw.ROOT = self.root

    def tearDown(self):
        vw.ROOT = self.saved
        self.tmp.cleanup()

    def write(self, path, text=""):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)
        return full


class CheckTests(AppTest):
    def test_a_bare_citation_names_the_link_to_write_from_where_the_note_sits(self):
        self.write("raw/site/acme.com/pages/pricing.md", "x")
        note = self.write("brain/sops/refunds.md", "Refunds in 30 days (raw/site/acme.com/pages/pricing.md).\n")
        [(line, what, write)] = vw.check_file(note)
        self.assertEqual(line, 1)
        self.assertIn("is a path, not a link", what)
        self.assertEqual(write, "[pricing](../../raw/site/acme.com/pages/pricing.md)")

    def test_links_that_resolve_pass_and_ones_that_do_not_are_named(self):
        self.write("raw/docs/2026-09-02-brochure.md", "x")
        self.write("public/services.md", "x")
        note = self.write("brain/overview.md", "\n".join([
            "---",
            "sources: [raw/docs/2026-09-02-brochure.md]",
            "---",
            "Prices ([brochure](../raw/docs/2026-09-02-brochure.md)), [services](../public/services.md#repair).",
            "See [gone](../public/gone.md), [site](https://acme.com), [top](#details), [root](/raw/docs).",
            "```",
            "raw/docs/in-code.md [x](nowhere.md)",
            "```",
            "Inline `raw/docs/in-code.md` is code.",
        ]))
        found = vw.check_file(note)
        self.assertEqual([(n, w) for n, w, _ in found],
                         [(5, "../public/gone.md points nowhere"), (5, "/raw/docs starts at /")])

    def test_a_link_to_a_file_the_viewer_leaves_out_is_named(self):
        self.write("raw/places/abc.json", "{}")
        self.write("raw/site/acme.com/images/logo.svg", "<svg/>")
        self.write("brand/logo.svg", "<svg/>")
        note = self.write("public/proof.md", "[rating](../raw/places/abc.json) ![logo](../raw/site/acme.com/images/logo.svg) ![ok](../brand/logo.svg)\n")
        self.assertEqual([w for _, w, _ in vw.check_file(note)],
                         ["../raw/places/abc.json is a file the viewer leaves out",
                          "../raw/site/acme.com/images/logo.svg is a file the viewer leaves out"])

    def test_a_link_whose_text_is_a_raw_path_is_not_a_bare_citation(self):
        self.write("raw/docs/a.md", "x")
        note = self.write("brain/a.md", "See [raw/docs/a.md](../raw/docs/a.md).\n")
        self.assertEqual(vw.check_file(note), [])

    def test_the_config_never_serves_what_check_calls_left_out(self):
        text = vw.config_text()
        self.assertIn("ignorePatterns: " + json.dumps(vw.LEFT_OUT), text)
        self.assertTrue(vw.left_out("raw/site/x/_cache/page.html"))
        self.assertFalse(vw.left_out("brand/logo.svg"))

    def test_check_covers_the_note_folders_not_raw(self):
        self.write("brain/a.md", "[x](nope.md)\n")
        self.write("raw/site/acme.com/pages/a.md", "[x](nope.md) raw/elsewhere.md\n")
        self.assertEqual([f[0] for f in vw.check()], ["brain/a.md"])
        report = vw.check_report(vw.check())
        self.assertTrue(report[0].startswith("viewer check: 1 link(s) point nowhere"))
        self.assertIn("brain/a.md:1  nope.md points nowhere", report[1])

    def test_a_clean_brain_says_so(self):
        self.write("brain/a.md", "[b](b.md)\n")
        self.write("brain/b.md", "b\n")
        self.assertEqual(vw.check(), [])
        self.assertIn("every citation is a link", vw.check_report([])[0])


class StagingTests(AppTest):
    def test_the_home_page_names_the_business_and_links_every_folder(self):
        self.write("public/business.md", "---\nname: Acme Hose Co\n---\n")
        page = vw.home_page()
        self.assertIn('title: "Acme Hose Co"', page)
        for target in ("brain/overview.md", "brain/", "brand/", "public/", "raw/"):
            self.assertIn(f"]({target})", page)

    def test_stage_links_the_folders_and_makes_missing_ones(self):
        self.write("brain/overview.md", "x")
        content = os.path.join(self.root, "content")
        saved = vw.QUARTZ_DIR
        vw.QUARTZ_DIR = os.path.join(self.root, "quartz")
        os.makedirs(vw.QUARTZ_DIR)
        self.write("viewer/quartz.config.yaml", "x")
        saved_viewer, vw.VIEWER = vw.VIEWER, os.path.join(self.root, "viewer")
        try:
            vw.stage(content)
            vw.stage(content)
        finally:
            vw.QUARTZ_DIR, vw.VIEWER = saved, saved_viewer
        self.assertEqual(sorted(os.listdir(content)), ["brain", "brand", "index.md", "legal", "public", "raw"])
        self.assertTrue(os.path.isdir(os.path.join(self.root, "raw")))
        self.assertEqual(os.path.realpath(os.path.join(content, "brain")), os.path.join(self.root, "brain"))

    def test_the_title_is_the_business_name_until_the_owner_sets_another(self):
        self.write("viewer/quartz.config.yaml", "configuration:\n  pageTitle: Company Brain\nsource: \"@SAFE_TEXT@\"\n")
        saved = vw.VIEWER
        vw.VIEWER = os.path.join(self.root, "viewer")
        try:
            self.assertIn("pageTitle: Company Brain", vw.config_text())
            self.write("public/business.md", "---\nname: to fill\n---\n")
            self.assertIn("pageTitle: Company Brain", vw.config_text())
            self.write("public/business.md", "---\nname: \"Joe's #1 Plumbing\"  # trading name\n---\n")
            text = vw.config_text()
            self.assertIn('pageTitle: "Joe\'s #1 Plumbing"', text)
            self.assertIn(os.path.join(vw.VIEWER, "safe-text"), text)
            self.write("viewer/quartz.config.yaml", "configuration:\n  pageTitle: Our Wiki\n")
            self.assertIn("pageTitle: Our Wiki", vw.config_text())
        finally:
            vw.VIEWER = saved

    def test_prune_drops_what_cloudflare_will_not_take(self):
        self.write("dist/index.html", "x")
        self.write("dist/raw/docs/huge.pdf", "x" * 50)
        saved = vw.MAX_ASSET
        vw.MAX_ASSET = 10
        try:
            kept, dropped = vw.prune(os.path.join(self.root, "dist"))
        finally:
            vw.MAX_ASSET = saved
        self.assertEqual(kept, 1)
        self.assertEqual(dropped, [("raw/docs/huge.pdf", 50)])
        self.assertFalse(os.path.exists(os.path.join(self.root, "dist/raw/docs/huge.pdf")))


class CommandTests(unittest.TestCase):
    SCRIPT = os.path.join(SCRIPTS, "viewer.py")

    def run_it(self, *args):
        return subprocess.run([sys.executable, self.SCRIPT, *args], capture_output=True, text=True)

    def test_help_and_misuse(self):
        for ok in (("--help",), ("-h",), ("check", "--help"), ("dev", "-h")):
            r = self.run_it(*ok)
            self.assertEqual(r.returncode, 0, ok)
            self.assertTrue(r.stdout.strip(), ok)
        for bad in (("frobnicate",), ("check", "--bogus"), ("build", "extra"), ("dev", "--port", "x"), ()):
            r = self.run_it(*bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertEqual(r.stdout, "", bad)
            self.assertIn("Try: ", r.stderr, bad)

    def test_check_exits_1_while_anything_needs_fixing(self):
        with tempfile.TemporaryDirectory() as app:
            os.makedirs(os.path.join(app, "scripts"))
            for name in ("viewer.py", "cli.py"):
                with open(os.path.join(SCRIPTS, name)) as src, \
                        open(os.path.join(app, "scripts", name), "w") as dst:
                    dst.write(src.read())
            os.makedirs(os.path.join(app, "brain"))
            note = os.path.join(app, "brain", "a.md")
            with open(note, "w") as f:
                f.write("See (raw/docs/a.md).\n")
            r = subprocess.run([sys.executable, os.path.join(app, "scripts", "viewer.py"), "check"],
                               capture_output=True, text=True, cwd="/")
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("write [a](../raw/docs/a.md)", r.stdout)
            with open(note, "w") as f:
                f.write("Nothing cited.\n")
            r = subprocess.run([sys.executable, os.path.join(app, "scripts", "viewer.py"), "check"],
                               capture_output=True, text=True, cwd="/")
            self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
