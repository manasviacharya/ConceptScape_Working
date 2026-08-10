import logging
from pathlib import Path
from typing import List
from datetime import datetime

from ingestion.base_parser import BaseParser
from ingestion.pdf_parser import PDFParser
from ingestion.ppt_parser import PPTParser
from ingestion.models import IngestionResult, IngestedResource

class IngestionDispatcher:
    def __init__(self):
        self.parsers: List[BaseParser] = [
            PDFParser(),
            PPTParser()
            # Register future parsers here
        ]
        self.pdf_count = 0
        self.ppt_count = 0

    def _generate_resource_id(self, filepath: Path) -> str:
        ext = filepath.suffix.lower()
        if ext == ".pdf":
            self.pdf_count += 1
            return f"pdf_{self.pdf_count:03d}"
        elif ext in [".ppt", ".pptx"]:
            self.ppt_count += 1
            return f"ppt_{self.ppt_count:03d}"
        return "unknown_000"

    def run(self, documents_dir: str, subject_id: str) -> IngestionResult:
        doc_dir = Path(documents_dir)
        if not doc_dir.exists() or not doc_dir.is_dir():
            logging.error(f"Documents directory not found: {documents_dir}")
            return IngestionResult(subject_id=subject_id, resources=[], ingestion_timestamp=datetime.now().isoformat())

        files = [f for f in doc_dir.iterdir() if f.is_file()]
        supported_files = []
        
        for f in files:
            if any(parser.can_handle(f) for parser in self.parsers):
                supported_files.append(f)
            else:
                logging.warning(f"Unsupported file type: {f.name}")
                
        logging.info(f"Found {len(supported_files)} supported file(s)")
        
        ingested_resources = []
        
        for filepath in supported_files:
            handled = False
            for parser in self.parsers:
                if parser.can_handle(filepath):
                    handled = True
                    resource_id = self._generate_resource_id(filepath)
                    logging.info(f"Processing {filepath.suffix[1:].upper()}: {filepath.name}")
                    
                    resource = parser.parse(filepath, resource_id, subject_id)
                    if resource:
                        logging.info(f"  -> Extracted {len(resource.content)} {resource.content[0].location_type if resource.content else 'items'}s")
                        logging.info(f"  -> Resource ID: {resource.resource_id}")
                        ingested_resources.append(resource)
                    break
            
            if not handled:
                logging.warning(f"No parser available for {filepath.name} despite earlier check.")
                
        return IngestionResult(
            subject_id=subject_id,
            resources=ingested_resources,
            ingestion_timestamp=datetime.now().isoformat()
        )
