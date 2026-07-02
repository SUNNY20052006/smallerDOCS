from __future__ import annotations

import re


def apply_legal_rules(document, detected_document_type: str):
    for page in document.pages:
        for block in page.blocks:
            if block.type == "clauseNumber":
                display = block.attrs.get("display") or _first_token(block)
                style = block.attrs.get("numberingStyle") or _style_for(display)
                block.attrs["display"] = display
                block.attrs["numberingStyle"] = style
                block.attrs["depth"] = _depth_for(display, style)
    document.metadata.detected_document_type = detected_document_type
    return document


def _first_token(block) -> str:
    text = "".join(run.text for run in block.runs or [])
    return text.split(maxsplit=1)[0] if text.strip() else ""


def _style_for(display: str) -> str:
    if re.match(r"^\d+(?:\.\d+)*\.?$", display):
        return "legal_decimal"
    if re.match(r"^\(?[A-Za-z]\)?\.?$", display):
        return "alpha"
    return "roman"


def _depth_for(display: str, style: str) -> int:
    if style == "legal_decimal":
        return max(1, display.strip(".").count(".") + 1)
    if display.startswith("("):
        return 2
    return 1
