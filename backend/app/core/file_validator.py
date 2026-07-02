from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.core.errors import AppError
from app.models.api import FileType
from app.models.errors import ErrorCode

ACCEPTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
}
ACCEPTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def validate_upload(data: bytes, file_name: str, content_type: str | None) -> FileType:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ACCEPTED_EXTENSIONS or content_type not in ACCEPTED_MIME_TYPES:
        raise AppError(
            ErrorCode.UNSUPPORTED_FILE_TYPE,
            f"Unsupported upload type: {content_type}, extension: {suffix}",
            "Upload a PDF, JPG, or PNG file.",
            status_code=400,
        )
    if len(data) > settings.max_file_size_bytes:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE,
            f"File is {len(data)} bytes; max is {settings.max_file_size_bytes}.",
            "The file is larger than the 50 MB limit.",
            status_code=413,
        )
    file_type = ACCEPTED_MIME_TYPES[content_type]
    if file_type == "pdf":
        _validate_pdf(data)
    else:
        _validate_image(data)
    return file_type  # type: ignore[return-value]


def _validate_pdf(data: bytes) -> None:
    try:
        import fitz

        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise AppError(
                    ErrorCode.PASSWORD_PROTECTED_PDF,
                    "PDF is password protected.",
                    "Password-protected PDFs are not supported.",
                    status_code=400,
                )
            if len(doc) > settings.max_pages:
                raise AppError(
                    ErrorCode.TOO_MANY_PAGES,
                    f"PDF has {len(doc)} pages; max is {settings.max_pages}.",
                    "This PDF has more than 100 pages.",
                    status_code=400,
                )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            ErrorCode.CORRUPTED_PDF,
            f"PDF failed to open: {exc}",
            "This PDF could not be opened.",
            status_code=400,
        ) from exc


def _validate_image(data: bytes) -> None:
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise AppError(
            ErrorCode.INVALID_IMAGE,
            f"Image failed validation: {exc}",
            "This image could not be opened.",
            status_code=400,
        ) from exc
