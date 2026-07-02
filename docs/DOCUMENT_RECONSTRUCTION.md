# DOCUMENT_RECONSTRUCTION.md

## Purpose

This is the single most important contract in the system. It defines the **Intermediate Document
Model (IDM)** — the exact JSON shape the backend produces after OCR + layout analysis +
reconstruction, returned by `GET /api/v1/document/{jobId}`. Every other layer (editor, comparison
mode, export) is defined in terms of this schema. Nothing downstream invents its own document
representation.

The IDM is the Pydantic model `app.models.idm.DocumentModel`. The pipeline stages (`ocr/`,
`layout/`, `reconstruction/`) exist to produce it; nothing outside `reconstruction/idm_builder.py`
is allowed to construct a `DocumentModel` directly.

## Design Principles

1. **One canonical model, two consumers.** The IDM is read by the frontend to build the initial
   editor state (`EDITOR_SPECIFICATION.md`) and re-derived from the edited editor state to drive
   export (`EXPORT_SYSTEM.md`). The IDM is never partially populated — every block always has all
   required fields, even if a value is a safe default (empty string, `null` bbox for
   editor-inserted content).
2. **Geometry is preserved for comparison mode, not for rendering the editor.** The editor renders
   IDM content as flowing rich text, not as an absolute-positioned replica of the scan. Bounding
   boxes exist so Comparison Mode can highlight the matching region of the original image/PDF.
3. **Every block is traceable.** Every block and every run carries a stable `id`. This same id
   becomes the `sourceBlockId` attribute in the editor (see `EDITOR_SPECIFICATION.md`) and is the
   join key used by Comparison Mode's click-to-highlight feature.
4. **Confidence is explicit, never silently dropped.** OCR/layout confidence per block is retained
   through the whole pipeline so the frontend can (in a future version) flag low-confidence
   regions. v1 does not build UI for this, but the field is populated from day one so it isn't a
   breaking schema change later.

## Top-Level Schema

```json
{
  "documentId": "string (uuid)",
  "sourceType": "pdf" | "image",
  "sourceFileName": "string",
  "pageCount": "integer >= 1",
  "createdAt": "string (ISO 8601)",
  "pages": [ "Page" ],
  "metadata": {
    "detectedDocumentType": "contract" | "affidavit" | "lease" | "court_filing" | "notice" | "form" | "unknown",
    "language": "string (ISO 639-1, e.g. 'en')",
    "averageConfidence": "number 0.0-1.0"
  }
}
```

`detectedDocumentType` is a best-effort classification (see `LEGAL_DOCUMENT_RULES.md` for the
heuristic) used only to select clause-numbering rules. It never blocks processing if unknown.

## Page Object

```json
{
  "pageNumber": "integer, 1-indexed",
  "width": "integer, px at processing DPI (300)",
  "height": "integer, px at processing DPI (300)",
  "rotationApplied": "0 | 90 | 180 | 270",
  "blocks": [ "Block" ]
}
```

`width`/`height` are the pixel dimensions of the *preprocessed* (deskewed, rotation-corrected)
page image, at the fixed processing DPI of 300. All `bbox` values on that page's blocks are in
this same pixel space. This is the coordinate system Comparison Mode's overlay uses — the original
viewer renders the same preprocessed image (not the raw upload) so bbox and displayed pixels always
agree with no scaling ambiguity.

## Block Object

A `Block` is a structural unit: a heading, paragraph, list, list item, table, or a few
legal-specific block types. Blocks are returned in final reading order per page — the array order
*is* the reading order; there is no separate order field to keep in sync.

```json
{
  "id": "string (uuid)",
  "type": "heading" | "paragraph" | "list" | "listItem" | "table" | "tableRow" | "tableCell" | "clauseNumber" | "signatureLine" | "pageBreak",
  "bbox": { "x": "number", "y": "number", "width": "number", "height": "number" } | null,
  "confidence": "number 0.0-1.0",
  "attrs": { "...": "type-dependent, see below" },
  "runs": [ "Run" ] | null,
  "children": [ "Block" ] | null
}
```

Rules:
- `runs` is populated for text-bearing leaf blocks (`heading`, `paragraph`, `listItem`,
  `clauseNumber`, `signatureLine`, `tableCell`). It is `null` for container blocks.
- `children` is populated for container blocks (`list`, `table`, `tableRow`). It is `null` for
  leaf blocks.
- `bbox` is `null` only for blocks that don't originate from the source scan (never true for
  pipeline output — reserved for editor-inserted blocks once they round-trip through
  `tiptapToIdm.ts`, see `EDITOR_SPECIFICATION.md`).
- Exactly one of `runs` / `children` is non-null per block, never both, never neither.

### `attrs` by block type

| type | attrs fields |
|---|---|
| `heading` | `level: 1\|2\|3` (mapped from relative font size / layout role) |
| `paragraph` | `alignment: "left"\|"center"\|"right"\|"justify"`, `indentLevel: integer 0-8` |
| `list` | `listType: "bullet"\|"ordered"`, `startNumber: integer` (ordered only) |
| `listItem` | `indentLevel: integer 0-8` |
| `table` | `rowCount: integer`, `colCount: integer` |
| `tableRow` | `rowIndex: integer` |
| `tableCell` | `rowIndex: integer`, `colIndex: integer`, `rowSpan: integer >= 1`, `colSpan: integer >= 1` |
| `clauseNumber` | `numberingStyle: "decimal"\|"roman"\|"alpha"\|"legal_decimal"` (e.g. "1.2.3"), `depth: integer` |
| `signatureLine` | `role: "signatory"\|"witness"\|"notary"\|"date"` (best-effort classification) |
| `pageBreak` | `{}` (no fields) |

## Run Object

A `Run` is a contiguous span of text sharing the same formatting — the leaf-level text-with-marks
unit, directly analogous to a Tiptap `text` node with marks.

```json
{
  "id": "string (uuid)",
  "text": "string",
  "bbox": { "x": "number", "y": "number", "width": "number", "height": "number" },
  "confidence": "number 0.0-1.0",
  "marks": {
    "bold": "boolean",
    "italic": "boolean",
    "underline": "boolean"
  }
}
```

Runs never carry color/highlight from OCR (the source is a scan; color is not reliably
recoverable) — those marks only ever originate from user edits in the editor, and are added at the
editor layer, not the IDM-from-OCR layer. The IDM schema still reserves the fields (see
`EDITOR_SPECIFICATION.md` reverse mapping) so a round-tripped document doesn't lose user-applied
color/highlight, but the *initial* pipeline output never populates them.

## Table Representation

Tables are `table` blocks whose `children` is a flat array of `tableRow` blocks, each of whose
`children` is a flat array of `tableCell` blocks. Cells contain `runs` directly if the cell holds a
single paragraph (the common legal-document case), never a nested `children` of `paragraph`
blocks — this keeps cell content symmetric with other leaf blocks and simplifies the Tiptap
mapping. Merged cells are represented once, at their top-left position, with `rowSpan`/`colSpan` >
1; the cells they cover are omitted entirely (not emitted as empty placeholder cells).

## Full Example

A two-clause snippet of a lease agreement, one page:

```json
{
  "documentId": "3fa1b2c4-...",
  "sourceType": "pdf",
  "sourceFileName": "lease_agreement.pdf",
  "pageCount": 1,
  "createdAt": "2026-07-01T10:15:00Z",
  "pages": [
    {
      "pageNumber": 1,
      "width": 2550,
      "height": 3300,
      "rotationApplied": 0,
      "blocks": [
        {
          "id": "b-001",
          "type": "heading",
          "bbox": { "x": 850, "y": 200, "width": 850, "height": 60 },
          "confidence": 0.98,
          "attrs": { "level": 1 },
          "runs": [
            { "id": "r-001", "text": "RESIDENTIAL LEASE AGREEMENT", "bbox": { "x": 850, "y": 200, "width": 850, "height": 60 }, "confidence": 0.98, "marks": { "bold": true, "italic": false, "underline": false } }
          ],
          "children": null
        },
        {
          "id": "b-002",
          "type": "clauseNumber",
          "bbox": { "x": 300, "y": 320, "width": 1950, "height": 40 },
          "confidence": 0.95,
          "attrs": { "numberingStyle": "legal_decimal", "depth": 1 },
          "runs": [
            { "id": "r-002", "text": "1. TERM. ", "bbox": { "x": 300, "y": 320, "width": 100, "height": 40 }, "confidence": 0.95, "marks": { "bold": true, "italic": false, "underline": false } },
            { "id": "r-003", "text": "This lease shall commence on the date first written above and continue for twelve (12) months.", "bbox": { "x": 400, "y": 320, "width": 1850, "height": 40 }, "confidence": 0.95, "marks": { "bold": false, "italic": false, "underline": false } }
          ],
          "children": null
        },
        {
          "id": "b-003",
          "type": "table",
          "bbox": { "x": 300, "y": 420, "width": 1950, "height": 300 },
          "confidence": 0.91,
          "attrs": { "rowCount": 2, "colCount": 2 },
          "runs": null,
          "children": [
            {
              "id": "b-004",
              "type": "tableRow",
              "bbox": { "x": 300, "y": 420, "width": 1950, "height": 150 },
              "confidence": 0.91,
              "attrs": { "rowIndex": 0 },
              "runs": null,
              "children": [
                { "id": "b-005", "type": "tableCell", "bbox": { "x": 300, "y": 420, "width": 975, "height": 150 }, "confidence": 0.92, "attrs": { "rowIndex": 0, "colIndex": 0, "rowSpan": 1, "colSpan": 1 }, "runs": [ { "id": "r-004", "text": "Monthly Rent", "bbox": { "x": 300, "y": 420, "width": 975, "height": 150 }, "confidence": 0.92, "marks": { "bold": true, "italic": false, "underline": false } } ], "children": null },
                { "id": "b-006", "type": "tableCell", "bbox": { "x": 1275, "y": 420, "width": 975, "height": 150 }, "confidence": 0.90, "attrs": { "rowIndex": 0, "colIndex": 1, "rowSpan": 1, "colSpan": 1 }, "runs": [ { "id": "r-005", "text": "$1,500.00", "bbox": { "x": 1275, "y": 420, "width": 975, "height": 150 }, "confidence": 0.90, "marks": { "bold": false, "italic": false, "underline": false } } ], "children": null }
              ]
            }
          ]
        }
      ]
    }
  ],
  "metadata": {
    "detectedDocumentType": "lease",
    "language": "en",
    "averageConfidence": 0.94
  }
}
```

## Versioning

The IDM schema carries no explicit `schemaVersion` field in v1 (single-version system, no stored
documents to migrate). If a v2 introduces authentication/history (see project vision's future
expansion list), add `schemaVersion: "1.0"` to the top-level object at that time — this is a
forward-compat note, not a v1 requirement.
