from __future__ import annotations

from fastapi import APIRouter, UploadFile

from app.core.errors import AppError
from app.core.file_validator import validate_upload
from app.core.job_manager import job_manager
from app.core.temp_storage import temp_storage
from app.models.api import UploadResponse
from app.models.errors import ErrorCode

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_file(file: UploadFile) -> UploadResponse:
    data = await file.read()
    file_name = file.filename or "upload"
    try:
        file_type = validate_upload(data, file_name, file.content_type)
        record = job_manager.create_job(file_name, file_type, len(data))
        temp_storage.create_job_dir(record.job_id)
        source_path = temp_storage.store_upload(record.job_id, file_name, data)
        record.source_path = str(source_path)
        return UploadResponse(
            job_id=record.job_id,
            file_name=record.file_name,
            file_type=record.file_type,
            file_size_bytes=record.file_size_bytes,
            status="uploaded",
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            ErrorCode.UPLOAD_FAILED,
            f"Upload failed: {exc}",
            "The file could not be uploaded.",
            status_code=500,
        ) from exc
