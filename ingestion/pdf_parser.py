import hashlib
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import fitz  # PyMuPDF

from ingestion.base_parser import BaseParser
from ingestion.models import IngestedResource, ContentChunk
from ingestion.ocr_engine import PaddleOCREngine
from config import settings


class PDFParser(BaseParser):
    def __init__(self, ocr_engine: Optional[PaddleOCREngine] = None):
        self.ocr_engine = ocr_engine or PaddleOCREngine()

    def can_handle(self, filepath: Path) -> bool:
        return filepath.suffix.lower() == ".pdf"

    def parse(self, filepath: Path, resource_id: str, subject_id: str) -> Optional[IngestedResource]:
        try:
            with fitz.open(filepath) as doc:
                total_pages = len(doc)
                chunks = []
                for page_num, page in enumerate(doc, start=1):
                    native_text = page.get_text("text").strip()
                    native_len = len(native_text)

                    if native_len >= settings.pdf_native_text_min_chars:
                        logging.info(f"Page {page_num}/{total_pages}: native text ({native_len} chars)")
                        chunk = ContentChunk(
                            chunk_id=f"{resource_id}_page_{page_num}",
                            source_type="pdf",
                            location_type="page",
                            location_number=page_num,
                            text=native_text,
                            content_hash=hashlib.sha256(native_text.encode("utf-8")).hexdigest(),
                            extraction_method="native_text",
                        )
                        chunks.append(chunk)
                        continue

                    if not settings.enable_pdf_ocr_fallback:
                        if not native_text:
                            logging.warning(f"Page {page_num}/{total_pages}: empty text (OCR fallback disabled)")
                        chunk = ContentChunk(
                            chunk_id=f"{resource_id}_page_{page_num}",
                            source_type="pdf",
                            location_type="page",
                            location_number=page_num,
                            text=native_text,
                            content_hash=hashlib.sha256(native_text.encode("utf-8")).hexdigest(),
                            extraction_method="native_text",
                        )
                        chunks.append(chunk)
                        continue

                    logging.info(
                        f"Page {page_num}/{total_pages}: no reliable native text "
                        f"({native_len} chars) — rendering at {settings.pdf_ocr_render_dpi}dpi for OCR"
                    )

                    pix = page.get_pixmap(dpi=settings.pdf_ocr_render_dpi)
                    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

                    if pix.n == 4:
                        arr = arr[:, :, :3]
                    arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

                    combined_text, ocr_regions = self.ocr_engine.run(arr)

                    if ocr_regions:
                        logging.info(f"Page {page_num}/{total_pages}: PaddleOCR found {len(ocr_regions)} region(s)")
                    else:
                        logging.warning(f"Page {page_num}/{total_pages}: OCR attempted but found no text")

                    chunk = ContentChunk(
                        chunk_id=f"{resource_id}_page_{page_num}",
                        source_type="pdf",
                        location_type="page",
                        location_number=page_num,
                        text=combined_text,
                        content_hash=hashlib.sha256(combined_text.encode("utf-8")).hexdigest(),
                        extraction_method="paddleocr",
                        ocr_regions=ocr_regions if ocr_regions else None,
                    )
                    chunks.append(chunk)

                return IngestedResource(
                    resource_id=resource_id,
                    resource_type="pdf",
                    filename=filepath.name,
                    subject_id=subject_id,
                    content=chunks
                )

        except (fitz.FileDataError, fitz.FileNotFoundError) as e:
            logging.error(f"Error opening or reading PDF {filepath.name}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error parsing PDF {filepath.name}: {e}")
            return None
