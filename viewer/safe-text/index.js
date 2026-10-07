// Everything in raw/ came from somewhere the owner does not control: a crawled
// page, a review, a competitor's site. Quartz renders HTML inside markdown as
// HTML, so a page carrying <script> would run in the viewer. This plugin runs
// first and turns every HTML node into plain text, and points any link or
// picture whose scheme is not a web, mail or phone one at nothing. Search
// writes a page's title and tags into its results as HTML, so those lose
// their angle brackets once the frontmatter is read.

const SAFE_SCHEMES = new Set(["http", "https", "mailto", "tel"])

export function isSafeUrl(url) {
  const match = /^\s*([a-z][a-z0-9+.-]*):/i.exec(String(url ?? ""))
  return !match || SAFE_SCHEMES.has(match[1].toLowerCase())
}

export function neutralize(node) {
  if (node.type === "html") {
    node.type = "text"
  } else if ("url" in node && !isSafeUrl(node.url)) {
    node.url = "#"
  }
  for (const child of node.children ?? []) neutralize(child)
}

export function cleanFrontmatter(frontmatter) {
  if (!frontmatter) return
  const strip = (value) => (typeof value === "string" ? value.replace(/[<>]/g, "") : value)
  if (typeof frontmatter.title === "string") frontmatter.title = strip(frontmatter.title)
  if (Array.isArray(frontmatter.tags)) frontmatter.tags = frontmatter.tags.map(strip)
}

function remarkSafeText() {
  return (tree) => neutralize(tree)
}

export default function SafeText() {
  return {
    name: "SafeText",
    markdownPlugins() {
      return [remarkSafeText]
    },
    htmlPlugins() {
      return [() => (_tree, file) => cleanFrontmatter(file.data.frontmatter)]
    },
  }
}
