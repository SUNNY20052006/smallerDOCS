from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.models.errors import ErrorCode, ErrorObject


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        user_message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error = ErrorObject(
            code=code,
            message=message,
            user_message=user_message,
            retryable=retryable,
            details=details,
        )
        self.status_code = status_code
        super().__init__(message)


def error_response(error: ErrorObject, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error.model_dump(by_alias=True, mode="json")},
    )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.error, exc.status_code)


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    error = ErrorObject(
        code=ErrorCode.PROCESSING_FAILED,
        message=str(exc),
        user_message="Something went wrong while processing the document.",
        retryable=False,
        details=None,
    )
    return error_response(error, 500)
