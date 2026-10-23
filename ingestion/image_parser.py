import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import cv2

from ingestion.base_parser import BaseParser
from ingestion.models import IngestedResource, ContentChunk
from ingestion.ocr_engine import PaddleOCREngine


class ImageParser(BaseParser):
    """Parses image files (.png, .jpg, .jpeg, .webp) using a shared PaddleOCREngine."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self, ocr_engine: Optional[PaddleOCREngine] = None):
        self.ocr_engine = ocr_engine or PaddleOCREngine()

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

        Returns:
            IngestedResource with one ContentChunk, or None on error.
        """
        if not filepath.exists():
            logging.error(f"Image file not found: {filepath}")
            return None

        try:
            img = cv2.imread(str(filepath))
            if img is None:
                raise ValueError(f"cv2.imread could not read image: {filepath}")

            logging.info(f"Running PaddleOCR on: {filepath.name}")
            combined_text, ocr_regions = self.ocr_engine.run(img)

            if not ocr_regions:
                logging.warning(
                    f"No readable text found in {filepath.name} "
                    f"(0 regions above confidence={self.ocr_engine.min_confidence})"
                )
            else:
                logging.info(f"PaddleOCR: {len(ocr_regions)} region(s) detected in {filepath.name}")

            chunk = ContentChunk(
                chunk_id=f"{resource_id}_image_1",
                source_type="image",
                location_type="image",
                location_number=1,
                text=combined_text,
                content_hash=hashlib.sha256(combined_text.encode("utf-8")).hexdigest(),
                extraction_method="paddleocr",
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
