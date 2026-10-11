"""Unit tests for viewer.py — stdlib unittest, no deps, no Quartz.

    python3 tests/test_viewer.py
"""
import json
import os
import re
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

    def test_left_out_ignores_letter_case_and_covers_every_runnable_type(self):
        for path in ("raw/external/x.com/logo.SVG", "raw/a/p.HTML", "raw/a/q.shtml", "raw/a/r.xht",
                     "raw/a/s.svgz", "brand/x.Js", "public/y.XSL", "raw/a/z.mhtml"):
            self.assertTrue(vw.left_out(path), path)
        for path in ("brand/logo.SVG", "raw/site/a.com/images/photo.JPG", "brain/a.md"):
            self.assertFalse(vw.left_out(path), path)
        # The Quartz globs say the same: one any-case pattern per type.
        self.assertEqual(vw.any_case("svg"), "[sS][vV][gG]")
        for ext in vw.NEVER_SERVED:
            self.assertIn(f"**/*.{vw.any_case(ext)}", vw.LEFT_OUT)
        for ext in vw.NEVER_SERVED_FROM_RAW:
            self.assertIn(f"raw/**/*.{vw.any_case(ext)}", vw.LEFT_OUT)

    def test_a_link_outside_the_viewers_folders_is_named(self):
        self.write("README.md", "x")
        note = self.write("brain/a.md", "[readme](../README.md)\n")
        [(_, what, _)] = vw.check_file(note)
        self.assertIn("is outside what the viewer shows", what)

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
        for target in ("brain/", "brand/", "public/", "raw/"):
            self.assertIn(f"]({target})", page)

    def test_every_home_page_link_has_a_page_on_a_fresh_brain(self):
        # Against the repository as it ships: a folder with no file in it has
        # no page in Quartz, so each linked folder must ship one.
        shipped = os.path.realpath(os.path.join(SCRIPTS, ".."))
        for target in re.findall(r"\]\(([^)]+)\)", vw.home_page()):
            folder = os.path.join(shipped, target)
            files = [n for n in os.listdir(folder) if n.endswith(".md")] if os.path.isdir(folder) else []
            self.assertTrue(files, f"{target} ships no page")

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
        for bad in (("frobnicate",), ("check", "--bogus"), ("build", "extra"), ("dev", "extra"), ()):
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


class InstallTests(AppTest):
    def test_the_quartz_patches_apply_once_and_refuse_other_code(self):
        saved = vw.QUARTZ_DIR
        vw.QUARTZ_DIR = os.path.join(self.root, "quartz")
        try:
            # the folder lists, and the dev server's watch of public/
            self.assertEqual([p[0] for p in vw.QUARTZ_PATCHES],
                             ["quartz/plugins/pageTypes/dispatcher.ts", "quartz/build.ts"])
            paths = []
            for name, shipped, _ in vw.QUARTZ_PATCHES:
                paths.append(self.write(os.path.join("quartz", name), "before\n" + shipped + "after\n"))
            vw.patch_quartz()
            vw.patch_quartz()
            for path, (_, _, fixed) in zip(paths, vw.QUARTZ_PATCHES):
                with open(path) as f:
                    self.assertEqual(f.read(), "before\n" + fixed + "after\n")
            self.write(os.path.join("quartz", vw.QUARTZ_PATCHES[1][0]), "some other Quartz\n")
            with self.assertRaises(vw.Failed) as e:
                vw.patch_quartz()
            self.assertIn("move", e.exception.try_cmd)
            self.assertNotIn("rm -rf", e.exception.try_cmd)
        finally:
            vw.QUARTZ_DIR = saved

    def test_the_patches_match_the_pinned_quartz(self):
        # Against the real Quartz install when this computer has one.
        source = os.path.expanduser(f"~/.local/share/company-brain/quartz-{vw.QUARTZ_TAG}")
        if not os.path.isdir(source):
            self.skipTest("no Quartz installed here")
        for name, shipped, fixed in vw.QUARTZ_PATCHES:
            with open(os.path.join(source, name)) as f:
                text = f.read()
            self.assertTrue(shipped in text or fixed in text, name)

    def fake_clone(self, calls):
        """vw.run that makes a clone where git was asked to, and stops the
        install at the next step (npm), so nothing touches the network."""
        def run(args, cwd, what, try_cmd=None):
            calls.append(args)
            if args[0] == "git":
                os.makedirs(os.path.join(args[-1], ".git"))
                return ""
            raise vw.Failed("stopped after the clone")
        return run

    def with_quartz_dir(self, fn):
        saved = (vw.QUARTZ_DIR, vw.run, vw.node_major)
        vw.QUARTZ_DIR = os.path.join(self.root, "share", "quartz")
        vw.node_major = lambda: 24
        try:
            fn()
        finally:
            vw.QUARTZ_DIR, vw.run, vw.node_major = saved

    def test_a_folder_that_is_not_a_clone_is_left_alone(self):
        def go():
            keep = self.write("share/quartz/notes.txt", "not ours")
            calls = []
            vw.run = self.fake_clone(calls)
            with self.assertRaises(vw.Failed) as e:
                vw._install()
            self.assertIn("is not a Quartz clone", str(e.exception))
            self.assertTrue(os.path.exists(keep))
            self.assertEqual(calls, [])
        self.with_quartz_dir(go)

    def test_the_clone_lands_whole_or_not_at_all(self):
        def go():
            self.write("share/quartz.partial/half.txt", "a clone cut off earlier")
            calls = []
            vw.run = self.fake_clone(calls)
            with self.assertRaises(vw.Failed):
                vw._install()
            self.assertEqual(calls[0][-1], vw.QUARTZ_DIR + ".partial")
            self.assertTrue(os.path.isdir(os.path.join(vw.QUARTZ_DIR, ".git")))
            self.assertFalse(os.path.exists(vw.QUARTZ_DIR + ".partial"))
            self.assertFalse(os.path.exists(os.path.join(vw.QUARTZ_DIR, "half.txt")))
        self.with_quartz_dir(go)

    def test_a_missing_or_misplaced_plugin_is_caught(self):
        def go():
            plugins = os.path.join(vw.QUARTZ_DIR, ".quartz", "plugins")
            with open(os.path.join(vw.VIEWER, "quartz.lock.json")) as f:
                names = list(json.load(f)["plugins"])
            for name in names:
                self.write(os.path.join("share/quartz/.quartz/plugins", name, "package.json"), "{}")
            # the local plugins not linked yet
            self.assertEqual(vw.plugins_missing(), list(vw.LOCAL_PLUGINS))
            for name in vw.LOCAL_PLUGINS:
                os.symlink(os.path.join(vw.VIEWER, name), os.path.join(plugins, name))
            self.assertEqual(vw.plugins_missing(), [])
            os.unlink(os.path.join(plugins, names[0], "package.json"))
            self.assertEqual(vw.plugins_missing(), [names[0]])
        self.with_quartz_dir(go)

    def test_a_build_without_its_plugins_fails_and_ships_nothing(self):
        saved = (vw._install, vw.stage, vw.run, vw.production_host, vw.QUARTZ_DIR)
        vw.QUARTZ_DIR = os.path.join(self.root, "share", "quartz")
        vw._install = lambda: False
        vw.stage = lambda content, base_url=None: None
        vw.production_host = lambda bridge=None: None

        def quartz_build(args, cwd, what, try_cmd=None):
            self.write("dist/index.html", "<p>built</p>")
            return "Parsing input files\nFailed to load plugin safe-text: Cannot find module\n"
        vw.run = quartz_build
        try:
            with self.assertRaises(vw.Failed) as e:
                vw.build()
        finally:
            vw._install, vw.stage, vw.run, vw.production_host, vw.QUARTZ_DIR = saved
        self.assertIn("without all its plugins", str(e.exception))
        self.assertFalse(os.path.exists(os.path.join(self.root, "dist")))


class ProductionTests(AppTest):
    # What `status --json` prints: the platform's serving reply as is
    # (MachineAPIController.serving_status), indented by the bridge.
    STATUS_REPLY = {
        "ok": True,
        "development_url": "https://acme-brain-dev.taskandtool.app",
        "production_url": "https://acme-brain.taskandtool.app",
        "private_paths": [],
        "deployed_at": None,
        "visible_to": "team",
        "can_deploy": True,
        "note": "Production is visible to your team.",
    }

    def test_a_build_names_production_in_link_previews(self):
        self.assertIn("baseUrl: localhost", vw.config_text())
        self.assertIn("baseUrl: acme-brain.taskandtool.app", vw.config_text("acme-brain.taskandtool.app"))
        saved = os.environ.get("HOME")
        os.environ["HOME"] = self.root  # no bridge here: nothing to ask
        try:
            self.assertIsNone(vw.production_host())
        finally:
            os.environ["HOME"] = saved

    def bridge_printing(self, reply, code=0):
        """A bridge whose `status --json` prints `reply` and exits `code`."""
        script = self.write("bridge.py", "import json, sys\n"
                            f"print(json.dumps({reply!r}, indent=2))\nsys.exit({code})\n")
        return f"{sys.executable} {script}"

    def test_production_host_reads_the_status_reply(self):
        self.assertEqual(vw.production_host(self.bridge_printing(self.STATUS_REPLY)),
                         "acme-brain.taskandtool.app")

    def test_no_production_address_is_none(self):
        self.assertIsNone(vw.production_host(self.bridge_printing(dict(self.STATUS_REPLY, production_url=None))))
        self.assertIsNone(vw.production_host(self.bridge_printing({"error": "unauthorized"}, code=1)))
        self.assertIsNone(vw.production_host(f"{sys.executable} -c 'print(\"not json\")'"))

    def test_the_build_says_when_production_is_not_known(self):
        unknown = vw.build_report(3, 5, [], None)
        self.assertIn("production's address is not known here", unknown[1])
        self.assertEqual(vw.build_report(3, 5, [], "acme-brain.taskandtool.app"),
                         ["viewer build: 3 pages and 2 other files in dist/"])


if __name__ == "__main__":
    unittest.main()
