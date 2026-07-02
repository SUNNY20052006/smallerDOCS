from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from .base import CamelModel

SourceType = Literal["pdf", "image"]
DocumentType = Literal[
    "contract",
    "affidavit",
    "lease",
    "court_filing",
    "notice",
    "form",
    "unknown",
]
BlockType = Literal[
    "heading",
    "paragraph",
    "list",
    "listItem",
    "table",
    "tableRow",
    "tableCell",
    "clauseNumber",
    "signatureLine",
    "pageBreak",
]


class BBox(CamelModel):
    x: float
    y: float
    width: float
    height: float


class RunMarks(CamelModel):
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: str | None = None
    highlight: str | None = None


class Run(CamelModel):
    id: str
    text: str
    bbox: BBox
    confidence: float = Field(ge=0.0, le=1.0)
    marks: RunMarks


class Block(CamelModel):
    id: str
    type: BlockType
    bbox: BBox | None
    confidence: float = Field(ge=0.0, le=1.0)
    attrs: dict[str, Any]
    runs: list[Run] | None = None
    children: list["Block"] | None = None

    @field_validator("children")
    @classmethod
    def validate_content_shape(cls, children: list["Block"] | None, info: Any) -> list["Block"] | None:
        runs = info.data.get("runs")
        if runs is None and children is None:
            raise ValueError("exactly one of runs or children must be populated")
        if runs is not None and children is not None:
            raise ValueError("runs and children cannot both be populated")
        return children


class Page(CamelModel):
    page_number: int = Field(ge=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    rotation_applied: Literal[0, 90, 180, 270]
    blocks: list[Block]


class DocumentMetadata(CamelModel):
    detected_document_type: DocumentType
    language: str = "en"
    average_confidence: float = Field(ge=0.0, le=1.0)


class DocumentModel(CamelModel):
    document_id: str
    source_type: SourceType
    source_file_name: str
    page_count: int = Field(ge=1)
    created_at: datetime
    pages: list[Page]
    metadata: DocumentMetadata
