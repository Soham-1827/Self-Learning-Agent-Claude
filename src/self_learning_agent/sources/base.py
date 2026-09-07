"""The Source seam (I4).

Everything downstream depends on SourceDocument, never on YouTube. Adding
articles or PDFs later means writing one adapter, not touching the pipeline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import SourceDocument


@runtime_checkable
class Source(Protocol):
    source_type: str

    def handles(self, ref: str) -> bool:
        """Whether this source can interpret `ref`."""

    def resolve(self, ref: str, limit: int = 1) -> list[str]:
        """A user-supplied reference to a list of concrete source ids."""

    def fetch(self, source_id: str) -> SourceDocument:
        """One source id to a normalized document."""
