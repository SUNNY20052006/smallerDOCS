from __future__ import annotations

from typing import Any, Literal

from .base import CamelModel
from .errors import ErrorObject

FileType = Literal["pdf", "image"]
JobStatus = Literal[
    "uploaded",
    "queued",
    "preprocessing",
    "ocr",
    "layout_analysis",
    "reconstruction",
    "completed",
    "failed",
]
ExportFormat = Literal["docx", "html"]


class UploadResponse(CamelModel):
    job_id: str
    file_name: str
    file_type: FileType
    file_size_bytes: int
    status: Literal["uploaded"]


class ProcessResponse(CamelModel):
    job_id: str
    status: Literal["queued"]


class StatusResponse(CamelModel):
    job_id: str
    status: JobStatus
    progress: int
    current_page: int | None = None
    total_pages: int | None = None
    error: ErrorObject | None = None


class ExportRequest(CamelModel):
    format: ExportFormat
    content: dict[str, Any]


class ExportResponse(CamelModel):
    file_name: str
    content_type: str


class HealthResponse(CamelModel):
    status: Literal["ok"]
    ocr_engine_loaded: bool
