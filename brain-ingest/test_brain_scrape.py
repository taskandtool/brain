"""Unit tests for brain_scrape.py's pure helpers — stdlib unittest, no deps.

    python3 kits/packs/brain/brain-ingest/test_brain_scrape.py

(Run the file directly — `unittest discover` can't import the hyphenated kit
skill dir as a package.) The trafilatura import in brain_scrape is lazy
(inside main), so these run
without installing it. This is the kit-code test tier (see docs/plans/kits.md
"Testing a kit").
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import brain_scrape as bs  # noqa: E402


class SlugTests(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(bs.slugify("https://x.com/services/"), "services")
        self.assertEqual(bs.slugify("https://x.com/"), "index")
        self.assertEqual(bs.slugify("https://x.com"), "index")
        self.assertEqual(bs.slugify("https://x.com/a/b/c/"), "a-b-c")

    def test_truncated_and_safe(self):
        slug = bs.slugify("https://x.com/" + "z" * 200)
        self.assertLessEqual(len(slug), 80)
        self.assertRegex(slug, r"^[a-z0-9-]+$")


class ExtTests(unittest.TestCase):
    def test_from_path_and_ctype(self):
        self.assertEqual(bs.ext_for("https://x.com/a.png", ""), "png")
        self.assertEqual(bs.ext_for("https://x.com/a", "image/png"), "png")
        self.assertEqual(bs.ext_for("https://x.com/a.JPEG", ""), "jpg")  # normalized
        self.assertEqual(bs.ext_for("https://x.com/a", "image/svg+xml"), "img")  # not [a-z0-9]{2,5}


class SameSiteTests(unittest.TestCase):
    def test(self):
        self.assertTrue(bs.same_site("https://x.com/a", "x.com"))
        self.assertFalse(bs.same_site("https://evil.com/a", "x.com"))
        self.assertFalse(bs.same_site("https://sub.x.com/a", "x.com"))


class SsrfGuardTests(unittest.TestCase):
    def test_private_and_loopback_refused(self):
        self.assertFalse(bs.is_public_host("127.0.0.1"))
        self.assertFalse(bs.is_public_host("192.168.1.1"))
        self.assertFalse(bs.is_public_host("10.0.0.5"))
        self.assertFalse(bs.is_public_host("localhost"))

    def test_public_allowed(self):
        self.assertTrue(bs.is_public_host("8.8.8.8"))

    def test_unresolvable_refused(self):
        self.assertFalse(bs.is_public_host("nonexistent.invalid"))


class DedupTests(unittest.TestCase):
    def test_identical_is_near_dup(self):
        text = "the quick brown fox jumps over the lazy dog again and again " * 5
        dup, sset = bs.near_duplicate(text, [])
        self.assertFalse(dup)  # nothing kept yet
        dup2, _ = bs.near_duplicate(text, [sset])
        self.assertTrue(dup2)  # identical vs the kept set

    def test_different_is_not_dup(self):
        a = "hydraulic cylinder repair and hose crimping services in springfield " * 3
        b = "we bake sourdough bread and pastries fresh every morning downtown " * 3
        _, sa = bs.near_duplicate(a, [])
        dup, _ = bs.near_duplicate(b, [sa])
        self.assertFalse(dup)


class MarkdownImageTests(unittest.TestCase):
    def test_extracts_image_urls(self):
        md = "text ![alt](https://x.com/a.jpg) more ![](images/b.png) end"
        self.assertEqual(
            bs.MD_IMAGE_RE.findall(md),
            ["https://x.com/a.jpg", "images/b.png"],
        )

    def test_ignores_plain_links(self):
        md = "a [link](https://x.com/page) not an image"
        self.assertEqual(bs.MD_IMAGE_RE.findall(md), [])


class RewriteImagesTests(unittest.TestCase):
    def test_rewrites_only_mapped_image_tokens(self):
        md = "![a](https://x.com/a.jpg) and ![b](https://x.com/a.jpg?w=800)"
        out = bs.rewrite_images(md, {"https://x.com/a.jpg": "images/h1.jpg"})
        # the first is rewritten; the ?w=800 variant is NOT clobbered by the
        # substring of the first (the bug this fix closes)
        self.assertEqual(out, "![a](images/h1.jpg) and ![b](https://x.com/a.jpg?w=800)")

    def test_never_touches_a_link_sharing_the_url(self):
        md = "![img](https://x.com/a.jpg) see [also](https://x.com/a.jpg)"
        out = bs.rewrite_images(md, {"https://x.com/a.jpg": "images/h1.jpg"})
        self.assertEqual(out, "![img](images/h1.jpg) see [also](https://x.com/a.jpg)")

    def test_unmapped_left_alone(self):
        md = "![x](https://x.com/unfetched.jpg)"
        self.assertEqual(bs.rewrite_images(md, {}), md)




class _Proc:
    def __init__(self, returncode=0, stdout=b""):
        self.returncode = returncode
        self.stdout = stdout


class RenderFallbackTests(unittest.TestCase):
    def test_find_obscura_prefers_explicit_env_and_refuses_a_missing_one(self):
        self.assertEqual(
            bs.find_obscura(env={"OBSCURA_BIN": "/x/obscura"}, which=lambda _: None,
                            exists=lambda p: p == "/x/obscura"),
            "/x/obscura")
        # an explicit path that does not exist is a misconfiguration, not a
        # reason to silently pick another binary
        self.assertIsNone(
            bs.find_obscura(env={"OBSCURA_BIN": "/gone"}, which=lambda _: "/usr/bin/obscura",
                            exists=lambda p: p != "/gone"))

    def test_find_obscura_path_then_install_locations_then_none(self):
        self.assertEqual(bs.find_obscura(env={}, which=lambda _: "/usr/bin/obscura",
                                         exists=lambda p: False), "/usr/bin/obscura")
        self.assertEqual(bs.find_obscura(env={}, which=lambda _: None,
                                         exists=lambda p: p == "/usr/local/bin/obscura"),
                         "/usr/local/bin/obscura")
        self.assertIsNone(bs.find_obscura(env={}, which=lambda _: None, exists=lambda p: False))

    def test_render_html_returns_rendered_dom(self):
        seen = {}

        def runner(cmd, **kw):
            seen["cmd"] = cmd
            return _Proc(0, b"<html><body><p>hello from js</p></body></html>")

        out = bs.render_html("https://x.com/a", "/bin/obscura", runner=runner)
        self.assertIn("hello from js", out)
        self.assertEqual(seen["cmd"][:3], ["/bin/obscura", "fetch", "https://x.com/a"])
        self.assertIn("--dump", seen["cmd"])
        self.assertIn("html", seen["cmd"])
        # the private-network override must never be passed: the SSRF rail
        # on the render path IS obscura's default refusal
        self.assertNotIn("--allow-private-network", seen["cmd"])

    def test_render_html_failure_modes_are_none_not_exceptions(self):
        import subprocess as sp
        self.assertIsNone(bs.render_html("https://x.com", "/bin/o", runner=lambda c, **k: _Proc(1, b"")))
        self.assertIsNone(bs.render_html("https://x.com", "/bin/o", runner=lambda c, **k: _Proc(0, b"  \n")))

        def timeout(c, **k):
            raise sp.TimeoutExpired(c, 1)

        def missing(c, **k):
            raise OSError("no such binary")

        self.assertIsNone(bs.render_html("https://x.com", "/bin/o", runner=timeout))
        self.assertIsNone(bs.render_html("https://x.com", "/bin/o", runner=missing))




class UrlTests(unittest.TestCase):
    def test_normalize_drops_fragment_tracking_and_trailing_slash(self):
        self.assertEqual(bs.normalize_url("https://X.com/About/?utm_source=x&b=2#top"),
                         "https://x.com/About?b=2")
        self.assertEqual(bs.normalize_url("https://x.com/"), "https://x.com/")
        self.assertEqual(bs.normalize_url("https://x.com"), "https://x.com/")
        self.assertIsNone(bs.normalize_url("mailto:a@x.com"))
        self.assertIsNone(bs.normalize_url("javascript:void(0)"))

    def test_crawlable_skips_binary_and_asset_urls(self):
        self.assertTrue(bs.crawlable("https://x.com/services"))
        self.assertFalse(bs.crawlable("https://x.com/brochure.PDF"))
        self.assertFalse(bs.crawlable("https://x.com/a.jpg"))

    def test_parse_sitemap(self):
        xml = "<urlset><url><loc> https://x.com/a </loc></url><url><loc>https://x.com/b</loc></url></urlset>"
        self.assertEqual(bs.parse_sitemap(xml), ["https://x.com/a", "https://x.com/b"])


class ImageKeyTests(unittest.TestCase):
    def test_size_variants_and_queries_collapse(self):
        k = bs.image_key("https://x.com/wp-content/uploads/team.jpg")
        self.assertEqual(bs.image_key("https://x.com/wp-content/uploads/team-300x200.jpg?v=3"), k)
        self.assertEqual(bs.image_key("https://X.com/wp-content/uploads/team-scaled.jpg"), k)
        self.assertEqual(bs.image_key("https://x.com/wp-content/uploads/team@2x.jpg"), k)
        # a genuinely different picture stays different
        self.assertNotEqual(bs.image_key("https://x.com/wp-content/uploads/team2.jpg"), k)


class BoilerplateTests(unittest.TestCase):
    NAV = "[Home](/) [Services](/services) [Contact](/contact)"
    FOOTER = "© 2026 Acme Hydraulics · 12 Main St · 555-0100"
    LOGO = "![Acme Hydraulics](https://example.com/logo.png)"

    def page(self, body):
        return f"{self.LOGO}\n{self.NAV}\n\n{body}\n\n{self.FOOTER}\n"

    def test_repeated_lines_are_removed_and_kept_once(self):
        pages = [self.page(f"# Page {i}\n\nUnique content number {i} about heat pumps.") for i in range(6)]
        cleaned, common = bs.strip_common_lines(pages)
        for i, md in enumerate(cleaned):
            self.assertIn(f"Unique content number {i}", md)
            self.assertNotIn("555-0100", md)
            self.assertNotIn("logo.png", md)          # the header logo is gone → never fetched
            self.assertNotIn("[Home](/)", md)
        self.assertEqual(common, [self.LOGO, self.NAV, self.FOOTER])   # first-seen order, once

    def test_threshold_spares_content_two_pages_share(self):
        shared = "We are licensed and insured."
        pages = [self.page(f"# P{i}\n\n{shared if i < 2 else 'Other text ' + str(i)}") for i in range(6)]
        cleaned, _ = bs.strip_common_lines(pages)
        self.assertIn(shared, cleaned[0])

    def test_small_sites_untouched(self):
        pages = [self.page("body") for _ in range(3)]
        cleaned, common = bs.strip_common_lines(pages)
        self.assertEqual(cleaned, pages)
        self.assertEqual(common, [])

    def test_threshold(self):
        self.assertEqual(bs.boilerplate_threshold(4), 3)
        self.assertEqual(bs.boilerplate_threshold(6), 3)
        self.assertEqual(bs.boilerplate_threshold(30), 10)
        self.assertEqual(bs.boilerplate_threshold(100), 34)


if __name__ == "__main__":
    unittest.main()
