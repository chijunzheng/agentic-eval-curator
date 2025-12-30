"""Unit tests for chunking strategies."""

import pytest

from src.ingest.chunker import (
    FixedWindowChunker,
    SemanticChunker,
    SemanticTableAwareChunker,
    TableAwareChunker,
    get_chunker,
)
from src.ingest.parsers import ParseResult


class TestFixedWindowChunker:
    """Tests for FixedWindowChunker."""

    def test_chunk_short_text(self):
        """Test chunking text shorter than chunk size."""
        chunker = FixedWindowChunker(chunk_size=100, overlap=10)
        result = ParseResult(text="Short text")

        chunks = chunker.chunk(result)

        assert len(chunks) == 1
        assert chunks[0].text == "Short text"

    def test_chunk_with_overlap(self):
        """Test that chunks overlap correctly."""
        # 50 char chunks with 10 char overlap = 40 char step
        chunker = FixedWindowChunker(chunk_size=50, overlap=10)
        text = "A" * 100  # 100 characters
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # With 40 char steps: 0-50, 40-90, 80-100 = 3 chunks
        assert len(chunks) == 3
        assert len(chunks[0].text) == 50
        assert len(chunks[1].text) == 50
        assert len(chunks[2].text) == 20  # Last chunk may be shorter

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunker = FixedWindowChunker(chunk_size=100, overlap=10)
        result = ParseResult(text="   ")

        chunks = chunker.chunk(result)

        assert len(chunks) == 0

    def test_chunk_with_page_refs(self):
        """Test that page references are assigned."""
        chunker = FixedWindowChunker(chunk_size=50, overlap=0)
        page_texts = ["Page 1 content here", "Page 2 content here"]
        full_text = "\n\n".join(page_texts)
        result = ParseResult(text=full_text, page_texts=page_texts)

        chunks = chunker.chunk(result)

        # First chunk should be on page 1
        assert chunks[0].page_ref == 1


class TestSemanticChunker:
    """Tests for SemanticChunker."""

    def test_chunk_by_paragraphs(self):
        """Test splitting by paragraphs."""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=100)
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # Should merge small paragraphs
        assert len(chunks) >= 1

    def test_chunk_merges_small_paragraphs(self):
        """Test that small paragraphs are merged."""
        chunker = SemanticChunker(min_chunk_size=50, max_chunk_size=500)
        text = "A.\n\nB.\n\nC."  # Very short paragraphs
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # Should merge into one chunk since they're small
        assert len(chunks) == 1
        assert "A." in chunks[0].text
        assert "B." in chunks[0].text
        assert "C." in chunks[0].text

    def test_chunk_respects_max_size(self):
        """Test that chunks don't exceed max size."""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=50)
        text = "A" * 30 + "\n\n" + "B" * 30 + "\n\n" + "C" * 30
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # Each paragraph is 30 chars, max is 50, so can't merge
        assert len(chunks) >= 2

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunker = SemanticChunker()
        result = ParseResult(text="")

        chunks = chunker.chunk(result)

        assert len(chunks) == 0


class TestTableAwareChunker:
    """Tests for TableAwareChunker."""

    def test_chunk_with_tables(self):
        """Test chunking document with tables."""
        chunker = TableAwareChunker(chunk_size=100)
        tables = [{"data": [["A", "B"], ["1", "2"]], "page": 1}]
        result = ParseResult(text="Some text content", tables=tables)

        chunks = chunker.chunk(result)

        # Should have table chunk(s) and text chunk(s)
        assert len(chunks) >= 2

        # Find table chunk
        table_chunks = [c for c in chunks if c.table_json is not None]
        assert len(table_chunks) == 1
        assert "A | B" in table_chunks[0].text

    def test_chunk_without_tables(self):
        """Test fallback to fixed window without tables."""
        chunker = TableAwareChunker(chunk_size=100)
        result = ParseResult(text="Some text content without tables")

        chunks = chunker.chunk(result)

        # Should fall back to fixed window
        assert len(chunks) >= 1
        assert chunks[0].table_json is None


class TestSemanticTableAwareChunker:
    """Tests for SemanticTableAwareChunker (hybrid strategy)."""

    def test_chunk_with_tables_uses_semantic_for_prose(self):
        """Test that prose is chunked semantically while tables are preserved."""
        chunker = SemanticTableAwareChunker(min_chunk_size=10, max_chunk_size=200)
        tables = [{"data": [["Col1", "Col2"], ["A", "B"]], "page": 1}]
        text = "First paragraph about topic X.\n\nSecond paragraph continues.\n\nThird paragraph."
        result = ParseResult(text=text, tables=tables)

        chunks = chunker.chunk(result)

        # Should have table chunk(s) and semantic text chunk(s)
        table_chunks = [c for c in chunks if c.table_json is not None]
        text_chunks = [c for c in chunks if c.table_json is None]

        assert len(table_chunks) == 1
        assert "Col1 | Col2" in table_chunks[0].text

        # Text should be semantically chunked (paragraphs merged)
        assert len(text_chunks) >= 1

    def test_chunk_without_tables_uses_semantic(self):
        """Test fallback to semantic chunking when no tables."""
        chunker = SemanticTableAwareChunker(min_chunk_size=10, max_chunk_size=100)
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # Should behave like SemanticChunker
        assert len(chunks) >= 1
        assert all(c.table_json is None for c in chunks)

    def test_inherits_table_to_text(self):
        """Test that table formatting is inherited."""
        chunker = SemanticTableAwareChunker()
        table_data = [["Header1", "Header2"], ["Value1", "Value2"]]

        text = chunker._table_to_text(table_data)

        assert "Header1 | Header2" in text
        assert "Value1 | Value2" in text


class TestGetChunker:
    """Tests for get_chunker factory function."""

    def test_get_fixed_window(self):
        """Test getting fixed window chunker."""
        chunker = get_chunker("fixed_window", chunk_size=200, overlap=20)

        assert isinstance(chunker, FixedWindowChunker)
        assert chunker.chunk_size == 200
        assert chunker.overlap == 20

    def test_get_semantic(self):
        """Test getting semantic chunker."""
        chunker = get_chunker("semantic", chunk_size=500, overlap=50)

        assert isinstance(chunker, SemanticChunker)

    def test_get_table_aware(self):
        """Test getting table-aware chunker."""
        chunker = get_chunker("table_aware", chunk_size=300, overlap=30)

        assert isinstance(chunker, TableAwareChunker)

    def test_get_semantic_table_aware(self):
        """Test getting semantic table-aware chunker."""
        chunker = get_chunker("semantic_table_aware", chunk_size=500, overlap=50)

        assert isinstance(chunker, SemanticTableAwareChunker)

    def test_get_unknown_strategy(self):
        """Test error for unknown strategy."""
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            get_chunker("unknown_strategy")


class TestChunkIdStability:
    """Tests for chunk ID stability across runs."""

    def test_fixed_window_deterministic(self):
        """Test that fixed window produces same chunks."""
        chunker = FixedWindowChunker(chunk_size=50, overlap=10)
        text = "This is a test document with multiple words."
        result = ParseResult(text=text)

        chunks1 = chunker.chunk(result)
        chunks2 = chunker.chunk(result)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.text == c2.text

    def test_semantic_deterministic(self):
        """Test that semantic chunking is deterministic."""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=100)
        text = "Para one.\n\nPara two.\n\nPara three."
        result = ParseResult(text=text)

        chunks1 = chunker.chunk(result)
        chunks2 = chunker.chunk(result)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.text == c2.text
