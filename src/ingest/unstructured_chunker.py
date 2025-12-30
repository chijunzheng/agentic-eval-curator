"""Unstructured.io-based semantic chunking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from src.ingest.chunker import BaseChunker, ChunkMetadata
from src.ingest.parsers import ParseResult

if TYPE_CHECKING:
    pass

# Check if unstructured is available
try:
    from unstructured.chunking.title import chunk_by_title
    from unstructured.documents.elements import Table
    from unstructured.partition.auto import partition

    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False


class UnstructuredChunker(BaseChunker):
    """Chunker using unstructured.io for semantic document chunking.

    This chunker leverages unstructured.io's document-aware partitioning
    to create semantically coherent chunks that:
    - Respect section boundaries (titles, headers)
    - Keep tables isolated as separate chunks
    - Never split mid-sentence or mid-word
    - Preserve document hierarchy in metadata

    Requires: pip install "unstructured[all-docs]"
    """

    def __init__(
        self,
        max_characters: int = 1500,
        new_after_n_chars: int = 1000,
        combine_text_under_n_chars: int = 200,
        overlap: int = 100,
        multipage_sections: bool = True,
    ):
        """Initialize UnstructuredChunker.

        Args:
            max_characters: Hard maximum chunk size (default: 1500).
            new_after_n_chars: Soft target size - start new chunk after this (default: 1000).
            combine_text_under_n_chars: Merge sections smaller than this (default: 200).
            overlap: Character overlap when text-splitting occurs (default: 100).
            multipage_sections: Whether sections can span pages (default: True).
        """
        if not UNSTRUCTURED_AVAILABLE:
            raise ImportError(
                "unstructured library not installed. "
                "Install with: pip install 'unstructured[all-docs]'"
            )

        self.max_characters = max_characters
        self.new_after_n_chars = new_after_n_chars
        self.combine_text_under_n_chars = combine_text_under_n_chars
        self.overlap = overlap
        self.multipage_sections = multipage_sections

    def chunk_file(self, file_path: Path) -> list[ChunkMetadata]:
        """Chunk directly from a file using unstructured.io.

        This is the preferred method as it allows unstructured to
        extract full document structure including tables, headers, etc.

        Args:
            file_path: Path to the document file.

        Returns:
            List of ChunkMetadata objects.
        """
        # Partition the document into semantic elements
        elements = partition(filename=str(file_path))

        # Chunk by title/section boundaries
        chunks = chunk_by_title(
            elements,
            max_characters=self.max_characters,
            new_after_n_chars=self.new_after_n_chars,
            combine_text_under_n_chars=self.combine_text_under_n_chars,
            overlap=self.overlap,
            multipage_sections=self.multipage_sections,
        )

        result = []
        for chunk in chunks:
            # Check if this is a table chunk
            is_table = isinstance(chunk, Table)

            # Extract metadata
            page_ref = None
            if hasattr(chunk, "metadata") and hasattr(chunk.metadata, "page_number"):
                page_ref = chunk.metadata.page_number

            section_path = None
            if hasattr(chunk, "metadata"):
                # Build section path from parent elements if available
                if hasattr(chunk.metadata, "section"):
                    section_path = chunk.metadata.section

            # For tables, store the HTML representation
            table_json = None
            if is_table and hasattr(chunk, "metadata"):
                if hasattr(chunk.metadata, "text_as_html"):
                    table_json = {"html": chunk.metadata.text_as_html}
                # Also include the raw table data if available
                if hasattr(chunk.metadata, "table_data"):
                    if table_json is None:
                        table_json = {}
                    table_json["data"] = chunk.metadata.table_data

            metadata = ChunkMetadata(
                text=chunk.text,
                page_ref=page_ref,
                section_path=section_path,
                table_json=table_json,
            )
            result.append(metadata)

        return result

    def chunk(self, parse_result: ParseResult) -> list[ChunkMetadata]:
        """Chunk from pre-parsed text.

        Note: This method is less accurate than chunk_file() because
        unstructured.io works best with direct file access for full
        document structure extraction. When possible, use chunk_file().

        For pre-parsed text, this falls back to SentenceTableAwareChunker.

        Args:
            parse_result: Parsed document result.

        Returns:
            List of ChunkMetadata objects.
        """
        # For pre-parsed text, fall back to sentence-aware chunking
        # since we don't have access to the original document structure
        from src.ingest.chunker import SentenceTableAwareChunker

        fallback = SentenceTableAwareChunker(
            min_chunk_size=self.combine_text_under_n_chars,
            max_chunk_size=self.max_characters,
        )
        return fallback.chunk(parse_result)


def get_unstructured_chunker(**kwargs) -> UnstructuredChunker:
    """Factory function to get an UnstructuredChunker.

    Args:
        **kwargs: Arguments passed to UnstructuredChunker.

    Returns:
        Configured UnstructuredChunker instance.

    Raises:
        ImportError: If unstructured library is not installed.
    """
    return UnstructuredChunker(**kwargs)
