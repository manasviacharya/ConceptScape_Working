from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ingestion.models import IngestedResource

class BaseParser(ABC):
    @abstractmethod
    def can_handle(self, filepath: Path) -> bool:
        """Return True if this parser supports the given file."""
        pass

    @abstractmethod
    def parse(self, filepath: Path, resource_id: str, subject_id: str) -> Optional[IngestedResource]:
        """Parse the file and return a common IngestedResource, or None if failed."""
        pass
