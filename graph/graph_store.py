from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseGraphStore(ABC):
    """
    Storage-agnostic interface for the concept graph.

    Every caller — graph construction, queries, the React Flow view, and the
    graph-aware retriever — talks to this interface rather than to a driver.
    Swapping the backend then means writing one new subclass, not rewriting
    the pipeline. It also lets graph logic be exercised without a live
    database connection.
    """

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def init_schema(self) -> None:
        """Create constraints/indexes. Must be idempotent."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all concepts and relationships owned by this graph."""

    @abstractmethod
    def upsert_concepts(self, concepts: List[Dict[str, Any]]) -> int: ...

    @abstractmethod
    def upsert_relationships(self, relationships: List[Dict[str, Any]]) -> int: ...

    @abstractmethod
    def get_concept(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up by canonical_name or alias, case-insensitively."""

    @abstractmethod
    def get_neighbors(self, concept_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_subgraph(self, concept_id: str, hops: int = 2) -> Dict[str, Any]: ...

    @abstractmethod
    def shortest_path(self, source_id: str, target_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def concepts_by_document(self, filename: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def most_connected(self, limit: int = 10) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def export_graph(self) -> Dict[str, Any]:
        """Whole graph as {nodes, edges} — the payload the UI renders."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]: ...
