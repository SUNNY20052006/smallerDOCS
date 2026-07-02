from __future__ import annotations

import cv2
import numpy as np


def denoise_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
