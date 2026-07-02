from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.core.errors import AppError
from app.core.job_manager import job_manager, pipeline_error
from app.models.api import ProcessResponse
from app.models.errors import ErrorCode
from app.pipeline import run_pipeline

router = APIRouter()


@router.post("/process/{jobId}", response_model=ProcessResponse, status_code=202)
async def start_processing(jobId: str) -> ProcessResponse:
    record = job_manager.get(jobId)
    if record is None:
        raise AppError(ErrorCode.JOB_NOT_FOUND, f"Unknown job {jobId}", "This upload has expired.", status_code=404)
    if record.status != "uploaded":
        raise AppError(
            ErrorCode.JOB_ALREADY_PROCESSING,
            f"Job {jobId} is already {record.status}.",
            "This document is already being processed.",
            status_code=409,
        )
    job_manager.transition(jobId, "queued", progress=0)
    asyncio.create_task(_run(jobId))
    return ProcessResponse(job_id=jobId, status="queued")


async def _run(job_id: str) -> None:
    try:
        await asyncio.to_thread(run_pipeline, job_id)
    except Exception as exc:
        record = job_manager.get(job_id)
        status = record.status if record else "failed"
        code = {
            "ocr": ErrorCode.OCR_FAILED,
            "layout_analysis": ErrorCode.LAYOUT_ANALYSIS_FAILED,
            "reconstruction": ErrorCode.RECONSTRUCTION_FAILED,
        }.get(status, ErrorCode.PROCESSING_FAILED)
        job_manager.fail(
            job_id,
            pipeline_error(
                code,
                str(exc),
                "The document could not be processed.",
                {"stage": status},
            ),
        )
