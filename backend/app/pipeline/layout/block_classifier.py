from __future__ import annotations

import re
from statistics import median
from uuid import uuid4

from app.models.idm import BBox

TABLE_KEYWORDS = {
    "SLNO",
    "SL.NO",
    "TRANSFEROR",
    "TRANSFEREE",
    "PARTICULARS",
    "EXTENT",
    "SHARE",
    "FLOOR",
    "FLOORS",
    "AREA",
    "OCCUPANT",
    "OCCUPANTS",
    "SCHEDULE",
    "DESCRIPTION",
}

CLAUSE_PATTERNS = [
    ("legal_decimal", re.compile(r"^(\d+(?:\.\d+)*\.?)\s+")),
    ("roman", re.compile(r"^([IVXLCDMivxlcdm]+\.?)\s+")),
    ("alpha", re.compile(r"^(\([A-Za-z]\)|[A-Za-z]\.)\s+")),
]
LIST_PATTERN = re.compile(r"^\s*(?:[-*•‣]|\d+\)|\([ivxlcdm]+\))\s+", re.IGNORECASE)


def classify_blocks(layout_pages: list[dict], ordered_pages: list[dict], detected_document_type: str) -> list[dict]:
    region_map = {region["id"]: region for page in layout_pages for region in page["regions"]}
    classified_pages: list[dict] = []
    for page_index, ordered in enumerate(ordered_pages):
        blocks = []
        for region_id in ordered["orderedRegionIds"]:
            region = region_map[region_id]
            blocks.extend(_classify_region(region))
        if page_index > 0:
            blocks.insert(0, _page_break())
        classified_pages.append({"pageNumber": ordered["pageNumber"], "blocks": blocks})
    return classified_pages


def _classify_region(region: dict) -> list[dict]:
    text = " ".join(line["text"] for line in region.get("containedLines", [])).strip()
    coarse = region["coarseType"]
    if coarse == "table" or _is_table_like_region(region):
        return [_block("table", region, {"rowCount": 0, "colCount": 0})]
    if coarse == "title":
        return [_block("heading", region, {"level": 1})]
    signature_role = _signature_role(region)
    if coarse == "figure" and signature_role:
        return [_block("signatureLine", region, {"role": signature_role})]
    if _all_lines_match(region, LIST_PATTERN):
        return [_list_block(region)]
    clause = _clause_match(text)
    if clause:
        style, display = clause
        block = _block("clauseNumber", region, {"numberingStyle": style, "depth": 1, "display": display})
        block["clauseDisplay"] = display
        return [block]
    return [_block("paragraph", region, {"alignment": "left", "indentLevel": 0})]


def _block(block_type: str, region: dict, attrs: dict) -> dict:
    return {
        "id": str(uuid4()),
        "type": block_type,
        "bbox": region["bbox"],
        "confidence": _region_confidence(region),
        "attrs": attrs,
        "lines": region.get("containedLines", []),
    }


def _page_break() -> dict:
    return {
        "id": str(uuid4()),
        "type": "pageBreak",
        "bbox": None,
        "confidence": 1.0,
        "attrs": {},
        "lines": [],
    }


def _list_block(region: dict) -> dict:
    children = []
    for index, line in enumerate(region.get("containedLines", [])):
        bbox = line["bbox"]
        children.append(
            {
                "id": str(uuid4()),
                "type": "listItem",
                "bbox": bbox,
                "confidence": float(line.get("confidence", 1.0)),
                "attrs": {"indentLevel": 0},
                "lines": [line],
            }
        )
    return {
        "id": str(uuid4()),
        "type": "list",
        "bbox": region["bbox"],
        "confidence": min((child["confidence"] for child in children), default=_region_confidence(region)),
        "attrs": {"listType": "bullet", "startNumber": 1},
        "children": children,
        "lines": [],
    }


def _all_lines_match(region: dict, pattern: re.Pattern[str]) -> bool:
    lines = [line["text"] for line in region.get("containedLines", []) if line.get("text", "").strip()]
    return len(lines) > 1 and all(pattern.match(line) for line in lines)


def _clause_match(text: str) -> tuple[str, str] | None:
    for style, pattern in CLAUSE_PATTERNS:
        match = pattern.match(text)
        if match:
            return style, match.group(1)
    return None


def _is_table_like_region(region: dict) -> bool:
    if region["coarseType"] not in {"figure", "text", "table"}:
        return False
    lines = [line for line in region.get("containedLines", []) if line.get("text", "").strip() and line.get("bbox") is not None]
    if len(lines) < 6:
        return False

    bbox = region["bbox"]
    text = " ".join(line["text"] for line in lines).upper()
    keyword_hits = sum(1 for keyword in TABLE_KEYWORDS if keyword in text)
    column_count = _cluster_count([_center_x(line["bbox"]) for line in lines], _column_threshold(lines))
    row_band_count = _cluster_count([_center_y(line["bbox"]) for line in lines], _row_threshold(lines))
    left_serial_count = sum(
        1
        for line in lines
        if re.fullmatch(r"\d{1,3}", line["text"].strip())
        and line["bbox"].x <= bbox.x + max(90.0, bbox.width * 0.18)
    )

    if column_count >= 4 and row_band_count >= 3 and (keyword_hits >= 2 or left_serial_count >= 2):
        return True
    return column_count >= 3 and row_band_count >= 4 and keyword_hits >= 4


def _cluster_count(values: list[float], threshold: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    count = 1
    previous = ordered[0]
    for value in ordered[1:]:
        if value - previous > threshold:
            count += 1
        previous = value
    return count


def _column_threshold(lines: list[dict]) -> float:
    widths = [line["bbox"].width for line in lines if line["bbox"].width > 0]
    typical_width = median(widths) if widths else 80.0
    return max(55.0, min(100.0, typical_width * 0.75))


def _row_threshold(lines: list[dict]) -> float:
    heights = [line["bbox"].height for line in lines if line["bbox"].height > 0]
    typical_height = median(heights) if heights else 20.0
    return max(24.0, typical_height * 1.35)


def _signature_role(region: dict) -> str | None:
    lines = [line for line in region.get("containedLines", []) if line.get("text", "").strip()]
    text = " ".join(line["text"] for line in lines).strip()
    if len(lines) > 4 or len(text) > 180:
        return None
    lowered = text.lower()
    if "witness" in lowered:
        return "witness"
    if "notary" in lowered:
        return "notary"
    if re.search(r"\bdate(?:d)?\s*[:_]+|\bdate\s*$", lowered):
        return "date"
    if "signature" in lowered or "signed" in lowered:
        return "signatory"
    return None


def _region_confidence(region: dict) -> float:
    return min((float(line.get("confidence", 1.0)) for line in region.get("containedLines", [])), default=1.0)


def _center_x(bbox: BBox) -> float:
    return bbox.x + bbox.width / 2


def _center_y(bbox: BBox) -> float:
    return bbox.y + bbox.height / 2
