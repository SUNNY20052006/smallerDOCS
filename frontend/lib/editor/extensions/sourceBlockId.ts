import { Extension } from "@tiptap/core";

const TYPES = [
  "paragraph",
  "heading",
  "bulletList",
  "orderedList",
  "listItem",
  "table",
  "tableRow",
  "tableCell",
  "tableHeader",
];

export const SourceBlockId = Extension.create({
  name: "sourceBlockId",

  addGlobalAttributes() {
    return [
      {
        types: TYPES,
        attributes: {
          sourceBlockId: {
            default: null,
            parseHTML: (element) => element.getAttribute("data-source-block-id"),
            renderHTML: (attributes) =>
              attributes.sourceBlockId ? { "data-source-block-id": attributes.sourceBlockId } : {},
          },
          indentLevel: {
            default: 0,
          },
          blockRole: {
            default: null,
          },
        },
      },
    ];
  },
});
