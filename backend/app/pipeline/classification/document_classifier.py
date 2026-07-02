from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.config import settings

PageSource = Literal["native", "scanned"]


@dataclass(frozen=True)
class ClassifiedPage:
    page_number: int
    source: PageSource


@dataclass(frozen=True)
class ClassificationResult:
    pages: list[ClassifiedPage]
    detected_document_type: str


KEYWORDS = {
    "lease": {"LEASE", "LESSOR", "LESSEE", "LANDLORD", "TENANT"},
    "affidavit": {"AFFIDAVIT", "SWORN", "DEPONENT", "NOTARY"},
    "court_filing": {"IN THE COURT OF", "PLAINTIFF", "DEFENDANT", "CASE NO"},
    "contract": {"AGREEMENT", "WHEREAS", "PARTY OF THE FIRST PART", "TERMS AND CONDITIONS"},
    "notice": {"NOTICE", "HEREBY GIVEN", "DEMAND"},
    "form": {"CHECKBOX", "OPTION", "INITIALS"},
}


def classify_document(source_path: Path, source_type: str) -> ClassificationResult:
    if source_type == "image":
        return ClassificationResult([ClassifiedPage(1, "scanned")], "unknown")

    import fitz

    pages: list[ClassifiedPage] = []
    first_page_text = ""
    with fitz.open(source_path) as doc:
        for index, page in enumerate(doc, start=1):
            words = page.get_text("words") or []
            if index == 1:
                first_page_text = page.get_text("text") or ""
            area = float(page.rect.width * page.rect.height) or 1.0
            covered = sum(max(0.0, (w[2] - w[0]) * (w[3] - w[1])) for w in words) / area
            source = "native" if len(words) > settings.native_pdf_min_words and covered > 0.05 else "scanned"
            pages.append(ClassifiedPage(index, source))
    return ClassificationResult(pages, _detect_type(first_page_text))


def _detect_type(text: str) -> str:
    normalized = " ".join(text.upper().split())
    scores = {
        document_type: sum(1 for keyword in keywords if keyword in normalized)
        for document_type, keywords in KEYWORDS.items()
    }
    best_type, best_score = max(scores.items(), key=lambda item: item[1], default=("unknown", 0))
    return best_type if best_score > 0 else "unknown"
