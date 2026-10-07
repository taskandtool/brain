// The viewer's safe-text plugin: HTML in markdown shows as text, and only
// web, mail and phone links survive.
//
//     node --test tests/safe_text.test.mjs
import { test } from "node:test"
import assert from "node:assert/strict"
import SafeText, { cleanFrontmatter, isSafeUrl, neutralize } from "../viewer/safe-text/index.js"

test("HTML anywhere in the tree becomes text, word for word", () => {
  const tree = {
    type: "root",
    children: [
      { type: "html", value: "<script>alert(1)</script>" },
      { type: "paragraph", children: [{ type: "html", value: '<img src=x onerror="alert(2)">' }] },
    ],
  }
  neutralize(tree)
  assert.deepEqual(tree.children[0], { type: "text", value: "<script>alert(1)</script>" })
  assert.equal(tree.children[1].children[0].type, "text")
})

test("a link or picture with a script scheme points at nothing", () => {
  const tree = {
    type: "root",
    children: [
      { type: "link", url: "JavaScript:alert(1)", children: [] },
      { type: "image", url: " data:text/html,<b>x</b>" },
      { type: "definition", url: "vbscript:x" },
      { type: "link", url: "https://acme.com/pricing", children: [] },
      { type: "link", url: "../raw/site/acme.com/pages/pricing.md", children: [] },
      { type: "link", url: "mailto:hi@acme.com", children: [] },
    ],
  }
  neutralize(tree)
  assert.deepEqual(
    tree.children.map((n) => n.url),
    ["#", "#", "#", "https://acme.com/pricing", "../raw/site/acme.com/pages/pricing.md", "mailto:hi@acme.com"],
  )
  assert.equal(isSafeUrl("tel:+15551234"), true)
})

test("a title and tags lose their angle brackets, since search writes them as HTML", () => {
  const frontmatter = { title: "Rival <img src=x onerror=alert(1)>", tags: ["<b>x</b>", 3], type: "<kept>" }
  cleanFrontmatter(frontmatter)
  assert.deepEqual(frontmatter, { title: "Rival img src=x onerror=alert(1)", tags: ["bx/b", 3], type: "<kept>" })
  cleanFrontmatter(undefined)
})

test("Quartz sees a transformer", () => {
  const plugin = SafeText()
  assert.equal(plugin.name, "SafeText")
  assert.equal(plugin.markdownPlugins().length, 1)
  assert.equal(plugin.htmlPlugins().length, 1)
})
