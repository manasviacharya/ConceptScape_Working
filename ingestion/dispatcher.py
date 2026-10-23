import hashlib
import json
import logging
import os
from pathlib import Path
from typing import List, Tuple
from dataclasses import asdict
from datetime import datetime

from ingestion.base_parser import BaseParser
from ingestion.ocr_engine import PaddleOCREngine
from ingestion.pdf_parser import PDFParser
from ingestion.ppt_parser import PPTParser
from ingestion.youtube_parser import YouTubeParser
from ingestion.image_parser import ImageParser
from ingestion.models import IngestionResult, IngestedResource, ContentChunk
from config import settings


def _compute_file_hash(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _load_previous_ingestion_cache() -> dict:
    cache_path = os.path.join(settings.output_dir, "ingestion_result.json")
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        lookup = {}
        for resource in data.get("resources", []):
            filename = resource.get("filename")
            content_hash = resource.get("content_hash")
            if filename and content_hash:
                lookup[filename] = resource
        return lookup
    except Exception:
        logging.warning("Could not load previous ingestion_result.json for caching — treating as full cache miss")
        return {}


def _reconstruct_resource(resource_dict: dict) -> IngestedResource:
    chunks = []
    for c in resource_dict.get("content", []):
        chunks.append(ContentChunk(
            chunk_id=c.get("chunk_id", c.get("content_id", "")),
            source_type=c.get("source_type", ""),
            location_type=c.get("location_type", ""),
            location_number=c.get("location_number", 0),
            text=c.get("text", ""),
            content_hash=c.get("content_hash", ""),
            extraction_method=c.get("extraction_method", ""),
            ocr_regions=c.get("ocr_regions"),
        ))
    return IngestedResource(
        resource_id=resource_dict.get("resource_id", ""),
        resource_type=resource_dict.get("resource_type", ""),
        filename=resource_dict.get("filename", ""),
        subject_id=resource_dict.get("subject_id", ""),
        content=chunks,
        content_hash=resource_dict.get("content_hash", ""),
    )


class IngestionDispatcher:
    def __init__(self):
        ocr_engine = PaddleOCREngine()
        self.parsers: List[BaseParser] = [
            PDFParser(ocr_engine=ocr_engine),
            PPTParser(),
            ImageParser(ocr_engine=ocr_engine),
            YouTubeParser(),
        ]

    def _generate_resource_id(self, filepath: Path) -> str:
        ext = filepath.suffix.lower()
        prefix = ("pdf" if ext == ".pdf"
                  else "ppt" if ext in (".ppt", ".pptx")
                  else "youtube" if ext in YouTubeParser.SUPPORTED_EXTENSIONS
                  else "image" if ext in ImageParser.SUPPORTED_EXTENSIONS
                  else "unknown")
        digest = hashlib.sha256(filepath.name.encode("utf-8")).hexdigest()[:8]
        return f"{prefix}_{digest}"

    def run(self, documents_dir: str, subject_id: str) -> Tuple[IngestionResult, List[Tuple[str, str]]]:
        doc_dir = Path(documents_dir)
        if not doc_dir.exists() or not doc_dir.is_dir():
            logging.error(f"Documents directory not found: {documents_dir}")
            return IngestionResult(subject_id=subject_id, resources=[], ingestion_timestamp=datetime.now().isoformat()), []

        files = [f for f in doc_dir.iterdir() if f.is_file()]
        supported_files = []

        for f in files:
            if any(parser.can_handle(f) for parser in self.parsers):
                supported_files.append(f)
            else:
                logging.warning(f"Unsupported file type: {f.name}")

        logging.info(f"Found {len(supported_files)} supported file(s)")

        previous_cache = _load_previous_ingestion_cache()
        ingested_resources = []
        failed_files: List[Tuple[str, str]] = []

        for filepath in supported_files:
            file_hash = _compute_file_hash(filepath)

            cached = previous_cache.get(filepath.name)
            if cached and cached.get("content_hash") == file_hash:
                logging.info(f"CACHE HIT (unchanged): {filepath.name}")
                ingested_resources.append(_reconstruct_resource(cached))
                continue

            logging.info(f"CACHE MISS (parsing): {filepath.name}")

            handled = False
            for parser in self.parsers:
                if parser.can_handle(filepath):
                    handled = True
                    resource_id = self._generate_resource_id(filepath)
                    logging.info(f"Processing {filepath.suffix[1:].upper()}: {filepath.name}")

                    resource = parser.parse(filepath, resource_id, subject_id)
                    if resource:
                        resource.content_hash = file_hash
                        logging.info(f"  -> Extracted {len(resource.content)} {resource.content[0].location_type if resource.content else 'items'}s")
                        logging.info(f"  -> Resource ID: {resource.resource_id}")
                        ingested_resources.append(resource)
                    else:
                        failed_files.append((filepath.name, "parser returned no result"))
                    break

            if not handled:
                reason = "no parser available despite earlier check"
                logging.warning(f"{reason}: {filepath.name}")
                failed_files.append((filepath.name, reason))

        if failed_files:
            for fname, reason in failed_files:
                logging.error(f"FAILED: {fname} — {reason}")

        return IngestionResult(
            subject_id=subject_id,
            resources=ingested_resources,
            ingestion_timestamp=datetime.now().isoformat()
        ), failed_files
