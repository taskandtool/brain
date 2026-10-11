// The viewer's swatches plugin: a hex colour written as code shows its colour.
//
//     node --test tests/swatches.test.mjs
import { test } from "node:test"
import assert from "node:assert/strict"
import Swatches, { swatch } from "../viewer/swatches/index.js"

test("a hex colour in code gets its colour; other code is left alone", () => {
  const code = (value) => ({ type: "inlineCode", value })
  const tree = {
    type: "root",
    children: [
      { type: "tableCell", children: [code("#4e3223"), code("#FFF")] },
      code("#4e322"), code("#4e3223; background:url(x)"), code("npm run dev"),
    ],
  }
  swatch(tree)
  const [brown, white] = tree.children[0].children
  assert.match(brown.data.hProperties.style, /^border-left: 1\.2em solid #4e3223;/)
  assert.match(white.data.hProperties.style, /solid #FFF;/)
  assert.deepEqual(tree.children.slice(1).map((n) => n.data), [undefined, undefined, undefined])
})

test("Quartz sees a transformer", () => {
  const plugin = Swatches()
  assert.equal(plugin.name, "Swatches")
  assert.equal(plugin.markdownPlugins().length, 1)
})
