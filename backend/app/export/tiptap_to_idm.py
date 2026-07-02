from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.idm import BBox, Block, DocumentMetadata, DocumentModel, Page, Run, RunMarks


def tiptap_to_idm(
    tiptap_doc: dict[str, Any],
    original_document_id: str,
    original_document: DocumentModel | None = None,
) -> DocumentModel:
    original_blocks = _index_blocks(original_document) if original_document else {}
    source_file_name = original_document.source_file_name if original_document else "document"
    source_type = original_document.source_type if original_document else "pdf"
    page_width = original_document.pages[0].width if original_document and original_document.pages else 2550
    page_height = original_document.pages[0].height if original_document and original_document.pages else 3300

    blocks: list[Block] = []
    for node in tiptap_doc.get("content", []):
        blocks.extend(_node_to_blocks(node, original_blocks))

    document = DocumentModel(
        document_id=original_document_id,
        source_type=source_type,
        source_file_name=source_file_name,
        page_count=1,
        created_at=datetime.now(timezone.utc),
        pages=[Page(page_number=1, width=page_width, height=page_height, rotation_applied=0, blocks=blocks)],
        metadata=DocumentMetadata(
            detected_document_type=original_document.metadata.detected_document_type if original_document else "unknown",
            language=original_document.metadata.language if original_document else "en",
            average_confidence=1.0,
        ),
    )
    document.metadata.average_confidence = _average(document)
    return document


def _node_to_blocks(node: dict[str, Any], original_blocks: dict[str, Block]) -> list[Block]:
    node_type = node.get("type")
    attrs = node.get("attrs") or {}
    source_id = attrs.get("sourceBlockId")
    original = original_blocks.get(source_id) if source_id else None

    if node_type == "heading":
        return [_leaf_block("heading", node, original, {"level": attrs.get("level", 1)})]
    if node_type == "paragraph":
        return _paragraph_to_blocks(node, original)
    if node_type in {"bulletList", "orderedList"}:
        children = []
        for child in node.get("content", []):
            if child.get("type") == "listItem":
                children.append(_list_item(child, original_blocks))
        return [
            Block(
                id=source_id or str(uuid4()),
                type="list",
                bbox=original.bbox if original else None,
                confidence=1.0,
                attrs={"listType": "bullet" if node_type == "bulletList" else "ordered", "startNumber": attrs.get("start", 1)},
                runs=None,
                children=children,
            )
        ]
    if node_type == "table":
        rows = []
        for row_index, row_node in enumerate(node.get("content", [])):
            row_children = []
            for col_index, cell_node in enumerate(row_node.get("content", [])):
                cell_attrs = cell_node.get("attrs") or {}
                cell_source = cell_attrs.get("sourceBlockId")
                cell_original = original_blocks.get(cell_source) if cell_source else None
                row_children.append(
                    Block(
                        id=cell_source or str(uuid4()),
                        type="tableCell",
                        bbox=cell_original.bbox if cell_original else None,
                        confidence=1.0,
                        attrs={
                            "rowIndex": row_index,
                            "colIndex": col_index,
                            "rowSpan": cell_attrs.get("rowspan", 1),
                            "colSpan": cell_attrs.get("colspan", 1),
                        },
                        runs=_runs_from_content(_cell_text_content(cell_node), cell_original),
                        children=None,
                    )
                )
            rows.append(
                Block(
                    id=str(uuid4()),
                    type="tableRow",
                    bbox=None,
                    confidence=1.0,
                    attrs={"rowIndex": row_index},
                    runs=None,
                    children=row_children,
                )
            )
        return [
            Block(
                id=source_id or str(uuid4()),
                type="table",
                bbox=original.bbox if original else None,
                confidence=1.0,
                attrs={"rowCount": len(rows), "colCount": max((len(row.children or []) for row in rows), default=0)},
                runs=None,
                children=rows,
            )
        ]
    return []


def _paragraph_to_blocks(node: dict[str, Any], original: Block | None) -> list[Block]:
    attrs = node.get("attrs") or {}
    content = node.get("content", [])
    produced: list[Block] = []
    text_nodes = content
    if content and content[0].get("type") == "clauseNumber":
        clause_attrs = content[0].get("attrs") or {}
        display = clause_attrs.get("display", "")
        produced.append(
            Block(
                id=attrs.get("sourceBlockId") or str(uuid4()),
                type="clauseNumber",
                bbox=original.bbox if original else None,
                confidence=1.0,
                attrs={
                    "numberingStyle": clause_attrs.get("numberingStyle", "legal_decimal"),
                    "depth": clause_attrs.get("depth", 1),
                    "display": display,
                },
                runs=[_run(display, original)],
                children=None,
            )
        )
        text_nodes = content[1:]
    role = attrs.get("blockRole")
    block_type = "signatureLine" if role == "signatureLine" else "pageBreak" if role == "pageBreak" else "paragraph"
    block_attrs = {"alignment": attrs.get("textAlign", "left"), "indentLevel": attrs.get("indentLevel", 0)}
    if block_type == "signatureLine":
        block_attrs = {"role": attrs.get("role", "signatory")}
    if block_type == "pageBreak":
        block_attrs = {}
    produced.append(
        Block(
            id=attrs.get("sourceBlockId") or str(uuid4()),
            type=block_type,
            bbox=original.bbox if original else None,
            confidence=1.0,
            attrs=block_attrs,
            runs=_runs_from_content(text_nodes, original) or [_run("", original)],
            children=None,
        )
    )
    return produced


def _leaf_block(block_type: str, node: dict[str, Any], original: Block | None, attrs: dict[str, Any]) -> Block:
    node_attrs = node.get("attrs") or {}
    return Block(
        id=node_attrs.get("sourceBlockId") or str(uuid4()),
        type=block_type,
        bbox=original.bbox if original else None,
        confidence=1.0,
        attrs=attrs,
        runs=_runs_from_content(node.get("content", []), original) or [_run("", original)],
        children=None,
    )


def _list_item(node: dict[str, Any], original_blocks: dict[str, Block]) -> Block:
    attrs = node.get("attrs") or {}
    source_id = attrs.get("sourceBlockId")
    original = original_blocks.get(source_id) if source_id else None
    content = []
    for child in node.get("content", []):
        content.extend(child.get("content", []) if child.get("type") == "paragraph" else [child])
    return Block(
        id=source_id or str(uuid4()),
        type="listItem",
        bbox=original.bbox if original else None,
        confidence=1.0,
        attrs={"indentLevel": attrs.get("indentLevel", 0)},
        runs=_runs_from_content(content, original) or [_run("", original)],
        children=None,
    )


def _cell_text_content(cell_node: dict[str, Any]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for child in cell_node.get("content", []):
        content.extend(child.get("content", []) if child.get("type") == "paragraph" else [child])
    return content


def _runs_from_content(content: list[dict[str, Any]], original: Block | None) -> list[Run]:
    runs: list[Run] = []
    for node in content:
        if node.get("type") == "text":
            runs.append(_run(node.get("text", ""), original, node.get("marks") or []))
        elif node.get("type") == "hardBreak":
            runs.append(_run("\n", original, []))
    return runs


def _run(text: str, original: Block | None, marks: list[dict[str, Any]] | None = None) -> Run:
    original_bbox = original.bbox if original and original.bbox else BBox(x=0, y=0, width=0, height=0)
    return Run(id=str(uuid4()), text=text, bbox=original_bbox, confidence=1.0, marks=_marks(marks or []))


def _marks(marks: list[dict[str, Any]]) -> RunMarks:
    result = RunMarks()
    for mark in marks:
        mark_type = mark.get("type")
        attrs = mark.get("attrs") or {}
        if mark_type == "bold":
            result.bold = True
        elif mark_type == "italic":
            result.italic = True
        elif mark_type == "underline":
            result.underline = True
        elif mark_type == "textStyle":
            result.color = attrs.get("color")
        elif mark_type == "highlight":
            result.highlight = attrs.get("color")
    return result


def _index_blocks(document: DocumentModel | None) -> dict[str, Block]:
    if document is None:
        return {}
    indexed: dict[str, Block] = {}
    for page in document.pages:
        for block in page.blocks:
            _index_block(block, indexed)
    return indexed


def _index_block(block: Block, indexed: dict[str, Block]) -> None:
    indexed[block.id] = block
    for child in block.children or []:
        _index_block(child, indexed)


def _average(document: DocumentModel) -> float:
    confidences = [block.confidence for page in document.pages for block in page.blocks]
    return round(sum(confidences) / len(confidences), 4) if confidences else 1.0
