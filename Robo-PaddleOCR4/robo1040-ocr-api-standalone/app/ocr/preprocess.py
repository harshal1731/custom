"""Image preprocessing for OCR accuracy improvement.

Applies grayscale conversion, adaptive thresholding (binarization),
morphological denoising, and contrast enhancement — but ONLY when
the image quality analysis indicates it would help.

Uses OpenCV (cv2) which is already bundled with PaddleOCR — no extra deps.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def _to_gray(arr: np.ndarray) -> np.ndarray:
    """Convert to grayscale if needed."""
    if len(arr.shape) == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return arr.copy()


def _image_stats(gray: np.ndarray) -> dict:
    """Compute image quality statistics for preprocessing decisions."""
    std = float(np.std(gray))
    mean = float(np.mean(gray))

    # Estimate noise: difference between original and slightly blurred
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    noise = float(np.std(gray.astype(float) - blurred.astype(float)))

    # Check if image is mostly white (document) or has heavy background
    white_frac = float(np.mean(gray > 200))  # fraction of near-white pixels
    dark_frac = float(np.mean(gray < 50))    # fraction of near-black pixels

    return {
        "std": std,
        "mean": mean,
        "noise": noise,
        "white_frac": white_frac,
        "dark_frac": dark_frac,
    }


def _needs_heavy_preprocessing(stats: dict) -> bool:
    """Decide if the image needs full binarization + denoising.

    Returns True for:
    - Low contrast scans (std < 50): faded or washed out text
    - High noise (noise > 15): grainy/speckled scans
    - Gray background (white_frac < 0.4): colored or dark backgrounds

    Returns False for:
    - Clean digital renders (high contrast, low noise, mostly white)
    - Already-clean scans that PaddleOCR handles well
    """
    if stats["std"] < 50:
        return True   # low contrast — needs enhancement
    if stats["noise"] > 15:
        return True   # noisy scan — needs denoising
    if stats["white_frac"] < 0.4:
        return True   # non-white background
    return False


def _needs_light_preprocessing(stats: dict) -> bool:
    """Decide if light preprocessing (just contrast) would help.

    For medium-quality images that don't need full binarization.
    """
    if stats["std"] < 70:
        return True
    if stats["noise"] > 8:
        return True
    return False


def preprocess_heavy(image: Image.Image) -> Image.Image:
    """Full preprocessing: grayscale → CLAHE → binarize → denoise.

    For genuinely poor quality scanned images.
    """
    arr = np.array(image)
    gray = _to_gray(arr)

    # CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Adaptive thresholding → clean binary
    binary = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )

    # Morphological denoising
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    return Image.fromarray(cleaned).convert("RGB")


def preprocess_light(image: Image.Image) -> Image.Image:
    """Light preprocessing: just CLAHE contrast + slight sharpening.

    For medium-quality images where binarization would be destructive.
    """
    arr = np.array(image)
    gray = _to_gray(arr)

    # CLAHE — gentle contrast boost
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Slight sharpen via unsharp mask
    blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.0)
    sharpened = cv2.addWeighted(enhanced, 1.3, blurred, -0.3, 0)

    return Image.fromarray(sharpened).convert("RGB")


def smart_preprocess(image: Image.Image) -> Image.Image:
    """Analyze image quality and apply appropriate preprocessing.

    - Clean images → pass through unchanged (no damage)
    - Medium quality → light contrast/sharpen only
    - Poor quality → full binarization + denoising
    """
    arr = np.array(image)
    gray = _to_gray(arr)
    stats = _image_stats(gray)

    if _needs_heavy_preprocessing(stats):
        logger.info(
            "Applying heavy preprocessing (std=%.1f, noise=%.1f, white=%.2f)",
            stats["std"], stats["noise"], stats["white_frac"],
        )
        return preprocess_heavy(image)

    if _needs_light_preprocessing(stats):
        logger.info(
            "Applying light preprocessing (std=%.1f, noise=%.1f)",
            stats["std"], stats["noise"],
        )
        return preprocess_light(image)

    # Clean image — don't touch it
    logger.debug("Image quality good (std=%.1f) — skipping preprocessing", stats["std"])
    return image
