import logging
from typing import Optional, List, Dict, Any, Tuple

import cv2
import numpy as np

from config import settings

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False


class PaddleOCREngine:
    """
    Shared PaddleOCR engine used by both ImageParser and PDFParser.

    Owns the lazily-initialised PaddleOCR instance — init downloads models
    on first run and is slow, so it must happen at most once per process.
    The dispatcher constructs ONE engine instance and injects it into both
    parsers.

    Preprocessing:
        Large images (phone photos at 3072x4096+) are resized to
        ocr_target_width before OCR to keep memory usage reasonable.
        PaddleOCR's DB text detector handles contrast normalisation
        internally, so no manual CLAHE is needed.

    Bounding box format:
        Stored as compact [x1, y1, x2, y2] in original image pixel
        coordinates. PaddleOCR returns 4-point polygons in
        preprocessed-image coordinates; run() converts them to
        axis-aligned rectangles in original-image space.
    """

    def __init__(self):
        self.language = settings.ocr_language
        self.use_angle_cls = settings.ocr_use_angle_cls
        self.use_gpu = settings.ocr_use_gpu
        self.min_confidence = settings.ocr_min_confidence
        self.target_width = settings.ocr_target_width
        self._ocr: Optional["PaddleOCR"] = None

    def _get_ocr(self) -> "PaddleOCR":
        """Lazily initialise the PaddleOCR instance (shared across all callers in a run)."""
        if not PADDLEOCR_AVAILABLE:
            raise RuntimeError("paddleocr is not installed. Run: pip install paddleocr paddlepaddle")
        if self._ocr is None:
            logging.info(
                f"Initializing PaddleOCR "
                f"(lang={self.language}, use_angle_cls={self.use_angle_cls}, use_gpu={self.use_gpu})"
            )
            self._ocr = PaddleOCR(
                use_angle_cls=self.use_angle_cls,
                lang=self.language,
                use_gpu=self.use_gpu,
                show_log=False,
            )
        return self._ocr

    def _resize_if_needed(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Resize image if wider than target_width to avoid memory issues
        with very large images (phone photos etc.).

        Returns:
            (resized_img, scale) where scale maps resized coords back to
            original coords. scale=1.0 if no resize was needed.
        """
        orig_h, orig_w = img.shape[:2]
        if orig_w <= self.target_width:
            return img, 1.0

        ratio = self.target_width / orig_w
        new_w = self.target_width
        new_h = int(orig_h * ratio)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        scale = orig_w / new_w
        return resized, scale

    def run(self, img: np.ndarray) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Run PaddleOCR on an image, filter by confidence, and return results.

        Args:
            img: numpy array (BGR or RGB — PaddleOCR handles both).

        Returns:
            (combined_text, regions) where:
                combined_text: all kept lines joined by newlines.
                regions: list of {text, confidence, bbox: [x1, y1, x2, y2]}
                         in original image pixel coordinates.
        """
        resized, scale = self._resize_if_needed(img)
        ocr = self._get_ocr()
        result = ocr.ocr(resized, cls=self.use_angle_cls)

        regions: List[Dict[str, Any]] = []
        text_lines: List[str] = []

        if not result or not result[0]:
            return "", []

        for line in result[0]:
            bbox_pts, (text, conf) = line
            clean_text = str(text).strip()
            conf = float(conf)

            if not clean_text or conf < self.min_confidence:
                continue

            # PaddleOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
            # Convert to compact [x1, y1, x2, y2] in original image coords
            xs = [pt[0] for pt in bbox_pts]
            ys = [pt[1] for pt in bbox_pts]
            bbox = [
                int(min(xs) * scale),
                int(min(ys) * scale),
                int(max(xs) * scale),
                int(max(ys) * scale),
            ]

            regions.append({
                "text": clean_text,
                "confidence": round(conf, 3),
                "bbox": bbox,
            })
            text_lines.append(clean_text)

        combined_text = "\n".join(text_lines).strip()
        return combined_text, regions
