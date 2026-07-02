from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.idm import BBox, Block, DocumentMetadata, DocumentModel, Page, Run, RunMarks


def build_document_model(
    *,
    document_id: str,
    source_type: str,
    source_file_name: str,
    preprocessed_pages: list,
    classified_pages: list[dict],
    detected_document_type: str,
) -> DocumentModel:
    page_lookup = {page.page_number: page for page in preprocessed_pages}
    pages: list[Page] = []
    for classified_page in classified_pages:
        preprocessed = page_lookup[classified_page["pageNumber"]]
        blocks = [_build_block(block) for block in classified_page["blocks"]]
        pages.append(
            Page(
                page_number=classified_page["pageNumber"],
                width=preprocessed.width,
                height=preprocessed.height,
                rotation_applied=preprocessed.rotation_applied,
                blocks=blocks,
            )
        )
    document = DocumentModel(
        document_id=document_id,
        source_type=source_type,
        source_file_name=source_file_name,
        page_count=len(pages),
        created_at=datetime.now(timezone.utc),
        pages=pages,
        metadata=DocumentMetadata(detected_document_type=detected_document_type, language="en", average_confidence=1.0),
    )
    document.metadata.average_confidence = _average_confidence(document)
    return document


def _build_block(block: dict) -> Block:
    block_type = block["type"]
    if block_type in {"list", "table", "tableRow"}:
        children = [_build_block(child) for child in block.get("children", [])]
        confidence = min((child.confidence for child in children), default=float(block.get("confidence", 1.0)))
        return Block(
            id=block.get("id", str(uuid4())),
            type=block_type,
            bbox=block.get("bbox"),
            confidence=confidence,
            attrs=block.get("attrs", {}),
            runs=None,
            children=children,
        )
    runs = _runs_from_lines(block.get("lines", []), block.get("bbox"))
    if block_type == "pageBreak" and not runs:
        runs = [Run(id=str(uuid4()), text="", bbox=BBox(x=0, y=0, width=0, height=0), confidence=1.0, marks=RunMarks())]
    confidence = min((run.confidence for run in runs), default=float(block.get("confidence", 1.0)))
    return Block(
        id=block.get("id", str(uuid4())),
        type=block_type,
        bbox=block.get("bbox"),
        confidence=confidence,
        attrs=block.get("attrs", {}),
        runs=runs,
        children=None,
    )


def _runs_from_lines(lines: list[dict], fallback_bbox: BBox | None) -> list[Run]:
    runs: list[Run] = []
    for line in lines:
        word_bboxes = line.get("wordBboxes") or []
        if word_bboxes:
            for word in word_bboxes:
                text = word.get("text", "")
                if not text:
                    continue
                runs.append(
                    Run(
                        id=str(uuid4()),
                        text=text,
                        bbox=word.get("bbox") or line.get("bbox") or fallback_bbox or BBox(x=0, y=0, width=0, height=0),
                        confidence=float(word.get("confidence", line.get("confidence", 1.0))),
                        marks=word.get("marks") or RunMarks(),
                    )
                )
        else:
            text = line.get("text", "")
            if text:
                runs.append(
                    Run(
                        id=str(uuid4()),
                        text=text,
                        bbox=line.get("bbox") or fallback_bbox or BBox(x=0, y=0, width=0, height=0),
                        confidence=float(line.get("confidence", 1.0)),
                        marks=RunMarks(),
                    )
                )
    return runs


def _average_confidence(document: DocumentModel) -> float:
    values: list[float] = []
    for page in document.pages:
        for block in page.blocks:
            _collect_confidences(block, values)
    return round(sum(values) / len(values), 4) if values else 1.0


def _collect_confidences(block: Block, values: list[float]) -> None:
    values.append(block.confidence)
    for run in block.runs or []:
        values.append(run.confidence)
    for child in block.children or []:
        _collect_confidences(child, values)
