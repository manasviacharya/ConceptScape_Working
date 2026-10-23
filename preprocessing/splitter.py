import logging
from typing import List

import pysbd


_segmenter = pysbd.Segmenter(language="en", clean=False)


def split_sentences(text: str) -> List[str]:
    if not text.strip():
        return []

    sentences = _segmenter.segment(text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences and text.strip():
        logging.warning("Sentence splitter returned nothing for non-empty input — treating as single sentence")
        sentences = [text.strip()]

    return sentences
