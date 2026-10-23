import re
import unicodedata
from typing import List, Optional

from config import settings


def clean_text(
    text: str,
    extraction_method: str = "",
    all_page_texts: Optional[List[str]] = None,
    page_index: Optional[int] = None,
) -> str:
    if not text:
        return text

    result = text

    if settings.clean_normalize_unicode:
        result = _normalize_unicode(result)

    if settings.clean_dehyphenate:
        result = _dehyphenate(result)

    if (
        settings.clean_remove_headers_footers
        and all_page_texts is not None
        and len(all_page_texts) >= 4
        and page_index is not None
    ):
        result = _remove_headers_footers(result, all_page_texts, page_index)

    if settings.clean_remove_page_numbers:
        result = _remove_page_numbers(result)

    if settings.clean_normalize_bullets:
        result = _normalize_bullets(result)

    if settings.clean_join_ocr_lines and extraction_method == "paddleocr":
        result = _join_ocr_lines(result)

    any_flag_on = (
        settings.clean_normalize_unicode
        or settings.clean_dehyphenate
        or settings.clean_remove_headers_footers
        or settings.clean_remove_page_numbers
        or settings.clean_normalize_bullets
        or settings.clean_join_ocr_lines
    )
    if any_flag_on:
        result = _collapse_whitespace(result)

    return result


def _normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _dehyphenate(text: str) -> str:
    return re.sub(r"(\w)-\n([a-z])", r"\1\2", text)


def _remove_headers_footers(
    text: str, all_page_texts: List[str], page_index: int
) -> str:
    total_pages = len(all_page_texts)
    threshold = int(total_pages * settings.header_footer_min_page_ratio)

    first_lines = []
    last_lines = []
    for pt in all_page_texts:
        lines = [l.strip() for l in pt.split("\n") if l.strip()]
        if lines:
            first_lines.append(lines[0])
            last_lines.append(lines[-1])

    from collections import Counter
    first_counts = Counter(first_lines)
    last_counts = Counter(last_lines)

    lines_to_remove = set()
    for line, count in first_counts.items():
        if count >= threshold and len(line) < 80:
            lines_to_remove.add(line)
    for line, count in last_counts.items():
        if count >= threshold and len(line) < 80:
            lines_to_remove.add(line)

    if not lines_to_remove:
        return text

    result_lines = []
    for line in text.split("\n"):
        if line.strip() in lines_to_remove:
            continue
        result_lines.append(line)

    return "\n".join(result_lines)


def _remove_page_numbers(text: str) -> str:
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\d+$", stripped):
            continue
        if re.match(r"^[Pp]age\s+\d+$", stripped):
            continue
        if re.match(r"^\d+\s*/\s*\d+$", stripped):
            continue
        result.append(line)
    return "\n".join(result)


def _normalize_bullets(text: str) -> str:
    return re.sub(r"^([•◦▪‣–—])\s", "- ", text, flags=re.MULTILINE)


def _join_ocr_lines(text: str) -> str:
    lines = text.split("\n")
    if len(lines) <= 1:
        return text

    merged = [lines[0]]
    for i in range(1, len(lines)):
        prev = merged[-1]
        curr = lines[i]
        if (
            prev
            and curr
            and not re.search(r"[.!?:;]\s*$", prev)
            and curr[0:1].islower()
        ):
            merged[-1] = prev + " " + curr
        else:
            merged.append(curr)

    return "\n".join(merged)


def _collapse_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
