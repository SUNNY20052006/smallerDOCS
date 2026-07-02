from __future__ import annotations

from fastapi import APIRouter

from app.models.api import HealthResponse
from app.pipeline.layout.structure_analysis import layout_engine
from app.pipeline.ocr.paddle_ocr_engine import ocr_engine

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", ocr_engine_loaded=ocr_engine.loaded and layout_engine.loaded)
