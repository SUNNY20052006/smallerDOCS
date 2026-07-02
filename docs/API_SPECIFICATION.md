# API_SPECIFICATION.md

## Conventions

- Base URL: `/api/v1`
- All request/response bodies are JSON except `POST /upload` (multipart) and the binary file
  stream from `POST /export`.
- All JSON field names are `camelCase` on the wire (backend Pydantic models use
  `alias_generator=to_camel`, `populate_by_name=True`).
- No authentication (per project scope — no accounts, no DB).
- No pagination anywhere (single-document, single-session tool).
- Every error response, regardless of endpoint or status code, uses the single `ErrorObject`
  shape defined below. The frontend's `lib/api/client.ts` normalizes all non-2xx responses into
  this shape before they reach any component.

## Common: `ErrorObject`

```json
{
  "code": "string, one of ErrorCode enum (see ERROR_HANDLING.md)",
  "message": "string, technical detail (logged, not shown to user)",
  "userMessage": "string, safe to render directly in ErrorState.tsx",
  "retryable": "boolean",
  "details": { "...": "optional, error-specific extra fields" }
}
```

Wrapped in all error HTTP responses as:

```json
{ "error": ErrorObject }
```

---

## `POST /api/v1/upload`

Multipart form upload. Field name: `file`.

**Accepted types:** `application/pdf`, `image/jpeg`, `image/png`.
**Max size:** 50 MB (see `PERFORMANCE.md` for rationale).

**Success — 201 Created**
```json
{
  "jobId": "string (uuid)",
  "fileName": "string",
  "fileType": "pdf" | "image",
  "fileSizeBytes": "integer",
  "status": "uploaded"
}
```

**Errors**

| HTTP | code | when |
|---|---|---|
| 400 | `UNSUPPORTED_FILE_TYPE` | MIME type not in accepted list |
| 400 | `INVALID_IMAGE` | file claims to be image/pdf but fails to open/parse |
| 413 | `FILE_TOO_LARGE` | exceeds 50 MB |
| 400 | `CORRUPTED_PDF` | PDF fails to open via PyMuPDF |
| 500 | `UPLOAD_FAILED` | disk write failure, etc. |

---

## `POST /api/v1/process/{jobId}`

Starts the async pipeline (preprocessing → OCR → layout → reconstruction) for a previously
uploaded job. No request body.

**Success — 202 Accepted**
```json
{ "jobId": "string (uuid)", "status": "queued" }
```

**Errors**

| HTTP | code | when |
|---|---|---|
| 404 | `JOB_NOT_FOUND` | unknown/expired jobId |
| 409 | `JOB_ALREADY_PROCESSING` | process already triggered for this job |

---

## `GET /api/v1/status/{jobId}`

Polled by the frontend every 1.5s while status is non-terminal.

**Success — 200 OK**
```json
{
  "jobId": "string (uuid)",
  "status": "queued" | "preprocessing" | "ocr" | "layout_analysis" | "reconstruction" | "completed" | "failed",
  "progress": "integer 0-100",
  "currentPage": "integer | null",
  "totalPages": "integer | null",
  "error": ErrorObject | null
}
```

`error` is non-null only when `status == "failed"`. See `DATA_FLOW.md` for the full status state
machine and valid transitions.

**Errors**

| HTTP | code | when |
|---|---|---|
| 404 | `JOB_NOT_FOUND` | unknown/expired jobId |

---

## `GET /api/v1/document/{jobId}`

Returns the reconstructed document. Only valid once `status == "completed"`.

**Success — 200 OK**

Body is a `DocumentModel` — the full IDM as specified in `DOCUMENT_RECONSTRUCTION.md`.

**Errors**

| HTTP | code | when |
|---|---|---|
| 404 | `JOB_NOT_FOUND` | unknown/expired jobId |
| 409 | `DOCUMENT_NOT_READY` | status is not yet `completed` |
| 500 | `RECONSTRUCTION_FAILED` | pipeline completed but produced no valid document (should not normally surface here — this state is instead reported via `status.failed`; retained as a defensive case) |

---

## `POST /api/v1/export/{jobId}`

Frontend posts the **current** Tiptap document JSON (post-edits) as the source of truth for
export. The backend converts it back to IDM (`tiptapToIdm` logic, server-side mirror — see
`EXPORT_SYSTEM.md`) and generates the requested format. This keeps DOCX/HTML generation
server-side-only and authoritative, per `EXPORT_SYSTEM.md`.

**Request**
```json
{
  "format": "docx" | "html",
  "content": { "type": "doc", "content": [ "...Tiptap ProseMirror JSON, see EDITOR_SPECIFICATION.md" ] }
}
```

**Success — 200 OK**, binary response.

- `format: "docx"` → `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `Content-Disposition: attachment; filename="{originalName}_reconstructed.docx"`
- `format: "html"` → `Content-Type: text/html`, `Content-Disposition: attachment; filename="{originalName}_reconstructed.html"`

**Errors**

| HTTP | code | when |
|---|---|---|
| 404 | `JOB_NOT_FOUND` | unknown/expired jobId |
| 400 | `INVALID_EXPORT_FORMAT` | format not `docx`/`html` |
| 400 | `INVALID_DOCUMENT_CONTENT` | posted Tiptap JSON fails schema validation |
| 500 | `EXPORT_FAILED` | docx/html generation raised |
| 504 | `EXPORT_TIMEOUT` | generation exceeded configured timeout (large multi-page tables) |

---

## `DELETE /api/v1/job/{jobId}`

Explicit cleanup, called by the frontend when the user navigates away or starts a new upload.
Also invoked automatically by a backend TTL sweep (see `SECURITY.md` / `temp_storage.py`) for
abandoned jobs.

**Success — 204 No Content**, empty body.

**Errors**

| HTTP | code | when |
|---|---|---|
| 404 | `JOB_NOT_FOUND` | already deleted / never existed |

---

## `GET /api/v1/health`

Liveness/readiness probe for deployment. No auth, no jobId.

**Success — 200 OK**
```json
{ "status": "ok", "ocrEngineLoaded": "boolean" }
```
