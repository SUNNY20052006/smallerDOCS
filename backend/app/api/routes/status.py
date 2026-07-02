from __future__ import annotations

from fastapi import APIRouter

from app.core.errors import AppError
from app.core.job_manager import job_manager
from app.models.api import StatusResponse
from app.models.errors import ErrorCode

router = APIRouter()


@router.get("/status/{jobId}", response_model=StatusResponse)
async def get_status(jobId: str) -> StatusResponse:
    try:
        return job_manager.status_response(jobId)
    except KeyError as exc:
        raise AppError(ErrorCode.JOB_NOT_FOUND, f"Unknown job {jobId}", "This upload has expired.", status_code=404) from exc
