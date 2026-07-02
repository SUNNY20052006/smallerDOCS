from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.errors import AppError
from app.core.job_manager import job_manager
from app.core.temp_storage import temp_storage
from app.models.errors import ErrorCode

router = APIRouter()


@router.delete("/job/{jobId}", status_code=204)
async def delete_job(jobId: str) -> Response:
    deleted = job_manager.delete(jobId)
    if not deleted:
        raise AppError(ErrorCode.JOB_NOT_FOUND, f"Unknown job {jobId}", "This upload has already been removed.", status_code=404)
    temp_storage.cleanup(jobId)
    return Response(status_code=204)
