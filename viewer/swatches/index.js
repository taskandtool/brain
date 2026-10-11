// A colour written as code, `#4e3223`, shows the colour beside it, so the
// brand's colours in brand/visual-identity.md can be seen, not just read.
// Only a whole 3 or 6 digit hex becomes a style; any other code stays code.

const HEX = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i

export function swatch(node) {
  if (node.type === "inlineCode" && HEX.test(node.value)) {
    node.data = {
      ...node.data,
      hProperties: {
        ...node.data?.hProperties,
        style: `border-left: 1.2em solid ${node.value}; box-shadow: inset 0 0 0 1px var(--lightgray)`,
      },
    }
  }
  for (const child of node.children ?? []) swatch(child)
}

export default function Swatches() {
  return {
    name: "Swatches",
    markdownPlugins() {
      return [() => (tree) => swatch(tree)]
    },
  }
}
