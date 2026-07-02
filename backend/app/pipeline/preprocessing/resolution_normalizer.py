from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .binarize import binarize_image
from .border_removal import remove_borders
from .denoise import denoise_image
from .deskew import deskew_image


@dataclass(frozen=True)
class PreprocessedPage:
    page_number: int
    image_path: Path
    width: int
    height: int
    rotation_applied: int


def preprocess_document(source_path: Path, source_type: str, output_dir: Path) -> list[PreprocessedPage]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_pages = _render_pdf(source_path) if source_type == "pdf" else [_load_image(source_path)]
    pages: list[PreprocessedPage] = []
    for page_number, image in enumerate(raw_pages, start=1):
        processed, rotation = _preprocess_image(image)
        height, width = processed.shape[:2]
        if height == 0 or width == 0:
            raise ValueError(f"page {page_number} rendered blank after preprocessing")
        out_path = output_dir / f"page_{page_number}.png"
        cv2.imwrite(str(out_path), processed)
        pages.append(PreprocessedPage(page_number, out_path, width, height, rotation))
    return pages


def _render_pdf(source_path: Path) -> list[np.ndarray]:
    import fitz

    images: list[np.ndarray] = []
    with fitz.open(source_path) as doc:
        matrix = fitz.Matrix(300 / 72, 300 / 72)
        for page in doc:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
            images.append(cv2.cvtColor(array, cv2.COLOR_RGB2BGR))
    return images


def _load_image(source_path: Path) -> np.ndarray:
    with Image.open(source_path) as image:
        image = image.convert("RGB")
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _preprocess_image(image: np.ndarray) -> tuple[np.ndarray, int]:
    denoised = denoise_image(image)
    deskewed, _ = deskew_image(denoised)
    cropped = remove_borders(deskewed)
    binarized = binarize_image(cropped)
    return binarized, 0
