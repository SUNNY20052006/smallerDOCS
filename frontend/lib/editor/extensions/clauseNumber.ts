import { Node } from "@tiptap/core";

export const ClauseNumber = Node.create({
  name: "clauseNumber",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,

  addAttributes() {
    return {
      numberingStyle: { default: "legal_decimal" },
      depth: { default: 1 },
      display: { default: "" },
    };
  },

  parseHTML() {
    return [{ tag: "span[data-clause-number]" }];
  },

  renderHTML({ node }) {
    return [
      "span",
      {
        "data-clause-number": "",
        contenteditable: "false",
        class: "clause-number",
      },
      node.attrs.display,
    ];
  },
});
