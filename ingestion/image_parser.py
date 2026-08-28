import hashlib
import logging
import ssl
from pathlib import Path
from typing import Optional, List, Dict, Any

import cv2
import numpy as np

from ingestion.base_parser import BaseParser
from ingestion.models import IngestedResource, ContentChunk
from config import settings

# macOS SSL fix: set BEFORE importing easyocr to prevent SSL errors
# when EasyOCR downloads its model files on first run.
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


class ImageParser(BaseParser):
    """
    Parses image files (.png, .jpg, .jpeg, .webp) using EasyOCR.

    IMPORTANT — Why cv2.imread() and not PIL:
        EasyOCR's internal reformat_input() treats numpy arrays as BGR (OpenCV format).
        PIL produces RGB arrays. Passing an RGB array to EasyOCR feeds reversed color
        channels to CRAFT, which destroys detection accuracy.
        cv2.imread() produces BGR natively — this is the correct format.

    IMPORTANT — Why resize before passing to EasyOCR:
        EasyOCR passes images to CRAFT scaled to canvas_size=2560 by default.
        A 3072×4096 source image is still ~1920×2560 after this — too large for
        reliable CRAFT detection. Pre-resizing to 1200px puts the image in CRAFT's
        reliable detection range.

    Bounding box format:
        Stored as compact [x1, y1, x2, y2] in original image pixel coordinates.
        EasyOCR returns 4-point polygons in preprocessed-image coordinates;
        this class converts them to axis-aligned rectangles in original-image space.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(
        self,
        languages: Optional[List[str]] = None,
        gpu: bool = settings.ocr_gpu,
        min_confidence: float = settings.ocr_min_confidence,
        target_width: int = settings.ocr_target_width,
        clahe_clip_limit: float = settings.ocr_clahe_clip_limit,
    ):
        self.languages = languages or settings.ocr_languages
        self.gpu = gpu
        self.min_confidence = min_confidence
        self.target_width = target_width
        self.clahe_clip_limit = clahe_clip_limit
        self._reader: Optional["easyocr.Reader"] = None

    def _get_reader(self) -> "easyocr.Reader":
        if not EASYOCR_AVAILABLE:
            raise RuntimeError(
                "easyocr is not installed. Run: pip install easyocr"
            )
        if self._reader is None:
            logging.info(
                f"Initializing EasyOCR Reader "
                f"(languages={self.languages}, gpu={self.gpu})"
            )
            self._reader = easyocr.Reader(self.languages, gpu=self.gpu)
        return self._reader

    def _preprocess(self, filepath: Path) -> tuple:
        """
        Load and preprocess image as a BGR numpy array for EasyOCR.

        Returns:
            (img_bgr: np.ndarray with shape (H, W, 3) dtype uint8, scale: float)
        """
        img = cv2.imread(str(filepath))
        if img is None:
            raise ValueError(
                f"cv2.imread could not read image (corrupt or unsupported): {filepath}"
            )

        orig_h, orig_w = img.shape[:2]
        scale = 1.0

        if orig_w > self.target_width:
            ratio = self.target_width / orig_w
            new_w = self.target_width
            new_h = int(orig_h * ratio)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            scale = orig_w / new_w
            logging.debug(
                f"Resized {filepath.name}: {orig_w}×{orig_h} → {new_w}×{new_h}"
            )

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=self.clahe_clip_limit, tileGridSize=(8, 8))
        l_chan = clahe.apply(l_chan)
        lab = cv2.merge([l_chan, a_chan, b_chan])
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return img, scale

    def can_handle(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def parse(
        self,
        filepath: Path,
        resource_id: str,
        subject_id: str,
    ) -> Optional[IngestedResource]:
        if not filepath.exists():
            logging.error(f"Image file not found: {filepath}")
            return None

        try:
            img_bgr, scale = self._preprocess(filepath)

            reader = self._get_reader()
            logging.info(f"Running EasyOCR on: {filepath.name}")
            raw_results = reader.readtext(img_bgr)

            ocr_regions: List[Dict[str, Any]] = []
            text_lines: List[str] = []

            for bbox_pts, text, confidence in raw_results:
                clean_text = str(text).strip()
                conf = float(confidence)

                if not clean_text or conf < self.min_confidence:
                    continue

                xs = [pt[0] for pt in bbox_pts]
                ys = [pt[1] for pt in bbox_pts]
                bbox = [
                    int(min(xs) * scale),
                    int(min(ys) * scale),
                    int(max(xs) * scale),
                    int(max(ys) * scale),
                ]

                ocr_regions.append({
                    "text": clean_text,
                    "confidence": round(conf, 3),
                    "bbox": bbox,
                })
                text_lines.append(clean_text)

            combined_text = "\n".join(text_lines).strip()

            if not ocr_regions:
                logging.warning(
                    f"No readable text found in {filepath.name} "
                    f"(0 regions above confidence={self.min_confidence})"
                )
            else:
                logging.info(
                    f"EasyOCR: {len(ocr_regions)} region(s) detected in {filepath.name}"
                )

            chunk = ContentChunk(
                chunk_id=f"{resource_id}_image_1",
                source_type="image",
                location_type="image",
                location_number=1,
                text=combined_text,
                content_hash=hashlib.sha256(combined_text.encode("utf-8")).hexdigest(),
                ocr_regions=ocr_regions if ocr_regions else None,
            )

            return IngestedResource(
                resource_id=resource_id,
                resource_type="image",
                filename=filepath.name,
                subject_id=subject_id,
                content=[chunk],
            )

        except Exception as e:
            logging.error(f"Error parsing image {filepath.name}: {e}")
            return None
