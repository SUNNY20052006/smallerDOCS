from __future__ import annotations

import re


def order_pages(layout_pages: list[dict]) -> list[dict]:
    repeated_texts = _find_repeated_header_footer_texts(layout_pages)
    ordered_pages: list[dict] = []
    for page in layout_pages:
        regions = page["regions"]
        suppressed = []
        body = []
        page_height = _page_height(page)
        for region in regions:
            text = _region_text(region)
            in_margin = region["bbox"].y < page_height * 0.08 or region["bbox"].y > page_height * 0.92
            if (
                region["coarseType"] in {"header", "footer"}
                or (in_margin and _is_page_number(text))
                or (in_margin and _normalize_text(text) in repeated_texts)
            ):
                suppressed.append(region["id"])
            else:
                body.append(region)
        ordered = sorted(body, key=lambda region: (region["bbox"].y, region["bbox"].x))
        ordered_pages.append(
            {
                "pageNumber": page["pageNumber"],
                "orderedRegionIds": [region["id"] for region in ordered],
                "suppressedRegionIds": suppressed,
            }
        )
    return ordered_pages


def _find_repeated_header_footer_texts(layout_pages: list[dict]) -> set[str]:
    if len(layout_pages) < 2:
        return set()
    counts: dict[str, int] = {}
    total = max(1, len(layout_pages))
    for page in layout_pages:
        height = _page_height(page)
        seen: set[str] = set()
        for region in page["regions"]:
            y = region["bbox"].y
            if region["coarseType"] in {"header", "footer"} or ((y < height * 0.08 or y > height * 0.92) and not _is_page_number(_region_text(region))):
                text = _normalize_text(_region_text(region))
                if text:
                    seen.add(text)
        for text in seen:
            counts[text] = counts.get(text, 0) + 1
    return {text for text, count in counts.items() if count / total >= 0.6}


def _page_height(page: dict) -> float:
    height = page.get("height")
    if height:
        return float(height)
    return max((region["bbox"].y + region["bbox"].height for region in page.get("regions", [])), default=1.0)


def _region_text(region: dict) -> str:
    return " ".join(line["text"] for line in region.get("containedLines", []))


def _normalize_text(text: str) -> str:
    return re.sub(r"\b\d+\b", "{n}", " ".join(text.lower().split()))


def _is_page_number(text: str) -> bool:
    normalized = " ".join(text.strip().lower().split())
    return bool(re.fullmatch(r"\d{1,4}", normalized) or re.fullmatch(r"page\s+\d{1,4}(?:\s+of\s+\d{1,4})?", normalized))
