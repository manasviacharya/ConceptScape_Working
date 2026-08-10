import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from ingestion.base_parser import BaseParser
from ingestion.models import IngestedResource, ContentChunk

class PDFParser(BaseParser):
    def can_handle(self, filepath: Path) -> bool:
        return filepath.suffix.lower() == ".pdf"

    def parse(self, filepath: Path, resource_id: str, subject_id: str) -> Optional[IngestedResource]:
        try:
            doc = fitz.open(filepath)
            chunks = []
            
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if not text:
                    logging.warning(f"Empty text found on page {page_num} of {filepath.name}")
                
                chunk = ContentChunk(
                    content_id=f"{resource_id}_page_{page_num}",
                    location_type="page",
                    location_number=page_num,
                    text=text
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
