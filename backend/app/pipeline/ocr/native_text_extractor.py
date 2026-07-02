from __future__ import annotations

from pathlib import Path

from app.models.idm import BBox, RunMarks


def extract_native_page(source_path: Path, page_number: int) -> dict:
    import fitz

    scale = 300 / 72
    lines: list[dict] = []
    with fitz.open(source_path) as doc:
        page = doc[page_number - 1]
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(span.get("text", "") for span in spans)
                if not text.strip():
                    continue
                x0, y0, x1, y1 = line.get("bbox")
                word_bboxes = []
                for span in spans:
                    sx0, sy0, sx1, sy1 = span.get("bbox")
                    flags = int(span.get("flags", 0))
                    word_bboxes.append(
                        {
                            "text": span.get("text", ""),
                            "bbox": BBox(x=sx0 * scale, y=sy0 * scale, width=(sx1 - sx0) * scale, height=(sy1 - sy0) * scale),
                            "confidence": 1.0,
                            "marks": RunMarks(
                                bold="bold" in span.get("font", "").lower(),
                                italic=bool(flags & 2) or "italic" in span.get("font", "").lower(),
                                underline=False,
                            ),
                        }
                    )
                lines.append(
                    {
                        "text": text,
                        "bbox": BBox(x=x0 * scale, y=y0 * scale, width=(x1 - x0) * scale, height=(y1 - y0) * scale),
                        "confidence": 1.0,
                        "wordBboxes": word_bboxes,
                    }
                )
    return {"pageNumber": page_number, "lines": lines}
