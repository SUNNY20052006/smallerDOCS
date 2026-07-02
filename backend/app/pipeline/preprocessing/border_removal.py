from __future__ import annotations

import cv2
import numpy as np


def remove_borders(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    _, threshold = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image
    largest = max(contours, key=cv2.contourArea)
    x, y, width, height = cv2.boundingRect(largest)
    image_area = image.shape[0] * image.shape[1]
    if width * height < image_area * 0.25:
        return image
    pad = 6
    x = max(0, x - pad)
    y = max(0, y - pad)
    width = min(image.shape[1] - x, width + pad * 2)
    height = min(image.shape[0] - y, height + pad * 2)
    return image[y : y + height, x : x + width]
