import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from config import settings
from ingestion.base_parser import BaseParser
from ingestion.models import ContentChunk, IngestedResource

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YT_AVAILABLE = True
except ImportError:
    YT_AVAILABLE = False


# Accepts the forms people actually paste: watch links, short links, embeds,
# and a bare 11-character id.
_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?(?:.*&)?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/(?:embed|v|shorts)/)([A-Za-z0-9_-]{11})"),
    re.compile(r"^([A-Za-z0-9_-]{11})$"),
]


def extract_video_id(text: str) -> Optional[str]:
    text = (text or "").strip()
    for pattern in _ID_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1)
    return None


def _timestamp(seconds: float) -> str:
    total = int(seconds)
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class YouTubeParser(BaseParser):
    """
    Ingests a YouTube transcript from a `.yt` file containing the video URL.

    A URL is not a file, but the dispatcher scans a folder and routes by
    extension — so the URL lives in a small file and this parser slots in beside
    the PDF, PPTX and image parsers with no changes to dispatch, caching or
    provenance.

    Provenance uses `location_type="timestamp"` with the segment's start time in
    seconds. Everything downstream is location-agnostic, so a citation becomes
    "video at 4:32" rather than "slide 3" without touching extraction,
    relationships or the RAG pipeline.
    """

    SUPPORTED_EXTENSIONS = {".yt", ".youtube"}

    def can_handle(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def _fetch(self, video_id: str) -> Tuple[List[dict], str, bool]:
        """
        Returns (snippets, language_code, was_translated).

        Manual captions are preferred over auto-generated ones: they carry
        punctuation and capitalisation, which the sentence splitter needs and
        which makes the verbatim evidence spans far more usable. Translation is
        a last resort — machine-translating an auto-caption compounds two lossy
        steps, and the resulting evidence quotes what a translator produced
        rather than what the speaker said.
        """
        api = YouTubeTranscriptApi()
        listing = api.list(video_id)

        tracks = list(listing)
        manual_en = [t for t in tracks if not t.is_generated and t.language_code.startswith("en")]
        auto_en = [t for t in tracks if t.is_generated and t.language_code.startswith("en")]

        for track, label in ((manual_en, "manual"), (auto_en, "auto")):
            if track:
                chosen = track[0]
                logging.info(f"  transcript: {chosen.language_code} ({label})")
                return [vars(s) for s in chosen.fetch()], chosen.language_code, False

        translatable = [t for t in tracks if t.is_translatable]
        if translatable:
            src = translatable[0]
            logging.warning(
                f"  no English transcript — translating from {src.language_code}. "
                f"Evidence spans will quote a machine translation, not the speaker."
            )
            return [vars(s) for s in src.translate("en").fetch()], f"{src.language_code}->en", True

        available = ", ".join(t.language_code for t in tracks) or "none"
        raise RuntimeError(
            f"No English transcript and none translatable (available: {available})"
        )

    def _segment(self, snippets: List[dict]) -> List[Tuple[float, str]]:
        """
        Group snippets into segments of roughly `youtube_segment_seconds`.

        Caption snippets are a few words each — far too small to be a unit of
        provenance or a chunk. Grouping by time gives segments comparable to a
        slide, and the segment's start time becomes its citable location.
        """
        window = settings.youtube_segment_seconds
        segments: List[Tuple[float, str]] = []
        start: Optional[float] = None
        parts: List[str] = []

        for s in snippets:
            text = (s.get("text") or "").replace("\n", " ").strip()
            if not text:
                continue
            if start is None:
                start = float(s.get("start", 0.0))
            parts.append(text)
            if float(s.get("start", 0.0)) - start >= window:
                segments.append((start, " ".join(parts)))
                start, parts = None, []

        if parts and start is not None:
            segments.append((start, " ".join(parts)))
        return segments

    def parse(self, filepath: Path, resource_id: str, subject_id: str) -> Optional[IngestedResource]:
        if not YT_AVAILABLE:
            logging.error("youtube-transcript-api not installed. Run: pip install youtube-transcript-api")
            return None

        try:
            raw = filepath.read_text(encoding="utf-8").strip()
            video_id = extract_video_id(raw)
            if not video_id:
                logging.error(f"{filepath.name}: no YouTube video id found in {raw[:60]!r}")
                return None

            logging.info(f"Fetching transcript for {video_id}")
            snippets, language, translated = self._fetch(video_id)
            segments = self._segment(snippets)

            if not segments:
                logging.warning(f"{filepath.name}: transcript was empty")
                return None

            method = "youtube_transcript_translated" if translated else "youtube_transcript"
            chunks = [
                ContentChunk(
                    chunk_id=f"{resource_id}_timestamp_{int(start)}",
                    source_type="youtube",
                    location_type="timestamp",
                    location_number=int(start),
                    text=text,
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    extraction_method=method,
                )
                for start, text in segments
            ]

            total = segments[-1][0]
            logging.info(
                f"  {len(snippets)} snippets -> {len(chunks)} segments "
                f"covering {_timestamp(total)} ({language})"
            )

            return IngestedResource(
                resource_id=resource_id,
                resource_type="youtube",
                filename=filepath.name,
                subject_id=subject_id,
                content=chunks,
            )

        except Exception as e:
            logging.error(f"Error parsing {filepath.name}: {e}")
            return None
