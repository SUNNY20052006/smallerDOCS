from __future__ import annotations

from pathlib import Path

from app.core.job_manager import job_manager
from app.core.temp_storage import temp_storage
from app.models.idm import DocumentModel
from app.pipeline.classification.document_classifier import classify_document
from app.pipeline.layout.block_classifier import classify_blocks
from app.pipeline.layout.reading_order import order_pages
from app.pipeline.layout.structure_analysis import layout_engine
from app.pipeline.layout.table_detector import resolve_tables
from app.pipeline.ocr.native_text_extractor import extract_native_page
from app.pipeline.ocr.paddle_ocr_engine import ocr_engine
from app.pipeline.preprocessing.resolution_normalizer import preprocess_document
from app.pipeline.reconstruction.clause_numbering import apply_legal_rules
from app.pipeline.reconstruction.idm_builder import build_document_model


def run_pipeline(job_id: str) -> DocumentModel:
    record = job_manager.require(job_id)
    job_dir = temp_storage.job_dir(job_id)
    source_path = Path(record.source_path)

    job_manager.transition(job_id, "preprocessing", progress=0)
    classification = classify_document(source_path, record.file_type)
    preprocessed_pages = preprocess_document(source_path, record.file_type, job_dir / "preprocessed")
    total_pages = len(preprocessed_pages)
    job_manager.update_progress(job_id, progress=10, current_page=total_pages, total_pages=total_pages)

    job_manager.transition(job_id, "ocr", progress=10, current_page=1, total_pages=total_pages)
    ocr_pages = []
    source_by_page = {page.page_number: page.source for page in classification.pages}
    for index, page in enumerate(preprocessed_pages, start=1):
        if source_by_page.get(page.page_number) == "native" and record.file_type == "pdf":
            ocr_pages.append(extract_native_page(source_path, page.page_number))
        else:
            ocr_pages.append(ocr_engine.ocr_page(page.image_path, page.page_number))
        job_manager.update_progress(job_id, progress=10 + int(50 * index / total_pages), current_page=index, total_pages=total_pages)

    job_manager.transition(job_id, "layout_analysis", progress=60, current_page=1, total_pages=total_pages)
    layout_pages = []
    for index, (page, ocr_page) in enumerate(zip(preprocessed_pages, ocr_pages, strict=True), start=1):
        layout_pages.append(layout_engine.analyze_page(page.image_path, ocr_page))
        job_manager.update_progress(job_id, progress=60 + int(20 * index / total_pages), current_page=index, total_pages=total_pages)
    ordered_pages = order_pages(layout_pages)
    classified_pages = classify_blocks(layout_pages, ordered_pages, classification.detected_document_type)
    classified_pages = resolve_tables(classified_pages)

    job_manager.transition(job_id, "reconstruction", progress=80, current_page=None, total_pages=total_pages)
    document = build_document_model(
        document_id=job_id,
        source_type=record.file_type,
        source_file_name=record.file_name,
        preprocessed_pages=preprocessed_pages,
        classified_pages=classified_pages,
        detected_document_type=classification.detected_document_type,
    )
    document = apply_legal_rules(document, classification.detected_document_type)
    temp_storage.write_document(job_id, document)
    job_manager.transition(job_id, "completed", progress=100, current_page=None, total_pages=total_pages)
    return document
