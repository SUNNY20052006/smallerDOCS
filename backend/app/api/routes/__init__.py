from fastapi import APIRouter

from . import document, export, health, job, process, status, upload

router = APIRouter(prefix="/api/v1")
router.include_router(upload.router)
router.include_router(process.router)
router.include_router(status.router)
router.include_router(document.router)
router.include_router(export.router)
router.include_router(job.router)
router.include_router(health.router)
