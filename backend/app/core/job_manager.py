from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.models.api import FileType, JobStatus, StatusResponse
from app.models.errors import ErrorCode, ErrorObject


TERMINAL_STATUSES = {"completed", "failed"}
LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "uploaded": {"queued", "failed"},
    "queued": {"preprocessing", "failed"},
    "preprocessing": {"ocr", "failed"},
    "ocr": {"layout_analysis", "failed"},
    "layout_analysis": {"reconstruction", "failed"},
    "reconstruction": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


@dataclass
class JobRecord:
    job_id: str
    file_name: str
    file_type: FileType
    file_size_bytes: int
    source_path: str
    status: JobStatus
    progress: int
    current_page: int | None
    total_pages: int | None
    created_at: datetime
    updated_at: datetime
    error: ErrorObject | None = None


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = RLock()

    def create_job(self, file_name: str, file_type: FileType, file_size_bytes: int, source_path: str = "") -> JobRecord:
        now = datetime.now(timezone.utc)
        job_id = str(uuid4())
        record = JobRecord(
            job_id=job_id,
            file_name=file_name,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            source_path=source_path,
            status="uploaded",
            progress=0,
            current_page=None,
            total_pages=None,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job_id] = record
        return record

    def register_job(self, record: JobRecord) -> None:
        with self._lock:
            self._jobs[record.job_id] = record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def require(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        if record is None:
            raise KeyError(job_id)
        return record

    def transition(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress: int | None = None,
        current_page: int | None = None,
        total_pages: int | None = None,
    ) -> JobRecord:
        with self._lock:
            record = self.require(job_id)
            if status not in LEGAL_TRANSITIONS[record.status]:
                raise ValueError(f"invalid transition {record.status} -> {status}")
            record.status = status
            if progress is not None:
                record.progress = max(0, min(100, progress))
            record.current_page = current_page
            record.total_pages = total_pages
            record.updated_at = datetime.now(timezone.utc)
            return record

    def update_progress(
        self,
        job_id: str,
        *,
        progress: int,
        current_page: int | None = None,
        total_pages: int | None = None,
    ) -> None:
        with self._lock:
            record = self.require(job_id)
            if record.status in TERMINAL_STATUSES:
                return
            record.progress = max(0, min(100, progress))
            record.current_page = current_page
            record.total_pages = total_pages
            record.updated_at = datetime.now(timezone.utc)

    def fail(self, job_id: str, error: ErrorObject) -> None:
        with self._lock:
            record = self.require(job_id)
            if record.status in TERMINAL_STATUSES:
                return
            record.status = "failed"
            record.error = error
            record.updated_at = datetime.now(timezone.utc)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def remove_many(self, job_ids: list[str]) -> None:
        with self._lock:
            for job_id in job_ids:
                self._jobs.pop(job_id, None)

    def status_response(self, job_id: str) -> StatusResponse:
        record = self.require(job_id)
        return StatusResponse(
            job_id=record.job_id,
            status=record.status,
            progress=record.progress,
            current_page=record.current_page,
            total_pages=record.total_pages,
            error=record.error,
        )


job_manager = JobManager()


def pipeline_error(code: ErrorCode, message: str, user_message: str, details: dict | None = None) -> ErrorObject:
    return ErrorObject(code=code, message=message, user_message=user_message, retryable=False, details=details)
