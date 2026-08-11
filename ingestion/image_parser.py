import logging
import ssl
from pathlib import Path
from typing import Optional, List, Dict, Any

import cv2
import numpy as np

from ingestion.base_parser import BaseParser
from ingestion.models import IngestedResource, ContentChunk

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


# ── Constants ─────────────────────────────────────────────────────────────────

# Resize images to this width (px) before passing to EasyOCR.
# EasyOCR's CRAFT detection network works best in the 1000–1400px range.
# Phone photos (3072×4096+) MUST be resized down or CRAFT produces garbled output.
OCR_TARGET_WIDTH = 1200

# CLAHE clip limit for contrast enhancement (applied on L channel in LAB space).
# Normalises uneven lighting in phone photos of diagrams.
CLAHE_CLIP_LIMIT = 2.0

# Minimum EasyOCR confidence to keep a detected text region.
# 0.3 filters noise (random marks, artifacts) while retaining all real text.
OCR_MIN_CONFIDENCE = 0.3


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
        gpu: bool = False,
        min_confidence: float = OCR_MIN_CONFIDENCE,
        target_width: int = OCR_TARGET_WIDTH,
        clahe_clip_limit: float = CLAHE_CLIP_LIMIT,
    ):
        """
        Args:
            languages: EasyOCR language codes. Default ['en'].
            gpu: Whether EasyOCR uses GPU. Default False.
            min_confidence: Confidence threshold to keep OCR regions. Default 0.3.
            target_width: Resize images to this width (px) before OCR. Default 1200.
            clahe_clip_limit: CLAHE clip limit for contrast normalisation. Default 2.0.
        """
        self.languages = languages or ["en"]
        self.gpu = gpu
        self.min_confidence = min_confidence
        self.target_width = target_width
        self.clahe_clip_limit = clahe_clip_limit
        self._reader: Optional["easyocr.Reader"] = None

    def _get_reader(self) -> "easyocr.Reader":
        """Lazily initialise the EasyOCR reader (shared across all images in a run)."""
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

        Steps:
            1. cv2.imread() — loads as BGR uint8 (EasyOCR-native format)
            2. Resize to self.target_width using LANCZOS4 (only if wider)
            3. CLAHE on L channel of LAB space — normalises uneven lighting
            4. Return (bgr_array, scale_factor)
               scale_factor maps preprocessed-image coords → original-image coords

        Returns:
            (img_bgr: np.ndarray with shape (H, W, 3) dtype uint8, scale: float)

        Raises:
            ValueError if cv2.imread returns None (file unreadable or corrupt).
        """
        img = cv2.imread(str(filepath))  # BGR, uint8
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
            scale = orig_w / new_w  # ~= 1/ratio; maps new coords → original coords
            logging.debug(
                f"Resized {filepath.name}: {orig_w}×{orig_h} → {new_w}×{new_h}"
            )

        # Apply CLAHE on L channel in LAB colorspace for contrast normalisation
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
        """
        Parse an image file and return an IngestedResource with OCR content.

        The ContentChunk in the returned resource contains:
            text        — all detected text joined by newlines (fed to concept extractor)
            ocr_regions — list of {text, confidence, bbox: [x1, y1, x2, y2]} in
                          original image pixel coordinates.
                          None if no regions passed the confidence threshold.

        Returns:
            IngestedResource with one ContentChunk, or None on error.
        """
        if not filepath.exists():
            logging.error(f"Image file not found: {filepath}")
            return None

        try:
            # ── Step 1: Preprocess ────────────────────────────────────────────
            img_bgr, scale = self._preprocess(filepath)

            # ── Step 2: EasyOCR ───────────────────────────────────────────────
            reader = self._get_reader()
            logging.info(f"Running EasyOCR on: {filepath.name}")
            raw_results = reader.readtext(img_bgr)  # pass BGR numpy array directly

            # ── Step 3: Filter and convert results ────────────────────────────
            ocr_regions: List[Dict[str, Any]] = []
            text_lines: List[str] = []

            for bbox_pts, text, confidence in raw_results:
                clean_text = str(text).strip()
                conf = float(confidence)

                if not clean_text or conf < self.min_confidence:
                    continue

                # EasyOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] in preprocessed coords
                # Convert to compact [x1, y1, x2, y2] in original image coords
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
                    "bbox": bbox,  # [x1, y1, x2, y2] in original image pixels
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

            # ── Step 4: Build and return IngestedResource ─────────────────────
            chunk = ContentChunk(
                content_id=f"{resource_id}_image_1",
                location_type="image",
                location_number=1,
                text=combined_text,
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
