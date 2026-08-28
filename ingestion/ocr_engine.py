import logging
import os
from typing import Optional, List, Dict, Any, Tuple

import cv2
import numpy as np

from config import settings

# Disable MKL-DNN before any paddle import to avoid OneDNN errors on Windows
os.environ.setdefault('FLAGS_use_mkldnn', '0')

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False


class PaddleOCREngine:

    def __init__(self):
        self.language = settings.ocr_language
        self.min_confidence = settings.ocr_min_confidence
        self.target_width = settings.ocr_target_width
        self._ocr: Optional["PaddleOCR"] = None

    def _get_ocr(self) -> "PaddleOCR":
        if not PADDLEOCR_AVAILABLE:
            raise RuntimeError("paddleocr is not installed. Run: pip install paddleocr paddlepaddle")
        if self._ocr is None:
            logging.info(f"Initializing PaddleOCR (lang={self.language}, engine=onnxruntime)")
            self._ocr = PaddleOCR(
                lang=self.language,
                enable_mkldnn=False,
                engine="onnxruntime",
            )
        return self._ocr

    def _resize_if_needed(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
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
        resized, scale = self._resize_if_needed(img)
        ocr = self._get_ocr()

        results = list(ocr.predict(resized))

        if not results:
            return "", []

        r = results[0]
        texts = r.get("rec_texts", [])
        scores = r.get("rec_scores", [])
        polys = r.get("dt_polys", [])

        regions: List[Dict[str, Any]] = []
        text_lines: List[str] = []

        for i, text in enumerate(texts):
            clean_text = str(text).strip()
            conf = float(scores[i]) if i < len(scores) else 0.0

            if not clean_text or conf < self.min_confidence:
                continue

            bbox = [0, 0, 0, 0]
            if i < len(polys):
                poly = np.array(polys[i])
                xs = poly[:, 0]
                ys = poly[:, 1]
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
