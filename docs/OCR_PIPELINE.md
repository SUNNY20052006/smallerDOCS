# OCR_PIPELINE.md

## Relationship to Existing Documents

This document defines everything that happens between `POST /api/v1/process/{jobId}` and the
`DocumentModel` (IDM) returned by `GET /api/v1/document/{jobId}`, as specified in
`API_SPECIFICATION.md` and `DOCUMENT_RECONSTRUCTION.md`. It also **expands** the `pipeline/` tree
sketched in `PROJECT_STRUCTURE.md` into its full, final file list — see "Pipeline Folder
Responsibilities" below, which is the authoritative version of that folder from this point
forward. No architectural decision made in the six prior documents is changed here.

## Overall Pipeline

```
Upload (API_SPECIFICATION.md, synchronous)
   ↓
File Validation (synchronous, part of POST /upload)
   ↓
──────────── everything below runs async under POST /process/{jobId} ────────────
   ↓
Document Classification         ┐
   ↓                            │ job status = "preprocessing"  (progress 0–10%)
Image Preprocessing             ┘
   ↓
OCR                                job status = "ocr"             (progress 10–60%)
   ↓
Layout Analysis                 ┐
   ↓                            │
Reading Order Detection         │ job status = "layout_analysis" (progress 60–80%)
   ↓                            │
Block Classification            │
   ↓                            │
Table Detection                 ┘
   ↓
Formatting Reconstruction       ┐ job status = "reconstruction"  (progress 80–100%)
   ↓                            │
Legal Rules Engine              ┘
   ↓
Intermediate Document Model (IDM)     job status = "completed"
   ↓
Frontend (GET /api/v1/document/{jobId})
```

The four-value `status` enum (`preprocessing` / `ocr` / `layout_analysis` / `reconstruction`) is
exactly the one already defined in `DATA_FLOW.md`. Every finer-grained stage below nests inside
one of those four buckets so the coarse API contract never has to change even though this document
defines eleven distinct internal stages. `currentPage`/`totalPages` on `GET /status` update
continuously as each stage processes each page.

Every stage is a pure function: `stage(input) -> output`, executed synchronously in-process by an
async worker task per job (no message queue in v1 — see `PERFORMANCE.md` for why this is
acceptable at target load). No stage reaches into another stage's module. No stage calls the OCR
model or the layout model except the two stages that own those models (`OCR`, `Layout Analysis`).

---

## Stage Reference

Each stage below is documented with: Purpose, Responsibilities, Inputs, Outputs, Dependencies,
Failure conditions, Recovery behaviour, Files, Execution order, State, Handoff to next stage.

### 1. File Validation

| | |
|---|---|
| Purpose | Reject anything the pipeline cannot safely or usefully process, before a job is ever created. |
| Responsibilities | MIME/extension check; size check; PDF structural integrity check; password-protection check; page count sanity check. |
| Inputs | Raw uploaded bytes + declared filename from the multipart request. |
| Outputs | Either a valid `jobId` + stored file (success path in `API_SPECIFICATION.md`), or a 4xx `ErrorObject`. |
| Dependencies | `PyMuPDF` (`fitz`) for PDF structural checks; `Pillow` for image checks. |
| Failure conditions | Unsupported MIME type; file >50MB; PDF fails to open (`fitz.open` raises); PDF requires a password (`doc.needs_pass == True`); image fails `Image.open().verify()`; page count >100 (see Performance Targets). |
| Recovery behaviour | No retry — this stage is synchronous within the upload request. The user is shown the specific error immediately and re-uploads. No job or temp directory is created on failure. |
| Files | `backend/app/core/file_validator.py`, called from `backend/app/api/routes/upload.py`. |
| Execution order | Before job creation — not part of the async pipeline at all. |
| State | Stateless. |
| Handoff | On success: file bytes written to `{TEMP_ROOT}/{jobId}/source.{ext}`; job registered in `job_manager` with status `uploaded`. |

Format-specific rules:

- **Password-protected PDFs**: rejected outright in v1 with a dedicated error code
  `PASSWORD_PROTECTED_PDF` (`400`). smallerDOCS never prompts for or stores a password — the
  project has no auth/session concept to safely hold one. This is added to the error taxonomy
  alongside the codes already listed for `POST /upload` in `API_SPECIFICATION.md`.
- **Digital vs. scanned PDFs**: validation does *not* yet decide this (that's `Document
  Classification`'s job) — it only confirms the PDF opens and is not encrypted.
- **Multi-page PDFs**: page count is read via `len(fitz.open(...))`. >100 pages →
  `TOO_MANY_PAGES` (`400`). This cap exists purely for the performance envelope in this
  document's "Performance Targets" section, not a technical ceiling of any library used.
- **Corrupted PDFs**: any `fitz` exception during open/parse → `CORRUPTED_PDF` (`400`), matching
  the code already declared in `API_SPECIFICATION.md`.

---

### 2. Document Classification

| | |
|---|---|
| Purpose | Decide, per page, whether OCR is even needed — and make a best-effort guess at legal document type to steer the Legal Rules Engine later. |
| Responsibilities | (a) Per-page digital-vs-scanned classification; (b) whole-document `detectedDocumentType` heuristic. |
| Inputs | The validated source file from disk. |
| Outputs | `ClassificationResult { pages: [{ pageNumber, source: "native" \| "scanned" }], detectedDocumentType }`. |
| Dependencies | `PyMuPDF` for embedded text-layer inspection. |
| Failure conditions | None that are fatal — this stage never blocks the pipeline. A page that can't be confidently classified defaults to `"scanned"` (the safer, more expensive path, never the reverse — silently trusting a bad text layer would be a worse failure mode than a slower OCR pass). |
| Recovery behaviour | N/A (does not fail). |
| Files | `backend/app/pipeline/classification/document_classifier.py`. |
| Execution order | Stage 2 of 11. First step inside job status `preprocessing`. |
| State | Stateless. |
| Handoff | `ClassificationResult` passed to `Image Preprocessing` (per-page `source`) and to the final `DocumentModel.metadata.detectedDocumentType` (untouched by any later stage). |

**Digital vs. scanned rule**: a page is `"native"` if `page.get_text("words")` returns more than
`MIN_NATIVE_WORD_COUNT` (default 10) words *and* the words' bounding boxes cover more than 5% of
the page area (guards against pages with only a stray digital watermark/pagination artifact but
otherwise scanned content). Otherwise `"scanned"`.

**Document type heuristic** (keyword + structural scoring, not ML — deterministic and
explainable): first-page text is scanned for keyword sets per type (e.g. "LEASE", "LESSOR",
"LESSEE" → `lease`; "AFFIDAVIT", "SWORN" → `affidavit`; "IN THE COURT OF", "PLAINTIFF",
"DEFENDANT" → `court_filing`; "WHEREAS", "PARTY OF THE FIRST PART" → `contract`; presence of a
dense grid of short-answer table cells with checkbox-like glyphs → `form`). Highest keyword-set
match count wins; ties or zero matches → `unknown`. This value is advisory only — it never blocks
processing and a wrong guess degrades gracefully (see `LEGAL_DOCUMENT_RULES.md`).

---

### 3. Image Preprocessing

| | |
|---|---|
| Purpose | Turn a raw scan/photo into a clean, normalized image that maximizes OCR accuracy. |
| Responsibilities | Rotation correction, deskew, denoise, contrast/threshold normalization, border removal, resolution normalization. |
| Inputs | Per-page rendered image: `"scanned"` pages rendered at 300 DPI via `fitz.Page.get_pixmap()`; uploaded `image/*` files loaded directly via `Pillow`. `"native"` pages are *also* rendered at 300 DPI here (needed for Layout Analysis's region detection, which always operates on an image regardless of text source — see Stage 5). |
| Outputs | `PreprocessedPage { pageNumber, imagePath, width, height, rotationApplied }` — this is exactly the `Page.width/height/rotationApplied` that ends up in the final IDM, so the coordinate system is fixed here, once, for the rest of the pipeline. |
| Dependencies | `OpenCV` (`opencv-python-headless`), `PyMuPDF`, `Pillow`, `numpy`. |
| Failure conditions | Image fails to decode; page renders as fully blank/zero-content after preprocessing (likely a corrupt embedded image) → `INVALID_IMAGE`. |
| Recovery behaviour | Failure on any single page fails the whole job (`status: failed`, code `PROCESSING_FAILED`, `details.pageNumber` set) — smallerDOCS does not silently skip a page and produce a document missing a page, since that would violate "never silently drop content" (Design Principles below). User must re-upload. |
| Files | `backend/app/pipeline/preprocessing/deskew.py`, `denoise.py`, `binarize.py`, `border_removal.py`, `resolution_normalizer.py`. |
| Execution order | Stage 3 of 11. Second half of job status `preprocessing`. |
| State | Stateless per page (each page processed independently; pages *can* be processed in parallel — see Performance Targets). |
| Handoff | `PreprocessedPage[]` (one per page) passed to `OCR`. |

Step-by-step, and why each exists:

| Step | Technique | Why |
|---|---|---|
| Rotation correction | `resolution_normalizer.py` reads PDF `/Rotate` metadata first (authoritative when present); for images and pages without that metadata, Tesseract's OSD (`pytesseract.image_to_osd`, used here *only* for orientation detection, not text recognition) estimates 0/90/180/270. | Phone-camera photos and some scans are stored sideways or upside-down; every downstream bbox and reading-order assumption depends on upright text. |
| Deskew | `deskew.py` — Hough line transform on binarized edges to estimate skew angle, then `cv2.warpAffine` rotation correction for angles beyond a 0.3° threshold. | Scanned legal documents are frequently a degree or two off from a flatbed scanner or handheld photo; even small skew measurably degrades OCR line-detection accuracy and, worse, corrupts bbox-based reading order. |
| Denoise | `denoise.py` — `cv2.fastNlMeansDenoising` for grayscale scans; light Gaussian blur pre-pass for phone-camera JPEG artifacts. | Scanner speckle and JPEG compression noise both increase OCR character-level error rate, especially on serif fonts common in legal documents. |
| Contrast enhancement | `binarize.py` — CLAHE (`cv2.createCLAHE`) applied before thresholding. | Phone photos of documents routinely have uneven lighting (shadow from the phone/hand); CLAHE normalizes local contrast so a shadowed corner doesn't get binarized to solid black. |
| Adaptive thresholding | `binarize.py` — `cv2.adaptiveThreshold` (Gaussian, block size 35, tuned per-DPI), not a single global threshold. | Global thresholding fails on documents with uneven background (coffee-stained scans, watermarked letterhead paper); adaptive thresholding handles this per-region. |
| Border removal | `border_removal.py` — largest-contour detection to crop out scanner bed borders / black photo edges. | Scanner "black frame" artifacts and photo backgrounds are not part of the document and would otherwise be fed to layout analysis as noise regions. |
| Resolution normalization | `resolution_normalizer.py` — every page, regardless of source DPI, is resampled to exactly 300 DPI. | Fixes the coordinate system once. Every bbox anywhere in the IDM, and therefore Comparison Mode's overlay, assumes this single fixed DPI — see `DOCUMENT_RECONSTRUCTION.md`. |
| Cropping | Applied as the final step, using the border-removal contour. | Ensures `Page.width`/`height` reflect only actual document content. |

---

### 4. OCR

| | |
|---|---|
| Purpose | Produce ground-truth or near-ground-truth text with precise bounding boxes for every page. |
| Responsibilities | For `"scanned"` pages: text detection + recognition via the OCR engine (decision below). For `"native"` pages: extraction of the existing text layer with per-word bboxes and font attributes — no recognition model involved at all. |
| Inputs | `PreprocessedPage[]` + the per-page `source` flag from `Document Classification`. |
| Outputs | `OcrPage { pageNumber, lines: [{ text, bbox, confidence, wordBboxes, fontFlags? }] }` — line-level text with word-level bboxes nested inside, confidence populated (native text always `1.0`). |
| Dependencies | `paddleocr` (PP-OCRv5) for scanned pages; `PyMuPDF` (`page.get_text("dict")`, which exposes per-span font name/flags — used to seed bold/italic detection) for native pages. |
| Failure conditions | OCR model raises (out-of-memory, corrupt image tensor); a page returns zero detected lines where preprocessing confirmed non-blank content. |
| Recovery behaviour | Same as Image Preprocessing — whole-job failure (`OCR_FAILED`), no partial/silent page skipping. |
| Files | `backend/app/pipeline/ocr/paddle_ocr_engine.py`, `backend/app/pipeline/ocr/native_text_extractor.py`. |
| Execution order | Stage 4 of 11. Entire duration of job status `ocr`. |
| State | Stateless per page; the PaddleOCR model itself is loaded once at process startup (`app/main.py` lifespan hook) and shared read-only across all jobs — never reloaded per-request. |
| Handoff | `OcrPage[]` passed to `Layout Analysis`. |

Why the native/scanned branch exists: for a born-digital PDF (the common case for contracts drawn
up in Word and exported to PDF), the text layer *is* the ground truth — running a recognition
model on a rendering of it can only introduce error the source never had. Extracting it directly
gives `confidence: 1.0` and perfect character fidelity, and is dramatically faster (no model
inference at all for that page). This also directly serves the "Never invent text" design
principle: native extraction is definitionally non-generative.

---

### 5. Layout Analysis

| | |
|---|---|
| Purpose | Segment each page into typed regions — the coarse structural skeleton the rest of reconstruction refines. |
| Responsibilities | Region detection (title / text / list / table / figure / header / footer) via PP-StructureV3's layout model; correlating `OcrPage` lines into each detected region by bbox containment. |
| Inputs | `PreprocessedPage[]` (image) + `OcrPage[]` (text/bboxes from Stage 4, for both native and scanned pages — the layout model itself always looks only at the image, never at extracted text). |
| Outputs | `LayoutPage { pageNumber, regions: [{ id, coarseType, bbox, containedLines }] }`. `coarseType` is one of PP-StructureV3's native categories: `title`, `text`, `list`, `table`, `figure`, `header`, `footer`. |
| Dependencies | `paddleocr[doc-parser]` (PP-StructureV3's layout detection module, `PP-DocLayout`). |
| Failure conditions | Layout model raises; a page produces zero regions where OCR found text (indicates a model/preprocessing mismatch). |
| Recovery behaviour | Whole-job failure, `LAYOUT_ANALYSIS_FAILED`. |
| Files | `backend/app/pipeline/layout/structure_analysis.py`. |
| Execution order | Stage 5 of 11. First step inside job status `layout_analysis`. |
| State | Stateless per page; layout model loaded once at startup, same as OCR. |
| Handoff | `LayoutPage[]` passed to `Reading Order Detection`. |

**Multi-column layouts**: PP-StructureV3's region detector natively separates columns into
distinct `text` regions with correct left-to-right, top-to-bottom bboxes per column — the model
was trained on multi-column academic/magazine layouts specifically for this. `Reading Order
Detection` (next stage) is what turns "two side-by-side regions" into a correctly ordered
single-column reading sequence (read all of column 1 top-to-bottom, then column 2), not this
stage. Most legal documents in scope (contracts, affidavits, leases) are single-column; the
capability exists mainly for the rare multi-column government form.

**Signatures**: a `figure`-classified region positioned in the bottom third of the final page of
the document, combined with a `text` line immediately above it matching a name/title pattern, is
tagged as a signature-block candidate here (`region.attrs.candidateRole: "signature"`), refined
into an actual `signatureLine` block later in Block Classification.

---

### 6. Reading Order Detection

| | |
|---|---|
| Purpose | Produce the single linear sequence of regions that becomes the IDM's `Page.blocks` array order. |
| Responsibilities | Sort regions into reading order; identify and set aside header/footer/page-number regions so they don't get interleaved into body content. |
| Inputs | `LayoutPage[]`. |
| Outputs | `OrderedPage { pageNumber, orderedRegionIds: [string], suppressedRegionIds: [string] }`. |
| Dependencies | None beyond pure Python — implements an XY-cut recursive projection algorithm over region bboxes (top-to-bottom split first, then left-to-right within each horizontal band; recurses into a band if it contains multiple columns). |
| Failure conditions | Circular/inconsistent ordering (should be structurally impossible given XY-cut, retained as a defensive check that raises `READING_ORDER_FAILED` rather than emit a nonsensical order). |
| Recovery behaviour | Whole-job failure. |
| Files | `backend/app/pipeline/layout/reading_order.py`. |
| Execution order | Stage 6 of 11, inside `layout_analysis`. |
| State | Stateless per page. |
| Handoff | `OrderedPage[]` passed to `Block Classification`, which iterates regions strictly in `orderedRegionIds` order. |

**Preventing the three named failure modes**:

- *Paragraphs merging with headers*: any region whose bbox falls within the top margin band
  (top 8% of page height) or bottom margin band (bottom 8%) and whose text matches a
  repeated-content heuristic (see below) is classified `header`/`footer` by Layout Analysis and
  placed in `suppressedRegionIds` here — it is never interleaved into `orderedRegionIds` at all,
  so it structurally cannot end up merged mid-paragraph.
- *Footers appearing in the middle of content*: same mechanism — footers are identified by
  position band, not by y-coordinate proximity to the surrounding text, so a body paragraph that
  happens to end near the bottom margin isn't misclassified.
- *Incorrect ordering of table content*: a `table` region is treated as a single atomic unit in
  the XY-cut — its internal row/column order is never decided by this stage (that's `Table
  Detection`'s job entirely); this stage only decides *where the table as a whole* sits relative
  to surrounding paragraphs.

**Repeated-header/footer detection**: after all pages are individually ordered, a cross-page pass
compares suppressed header/footer region text across pages; if the same normalized text (allowing
a page-number token to vary) appears in the header/footer band on ≥60% of pages, it's confirmed as
a running header/footer and flagged `attrs.repeated: true` for the Legal Rules Engine (see
`LEGAL_DOCUMENT_RULES.md`, "Repeated headers/footers"). It is still suppressed from the reading
order in the same way, on every page.

---

### 7. Block Classification

| | |
|---|---|
| Purpose | Convert each ordered region into one of the IDM's precise block types (not just PP-Structure's five coarse categories). |
| Responsibilities | Heading level assignment; clause-number detection; list vs. plain-paragraph distinction; signature-line/date-field confirmation; page-break insertion. |
| Inputs | `OrderedPage[]` + `LayoutPage[]` (for region text/bbox) + `ClassificationResult.detectedDocumentType` (numbering-style hint). |
| Outputs | `ClassifiedBlock[]` per page — same shape as the IDM `Block` minus `runs`/`children` population (text is still flat at this point; `Formatting Reconstruction` fills those in). |
| Dependencies | Pure Python + regex pattern library for clause-numbering styles (`legal_decimal`, `roman`, `alpha`) — see `LEGAL_DOCUMENT_RULES.md` for the full pattern set. |
| Failure conditions | None fatal — an unrecognized region defaults to `paragraph`, the safest fallback (never dropped, never guessed into something more specific than the evidence supports). |
| Recovery behaviour | N/A. |
| Files | `backend/app/pipeline/layout/block_classifier.py`. |
| Execution order | Stage 7 of 11, inside `layout_analysis`. |
| State | Stateless. |
| Handoff | `ClassifiedBlock[]` passed to `Table Detection` (which only acts on blocks of type `table`) and onward to `Formatting Reconstruction`. |

**Full supported block type list** (extends the five PP-Structure coarse types):

| IDM type | Classified from | Detection rule |
|---|---|---|
| `heading` | `title` region, or a `text` region with font size ≥1.4× the page's modal body font size | Relative font-size ranking within the page, computed from OCR/native span heights; `attrs.level` assigned 1/2/3 by size-rank tercile |
| `paragraph` | `text` region not matching any more specific rule | Default fallback |
| `list` / `listItem` | `list` region, or a `text` region whose lines each begin with a bullet glyph (•, -, ‣) or a repeating `(a)`/`(i)`/`1)` pattern | Per-line prefix regex match against the pattern library |
| `clauseNumber` | The leading token of a `text` region's first line, matched against the legal numbering pattern library | See `LEGAL_DOCUMENT_RULES.md` §"Clause hierarchy" |
| `table` / `tableRow` / `tableCell` | `table` region | Refined by `Table Detection` (Stage 8) |
| `signatureLine` | A `candidateRole: "signature"` region from Layout Analysis, confirmed if a nearby line matches `/^(Signature|Signed|Witness|Notary|Date)[:.]?/i` | `attrs.role` set from the matched keyword |
| `pageBreak` | Synthetic — inserted between the last block of page N and first block of page N+1 | Always inserted, never detected |

---

### 8. Table Detection

| | |
|---|---|
| Purpose | Recover exact row/column/merge structure for every region classified as `table`. |
| Responsibilities | Run table-structure recognition on the cropped sub-image of each table region; map recognized cells back to their contained OCR text. |
| Inputs | `ClassifiedBlock[]` filtered to `type == "table"`, plus the corresponding cropped region image. |
| Outputs | For each table block: fully populated `tableRow`/`tableCell` children with `rowIndex`/`colIndex`/`rowSpan`/`colSpan`, per `DOCUMENT_RECONSTRUCTION.md`'s table schema. |
| Dependencies | PP-StructureV3's table recognition module (`PP-TableMagic`), which outputs an HTML table structure that is parsed into the row/col/span model. |
| Failure conditions | Table region fails structure recognition (returns no cells) — falls back to emitting the region as a single `paragraph` block containing all its OCR text, rather than dropping it (a degraded-but-present table beats a silently missing one; flagged via `confidence: 0.0` on the fallback block so the source of the degradation is visible in the IDM). |
| Recovery behaviour | Per-table fallback as above; does not fail the whole job. |
| Files | `backend/app/pipeline/layout/table_detector.py`. |
| Execution order | Stage 8 of 11, final step inside `layout_analysis`. |
| State | Stateless per table region. |
| Handoff | Fully structured table blocks merged back into `ClassifiedBlock[]` in place of their originating `table` region, passed to `Formatting Reconstruction`. |

**Merged cells**: `PP-TableMagic`'s HTML output natively expresses merges as `rowspan`/`colspan`
attributes; these are parsed directly into `TableCell.rowSpan`/`colSpan` with no additional
heuristics needed. Covered cells are omitted from the emitted `children` array entirely, per the
"cells they cover are omitted" rule already fixed in `DOCUMENT_RECONSTRUCTION.md`.

---

### 9. Formatting Reconstruction

| | |
|---|---|
| Purpose | Assemble the final `Block`/`Run` IDM objects — this is where marks, alignment, and indentation are computed and where the shape becomes exactly what `DOCUMENT_RECONSTRUCTION.md` defines. |
| Responsibilities | Populate `runs` (splitting classified block text into mark-consistent spans); compute `attrs.alignment` from bbox position relative to page margins; compute `attrs.indentLevel` from left-bbox-offset banding; assign final `Block.id`/`Run.id` UUIDs. |
| Inputs | `ClassifiedBlock[]` (with table structure already resolved) + the underlying `OcrPage` line/word data (for font-flag-derived bold/italic on scanned pages, or native PDF font-flag data for digital pages). |
| Outputs | `DocumentModel.pages[].blocks` — the real IDM structure, fully populated. |
| Dependencies | Pure Python. |
| Failure conditions | None fatal — this stage is a deterministic transform of already-validated data. |
| Recovery behaviour | N/A. |
| Files | `backend/app/pipeline/reconstruction/idm_builder.py`. |
| Execution order | Stage 9 of 11. First step inside job status `reconstruction`. |
| State | Stateless. |
| Handoff | Assembled (but not yet clause-numbered/legal-refined) `DocumentModel` passed to `Legal Rules Engine`. |

**Bold/italic/underline detection**: for scanned pages, PP-OCRv5 recognition does not directly
output style flags, so bold is inferred from stroke-width heuristics (`cv2` contour thickness
analysis on the binarized crop of each word) and italic from measured glyph shear angle; both are
intentionally conservative (default to `false` on ambiguous evidence — a missed bold is a minor
fidelity loss, a *false* bold is a fabricated formatting claim, and the latter is worse under the
"never invent" principle). For native-text pages, bold/italic/underline come directly from
PyMuPDF's font-flag bits on each text span — exact, not inferred.

**Alignment**: a paragraph's left/right bbox offsets from the page's established left/right
margins (computed as the modal margin across all paragraph blocks on the page) determine
`left`/`right`/`center`/`justify` — `justify` specifically when both margins are matched *and*
word-spacing variance within the block is above a threshold (indicating stretched inter-word
spacing, the visual signature of justified text).

---

### 10. Legal Rules Engine

| | |
|---|---|
| Purpose | Apply the legal-document-specific reconstruction rules that make smallerDOCS distinct from a generic OCR tool. |
| Responsibilities | Clause numbering style detection and hierarchy assignment (`clauseNumber.attrs.numberingStyle`/`depth`); repeated header/footer tagging carried through from Stage 6; signature-block role refinement. |
| Inputs | The assembled `DocumentModel` from Stage 9, plus `ClassificationResult.detectedDocumentType`. |
| Outputs | The same `DocumentModel`, with clause hierarchy resolved and legal-specific `attrs` finalized. |
| Dependencies | Pure Python — the full rule set is documented exhaustively in `LEGAL_DOCUMENT_RULES.md`; this stage is that document's implementation. |
| Failure conditions | None fatal — an unresolvable numbering pattern is left as plain text within its paragraph rather than forced into a `clauseNumber` block (never guessing a structure the evidence doesn't support). |
| Recovery behaviour | N/A. |
| Files | `backend/app/pipeline/reconstruction/clause_numbering.py`. |
| Execution order | Stage 10 of 11. Final step inside job status `reconstruction`. |
| State | Stateless. |
| Handoff | Final `DocumentModel` passed to Stage 11 (IDM finalization/serialization). |

---

### 11. Intermediate Document Model (Finalization)

| | |
|---|---|
| Purpose | Serialize the completed `DocumentModel`, compute document-level `metadata.averageConfidence`, and make the result retrievable. |
| Responsibilities | Aggregate confidence across all blocks/runs; write the final JSON to the job's temp store; flip job status to `completed`. |
| Inputs | Final `DocumentModel` from Stage 10. |
| Outputs | Persisted `{TEMP_ROOT}/{jobId}/document.json`, retrievable via `GET /api/v1/document/{jobId}`. |
| Dependencies | Pydantic's `.model_dump_json()`. |
| Failure conditions | Disk write failure. |
| Recovery behaviour | `RECONSTRUCTION_FAILED`, whole-job failure. |
| Files | `backend/app/pipeline/reconstruction/idm_builder.py` (finalization function, same module as Stage 9). |
| Execution order | Stage 11 of 11. |
| State | Stateful — this is the one point where `job_manager` transitions status to the terminal `completed` state. |
| Handoff | Frontend polls, sees `completed`, calls `GET /document/{jobId}`. |

---

## OCR Engine Comparison and Decision

Evaluated against: accuracy on legal documents, table handling, heading/bullet detection,
multi-page throughput, CPU/GPU performance, community/maintenance, integration effort, memory
footprint, long-term viability, and — critically for this project — **license terms that hold up
under "completely free, no paid APIs" for a product that may eventually be commercialized**, not
just free for a hobbyist to run once.

| | PaddleOCR (PP-OCRv5 + PP-StructureV3) | Surya OCR | docTR | Tesseract | Marker |
|---|---|---|---|---|---|
| Accuracy, legal-document text | High — PP-OCRv5 is a mature, actively-tuned recognition model; PaddleOCR-VL variant scores 96.3% on OmniDocBench, though smallerDOCS deliberately does **not** use the VL variant (see below) | Very high on benchmarks | Good, general-purpose | Moderate — solid on clean printed text, degrades on noisy scans | Very high (built on Surya) |
| Table structure recognition | Native, first-party (`PP-TableMagic`), outputs row/col/span directly | Native (`TableRecPredictor`), good | Weak — no first-party structure recognition, text-only | None built-in | Native (via Surya), strong |
| Heading / bullet / list detection | Native, first-party via `PP-StructureV3` region types | Native via layout module | None — recognition only, no layout model | None | Native (markdown-oriented block types) |
| Multi-page PDF handling | Native, page-by-page, mature tooling | Native | Manual (page-by-page via caller) | Manual | Native, PDF-first design |
| CPU performance | Good — dedicated "mobile" model variants exist specifically for CPU-only deployment | Poor on CPU; **Surya 2 (2026) now requires a local vLLM or llama.cpp inference server** even for CPU, a heavier operational dependency than a plain Python import | Good, CPU-friendly | Best-in-class (always was CPU-only) | Poor on CPU — GPU strongly recommended (reported 5GB VRAM/worker) |
| GPU support | Optional, well-supported | Required for practical throughput | Optional | None (CPU-only) | Effectively required for production throughput |
| Community / maintenance | Very large (Baidu-backed), high release cadence — PP-OCRv6 shipped June 2026 during this document's research | Active, smaller | Active (Mindee-backed), moderate size | Extremely large, decades of maturity, low velocity | Active, smaller, same team as Surya |
| Ease of integration | `pip install paddleocr`, one Python API surface for OCR + layout + tables | `pip install surya-ocr`; v2 additionally requires standing up a local vLLM/llama.cpp server process | `pip install python-doctr` | `pip install pytesseract` + system Tesseract binary | `pip install marker-pdf`, heavier dependency tree (PyTorch + Surya) |
| Memory usage | Moderate; mobile models specifically optimized for constrained memory | High (VLM-class models) | Low–moderate | Very low | High (8GB+ RAM reported on complex documents) |
| License — code | **Apache-2.0** | Apache-2.0 (as of the 2026 Surya 2 rewrite) for the *code* | Apache-2.0 | Apache-2.0 | **GPL-3.0** |
| License — model weights | **Apache-2.0**, no revenue/funding conditions anywhere in the stack | Modified Open RAIL-M: free only for research, personal use, and organizations under ~$2–5M funding/revenue; commercial license required above that | Apache-2.0 | Public domain / Apache-2.0 tessdata | Modified Open RAIL-M, same revenue/funding ceiling as Surya |
| Long-term viability | Strong — multi-year track record, continuous major releases through mid-2026 | Strong technically, but commercial licensing terms are an explicit business risk, not just a technical one | Stable, smaller scope | Extremely stable, effectively a permanent baseline | Same licensing risk as Surya |

**Decision: PaddleOCR 3.0, specifically the traditional (non-generative) pipeline — PP-OCRv5 for
text detection/recognition, PP-StructureV3 for layout region detection and reading-order
postprocessing, PP-TableMagic for table structure.**

Reasoning, in priority order matching the project's stated optimization goals:

1. **No paid APIs, completely free, long-term.** This is the deciding factor over Surya and
   Marker. Both are excellent, and by some public benchmarks more accurate than PaddleOCR at the
   raw text-recognition level — but their *model weights* carry a funding/revenue-conditioned
   license (free only under roughly $2–5M in funding or annual revenue, verified directly from
   the current PyPI/GitHub license pages as of this document's research). smallerDOCS's own
   requirements state "completely free," "no paid APIs" with no carve-out for "free until the
   product succeeds." PaddleOCR's Apache-2.0 license, on both code and weights, has no such
   condition at any scale — this is the only stack in the comparison that is unconditionally free
   forever.
2. **Formatting preservation.** PP-StructureV3 is a first-party, integrated layout + table +
   reading-order suite purpose-built for exactly this project's core requirement — it is not a
   general OCR engine with structure bolted on. docTR and Tesseract have no comparable native
   structure understanding and would require assembling a separate layout-detection stack
   (e.g. LayoutParser) — more moving parts, more integration risk, worse long-term maintainability
   for a solo-maintained project.
3. **"Never invent text" (see Design Principles below).** smallerDOCS deliberately uses
   PP-OCRv5's traditional detection+recognition pipeline rather than **PaddleOCR-VL**, PaddleOCR's
   own newer end-to-end vision-language-model pipeline, even though PaddleOCR-VL scores higher on
   public benchmarks (96.3% on OmniDocBench v1.6 as of the June 2026 release). A VLM is a
   generative model — it can produce plausible-looking text for a region it didn't actually read
   correctly. A detection+recognition pipeline like PP-OCRv5 has no generative capacity at the
   character level; it can misread a character, but it cannot hallucinate a plausible sentence
   that was never on the page. For legal document reconstruction, a wrong-but-honest low-confidence
   read is a far smaller risk than a fluent invention, so the traditional pipeline is the correct
   choice even at a measurable accuracy cost. The same reasoning excludes Surya 2's VLM-based
   architecture and Marker (which layers an optional LLM-correction pass on top of Surya).
4. **CPU-viable, ₹0/month-compatible deployment.** PaddleOCR ships dedicated CPU-optimized
   ("mobile") model variants; Surya 2 and Marker are both meaningfully GPU-oriented in their
   current architectures (Surya 2 specifically now runs its models behind a local vLLM/llama.cpp
   inference server, a materially heavier deployment footprint than a plain Python import). A
   free-tier or low-spec production deployment is a stated project constraint.
5. **Community and long-term maintenance.** PaddleOCR is backed by Baidu with a multi-year, high
   cadence release history (PP-OCRv6 shipped in June 2026, one month before this document's
   research), giving strong confidence the project will keep receiving updates and won't be
   abandoned.

**Tesseract and docTR are not selected as the primary engine** — both lack native layout/table
understanding, which is a hard requirement, not a nice-to-have, for this project. Neither is
introduced as a fallback engine in v1 either: adding a second OCR engine purely for edge-case
coverage is exactly the kind of architectural complexity this document's Design Principles caution
against, and PaddleOCR's own mobile+server model tiers already give a built-in speed/accuracy
trade-off lever if needed later.

---

## Confidence Handling

Every `Block` and `Run` in the IDM carries `confidence: 0.0–1.0`, populated as follows and never
overwritten to hide a low value:

| Band | Meaning | Origin |
|---|---|---|
| 0.99 – 1.00 | Ground truth | Native PDF text extraction (Stage 4, `"native"` branch); user-edited content re-saved through the editor (`EDITOR_SPECIFICATION.md` reverse mapping always sets `1.0` on edited text) |
| 0.95 – 0.99 | High-confidence OCR | Clean scanned text, PP-OCRv5 recognition score in this range |
| 0.90 – 0.95 | Medium-confidence OCR | Legible but imperfect scan (light skew residual, minor noise, small/dense font) |
| Below 0.90 | Low-confidence OCR | Degraded scans, damaged documents, unusual fonts, handwritten annotations mixed into printed text |

`Block.confidence` is the minimum of its constituent `Run.confidence` values (a block is only as
trustworthy as its least-confident span) except for container blocks (`table`, `list`), whose
confidence is the minimum across all descendant leaf blocks.

v1 ships no dedicated UI for surfacing this (per the project's "Professional. Minimal." UI
directive and explicit v1 scope) — but the field is populated with real, meaningful values from
day one specifically so a future version can add low-confidence highlighting without a pipeline
change, only a frontend change. This is a direct application of "never hide uncertainty."

---

## Performance Targets

| Metric | Target | Hardware assumption |
|---|---|---|
| Single scanned page, OCR + layout + reconstruction | ≤ 4 seconds | 4 vCPU, no GPU |
| Single scanned page | ≤ 1.5 seconds | 4 vCPU + entry-level GPU (optional path) |
| Single native-text (digital) PDF page | ≤ 0.5 seconds | 4 vCPU (no OCR model invoked at all) |
| 20-page scanned contract, end-to-end | ≤ 90 seconds | 4 vCPU, no GPU |
| 20-page scanned contract, end-to-end | ≤ 30 seconds | 4 vCPU + GPU |
| Maximum supported pages | 100 (hard cap, `TOO_MANY_PAGES` above this) | — |
| Peak memory per concurrent job | ≤ 2 GB | Excludes the once-loaded, shared OCR/layout models (~1–1.5 GB resident, loaded once at process startup, not per job) |
| Expected minimum deployment hardware | 4 vCPU / 8 GB RAM, no GPU required | Consistent with the project's ₹0/month free-tier hosting target |

Pages within a single document are processed with bounded parallelism
(`asyncio.Semaphore(PAGE_CONCURRENCY)`, default 4) at the Preprocessing/OCR/Layout stages, which
are page-independent by design (see "State" in each stage card above) — this is what makes the
20-page target achievable on CPU-only hardware without requiring pages to be processed strictly
serially.

---

## Pipeline Folder Responsibilities

This supersedes the abbreviated `pipeline/` listing in `PROJECT_STRUCTURE.md` with the complete,
final file list:

```
backend/app/pipeline/
├── classification/
│   └── document_classifier.py   # Stage 2
├── preprocessing/
│   ├── deskew.py                 # Stage 3
│   ├── denoise.py                # Stage 3
│   ├── binarize.py               # Stage 3
│   ├── border_removal.py         # Stage 3
│   └── resolution_normalizer.py  # Stage 3
├── ocr/
│   ├── paddle_ocr_engine.py      # Stage 4 (scanned branch)
│   └── native_text_extractor.py  # Stage 4 (native branch)
├── layout/
│   ├── structure_analysis.py     # Stage 5
│   ├── reading_order.py          # Stage 6
│   ├── block_classifier.py       # Stage 7
│   └── table_detector.py         # Stage 8
└── reconstruction/
    ├── idm_builder.py            # Stages 9 and 11
    └── clause_numbering.py       # Stage 10
```

| Module | Owns | Not allowed to |
|---|---|---|
| `classification/` | Deciding native-vs-scanned per page; document-type heuristic | Touch pixel data, run any model inference beyond text-layer inspection |
| `preprocessing/` | All pixel-level image transforms | Read or interpret text content; call any OCR/layout model |
| `ocr/` | Text + bbox extraction (model or native) | Make layout/structural decisions; know about block types |
| `layout/` | Region detection, reading order, block typing, table structure | Assign final `Block`/`Run` IDs; decide marks/alignment (that's `reconstruction/`'s job); apply legal-specific rules |
| `reconstruction/` | Final IDM assembly, marks, alignment, indentation, clause numbering, confidence aggregation | Call any model directly — it only consumes the already-extracted outputs of `ocr/` and `layout/` |

No module imports "sideways" from a module later in the pipeline (e.g. `preprocessing/` never
imports from `layout/`) — data only ever flows forward through the stage sequence, matching the
one-directional pipeline shown in "Overall Pipeline" above.

---

## Design Principles

Every stage in this pipeline, present and future, must uphold:

1. **Never invent text.** No stage may substitute a plausible guess for text it cannot confidently
   read. This is the specific reason smallerDOCS uses PP-OCRv5's traditional recognition pipeline
   over any generative VLM-based OCR engine (see "OCR Engine Comparison and Decision" above).
2. **Never silently drop content.** A failure in any stage fails the whole job with a visible
   error, rather than producing a document quietly missing a page, block, or table. A degraded
   result (e.g. a table that falls back to a flat paragraph, see Stage 8) is always preferred over
   a missing one, and is always flagged via `confidence`, never hidden.
3. **Preserve structure over appearance.** When a choice must be made between reproducing the
   *visual* layout exactly (pixel-perfect spacing) and reproducing the *logical* structure
   correctly (this is a numbered clause, this is a table cell), structure wins — because structure
   is what makes the output usefully editable, which is the entire point of the product.
4. **Maintain deterministic output.** Given the same input file, the pipeline produces the same
   IDM every time. No stage uses randomness or non-deterministic model sampling (recognition and
   layout models are run in their deterministic/greedy inference mode, not sampling mode).
5. **Never use AI to guess missing words.** If OCR cannot recognize a character or word, the
   pipeline emits its best literal reading with a correspondingly low `confidence` — it never asks
   a language model to "fill in" what the word was probably supposed to be. Confidence exists
   precisely so uncertainty is visible instead of papered over.
6. **Every stage is independently testable.** Because each stage is a pure function with a fixed
   input/output contract (this document), any stage can be unit-tested in isolation against fixed
   fixture inputs without running the full pipeline — a direct consequence of the "no sideways
   imports" rule above.
