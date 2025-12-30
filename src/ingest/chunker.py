"""Chunking strategies for document text."""

import re
from abc import ABC, abstractmethod
from typing import Any

from src.ingest.parsers import ParseResult


class ChunkMetadata:
    """Metadata for a single chunk."""

    def __init__(
        self,
        text: str,
        page_ref: int | None = None,
        section_path: str | None = None,
        table_json: dict[str, Any] | None = None,
    ):
        """Initialize chunk metadata.

        Args:
            text: Chunk text content.
            page_ref: Optional page number.
            section_path: Optional section hierarchy path.
            table_json: Optional table data.
        """
        self.text = text
        self.page_ref = page_ref
        self.section_path = section_path
        self.table_json = table_json


class BaseChunker(ABC):
    """Abstract base class for chunking strategies."""

    @abstractmethod
    def chunk(self, parse_result: ParseResult) -> list[ChunkMetadata]:
        """Split parsed document into chunks.

        Args:
            parse_result: Parsed document result.

        Returns:
            List of ChunkMetadata objects.
        """
        pass


class FixedWindowChunker(BaseChunker):
    """Fixed-size window chunker with configurable overlap."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        """Initialize fixed window chunker.

        Args:
            chunk_size: Target chunk size in characters.
            overlap: Overlap between consecutive chunks in characters.
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, parse_result: ParseResult) -> list[ChunkMetadata]:
        """Split text into fixed-size overlapping chunks.

        Args:
            parse_result: Parsed document result.

        Returns:
            List of ChunkMetadata objects.
        """
        text = parse_result.text
        if not text.strip():
            return []

        chunks = []
        start = 0
        step = self.chunk_size - self.overlap

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end].strip()

            if chunk_text:
                # Determine page reference if page_texts available
                page_ref = None
                if parse_result.page_texts:
                    page_ref = self._find_page_for_position(
                        start, parse_result.page_texts
                    )

                chunks.append(ChunkMetadata(
                    text=chunk_text,
                    page_ref=page_ref,
                ))

            start += step
            if start >= len(text):
                break

        return chunks

    def _find_page_for_position(
        self, position: int, page_texts: list[str]
    ) -> int | None:
        """Find page number for a character position.

        Args:
            position: Character position in full text.
            page_texts: List of per-page text.

        Returns:
            1-indexed page number or None.
        """
        current_pos = 0
        for page_num, page_text in enumerate(page_texts, start=1):
            page_end = current_pos + len(page_text) + 2  # +2 for "\n\n" separator
            if position < page_end:
                return page_num
            current_pos = page_end
        return len(page_texts)  # Last page if past end


class SemanticChunker(BaseChunker):
    """Paragraph-based semantic chunker with sentence-boundary fallback."""

    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 1000):
        """Initialize semantic chunker.

        Args:
            min_chunk_size: Minimum chunk size in characters.
            max_chunk_size: Maximum chunk size in characters.
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk(self, parse_result: ParseResult) -> list[ChunkMetadata]:
        """Split text by paragraphs, merging small ones.

        For paragraphs that exceed max_chunk_size, splits at sentence
        boundaries. Falls back to word boundaries if needed.

        Args:
            parse_result: Parsed document result.

        Returns:
            List of ChunkMetadata objects.
        """
        text = parse_result.text
        if not text.strip():
            return []

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r"\n\n+", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # Expand oversized paragraphs into smaller pieces
        expanded = []
        for para in paragraphs:
            if len(para) > self.max_chunk_size:
                expanded.extend(self._split_long_paragraph(para))
            else:
                expanded.append(para)

        chunks = []
        current_chunk = ""

        for para in expanded:
            # If adding this paragraph exceeds max, save current and start new
            if current_chunk and len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                if current_chunk.strip():
                    chunks.append(ChunkMetadata(text=current_chunk.strip()))
                current_chunk = para
            else:
                # Merge with current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Don't forget the last chunk
        if current_chunk.strip():
            # If it's too small and we have previous chunks, merge with last
            if len(current_chunk) < self.min_chunk_size and chunks:
                last = chunks.pop()
                combined = last.text + "\n\n" + current_chunk
                # Only merge if it won't exceed max
                if len(combined) <= self.max_chunk_size * 1.2:  # Allow 20% overflow
                    chunks.append(ChunkMetadata(text=combined.strip()))
                else:
                    chunks.append(last)
                    chunks.append(ChunkMetadata(text=current_chunk.strip()))
            else:
                chunks.append(ChunkMetadata(text=current_chunk.strip()))

        return chunks

    def _split_long_paragraph(self, para: str) -> list[str]:
        """Split an oversized paragraph at sentence or word boundaries.

        Args:
            para: Paragraph text that exceeds max_chunk_size.

        Returns:
            List of smaller text segments.
        """
        # Try splitting by sentences first (period/exclaim/question + space)
        sentences = re.split(r'(?<=[.!?])\s+', para)

        if len(sentences) > 1:
            # Merge sentences into chunks up to max_chunk_size
            return self._merge_segments(sentences, "\n")

        # If no sentence boundaries, try splitting by newlines (e.g., TOC entries)
        lines = para.split("\n")
        if len(lines) > 1:
            return self._merge_segments(lines, "\n")

        # Last resort: split by words at max_chunk_size boundaries
        return self._split_by_words(para)

    def _merge_segments(self, segments: list[str], separator: str) -> list[str]:
        """Merge segments into chunks respecting max_chunk_size.

        Args:
            segments: List of text segments (sentences or lines).
            separator: Separator to use when joining.

        Returns:
            List of merged chunks.
        """
        result = []
        current = ""

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue

            if not current:
                current = seg
            elif len(current) + len(sep := separator) + len(seg) <= self.max_chunk_size:
                current += sep + seg
            else:
                if current:
                    result.append(current)
                # If single segment exceeds max, split it further
                if len(seg) > self.max_chunk_size:
                    result.extend(self._split_by_words(seg))
                    current = ""
                else:
                    current = seg

        if current:
            result.append(current)

        return result

    def _split_by_words(self, text: str) -> list[str]:
        """Split text by words, respecting max_chunk_size.

        Args:
            text: Text to split.

        Returns:
            List of chunks split at word boundaries.
        """
        words = text.split()
        result = []
        current = ""

        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= self.max_chunk_size:
                current += " " + word
            else:
                result.append(current)
                current = word

        if current:
            result.append(current)

        return result


class TableAwareChunker(BaseChunker):
    """Chunker that preserves table boundaries."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        """Initialize table-aware chunker.

        Args:
            chunk_size: Target chunk size for non-table content.
            overlap: Overlap for non-table chunks.
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._text_chunker = FixedWindowChunker(chunk_size, overlap)

    def chunk(self, parse_result: ParseResult) -> list[ChunkMetadata]:
        """Split text while preserving table boundaries.

        Tables are kept as separate chunks with table_json populated.
        Non-table text is chunked with fixed window strategy.

        Args:
            parse_result: Parsed document result.

        Returns:
            List of ChunkMetadata objects.
        """
        chunks = []

        # If no tables, fall back to text chunker
        if not parse_result.tables:
            return self._text_chunker.chunk(parse_result)

        # Process tables first
        for table in parse_result.tables:
            table_text = self._table_to_text(table.get("data", []))
            if table_text:
                chunks.append(ChunkMetadata(
                    text=table_text,
                    page_ref=table.get("page"),
                    table_json=table,
                ))

        # Chunk remaining text (excluding table content)
        # For simplicity, we also chunk the full text
        # In production, you'd want to exclude table regions
        text_result = ParseResult(text=parse_result.text)
        text_chunks = self._text_chunker.chunk(text_result)

        # Interleave based on page order if available
        chunks.extend(text_chunks)

        return chunks

    def _table_to_text(self, table_data: list[list[str]]) -> str:
        """Convert table data to readable text.

        Args:
            table_data: 2D list of cell values.

        Returns:
            Text representation of table.
        """
        if not table_data:
            return ""

        lines = []
        for row in table_data:
            if row:
                lines.append(" | ".join(str(cell) if cell else "" for cell in row))

        return "\n".join(lines)


class SemanticTableAwareChunker(TableAwareChunker):
    """Hybrid chunker: semantic chunking for prose + table preservation.

    Best for structured documents like 3GPP/O-RAN specs that have
    both narrative prose and data tables.
    """

    def __init__(self, min_chunk_size: int = 100, max_chunk_size: int = 1000):
        """Initialize semantic table-aware chunker.

        Args:
            min_chunk_size: Minimum chunk size for prose.
            max_chunk_size: Maximum chunk size for prose.
        """
        # Don't call super().__init__ since we're replacing the text chunker
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self._text_chunker = SemanticChunker(min_chunk_size, max_chunk_size)


# Chunker registry
_CHUNKERS: dict[str, type[BaseChunker]] = {
    "fixed_window": FixedWindowChunker,
    "semantic": SemanticChunker,
    "table_aware": TableAwareChunker,
    "semantic_table_aware": SemanticTableAwareChunker,
}


def get_chunker(
    strategy: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> BaseChunker:
    """Get chunker instance by strategy name.

    Args:
        strategy: Chunking strategy name.
        chunk_size: Target chunk size.
        overlap: Overlap size (for fixed window strategies).

    Returns:
        Configured chunker instance.

    Raises:
        ValueError: If strategy is not supported.
    """
    if strategy not in _CHUNKERS:
        supported = ", ".join(_CHUNKERS.keys())
        raise ValueError(f"Unknown chunking strategy: {strategy}. Supported: {supported}")

    chunker_class = _CHUNKERS[strategy]

    if strategy == "fixed_window":
        return chunker_class(chunk_size=chunk_size, overlap=overlap)
    elif strategy == "semantic":
        return chunker_class(min_chunk_size=overlap, max_chunk_size=chunk_size * 2)
    elif strategy == "table_aware":
        return chunker_class(chunk_size=chunk_size, overlap=overlap)
    elif strategy == "semantic_table_aware":
        return chunker_class(min_chunk_size=overlap, max_chunk_size=chunk_size * 2)
    else:
        return chunker_class()
