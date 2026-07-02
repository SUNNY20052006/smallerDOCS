from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.core.job_manager import job_manager
from app.core.temp_storage import temp_storage
from app.models.errors import ErrorCode
from app.models.idm import DocumentModel

router = APIRouter()


@router.get("/document/{jobId}", response_model=DocumentModel)
async def get_document(jobId: str) -> DocumentModel:
    record = job_manager.get(jobId)
    if record is None:
        raise AppError(ErrorCode.JOB_NOT_FOUND, f"Unknown job {jobId}", "This upload has expired.", status_code=404)
    if record.status != "completed":
        raise AppError(
            ErrorCode.DOCUMENT_NOT_READY,
            f"Job {jobId} is {record.status}, not completed.",
            "The document is not ready yet.",
            status_code=409,
        )
    document = temp_storage.read_document(jobId)
    if document is None:
        raise AppError(
            ErrorCode.RECONSTRUCTION_FAILED,
            f"Job {jobId} completed without document.json.",
            "The document could not be reconstructed.",
            status_code=500,
        )
    return document


@router.get("/document/{jobId}/page/{pageNumber}/image")
async def get_page_image(jobId: str, pageNumber: int) -> FileResponse:
    record = job_manager.get(jobId)
    if record is None:
        raise AppError(ErrorCode.JOB_NOT_FOUND, f"Unknown job {jobId}", "This upload has expired.", status_code=404)
    if record.status != "completed":
        raise AppError(
            ErrorCode.DOCUMENT_NOT_READY,
            f"Job {jobId} is {record.status}, not completed.",
            "The document image is not ready yet.",
            status_code=409,
        )
    image_path = temp_storage.job_dir(jobId) / "preprocessed" / f"page_{pageNumber}.png"
    if not image_path.exists():
        raise AppError(
            ErrorCode.RECONSTRUCTION_FAILED,
            f"Missing preprocessed image for job {jobId}, page {pageNumber}.",
            "The original page image could not be loaded.",
            status_code=500,
        )
    return FileResponse(image_path, media_type="image/png")
