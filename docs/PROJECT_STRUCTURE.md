# PROJECT_STRUCTURE.md

## Purpose

This document is the authoritative folder-by-folder contract for smallerDOCS. It defines what
lives where, what each layer is allowed to import, and the naming/type-mirroring rule that keeps
the frontend and backend in sync. The coding agent must not invent new top-level folders without
updating this document first.

## Monorepo Layout

```
smallerDOCS/
├── frontend/                # Next.js 14 app (TypeScript, Tailwind)
├── backend/                 # FastAPI app (Python)
├── docs/                    # This planning package
└── docker-compose.yml       # Local dev orchestration (frontend + backend, no DB)
```

There is no shared `packages/` workspace. The frontend and backend communicate exclusively over
HTTP as defined in `API_SPECIFICATION.md`. They do not share a runtime or import each other's code.
Type parity between them is a *convention*, enforced by the mirroring rule below, not by a shared
package.

---

## Frontend Structure (`/frontend`)

```
frontend/
├── app/
│   ├── layout.tsx                     # Root layout, global providers (Zustand hydration, fonts)
│   ├── page.tsx                       # Landing / upload page
│   ├── globals.css                    # Tailwind base + design tokens (see DESIGN_SYSTEM.md)
│   └── editor/
│       └── [jobId]/
│           └── page.tsx               # Editor + comparison mode page (server component shell)
│
├── components/
│   ├── upload/
│   │   ├── UploadDropzone.tsx         # Drag/drop + file picker, client-side validation
│   │   ├── UploadProgress.tsx         # Upload % + status polling UI
│   │   └── FileTypeGuard.tsx          # Rejects unsupported types before network call
│   ├── editor/
│   │   ├── DocumentEditor.tsx         # Tiptap instance wrapper (see EDITOR_SPECIFICATION.md)
│   │   ├── EditorToolbar.tsx          # Formatting controls bound to Tiptap commands
│   │   ├── TableControls.tsx          # Merge/split/insert/delete row/col UI
│   │   └── FindReplacePanel.tsx       # Find/replace UI, operates on Tiptap doc
│   ├── comparison/
│   │   ├── ComparisonLayout.tsx       # Two-pane split view, resizable divider
│   │   ├── OriginalDocumentPane.tsx   # PDF/image viewer, renders bbox overlay
│   │   └── HighlightBridge.tsx        # Owns sourceBlockId <-> scroll/highlight sync (both panes)
│   ├── export/
│   │   └── ExportMenu.tsx             # Triggers POST /export, handles download
│   ├── errors/
│   │   └── ErrorState.tsx             # Renders ErrorObject per ERROR_HANDLING.md taxonomy
│   └── ui/                            # Design-system primitives (Button, Dialog, Toast, Spinner)
│
├── lib/
│   ├── api/
│   │   ├── client.ts                  # fetch wrapper: base URL, error normalization, timeouts
│   │   ├── upload.ts                  # uploadFile(), typed against UploadResponse
│   │   ├── process.ts                 # startProcessing(), pollStatus(), typed against StatusResponse
│   │   ├── document.ts                # getDocument(), typed against IDM (DocumentModel)
│   │   └── export.ts                  # exportDocument(), typed against ExportRequest/Response
│   ├── types/                         # MUST structurally mirror backend/app/models/*.py — see rule below
│   │   ├── idm.ts                     # Intermediate Document Model types
│   │   ├── api.ts                     # Request/response types per API_SPECIFICATION.md
│   │   └── errors.ts                  # ErrorObject, ErrorCode enum
│   └── editor/
│       ├── idmToTiptap.ts             # IDM -> Tiptap JSON (see EDITOR_SPECIFICATION.md)
│       ├── tiptapToIdm.ts             # Tiptap JSON -> IDM (reverse mapping, for export payloads)
│       └── extensions/                # Custom Tiptap nodes/marks (ClauseNumber, SourceBlockId mark)
│
├── store/
│   ├── useJobStore.ts                 # jobId, status, progress, error (Zustand)
│   ├── useDocumentStore.ts            # current IDM + current Tiptap doc, dirty flag
│   └── useComparisonStore.ts          # activeSourceBlockId, hoveredBlockId, pane scroll sync state
│
├── styles/
│   └── tokens.css                     # CSS variables for DESIGN_SYSTEM.md / COLOR_SYSTEM.md
│
├── public/
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

**Import rule:** `app/**` may import from `components/**`, `lib/**`, `store/**`. `components/**` may
import from `lib/**` and `store/**` but never from `app/**`. `lib/api/**` is the *only* code allowed
to call `fetch`. No component calls `fetch` directly.

---

## Backend Structure (`/backend`)

```
backend/
├── app/
│   ├── main.py                        # FastAPI app instance, CORS, router registration, startup/shutdown
│   ├── config.py                      # Env-driven settings (temp dir, max file size, model paths)
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── upload.py              # POST /api/v1/upload
│   │       ├── process.py             # POST /api/v1/process/{jobId}
│   │       ├── status.py              # GET /api/v1/status/{jobId}
│   │       ├── document.py            # GET /api/v1/document/{jobId}
│   │       ├── export.py              # POST /api/v1/export/{jobId}
│   │       ├── job.py                 # DELETE /api/v1/job/{jobId}
│   │       └── health.py              # GET /api/v1/health
│   │
│   ├── core/
│   │   ├── job_manager.py             # In-memory job registry + status state machine (DATA_FLOW.md)
│   │   ├── temp_storage.py            # Per-job temp directory lifecycle, cleanup on completion/expiry
│   │   └── errors.py                  # ErrorCode enum, AppError exception -> ErrorObject serializer
│   │
│   ├── pipeline/
│   │   ├── preprocessing/
│   │   │   ├── deskew.py              # OpenCV Hough-transform deskew
│   │   │   ├── denoise.py             # OpenCV fastNlMeansDenoising
│   │   │   └── binarize.py            # Adaptive threshold / CLAHE contrast normalization
│   │   ├── ocr/
│   │   │   └── paddle_ocr_engine.py   # PaddleOCR (PP-OCRv4) wrapper — see OCR_PIPELINE.md
│   │   ├── layout/
│   │   │   ├── structure_analysis.py  # PP-StructureV2 layout regions (heading/para/list/table)
│   │   │   └── table_detector.py      # Table cell/row/col + merge detection
│   │   └── reconstruction/
│   │       ├── idm_builder.py         # Merges OCR + layout output into IDM (DOCUMENT_RECONSTRUCTION.md)
│   │       └── clause_numbering.py    # Legal clause/section numbering detection (LEGAL_DOCUMENT_RULES.md)
│   │
│   ├── export/
│   │   ├── idm_to_docx.py             # IDM -> .docx via python-docx (EXPORT_SYSTEM.md)
│   │   └── idm_to_html.py             # IDM -> semantic HTML string (EXPORT_SYSTEM.md)
│   │
│   └── models/                        # Pydantic models — SOURCE OF TRUTH for all JSON contracts
│       ├── idm.py                     # DocumentModel, Page, Block, Run, TableCell, etc.
│       ├── api.py                     # UploadResponse, StatusResponse, ExportRequest, etc.
│       └── errors.py                  # ErrorObject, ErrorCode
│
├── requirements.txt
└── Dockerfile
```

**Import rule:** `pipeline/**` never imports from `api/**` (one-directional: routes call pipeline,
never the reverse). `export/**` only ever consumes `models.idm`, never raw pipeline output. All
inter-module data — including everything returned to the frontend — is a `models/*.py` Pydantic
object; nothing improvises a raw dict as an API response.

---

## Type-Mirroring Rule (Frontend ↔ Backend Contract)

Every Pydantic model in `backend/app/models/` has exactly one hand-written TypeScript counterpart
in `frontend/lib/types/`. Field names are identical (camelCase on both sides — Pydantic models use
`alias_generator=to_camel` with `populate_by_name=True`, so backend Python fields stay snake_case
internally but serialize as camelCase over the wire). This mapping is fixed for the lifetime of the
project:

| Backend (Pydantic, `app/models/`) | Frontend (TypeScript, `lib/types/`) |
|---|---|
| `idm.DocumentModel` | `idm.ts` → `DocumentModel` |
| `idm.Page` | `idm.ts` → `Page` |
| `idm.Block` | `idm.ts` → `Block` |
| `idm.Run` | `idm.ts` → `Run` |
| `idm.TableCell` | `idm.ts` → `TableCell` |
| `api.UploadResponse` | `api.ts` → `UploadResponse` |
| `api.StatusResponse` | `api.ts` → `StatusResponse` |
| `api.ExportRequest` / `ExportResponse` | `api.ts` → `ExportRequest` / `ExportResponse` |
| `errors.ErrorObject` / `ErrorCode` | `errors.ts` → `ErrorObject` / `ErrorCode` |

Any field added to a Pydantic model requires the same field added to its TypeScript counterpart in
the same change. This is a manual convention (no codegen in v1) but is treated as a hard rule —
drift here is the single most common source of integration bugs in this architecture.
