from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from app.config import settings
from app.core.errors import AppError
from app.core.job_manager import job_manager
from app.core.temp_storage import temp_storage
from app.export.idm_to_docx import idm_to_docx
from app.export.idm_to_html import idm_to_html
from app.export.tiptap_to_idm import tiptap_to_idm
from app.models.api import ExportRequest
from app.models.errors import ErrorCode
from app.models.tiptap_schema import validate_tiptap_document

router = APIRouter()


@router.post("/export/{jobId}")
async def export_document(jobId: str, request: ExportRequest) -> Response:
    record = job_manager.get(jobId)
    if record is None:
        raise AppError(ErrorCode.JOB_NOT_FOUND, f"Unknown job {jobId}", "This upload has expired.", status_code=404)
    if request.format not in {"docx", "html"}:
        raise AppError(ErrorCode.INVALID_EXPORT_FORMAT, request.format, "Choose DOCX or HTML export.", status_code=400)
    validate_tiptap_document(request.content)
    original = temp_storage.read_document(jobId)
    try:
        document = tiptap_to_idm(request.content, jobId, original)
        if request.format == "docx":
            data = await asyncio.wait_for(asyncio.to_thread(idm_to_docx, document), timeout=settings.export_timeout_seconds)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            suffix = "docx"
        else:
            html = await asyncio.wait_for(asyncio.to_thread(idm_to_html, document), timeout=settings.export_timeout_seconds)
            data = html.encode("utf-8")
            media_type = "text/html"
            suffix = "html"
    except asyncio.TimeoutError as exc:
        raise AppError(
            ErrorCode.EXPORT_TIMEOUT,
            "Export timed out.",
            "The export took too long.",
            status_code=504,
            retryable=True,
        ) from exc
    except AppError:
        raise
    except Exception as exc:
        raise AppError(ErrorCode.EXPORT_FAILED, str(exc), "The export could not be created.", status_code=500) from exc
    stem = Path(record.file_name).stem
    headers = {"Content-Disposition": f'attachment; filename="{stem}_reconstructed.{suffix}"'}
    return Response(content=data, media_type=media_type, headers=headers)
