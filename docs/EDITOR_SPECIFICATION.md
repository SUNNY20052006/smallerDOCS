# EDITOR_SPECIFICATION.md

## Editor Choice

**Tiptap** (headless, ProseMirror-based), MIT licensed, actively maintained, React bindings via
`@tiptap/react`. Chosen over alternatives:

| Option | Why not chosen |
|---|---|
| Slate.js | Weaker table support out of the box; more custom code required to reach Word-like table editing (merge/split/insert row/col) which is a hard requirement. |
| Quill | Not schema-based — harder to guarantee structural validity of nested blocks (tables inside legal clauses, list indentation levels), and table support is a third-party plugin of inconsistent quality. |
| Lexical | Younger ecosystem for the specific features needed (table cell merge, custom block-level `sourceBlockId` traceability) as of this writing; steeper custom-extension burden. |
| Tiptap | ProseMirror's schema system gives strict document validity guarantees, first-party `@tiptap/extension-table` supports merge/split/insert/delete natively, and custom nodes/marks (needed for `ClauseNumber` and `sourceBlockId`) are a well-documented extension point. |

## Required Tiptap Extensions

```
@tiptap/starter-kit        # paragraph, heading, bold, italic, bulletList, orderedList, listItem,
                            # history (undo/redo), hardBreak
@tiptap/extension-underline
@tiptap/extension-text-style
@tiptap/extension-color
@tiptap/extension-highlight
@tiptap/extension-text-align
@tiptap/extension-table
@tiptap/extension-table-row
@tiptap/extension-table-cell
@tiptap/extension-table-header
@tiptap/extension-placeholder   # empty-state hint only, not a data concern
```

Plus two project-specific custom extensions:

- **`ClauseNumber`** (custom Node, `frontend/lib/editor/extensions/clauseNumber.ts`): an inline
  leaf rendered at the start of a clause paragraph, carrying `numberingStyle` and `depth` attrs.
  Rendered as non-editable text (contenteditable=false) so users can't accidentally corrupt
  auto-detected clause numbers, but can be deleted as a unit or the paragraph re-tagged via the
  toolbar.
- **`SourceBlockId`** (custom Mark, applied globally, `frontend/lib/editor/extensions/sourceBlockId.ts`):
  every node emitted from `idmToTiptap.ts` carries a `data-source-block-id` attribute equal to the
  originating IDM `Block.id`. This is the join key Comparison Mode uses. It is preserved on edit
  (ProseMirror keeps node attrs through most transforms) and is dropped only if a user creates a
  wholly new block (e.g., pressing Enter mid-paragraph creates a new paragraph with no IDM
  origin — its `sourceBlockId` is `null`, which is valid, see Reverse Mapping below).

## Tiptap Document Shape (Contract Summary)

Tiptap serializes to standard ProseMirror JSON: `{ type: "doc", content: [Node] }`. Every Node has
`type`, optional `attrs`, optional `content` (children), and leaf text nodes have `text` plus
optional `marks`. This is the exact shape `GET /document` is converted into on load, and the exact
shape `POST /export` expects as its `content` field.

```json
{
  "type": "doc",
  "content": [
    {
      "type": "heading",
      "attrs": { "level": 1, "sourceBlockId": "b-001" },
      "content": [
        { "type": "text", "text": "RESIDENTIAL LEASE AGREEMENT", "marks": [{ "type": "bold" }] }
      ]
    },
    {
      "type": "paragraph",
      "attrs": { "sourceBlockId": "b-002", "textAlign": "left", "indentLevel": 0 },
      "content": [
        { "type": "clauseNumber", "attrs": { "numberingStyle": "legal_decimal", "depth": 1, "display": "1." } },
        { "type": "text", "text": "TERM. ", "marks": [{ "type": "bold" }] },
        { "type": "text", "text": "This lease shall commence on the date first written above and continue for twelve (12) months." }
      ]
    },
    {
      "type": "table",
      "attrs": { "sourceBlockId": "b-003" },
      "content": [
        {
          "type": "tableRow",
          "content": [
            {
              "type": "tableCell",
              "attrs": { "sourceBlockId": "b-005", "colspan": 1, "rowspan": 1 },
              "content": [
                { "type": "paragraph", "content": [ { "type": "text", "text": "Monthly Rent", "marks": [{ "type": "bold" }] } ] }
              ]
            },
            {
              "type": "tableCell",
              "attrs": { "sourceBlockId": "b-006", "colspan": 1, "rowspan": 1 },
              "content": [
                { "type": "paragraph", "content": [ { "type": "text", "text": "$1,500.00" } ] }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

Note `tableCell.content` always wraps text in a `paragraph` node — this is a ProseMirror table
extension requirement (cells must contain block content), unlike the IDM where a `tableCell` holds
`runs` directly. This wrapping/unwrapping is exactly what `idmToTiptap.ts` / `tiptapToIdm.ts` do.

## Forward Mapping: IDM → Tiptap (`idmToTiptap.ts`)

| IDM `Block.type` | Tiptap node `type` | Notes |
|---|---|---|
| `heading` | `heading` | `attrs.level` copied directly |
| `paragraph` | `paragraph` | `attrs.textAlign` ← `alignment`; `attrs.indentLevel` ← `indentLevel` |
| `list` (listType=bullet) | `bulletList` | children mapped to `listItem` |
| `list` (listType=ordered) | `orderedList` | `attrs.start` ← `startNumber` |
| `listItem` | `listItem` → wraps a `paragraph` | `indentLevel` handled via nested `bulletList`/`orderedList` for depth > 0 |
| `table` | `table` | — |
| `tableRow` | `tableRow` | — |
| `tableCell` | `tableCell` | `runs` wrapped into a single child `paragraph`; `colSpan`/`rowSpan` → `attrs.colspan`/`rowspan` |
| `clauseNumber` | inline `clauseNumber` node prepended to the following `paragraph`'s content | `display` attr computed from `numberingStyle`+running counter at conversion time |
| `signatureLine` | `paragraph` with `attrs.blockRole: "signatureLine"` | plain paragraph, role kept for potential future styling only |
| `pageBreak` | `paragraph` with `attrs.blockRole: "pageBreak"` and a horizontal-rule-styled render | Tiptap has no native hard page break node in v1; represented as a styled marker paragraph |

Run → text node marks:

| IDM `Run.marks` field | Tiptap mark |
|---|---|
| `bold: true` | `{ type: "bold" }` |
| `italic: true` | `{ type: "italic" }` |
| `underline: true` | `{ type: "underline" }` |
| (editor-only, absent from fresh OCR output) `color` | `{ type: "textStyle", attrs: { color: "#hex" } }` |
| (editor-only) `highlight` | `{ type: "highlight", attrs: { color: "#hex" } }` |

Every produced node/mark set that has an IDM origin receives `attrs.sourceBlockId = Block.id` (on
block-level nodes) so Comparison Mode can resolve clicks. Text nodes do not carry
`sourceBlockId` individually — traceability is at block granularity, which is sufficient for the
highlight feature and keeps text nodes mergeable by ProseMirror's normal coalescing.

## Reverse Mapping: Tiptap → IDM (`tiptapToIdm.ts`)

Used at export time and whenever the frontend needs to persist edits. This is the inverse table
above, plus these rules for content that didn't originate from the IDM:

- A block-level node with `attrs.sourceBlockId === null` (user-created via Enter/paste) is
  assigned a **new** `Block.id` (fresh UUID) and `bbox: null`. `confidence` is set to `1.0`
  (user-authored, not OCR-derived).
- A block whose `sourceBlockId` matches an IDM block but whose text content has changed keeps the
  original `id` and `bbox` (still useful for Comparison Mode — "roughly this region changed") but
  `confidence` is reset to `1.0` since the text is now user-verified/edited, not OCR output.
- `clauseNumber` inline nodes are re-collapsed into a sibling `clauseNumber` IDM block preceding
  the paragraph, mirroring the forward direction exactly (fully reversible).

The reverse mapping is what `POST /api/v1/export/{jobId}` runs server-side on the posted Tiptap
JSON before handing off to `idm_to_docx.py` / `idm_to_html.py` — see `EXPORT_SYSTEM.md`.

## Toolbar → Tiptap Command Mapping (reference, not exhaustive)

| Toolbar action | Tiptap command |
|---|---|
| Bold | `editor.chain().focus().toggleBold().run()` |
| Italic | `editor.chain().focus().toggleItalic().run()` |
| Underline | `editor.chain().focus().toggleUnderline().run()` |
| Text color | `editor.chain().focus().setColor(hex).run()` |
| Highlight | `editor.chain().focus().toggleHighlight({ color: hex }).run()` |
| Align left/center/right/justify | `editor.chain().focus().setTextAlign(value).run()` |
| Bullet list | `editor.chain().focus().toggleBulletList().run()` |
| Numbered list | `editor.chain().focus().toggleOrderedList().run()` |
| Indent / Outdent | Custom command adjusting `indentLevel` attr (Tiptap has no built-in indent for paragraphs; StarterKit's `Sink/LiftListItem` handles list depth, a custom command handles paragraph-level indent) |
| Insert table | `editor.chain().focus().insertTable({ rows: 2, cols: 2, withHeaderRow: false }).run()` |
| Merge cells | `editor.chain().focus().mergeCells().run()` |
| Split cell | `editor.chain().focus().splitCell().run()` |
| Insert row/col before/after | `addRowBefore()` / `addRowAfter()` / `addColumnBefore()` / `addColumnAfter()` |
| Delete row/col | `deleteRow()` / `deleteColumn()` |
| Undo / Redo | `editor.chain().focus().undo().run()` / `.redo()` |
| Clear formatting | `editor.chain().focus().clearNodes().unsetAllMarks().run()` |
| Find / Replace | Custom implementation over `editor.state.doc` text search (no official Tiptap extension in v1) |

Keyboard shortcuts use Tiptap/ProseMirror defaults (Ctrl/Cmd+B, +I, +U, +Z, +Shift+Z, +F for
find via custom binding) — no remapping in v1.
