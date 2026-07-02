from __future__ import annotations

import re
from statistics import median
from uuid import uuid4

from bs4 import BeautifulSoup

from app.models.idm import BBox


def resolve_tables(classified_pages: list[dict]) -> list[dict]:
    for page in classified_pages:
        resolved = []
        for block in page["blocks"]:
            if block["type"] == "table":
                table = _table_from_ocr_lines(block)
                resolved.append(table if table is not None else _fallback_table_as_paragraph(block))
            else:
                resolved.append(block)
        page["blocks"] = resolved
    return classified_pages


def parse_html_table(html: str, table_bbox: BBox) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return None
    rows = []
    col_count = 0
    for row_index, tr in enumerate(table.find_all("tr")):
        cells = []
        col_index = 0
        for td in tr.find_all(["td", "th"]):
            text = td.get_text(" ", strip=True)
            row_span = int(td.get("rowspan", 1))
            col_span = int(td.get("colspan", 1))
            col_count = max(col_count, col_index + col_span)
            cells.append(
                {
                    "type": "tableCell",
                    "bbox": table_bbox,
                    "confidence": 1.0,
                    "attrs": {"rowIndex": row_index, "colIndex": col_index, "rowSpan": row_span, "colSpan": col_span},
                    "lines": [{"text": text, "bbox": table_bbox, "confidence": 1.0, "wordBboxes": []}],
                }
            )
            col_index += col_span
        rows.append({"type": "tableRow", "bbox": table_bbox, "confidence": 1.0, "attrs": {"rowIndex": row_index}, "children": cells})
    return {"type": "table", "bbox": table_bbox, "confidence": 1.0, "attrs": {"rowCount": len(rows), "colCount": col_count}, "children": rows}


def _fallback_table_as_paragraph(block: dict) -> dict:
    text = " ".join(line.get("text", "") for line in block.get("lines", []))
    return {
        **block,
        "type": "paragraph",
        "confidence": 0.0,
        "attrs": {"alignment": "left", "indentLevel": 0},
        "lines": [{"text": text, "bbox": block["bbox"], "confidence": 0.0, "wordBboxes": []}],
    }


def _table_from_ocr_lines(block: dict) -> dict | None:
    lines = [line for line in block.get("lines", []) if line.get("text", "").strip() and line.get("bbox") is not None]
    if len(lines) < 4:
        return None

    row_groups = _cluster_rows(lines, block["bbox"])
    col_centers = _cluster_column_centers(lines, block["bbox"])
    if len(row_groups) < 2 or len(col_centers) < 2:
        return None

    row_count = len(row_groups)
    col_count = len(col_centers)
    table_bbox = block["bbox"]
    rows = []
    for row_index, row_lines in enumerate(row_groups):
        cells = []
        assigned: list[list[dict]] = [[] for _ in range(col_count)]
        for line in row_lines:
            col_index = _nearest_column_index(_center_x(line["bbox"]), col_centers)
            assigned[col_index].append(line)
        row_bbox = _union_bbox([line["bbox"] for line in row_lines]) or table_bbox
        for col_index, cell_lines in enumerate(assigned):
            cell_bbox = _cell_bbox(cell_lines, table_bbox, row_bbox, col_centers, col_index)
            text = " ".join(line["text"].strip() for line in sorted(cell_lines, key=lambda item: (item["bbox"].y, item["bbox"].x)))
            confidence = min((float(line.get("confidence", 1.0)) for line in cell_lines), default=float(block.get("confidence", 1.0)))
            cells.append(
                {
                    "id": str(uuid4()),
                    "type": "tableCell",
                    "bbox": cell_bbox,
                    "confidence": confidence,
                    "attrs": {"rowIndex": row_index, "colIndex": col_index, "rowSpan": 1, "colSpan": 1},
                    "lines": [{"text": text, "bbox": cell_bbox, "confidence": confidence, "wordBboxes": []}],
                }
            )
        rows.append(
            {
                "id": str(uuid4()),
                "type": "tableRow",
                "bbox": row_bbox,
                "confidence": min((cell["confidence"] for cell in cells), default=float(block.get("confidence", 1.0))),
                "attrs": {"rowIndex": row_index},
                "children": cells,
            }
        )

    return {
        **block,
        "type": "table",
        "confidence": min((row["confidence"] for row in rows), default=float(block.get("confidence", 1.0))),
        "attrs": {"rowCount": row_count, "colCount": col_count},
        "runs": None,
        "children": rows,
        "lines": [],
    }


def _cluster_rows(lines: list[dict], table_bbox: BBox) -> list[list[dict]]:
    serial_groups = _cluster_serial_number_rows(lines, table_bbox)
    if serial_groups is not None:
        return serial_groups

    ordered = sorted(lines, key=lambda line: _center_y(line["bbox"]))
    heights = [line["bbox"].height for line in ordered if line["bbox"].height > 0]
    threshold = max(28.0, (median(heights) if heights else 20.0) * 1.45)
    groups: list[list[dict]] = [[ordered[0]]]
    last_center = _center_y(ordered[0]["bbox"])
    for line in ordered[1:]:
        center = _center_y(line["bbox"])
        if center - last_center > threshold:
            groups.append([line])
        else:
            groups[-1].append(line)
        last_center = center
    return [sorted(group, key=lambda line: line["bbox"].x) for group in groups]


def _cluster_serial_number_rows(lines: list[dict], table_bbox: BBox) -> list[list[dict]] | None:
    ordered = sorted(lines, key=lambda line: (_center_y(line["bbox"]), line["bbox"].x))
    heights = [line["bbox"].height for line in ordered if line["bbox"].height > 0]
    typical_height = median(heights) if heights else 20.0
    row_margin = max(18.0, typical_height * 1.1)
    serial_limit_x = table_bbox.x + max(80.0, table_bbox.width * 0.16)
    serial_lines = [
        line
        for line in ordered
        if re.fullmatch(r"\d{1,3}", line.get("text", "").strip()) and line["bbox"].x <= serial_limit_x
    ]
    if len(serial_lines) < 2:
        return None

    serial_lines = _dedupe_nearby_serial_lines(serial_lines, row_margin)
    if len(serial_lines) < 2:
        return None

    first_start = _center_y(serial_lines[0]["bbox"]) - row_margin
    header_lines = [line for line in ordered if _center_y(line["bbox"]) < first_start]
    row_groups: list[list[dict]] = []
    if len(header_lines) >= 2:
        row_groups.append(sorted(header_lines, key=lambda line: line["bbox"].x))

    for index, serial_line in enumerate(serial_lines):
        start = _center_y(serial_line["bbox"]) - row_margin
        end = (
            _center_y(serial_lines[index + 1]["bbox"]) - row_margin
            if index + 1 < len(serial_lines)
            else table_bbox.y + table_bbox.height + row_margin
        )
        group = [line for line in ordered if start <= _center_y(line["bbox"]) < end]
        if group:
            row_groups.append(sorted(group, key=lambda line: line["bbox"].x))

    return row_groups if len(row_groups) >= 3 else None


def _dedupe_nearby_serial_lines(serial_lines: list[dict], row_margin: float) -> list[dict]:
    deduped: list[dict] = []
    for line in serial_lines:
        if deduped and abs(_center_y(line["bbox"]) - _center_y(deduped[-1]["bbox"])) <= row_margin:
            continue
        deduped.append(line)
    return deduped


def _cluster_column_centers(lines: list[dict], table_bbox: BBox) -> list[float]:
    serial_centers = [_center_x(line["bbox"]) for line in lines if _is_serial_line(line, table_bbox)]
    if len(serial_centers) >= 2:
        serial_center = median(serial_centers)
        remaining_centers = sorted(_center_x(line["bbox"]) for line in lines if _center_x(line["bbox"]) > serial_center + 45.0)
        remaining_clusters = _cluster_centers(remaining_centers, _column_threshold(lines))
        if len(remaining_clusters) >= 2:
            return [serial_center, *remaining_clusters]

    centers = sorted(_center_x(line["bbox"]) for line in lines)
    return _cluster_centers(centers, _column_threshold(lines))


def _cluster_centers(centers: list[float], threshold: float) -> list[float]:
    if not centers:
        return []
    clusters: list[list[float]] = [[centers[0]]]
    for center in centers[1:]:
        if center - clusters[-1][-1] > threshold:
            clusters.append([center])
        else:
            clusters[-1].append(center)
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _column_threshold(lines: list[dict]) -> float:
    widths = [line["bbox"].width for line in lines if line["bbox"].width > 0]
    typical_width = median(widths) if widths else 80.0
    return max(60.0, min(95.0, typical_width * 0.75))


def _is_serial_line(line: dict, table_bbox: BBox) -> bool:
    serial_limit_x = table_bbox.x + max(80.0, table_bbox.width * 0.16)
    return re.fullmatch(r"\d{1,3}", line.get("text", "").strip()) is not None and line["bbox"].x <= serial_limit_x


def _nearest_column_index(center: float, col_centers: list[float]) -> int:
    return min(range(len(col_centers)), key=lambda index: abs(col_centers[index] - center))


def _cell_bbox(cell_lines: list[dict], table_bbox: BBox, row_bbox: BBox, col_centers: list[float], col_index: int) -> BBox:
    if cell_lines:
        return _union_bbox([line["bbox"] for line in cell_lines]) or row_bbox
    left = table_bbox.x if col_index == 0 else (col_centers[col_index - 1] + col_centers[col_index]) / 2
    right = table_bbox.x + table_bbox.width if col_index == len(col_centers) - 1 else (col_centers[col_index] + col_centers[col_index + 1]) / 2
    return BBox(x=left, y=row_bbox.y, width=max(1.0, right - left), height=max(1.0, row_bbox.height))


def _union_bbox(boxes: list[BBox]) -> BBox | None:
    if not boxes:
        return None
    min_x = min(box.x for box in boxes)
    min_y = min(box.y for box in boxes)
    max_x = max(box.x + box.width for box in boxes)
    max_y = max(box.y + box.height for box in boxes)
    return BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)


def _center_x(bbox: BBox) -> float:
    return bbox.x + bbox.width / 2


def _center_y(bbox: BBox) -> float:
    return bbox.y + bbox.height / 2
