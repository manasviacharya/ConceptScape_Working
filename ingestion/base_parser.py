from abc import ABC, abstractmethod
from pathlib import Path

from ingestion.models import IngestedResource


class BaseParser(ABC):
    @abstractmethod
    def can_handle(self, filepath: Path) -> bool:
        """Return True if this parser supports the given file."""

    @abstractmethod
    def parse(self, filepath: Path, resource_id: str, subject_id: str) -> IngestedResource | None:
        """Parse the file and return a common IngestedResource, or None if failed."""
