from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from app.models.idm import BBox


class LayoutEngine:
    def __init__(self) -> None:
        self._model: Any | None = None
        self._fallback_model: Any | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        from paddlex import create_predictor

        self._model = create_predictor(model_name="PP-DocLayout-S")

    def analyze_page(self, image_path: Path, ocr_page: dict) -> dict:
        self.load()
        width, height = _image_size(image_path)
        raw_results = self._model.predict(str(image_path))
        raw_regions = []
        for result in raw_results:
            data = _result_data(result)
            raw_regions.extend(data.get("boxes", []))
        regions = []
        for raw_region in raw_regions:
            region = _region_from_raw(raw_region, ocr_page["lines"])
            if region is not None:
                regions.append(region)
        if not regions and ocr_page["lines"]:
            regions = self._analyze_with_pp_structure_fallback(image_path, ocr_page)
        if regions:
            regions = _append_orphan_regions(regions, ocr_page["lines"], width)
        if not regions and ocr_page["lines"]:
            regions = [_single_text_region(ocr_page["lines"])]
        return {"pageNumber": ocr_page["pageNumber"], "width": width, "height": height, "regions": regions}

    def _analyze_with_pp_structure_fallback(self, image_path: Path, ocr_page: dict) -> list[dict]:
        if self._fallback_model is None:
            from paddleocr import PPStructureV3

            self._fallback_model = PPStructureV3(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                use_table_recognition=False,
                use_formula_recognition=False,
                use_chart_recognition=False,
                use_seal_recognition=False,
                use_region_detection=False,
            )
        raw_results = self._fallback_model.predict(input=str(image_path))
        regions = []
        for result in raw_results:
            data = _result_data(result)
            for raw_region in (data.get("layout_det_res") or {}).get("boxes", []):
                region = _region_from_raw(raw_region, ocr_page["lines"])
                if region is not None:
                    regions.append(region)
        return regions


def _region_from_raw(region: dict[str, Any], lines: list[dict]) -> dict | None:
    bbox_values = region.get("coordinate") or region.get("bbox") or region.get("box")
    if not bbox_values or len(bbox_values) < 4:
        return None
    x0, y0, x1, y1 = map(float, bbox_values[:4])
    bbox = BBox(x=x0, y=y0, width=max(0, x1 - x0), height=max(0, y1 - y0))
    contained = [line for line in lines if _contains(bbox, line["bbox"])]
    coarse_type = str(region.get("label") or region.get("type") or "text")
    return {
        "id": str(uuid4()),
        "coarseType": _normalize_type(coarse_type),
        "bbox": bbox,
        "containedLines": contained,
        "attrs": {},
    }


def _single_text_region(lines: list[dict]) -> dict:
    min_x = min(line["bbox"].x for line in lines)
    min_y = min(line["bbox"].y for line in lines)
    max_x = max(line["bbox"].x + line["bbox"].width for line in lines)
    max_y = max(line["bbox"].y + line["bbox"].height for line in lines)
    return {
        "id": str(uuid4()),
        "coarseType": "text",
        "bbox": BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y),
        "containedLines": lines,
        "attrs": {},
    }


def _append_orphan_regions(regions: list[dict], lines: list[dict], page_width: int) -> list[dict]:
    claimed_line_ids = {id(line) for region in regions for line in region.get("containedLines", [])}
    orphan_lines = [line for line in lines if id(line) not in claimed_line_ids and line.get("text", "").strip()]
    if not orphan_lines:
        return regions
    return [*regions, *(_orphan_region(group, page_width) for group in _group_orphan_lines(orphan_lines))]


def _group_orphan_lines(lines: list[dict]) -> list[list[dict]]:
    ordered = sorted(lines, key=lambda line: (line["bbox"].y, line["bbox"].x))
    heights = [line["bbox"].height for line in ordered if line["bbox"].height > 0]
    typical_height = sorted(heights)[len(heights) // 2] if heights else 24.0
    threshold = max(36.0, typical_height * 2.0)
    groups: list[list[dict]] = [[ordered[0]]]
    last_bottom = ordered[0]["bbox"].y + ordered[0]["bbox"].height
    for line in ordered[1:]:
        if line["bbox"].y - last_bottom > threshold:
            groups.append([line])
        else:
            groups[-1].append(line)
        last_bottom = max(last_bottom, line["bbox"].y + line["bbox"].height)
    return groups


def _orphan_region(lines: list[dict], page_width: int) -> dict:
    bbox = _union_bbox([line["bbox"] for line in lines])
    text = " ".join(line["text"] for line in lines).strip()
    return {
        "id": str(uuid4()),
        "coarseType": _orphan_region_type(text, bbox, page_width, len(lines)),
        "bbox": bbox,
        "containedLines": lines,
        "attrs": {"source": "ocr_orphan"},
    }


def _orphan_region_type(text: str, bbox: BBox, page_width: int, line_count: int) -> str:
    center_x = bbox.x + bbox.width / 2
    page_center = page_width / 2
    normalized = text.replace(":", "").replace("-", "").strip()
    letter_count = sum(1 for char in normalized if char.isalpha())
    uppercase_count = sum(1 for char in normalized if char.isupper())
    mostly_upper = letter_count > 0 and uppercase_count >= max(3, letter_count * 0.6)
    centered = abs(center_x - page_center) <= max(80.0, page_width * 0.18)
    if line_count <= 2 and centered and (mostly_upper or "schedule" in text.lower()):
        return "title"
    return "text"


def _union_bbox(boxes: list[BBox]) -> BBox:
    min_x = min(box.x for box in boxes)
    min_y = min(box.y for box in boxes)
    max_x = max(box.x + box.width for box in boxes)
    max_y = max(box.y + box.height for box in boxes)
    return BBox(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)


def _contains(outer: BBox, inner: BBox) -> bool:
    cx = inner.x + inner.width / 2
    cy = inner.y + inner.height / 2
    return outer.x <= cx <= outer.x + outer.width and outer.y <= cy <= outer.y + outer.height


def _normalize_type(value: str) -> str:
    lowered = value.lower()
    if lowered in {"doc_title", "paragraph_title"}:
        return "title"
    if lowered == "image":
        return "figure"
    if lowered in {"title", "header", "footer", "table", "figure", "list"}:
        return lowered
    return "text"


def _image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def _result_data(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item.get("res", item)
    json_value = getattr(item, "json", None)
    if isinstance(json_value, dict):
        return json_value.get("res", json_value)
    if callable(json_value):
        generated = json_value()
        if isinstance(generated, dict):
            return generated.get("res", generated)
    return getattr(item, "res", {})


layout_engine = LayoutEngine()
