from __future__ import annotations

from typing import Any

from app.core.errors import AppError
from app.models.errors import ErrorCode

ALLOWED_NODE_TYPES = {
    "doc",
    "paragraph",
    "heading",
    "text",
    "bulletList",
    "orderedList",
    "listItem",
    "table",
    "tableRow",
    "tableCell",
    "tableHeader",
    "hardBreak",
    "clauseNumber",
}

ALLOWED_MARK_TYPES = {"bold", "italic", "underline", "textStyle", "highlight", "sourceBlockId"}


def validate_tiptap_document(doc: dict[str, Any]) -> None:
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        raise AppError(
            ErrorCode.INVALID_DOCUMENT_CONTENT,
            "Tiptap payload root must be a doc node.",
            "The document content could not be exported.",
            retryable=False,
        )
    _validate_node(doc, path="content")


def _validate_node(node: Any, path: str) -> None:
    if not isinstance(node, dict):
        _invalid(f"{path} must be an object")
    node_type = node.get("type")
    if node_type not in ALLOWED_NODE_TYPES:
        _invalid(f"Unknown Tiptap node type at {path}: {node_type!r}")
    if "attrs" in node and not isinstance(node["attrs"], dict):
        _invalid(f"attrs at {path} must be an object")
    if node_type == "text":
        if not isinstance(node.get("text"), str):
            _invalid(f"text node at {path} must include string text")
    content = node.get("content")
    if content is not None:
        if not isinstance(content, list):
            _invalid(f"content at {path} must be an array")
        for index, child in enumerate(content):
            _validate_node(child, f"{path}.{index}")
    marks = node.get("marks")
    if marks is not None:
        if not isinstance(marks, list):
            _invalid(f"marks at {path} must be an array")
        for index, mark in enumerate(marks):
            if not isinstance(mark, dict) or mark.get("type") not in ALLOWED_MARK_TYPES:
                _invalid(f"unknown mark at {path}.marks.{index}")


def _invalid(message: str) -> None:
    raise AppError(
        ErrorCode.INVALID_DOCUMENT_CONTENT,
        message,
        "The document content could not be exported.",
        retryable=False,
    )
