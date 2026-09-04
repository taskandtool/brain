"""Unit tests for brain_status.py — stdlib unittest, no deps.

    python3 kits/packs/brain/brain-distill/test_brain_status.py
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
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
        self.assertEqual(bst.unit_of("raw/web/services.md"), "website")
        self.assertEqual(bst.unit_of("raw/web/faq/hours.md"), "website")
        self.assertEqual(bst.unit_of("raw/external/competitor.com/pricing.md"), "external:competitor.com")
        self.assertEqual(bst.unit_of("raw/docs/2026-09-02-brochure.md"), "raw/docs/2026-09-02-brochure.md")
        d = bst.diff({"raw/web/a.md": "1", "raw/web/b.md": "2", "raw/external/x.com/p.md": "3"}, {"raw/web/b.md": "old"})
        self.assertEqual(d["units"], {"website": {"new": 1, "changed": 1}, "external:x.com": {"new": 1, "changed": 0}})
        self.assertIn("website (1 new, 1 changed)", bst.summarize(d))

    def test_summary_lists_pending_and_caps(self):
        d = {"new": [f"raw/{i}.md" for i in range(20)], "changed": [], "removed": []}
        s = bst.summarize(d)
        self.assertIn("20 new raw file(s) not yet ingested", s)
        self.assertIn("(+5 more)", s)
        self.assertEqual(bst.summarize({"new": [], "changed": [], "removed": []}), "")


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        os.makedirs("raw/web/images")
        with open("raw/web/index.md", "w") as f:
            f.write("hello")
        with open("raw/web/_manifest.json", "w") as f:
            f.write("{}")
        with open("raw/web/images/x.png", "wb") as f:
            f.write(b"png")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_raw_files_skip_images_and_underscore_files(self):
        self.assertEqual(list(bst.raw_files()), ["raw/web/index.md"])

    def test_status_then_mark_then_change(self):
        self.assertEqual(bst.status()["new"], ["raw/web/index.md"])
        self.assertEqual(bst.mark(), 1)
        self.assertEqual(bst.status(), {"new": [], "changed": [], "removed": [], "units": {}})
        with open("raw/web/index.md", "w") as f:
            f.write("hello again")
        self.assertEqual(bst.status()["changed"], ["raw/web/index.md"])
        with open("raw/docs.md", "w") as f:
            f.write("doc")
        # marking one path leaves the other pending
        bst.mark(["raw/docs.md"])
        st = bst.status()
        self.assertEqual((st["new"], st["changed"], st["removed"]), ([], ["raw/web/index.md"], []))
        self.assertEqual(st["units"], {"website": {"new": 0, "changed": 1}})

    def test_hook_blocks_once_with_the_list_then_never_loops(self):
        out, code = bst.hook_stop("{}")
        self.assertEqual(code, 0)
        decision = json.loads(out)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("raw/web/index.md", decision["reason"])
        self.assertIn("brain-distill", decision["reason"])
        # the second stop, while already continuing from this hook, passes
        self.assertEqual(bst.hook_stop(json.dumps({"stop_hook_active": True})), ("", 0))
        # nothing pending → silent pass
        bst.mark()
        self.assertEqual(bst.hook_stop("{}"), ("", 0))
        # garbage stdin is not an error
        self.assertEqual(bst.hook_stop("not json")[1], 0)


if __name__ == "__main__":
    unittest.main()
