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


class SentenceAwareChunker(BaseChunker):
    """Sentence-boundary chunker optimized for PDFs and technical documents.

    Key features:
    - Normalizes line-wrapped text before chunking
    - Splits at sentence boundaries (period, exclamation, question + space/newline)
    - Never cuts mid-word
    - Handles numbered lists, references, and technical notation
    """

    def __init__(self, min_chunk_size: int = 200, max_chunk_size: int = 1500):
        """Initialize sentence-aware chunker.

        Args:
            min_chunk_size: Minimum chunk size in characters.
            max_chunk_size: Maximum chunk size in characters.
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

        # Common abbreviations that shouldn't end sentences
        self.abbreviations = {
            'Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'Jr', 'Sr', 'vs', 'etc',
            'Fig', 'Sec', 'Vol', 'No', 'pp', 'e.g', 'i.e', 'al', 'cf',
            'et', 'viz', 'approx', 'ca', 'ch', 'ed', 'eds', 'esp',
            'n.b', 'p.m', 'a.m', 'Rev', 'St', 'Dept', 'Inc', 'Corp',
        }

    def chunk(self, parse_result: ParseResult) -> list[ChunkMetadata]:
        """Split text at sentence boundaries.

        Args:
            parse_result: Parsed document result.

        Returns:
            List of ChunkMetadata objects.
        """
        text = parse_result.text
        if not text.strip():
            return []

        # Step 1: Normalize text (join line-wrapped text, preserve paragraphs)
        normalized = self._normalize_text(text)

        # Step 2: Split into sentences
        sentences = self._split_sentences(normalized)

        # Step 3: Merge sentences into chunks
        chunks = self._merge_sentences_to_chunks(sentences)

        # Step 4: Create ChunkMetadata objects
        return [ChunkMetadata(text=chunk_text) for chunk_text in chunks if chunk_text.strip()]

    def _normalize_text(self, text: str) -> str:
        """Normalize text by joining line-wrapped content.

        PDF text often has single newlines for line wraps within paragraphs.
        This method joins them while preserving paragraph breaks (double newlines).

        Args:
            text: Raw text from parser.

        Returns:
            Normalized text with line wraps joined.
        """
        # First, preserve paragraph breaks by marking them
        text = re.sub(r'\n\n+', '\n\n<PARA_BREAK>\n\n', text)

        # Join lines that are wrapped mid-sentence
        # A line continuation is: lowercase or comma at start of next line,
        # or no sentence-ending punctuation at end of current line
        lines = text.split('\n')
        result_lines = []
        buffer = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line == '<PARA_BREAK>':
                if buffer:
                    result_lines.append(buffer)
                    buffer = ""
                result_lines.append('')  # Empty line for paragraph break
                continue

            if not buffer:
                buffer = line
            else:
                # Check if this looks like a continuation
                # (previous line doesn't end with sentence-ending punctuation
                # and current line starts with lowercase or continues a sentence)
                prev_ends_sentence = bool(re.search(r'[.!?:]\s*$', buffer))
                curr_starts_new = bool(re.match(r'^[A-Z\d\[\(\"]', line))

                if prev_ends_sentence and curr_starts_new:
                    # Likely a new sentence/paragraph
                    result_lines.append(buffer)
                    buffer = line
                else:
                    # Continuation - join with space
                    buffer = buffer + ' ' + line

        if buffer:
            result_lines.append(buffer)

        # Reconstruct text with double newlines for paragraph breaks
        result = []
        for i, line in enumerate(result_lines):
            if line == '' and i > 0 and result:
                result.append('\n')  # Add paragraph break
            elif line:
                result.append(line)

        return '\n\n'.join(result)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences, respecting abbreviations.

        Args:
            text: Normalized text.

        Returns:
            List of sentences.
        """
        # Split by paragraph first
        paragraphs = re.split(r'\n\n+', text)

        sentences = []
        for para in paragraphs:
            if not para.strip():
                continue

            # Split paragraph into sentences using a two-pass approach
            # First, find all potential sentence boundaries
            para_sentences = self._split_paragraph_into_sentences(para)
            sentences.extend(para_sentences)

        return sentences

    def _split_paragraph_into_sentences(self, para: str) -> list[str]:
        """Split a paragraph into sentences, handling abbreviations.

        Args:
            para: Paragraph text.

        Returns:
            List of sentences.
        """
        # Find all positions where we might split (after .!?)
        potential_splits = []
        i = 0
        while i < len(para):
            if para[i] in '.!?':
                # Check if followed by whitespace and capital letter or number
                remaining = para[i+1:]
                if remaining and (remaining[0].isspace() or remaining[0] == '\n'):
                    # Check next non-whitespace char
                    next_char_idx = i + 1
                    while next_char_idx < len(para) and para[next_char_idx].isspace():
                        next_char_idx += 1
                    if next_char_idx < len(para):
                        next_char = para[next_char_idx]
                        if next_char.isupper() or next_char.isdigit() or next_char in '[("':
                            # Check if this is an abbreviation
                            if not self._is_abbreviation(para, i):
                                potential_splits.append(i)
            i += 1

        # Split at valid boundaries
        if not potential_splits:
            return [para.strip()] if para.strip() else []

        sentences = []
        start = 0
        for split_pos in potential_splits:
            sentence = para[start:split_pos+1].strip()
            if sentence:
                sentences.append(sentence)
            # Find start of next sentence (skip whitespace)
            start = split_pos + 1
            while start < len(para) and para[start].isspace():
                start += 1

        # Don't forget the last part
        if start < len(para):
            last = para[start:].strip()
            if last:
                sentences.append(last)

        return sentences

    def _is_abbreviation(self, text: str, period_pos: int) -> bool:
        """Check if the period at period_pos is part of an abbreviation.

        Args:
            text: Full text.
            period_pos: Position of the period.

        Returns:
            True if this appears to be an abbreviation.
        """
        # Get the word before the period
        start = period_pos
        while start > 0 and (text[start-1].isalnum() or text[start-1] == '.'):
            start -= 1

        word = text[start:period_pos]

        # Check against known abbreviations
        if word in self.abbreviations:
            return True

        # Check for patterns like "e.g" or "i.e" (with internal periods)
        if '.' in word:
            return True

        # Single capital letter followed by period is likely an abbreviation
        if len(word) == 1 and word.isupper():
            return True

        # Numbers followed by period might be list items, not sentence ends
        if word.isdigit():
            return True

        return False

    def _merge_sentences_to_chunks(self, sentences: list[str]) -> list[str]:
        """Merge sentences into chunks respecting size limits.

        Args:
            sentences: List of sentences.

        Returns:
            List of chunk texts.
        """
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If sentence alone exceeds max, we need to split it
            if len(sentence) > self.max_chunk_size:
                # Save current chunk first
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                # Split long sentence at word boundaries
                chunks.extend(self._split_long_text(sentence))
                continue

            # Check if adding this sentence exceeds max
            test_chunk = current_chunk + (' ' if current_chunk else '') + sentence

            if len(test_chunk) > self.max_chunk_size:
                # Save current chunk and start new one
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                current_chunk = test_chunk

        # Don't forget the last chunk
        if current_chunk:
            # If it's too small and we have previous chunks, try to merge
            if len(current_chunk) < self.min_chunk_size and chunks:
                last = chunks.pop()
                combined = last + ' ' + current_chunk
                if len(combined) <= self.max_chunk_size * 1.1:  # Allow 10% overflow
                    chunks.append(combined)
                else:
                    chunks.append(last)
                    chunks.append(current_chunk)
            else:
                chunks.append(current_chunk)

        return chunks

    def _split_long_text(self, text: str) -> list[str]:
        """Split text that exceeds max_chunk_size at word boundaries.

        Args:
            text: Long text to split.

        Returns:
            List of chunks.
        """
        words = text.split()
        chunks = []
        current = ""

        for word in words:
            test = current + (' ' if current else '') + word
            if len(test) > self.max_chunk_size:
                if current:
                    chunks.append(current)
                current = word
            else:
                current = test

        if current:
            chunks.append(current)

        return chunks


class SentenceTableAwareChunker(TableAwareChunker):
    """Hybrid: sentence-aware chunking for prose + table preservation.

    Best for PDF documents like 3GPP/O-RAN specs that have:
    - Technical prose with references and citations
    - Data tables that should stay intact
    - Multi-column layouts or complex formatting
    """

    def __init__(self, min_chunk_size: int = 200, max_chunk_size: int = 1500):
        """Initialize sentence-table-aware chunker.

        Args:
            min_chunk_size: Minimum chunk size for prose.
            max_chunk_size: Maximum chunk size for prose.
        """
        # Don't call super().__init__ since we're replacing the text chunker
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self._text_chunker = SentenceAwareChunker(min_chunk_size, max_chunk_size)


# Chunker registry
_CHUNKERS: dict[str, type[BaseChunker]] = {
    "fixed_window": FixedWindowChunker,
    "semantic": SemanticChunker,
    "table_aware": TableAwareChunker,
    "semantic_table_aware": SemanticTableAwareChunker,
    "sentence_aware": SentenceAwareChunker,
    "sentence_table_aware": SentenceTableAwareChunker,
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
    elif strategy == "sentence_aware":
        return chunker_class(min_chunk_size=overlap * 2, max_chunk_size=chunk_size * 3)
    elif strategy == "sentence_table_aware":
        return chunker_class(min_chunk_size=overlap * 2, max_chunk_size=chunk_size * 3)
    else:
        return chunker_class()
