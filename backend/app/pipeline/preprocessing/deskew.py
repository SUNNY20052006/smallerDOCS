from __future__ import annotations

import cv2
import numpy as np


def deskew_image(image: np.ndarray) -> tuple[np.ndarray, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return image, 0.0
    angles = []
    for rho_theta in lines[:50]:
        theta = rho_theta[0][1]
        angle = (theta * 180 / np.pi) - 90
        if -15 <= angle <= 15:
            angles.append(angle)
    if not angles:
        return image, 0.0
    angle = float(np.median(angles))
    if abs(angle) <= 0.3:
        return image, 0.0
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return rotated, angle
