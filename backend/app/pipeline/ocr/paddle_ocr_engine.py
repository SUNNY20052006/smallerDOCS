from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.idm import BBox, RunMarks


class PaddleOcrEngine:
    def __init__(self) -> None:
        self._model: Any | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        from paddleocr import PaddleOCR

        self._model = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
        )

    def ocr_page(self, image_path: Path, page_number: int) -> dict:
        self.load()
        result = self._model.predict(str(image_path))
        lines: list[dict] = []
        for item in result:
            data = _result_data(item)
            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            polys = data.get("rec_polys") or data.get("rec_boxes") or []
            for text, score, poly in zip(texts, scores, polys, strict=False):
                if not str(text).strip():
                    continue
                bbox = _poly_to_bbox(poly)
                confidence = max(0.0, min(1.0, float(score)))
                lines.append(
                    {
                        "text": str(text),
                        "bbox": bbox,
                        "confidence": confidence,
                        "wordBboxes": [
                            {
                                "text": str(text),
                                "bbox": bbox,
                                "confidence": confidence,
                                "marks": RunMarks(),
                            }
                        ],
                    }
                )
        return {"pageNumber": page_number, "lines": lines}


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


def _poly_to_bbox(poly: Any) -> BBox:
    points = poly.tolist() if hasattr(poly, "tolist") else poly
    if points and isinstance(points[0], (int, float)):
        x0, y0, x1, y1 = map(float, points[:4])
        return BBox(x=x0, y=y0, width=max(0, x1 - x0), height=max(0, y1 - y0))
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return BBox(x=min(xs), y=min(ys), width=max(xs) - min(xs), height=max(ys) - min(ys))


ocr_engine = PaddleOcrEngine()
