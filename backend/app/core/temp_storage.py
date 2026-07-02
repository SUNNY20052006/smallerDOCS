from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models.idm import DocumentModel


class TempStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def create_job_dir(self, job_id: str) -> Path:
        path = self.job_dir(job_id)
        path.mkdir(parents=True, exist_ok=False)
        (path / "preprocessed").mkdir()
        return path

    def store_upload(self, job_id: str, file_name: str, data: bytes) -> Path:
        suffix = Path(file_name).suffix.lower()
        path = self.job_dir(job_id) / f"source{suffix}"
        path.write_bytes(data)
        return path

    def write_document(self, job_id: str, document: DocumentModel) -> Path:
        path = self.job_dir(job_id) / "document.json"
        path.write_text(document.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
        return path

    def read_document(self, job_id: str) -> DocumentModel | None:
        path = self.job_dir(job_id) / "document.json"
        if not path.exists():
            return None
        return DocumentModel.model_validate_json(path.read_text(encoding="utf-8"))

    def cleanup(self, job_id: str) -> None:
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)

    def sweep_expired(self, ttl_seconds: int) -> list[str]:
        now = datetime.now(timezone.utc).timestamp()
        removed: list[str] = []
        for path in self.root.iterdir():
            if not path.is_dir():
                continue
            if now - path.stat().st_mtime > ttl_seconds:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(path.name)
        return removed


temp_storage = TempStorage(settings.temp_root)
