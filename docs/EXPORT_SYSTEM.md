# EXPORT_SYSTEM.md

## Architectural Decision: Export Is Server-Side Only

Both DOCX and HTML export happen in `backend/app/export/`, never in the browser. This is a
deliberate contract decision, not a default:

- DOCX generation *requires* Python (`python-docx`) — there is no viable client-side DOCX writer
  with equivalent table/formatting fidelity.
- HTML export **could** be done client-side via Tiptap's `generateHTML()`, but is deliberately
  kept server-side too, so there is exactly one conversion implementation (`tiptapToIdm` →
  `idm_to_html.py`) rather than two independently-maintained serializers that could drift apart
  (e.g. clause-number rendering, table cell merge handling). Single source of truth beats saving
  one network round-trip.

Flow: frontend posts current Tiptap JSON to `POST /api/v1/export/{jobId}` (contract in
`API_SPECIFICATION.md`) → backend runs the **reverse mapping** (Tiptap JSON → IDM, mirroring
`tiptapToIdm.ts` in Python, implemented in `app/export/tiptap_to_idm.py`) → IDM is handed to
`idm_to_docx.py` or `idm_to_html.py`.

## Module Interfaces (signatures, not implementations)

```python
# app/export/tiptap_to_idm.py
def tiptap_to_idm(tiptap_doc: dict, original_document_id: str) -> DocumentModel:
    """Mirrors frontend/lib/editor/tiptapToIdm.ts. Must stay in sync with it —
    see EDITOR_SPECIFICATION.md 'Reverse Mapping' table for the authoritative rules."""

# app/export/idm_to_docx.py
def idm_to_docx(document: DocumentModel) -> bytes:
    """Returns raw .docx file bytes."""

# app/export/idm_to_html.py
def idm_to_html(document: DocumentModel) -> str:
    """Returns a self-contained HTML string (inline <style>, no external assets)."""
```

## IDM → DOCX Mapping (`python-docx`)

| IDM block/run | python-docx construct |
|---|---|
| `heading` (level N) | `document.add_heading(text, level=N)` |
| `paragraph` | `document.add_paragraph()`; `paragraph.alignment` ← `WD_ALIGN_PARAGRAPH` from `attrs.alignment`; `paragraph.paragraph_format.left_indent` ← `Inches(0.25 * indentLevel)` |
| `list` + `listItem` | Paragraphs with Word's built-in `List Bullet` / `List Number` style; nested depth via `paragraph_format.left_indent` increments per `indentLevel` |
| `table` | `document.add_table(rows, cols)`; `table.style = "Table Grid"` |
| `tableCell` with `rowSpan`/`colSpan` > 1 | `cell.merge(other_cell)` called for the covered range, reconstructed from the (rowIndex, colIndex, rowSpan, colSpan) tuple |
| `clauseNumber` | Prepended as a `run` at the start of the owning paragraph's text, bold, followed by a space — not a separate Word list-numbering field (keeps exact source numbering literal rather than relying on Word's auto-numbering, which the project vision calls for: "resemble the original as closely as possible") |
| `signatureLine` | Plain paragraph; no special Word construct |
| `pageBreak` | `document.add_page_break()` |
| `Run.marks.bold` | `run.bold = True` |
| `Run.marks.italic` | `run.italic = True` |
| `Run.marks.underline` | `run.underline = True` |
| `Run` with `textStyle.color` (editor-applied) | `run.font.color.rgb = RGBColor.from_string(hex)` |
| `Run` with `highlight` (editor-applied) | `run.font.highlight_color = WD_COLOR_INDEX.<nearest mapped value>` (python-docx highlight is a fixed palette; nearest-color mapping table maintained in `idm_to_docx.py`) |

Page geometry (margins, page size) defaults to Word's standard Letter/A4 based on the detected
source page aspect ratio (`width`/`height` from the IDM `Page` object) — not pixel-exact
reproduction of the scan layout, consistent with the project vision's "editable document" goal
rather than a fixed-layout replica.

## IDM → HTML Mapping

| IDM block | HTML |
|---|---|
| `heading` (level N) | `<h{N}>` |
| `paragraph` | `<p style="text-align:{alignment}; margin-left:{indentLevel*20}px">` |
| `list` (bullet) | `<ul>` | `list` (ordered) | `<ol start="{startNumber}">` |
| `listItem` | `<li>` |
| `table` | `<table>` |
| `tableRow` | `<tr>` |
| `tableCell` | `<td rowspan="{rowSpan}" colspan="{colSpan}">` |
| `clauseNumber` | `<span class="clause-number"><strong>{display}</strong></span>` |
| `pageBreak` | `<div class="page-break"></div>` with a CSS `page-break-after: always` rule in the embedded `<style>` |
| `Run.marks.bold` | `<strong>` |
| `Run.marks.italic` | `<em>` |
| `Run.marks.underline` | `<u>` |
| `Run.textStyle.color` | inline `style="color:{hex}"` |
| `Run.highlight` | inline `style="background-color:{hex}"` |

Output is a single self-contained `.html` file: a minimal `<style>` block in `<head>` covers
`.clause-number`, `table`/`td`/`th` borders (`border-collapse: collapse`, `1px solid #000`), and
print media rules — no external stylesheet or CDN dependency, so the exported file opens correctly
offline.

## Validation Before Conversion

`POST /export` validates the posted Tiptap JSON against the ProseMirror schema (via the same node
type whitelist used by the frontend editor's Tiptap instance, re-declared server-side in
`app/models/tiptap_schema.py`) before attempting `tiptap_to_idm()`. Malformed or unknown node types
produce `400 INVALID_DOCUMENT_CONTENT` (per `API_SPECIFICATION.md`) rather than a partial or
corrupted export file — the system never silently drops content it can't map.
