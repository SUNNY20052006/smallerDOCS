from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.job_manager import job_manager
from app.core.temp_storage import temp_storage
from app.pipeline.layout.structure_analysis import layout_engine
from app.pipeline.ocr.paddle_ocr_engine import ocr_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        await asyncio.wait_for(asyncio.to_thread(ocr_engine.load), timeout=120)
    except Exception:
        pass
    try:
        await asyncio.wait_for(asyncio.to_thread(layout_engine.load), timeout=120)
    except Exception:
        pass
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="smallerDOCS", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(router)


async def _cleanup_loop() -> None:
    ttl_seconds = settings.job_ttl_minutes * 60
    while True:
        await asyncio.sleep(settings.cleanup_interval_seconds)
        expired = await asyncio.to_thread(temp_storage.sweep_expired, ttl_seconds)
        job_manager.remove_many(expired)
