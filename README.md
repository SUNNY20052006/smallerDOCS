---
title: smallerDOCS
emoji: 📄
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# smallerDOCS

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688.svg" alt="FastAPI 0.111" />
  <img src="https://img.shields.io/badge/Next.js-14-000000.svg" alt="Next.js 14" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6.svg" alt="TypeScript 5" />
  <img src="https://img.shields.io/badge/PaddleOCR-3.1-013243.svg" alt="PaddleOCR 3.1" />
  <img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License: MIT" />
</p>

smallerDOCS reconstructs scanned and digital legal documents into editable, structured documents. Unlike generic OCR tools that extract raw text, smallerDOCS preserves document structure — headings, paragraphs, lists, tables, clause numbering, indentation, and formatting — so the output is immediately usable in a word processor.

The project consists of a Next.js frontend with a Tiptap-based rich text editor and a FastAPI backend running a multi-stage OCR and document reconstruction pipeline.

## Features

- **OCR for scanned documents** — text recognition via PaddleOCR (PP-OCRv5)
- **Native text extraction** — direct extraction from digital PDF text layers, bypassing OCR when possible
- **Image preprocessing** — deskew, denoise, adaptive thresholding, border removal, resolution normalization
- **Layout analysis** — region detection (headings, paragraphs, lists, tables, headers, footers) via PP-StructureV3
- **Reading order reconstruction** — XY-cut algorithm for correct linear ordering, including multi-column layouts
- **Block classification** — precise typing of each region (heading levels, clause numbers, signature lines, lists, tables)
- **Table detection** — row/column/cell structure with merged cell support via PP-TableMagic
- **Clause numbering detection** — supports legal decimal, roman, and alpha numbering styles with hierarchy tracking
- **Formatting preservation** — bold, italic, underline, alignment, indent levels
- **Rich text editor** — Tiptap-based with full formatting toolbar, table editing (merge/split/insert), and find/replace
- **Side-by-side comparison mode** — view the original scanned page alongside the reconstructed document with click-to-highlight synchronization
- **DOCX export** — via python-docx with preserved structure, formatting, and tables
- **HTML export** — self-contained HTML with inline styles, no external dependencies
- **Drag-and-drop upload** — accepts PDF, JPG, and PNG files (up to 50 MB)
- **Upload progress tracking** — real-time status polling with page-level progress
- **Error handling** — unified error taxonomy surfaced consistently across frontend and backend

## Why smallerDOCS?

Generic OCR tools extract text. smallerDOCS reconstructs documents.

Legal documents carry meaning in their structure — a clause number like "4.2(b)" is a cross-reference target, not just a bold paragraph prefix. A table's row and column layout conveys data relationships that a flat text dump destroys. Indentation signals nesting hierarchy. Capitalized defined terms carry specific legal significance.

smallerDOCS preserves these structural signals throughout the pipeline. The output is an editable document that faithfully represents what the original said and how it was organized — not a raw text transcript with formatting guesses pasted on top.

## Architecture

```
User
  │
  ▼
Frontend (Next.js / Tiptap)
  │  HTTP / JSON
  ▼
FastAPI Backend
  │
  ▼
OCR Pipeline (11 stages)
  │
  ▼
Intermediate Document Model (IDM)
  │
  ▼
Rich Text Editor ← → Comparison Mode
  │
  ▼
DOCX / HTML Export
```

The frontend and backend communicate exclusively over HTTP. The backend owns all document processing and export generation. The frontend provides the editing interface and comparison view.

The **Intermediate Document Model (IDM)** is the canonical document representation. Every layer — OCR pipeline, editor mapping, comparison mode, export — is defined in terms of it. The IDM is a structured JSON model containing pages, blocks (paragraphs, headings, tables, clause numbers, lists, signature lines), runs (formatted text spans with marks), and bounding box geometry.

## OCR Pipeline

Processing runs asynchronously after upload. The pipeline consists of 11 stages, grouped into four status phases:

### Preprocessing (status: `preprocessing`)
1. **File validation** — MIME check, size limit (50 MB), PDF integrity, page count cap (100 pages)
2. **Document classification** — per-page digital-vs-scanned detection; best-effort legal document type heuristic
3. **Image preprocessing** — rotation correction, deskew, denoise, CLAHE contrast normalization, adaptive thresholding, border removal, resolution normalization to 300 DPI

### OCR (status: `ocr`)
4. **OCR** — scanned pages via PaddleOCR PP-OCRv5; digital pages via PyMuPDF native text extraction (confidence: 1.0)

### Layout Analysis (status: `layout_analysis`)
5. **Layout analysis** — region detection via PP-StructureV3 (title, text, list, table, figure, header, footer)
6. **Reading order detection** — XY-cut recursive projection for correct linear ordering; repeated header/footer suppression
7. **Block classification** — precise typing per region: heading levels (by relative font size), clause numbers (pattern matching), lists, signature lines, page breaks
8. **Table detection** — cell structure recovery via PP-TableMagic with rowspan/colspan support

### Reconstruction (status: `reconstruction`)
9. **Formatting reconstruction** — bold/italic/underline detection (stroke-width heuristics for scanned pages, PyMuPDF font flags for digital), alignment, indent banding; IDM assembly
10. **Legal rules engine** — clause hierarchy assignment, numbering style detection, signature role refinement
11. **IDM finalization** — confidence aggregation, serialization, status transition to `completed`

The frontend polls `GET /api/v1/status/{jobId}` every 1.5 seconds and renders the document once processing completes.

## Technology Stack

### Frontend

| Library | Purpose |
|---|---|
| Next.js 14 | Application framework (App Router) |
| React 18 | UI library |
| TypeScript 5 | Type safety |
| Tailwind CSS 3 | Styling |
| Tiptap 2 | Rich text editor (ProseMirror-based) |
| Zustand 4 | State management |
| Lucide React | Icons |
| Radix UI Slider | Zoom slider |

### Backend

| Library | Purpose |
|---|---|
| FastAPI 0.111 | Web framework |
| Pydantic 2 | Data validation and settings |
| PaddleOCR 3.1 | OCR engine (PP-OCRv5) |
| PP-StructureV3 | Layout analysis and table detection |
| OpenCV 4.10 | Image preprocessing |
| PyMuPDF 1.24 | PDF parsing, native text extraction, page rendering |
| Pillow 10.3 | Image loading and validation |
| python-docx 1.1 | DOCX generation |
| Uvicorn | ASGI server |

### OCR Engine Decision

PaddleOCR was selected over alternatives (Surya, docTR, Tesseract, Marker) for the following reasons:

- **Apache 2.0 license** on both code and model weights — unconditionally free at any scale, unlike Surya and Marker (conditional licenses)
- **Native layout and table understanding** via PP-StructureV3 and PP-TableMagic — no need to assemble a separate structure-detection stack
- **PP-OCRv5 traditional recognition pipeline** (not a generative VLM) — cannot hallucinate text, consistent with the "never invent text" principle
- **CPU-viable deployment** — dedicated mobile model variants enable practical CPU-only operation

## Project Structure

```
smallerDOCS/
├── frontend/                   # Next.js application
│   ├── app/                    # Pages and layout
│   │   ├── page.tsx            # Upload page
│   │   └── editor/[jobId]/     # Editor + comparison page
│   ├── components/
│   │   ├── upload/             # Upload dropzone and progress
│   │   ├── editor/             # Tiptap editor, toolbar, find/replace
│   │   ├── comparison/         # Side-by-side original + reconstructed view
│   │   ├── export/             # Export menu
│   │   ├── errors/             # Error display
│   │   └── ui/                 # Button, Slider, Spinner
│   ├── lib/
│   │   ├── api/                # HTTP client and endpoint functions
│   │   ├── types/              # TypeScript mirrors of backend Pydantic models
│   │   └── editor/             # IDM↔Tiptap mapping, custom extensions
│   ├── store/                  # Zustand stores (document, job, comparison)
│   └── styles/                 # CSS design tokens
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/routes/         # API endpoints (upload, process, status, document, export, job, health)
│   │   ├── core/               # Job manager, temp storage, error handling
│   │   ├── pipeline/           # OCR pipeline stages
│   │   │   ├── classification/ # Digital vs scanned detection
│   │   │   ├── preprocessing/  # Image transforms
│   │   │   ├── ocr/            # Text recognition
│   │   │   ├── layout/         # Structure analysis, reading order, table detection
│   │   │   └── reconstruction/ # IDM builder, clause numbering
│   │   ├── export/             # DOCX and HTML generation
│   │   └── models/             # Pydantic models (IDM, API, errors)
│   ├── requirements.txt
│   └── Dockerfile
└── docker-compose.yml
```

## Running Locally

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (optional, for containerized setup)

### Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend starts on `http://localhost:8000`. OCR and layout models are loaded on startup (this may take 30–60 seconds on the first run as model weights are downloaded).

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend starts on `http://localhost:3000` and connects to the backend at `http://localhost:8000`.

### Docker Compose

```bash
docker compose up --build
```

This starts both services. The frontend is available at `http://localhost:3000` and the backend at `http://localhost:8000`.

### Environment Variables

The backend accepts the following environment variables (all prefixed with `SMALLERDOCS_`):

| Variable | Default | Description |
|---|---|---|
| `SMALLERDOCS_TEMP_ROOT` | `{TEMP}/smallerdocs` | Root directory for temporary job files |
| `SMALLERDOCS_MAX_FILE_SIZE_BYTES` | `52428800` (50 MB) | Maximum upload file size |
| `SMALLERDOCS_MAX_PAGES` | `100` | Maximum number of pages per document |
| `SMALLERDOCS_JOB_TTL_MINUTES` | `30` | Time after which completed/failed jobs are cleaned up |
| `SMALLERDOCS_CLEANUP_INTERVAL_SECONDS` | `600` | Interval between cleanup sweeps |
| `SMALLERDOCS_PAGE_CONCURRENCY` | `4` | Number of pages processed in parallel |
| `SMALLERDOCS_EXPORT_TIMEOUT_SECONDS` | `45` | Timeout for export generation |
| `SMALLERDOCS_CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |

## Deployment

The frontend and backend are independent services and can be deployed separately.

- **Frontend**: Build with `npm run build` and serve the static output or deploy as a Node.js application.
- **Backend**: Build the Docker image or run with `uvicorn` behind a reverse proxy.

OCR model weights are downloaded automatically on first startup. Do not commit model weights to Git. Ensure the deployment has sufficient memory (approximately 2 GB RAM per concurrent job plus 1–1.5 GB for shared model weights).

## Design Principles

smallerDOCS is built on a set of non-negotiable principles that govern every stage of the pipeline:

**Preserve structure over appearance.** When a choice must be made between reproducing the visual layout exactly and reproducing the logical structure correctly, structure wins. The output is an editable document, not a pixel replica.

**Never invent text.** No stage may substitute a plausible guess for text it cannot confidently read. Low-confidence OCR output is preserved with its original confidence score rather than replaced with an inferred alternative.

**Never silently drop content.** A failure in any stage fails the whole job with a visible error rather than producing a document quietly missing content. Degraded results (e.g., a table that falls back to a flat paragraph) are flagged via confidence scores, never hidden.

**Preserve legal formatting.** Clause numbers are reproduced literally — never auto-numbered, never resequenced. Capitalization, emphasis, and whitespace are reproduced exactly as recognized. Checkbox states are preserved as literal glyphs.

**Human verification through editing.** The editor exists so a human can verify and correct every OCR uncertainty. Once edited, the user's version is authoritative and is never re-inferred or blended with original OCR output.

**Deterministic reconstruction.** Given the same input, the pipeline produces the same output every time. No stage uses randomness or non-deterministic model sampling.

**Never use AI to guess missing words.** If OCR cannot recognize a character, the pipeline emits its best literal reading with a correspondingly low confidence score. No language model is asked to "fill in" what a word probably was.

## Current Limitations

- **Headers and footers** are suppressed from the editable body (preserved as detected but not round-tripped through the editor)
- **No user authentication or multi-user support** — single-session, single-document tool
- **No job cancellation** — running jobs must complete or fail; no cancellation endpoint in v1
- **Confidence scores are stored but not yet surfaced in the UI** — the field is populated throughout the pipeline for future use
- **No database** — job state is in-memory; restarting the backend loses all in-progress and completed jobs
- **Maximum 100 pages per document** — a performance cap, not a technical limit of the libraries used
- **Password-protected PDFs are rejected** — the project has no mechanism to hold credentials
- **No checkbox-specific block type** — checkbox state is preserved as literal text glyphs rather than a structured field
- **Table borders are normalized to grid style** on export regardless of the source table's original border style

## Future Improvements

- Confidence visualization in the editor (low-confidence region highlighting)
- Header and footer round-tripping through the editor and into export
- Signature field detection and structured representation
- Multi-user support with persistent storage
- Job cancellation
- Batch document processing
- Additional export formats (PDF with selectable text, Markdown)
- API documentation via auto-generated OpenAPI/Swagger UI

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
