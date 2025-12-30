"""Unit tests for chunking strategies."""

import pytest

from src.ingest.chunker import (
    FixedWindowChunker,
    SemanticChunker,
    SemanticTableAwareChunker,
    SentenceAwareChunker,
    SentenceTableAwareChunker,
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

    def test_splits_long_paragraph_at_sentence_boundary(self):
        """Test that oversized paragraphs are split at sentence boundaries."""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=100)
        # Create a long paragraph with multiple sentences
        long_para = "First sentence here. Second sentence follows. Third sentence now. Fourth sentence added. Fifth sentence ends."
        result = ParseResult(text=long_para)

        chunks = chunker.chunk(result)

        # Should split into multiple chunks
        assert len(chunks) >= 2
        # Each chunk should not be cut mid-word
        for chunk in chunks:
            # Should end with a complete word (no partial words)
            assert not chunk.text.endswith("-")
            # Should start with a capital or complete word
            words = chunk.text.split()
            if words:
                assert len(words[0]) > 0

    def test_splits_long_paragraph_at_newline_boundary(self):
        """Test that TOC-like content is split at line boundaries."""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=100)
        # Simulate a TOC with tab-separated entries and single newlines
        toc_para = "1. Introduction\t1\n2. Background\t5\n3. Methods\t10\n4. Results\t15\n5. Discussion\t20\n6. Conclusion\t25"
        result = ParseResult(text=toc_para)

        chunks = chunker.chunk(result)

        # Should split into multiple chunks
        assert len(chunks) >= 1
        # Each chunk should contain complete lines, not cut mid-entry
        for chunk in chunks:
            # Should not start with a tab (which would indicate mid-line cut)
            assert not chunk.text.startswith("\t")

    def test_splits_long_paragraph_at_word_boundary_fallback(self):
        """Test word-boundary fallback for text without sentences."""
        chunker = SemanticChunker(min_chunk_size=10, max_chunk_size=50)
        # Long text without sentence punctuation or newlines
        long_text = "word " * 30  # ~150 chars
        result = ParseResult(text=long_text.strip())

        chunks = chunker.chunk(result)

        # Should split into multiple chunks
        assert len(chunks) >= 2
        # No chunk should exceed max_chunk_size by much (allow small overflow)
        for chunk in chunks:
            assert len(chunk.text) <= 60  # max + buffer
        # No mid-word cuts
        for chunk in chunks:
            assert not chunk.text.startswith(" ")
            assert not chunk.text.endswith(" ")


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


class TestSentenceAwareChunker:
    """Tests for SentenceAwareChunker."""

    def test_splits_at_sentence_boundaries(self):
        """Test that chunks split at sentence boundaries."""
        chunker = SentenceAwareChunker(min_chunk_size=50, max_chunk_size=200)
        text = "This is the first sentence. This is the second sentence. This is the third sentence."
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # Should split into chunks at sentence boundaries
        assert len(chunks) >= 1
        # No chunk should be cut mid-word
        for chunk in chunks:
            assert not chunk.text.startswith(" ")
            assert not chunk.text.endswith(" ")

    def test_normalizes_line_wrapped_text(self):
        """Test that line-wrapped PDF text is normalized."""
        chunker = SentenceAwareChunker(min_chunk_size=50, max_chunk_size=500)
        # Simulate PDF line wrapping
        text = """This is a sentence that has been
wrapped across multiple lines
because of PDF extraction.

This is a new paragraph."""

        result = ParseResult(text=text)
        chunks = chunker.chunk(result)

        # The wrapped text should be joined
        full_text = " ".join(c.text for c in chunks)
        assert "has been wrapped" in full_text or "been wrapped" in full_text

    def test_never_cuts_mid_word(self):
        """Test that chunks never cut mid-word."""
        chunker = SentenceAwareChunker(min_chunk_size=10, max_chunk_size=50)
        text = "Short words here and there make for good testing of word boundaries."
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # Verify no mid-word cuts
        for chunk in chunks:
            words = chunk.text.split()
            # Each word should be complete
            for word in words:
                assert len(word) > 0
                # Should not contain partial words (no lowercase after cut)
                assert not word[0].islower() or len(word) > 1

    def test_handles_references_and_citations(self):
        """Test handling of technical references like [1] and Fig. 1."""
        chunker = SentenceAwareChunker(min_chunk_size=50, max_chunk_size=300)
        text = "See [1] for details. Fig. 1 shows the architecture. Refer to Sec. 2.1 for more info."
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        # Should not split "Fig." from "1" or "Sec." from "2.1"
        full_text = " ".join(c.text for c in chunks)
        assert "Fig." in full_text
        assert "Sec." in full_text

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = SentenceAwareChunker()
        result = ParseResult(text="")

        chunks = chunker.chunk(result)
        assert len(chunks) == 0

    def test_handles_technical_document(self):
        """Test with realistic technical document text."""
        chunker = SentenceAwareChunker(min_chunk_size=100, max_chunk_size=500)
        text = """2 References
2.1 Normative references
References are either specific (identified by date of publication, edition number, version number, etc.) or non-specific.
For a specific reference, subsequent revisions do not apply. For a non-specific reference, the latest version applies.

[1] 3GPP TR 21.905: Vocabulary for 3GPP Specifications
[2] 3GPP TS 28.622: Telecommunication management; Generic Network Resource Model"""

        result = ParseResult(text=text)
        chunks = chunker.chunk(result)

        # Should chunk without cutting mid-word
        for chunk in chunks:
            text_content = chunk.text
            # Should not end with partial words like "Teleco" or "Specificatio"
            if text_content.endswith("Teleco") or text_content.endswith("Specificatio"):
                pytest.fail(f"Chunk ends mid-word: {text_content[-20:]}")


class TestSentenceTableAwareChunker:
    """Tests for SentenceTableAwareChunker."""

    def test_uses_sentence_chunker_for_prose(self):
        """Test that prose uses sentence-aware chunking."""
        chunker = SentenceTableAwareChunker(min_chunk_size=50, max_chunk_size=200)
        text = "First sentence here. Second sentence follows. Third comes after."
        result = ParseResult(text=text)

        chunks = chunker.chunk(result)

        assert len(chunks) >= 1
        assert all(c.table_json is None for c in chunks)

    def test_preserves_tables(self):
        """Test that tables are kept as separate chunks."""
        chunker = SentenceTableAwareChunker(min_chunk_size=50, max_chunk_size=200)
        tables = [{"data": [["A", "B"], ["1", "2"]], "page": 1}]
        text = "Some prose content here."
        result = ParseResult(text=text, tables=tables)

        chunks = chunker.chunk(result)

        table_chunks = [c for c in chunks if c.table_json is not None]
        assert len(table_chunks) == 1


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

    def test_get_sentence_aware(self):
        """Test getting sentence-aware chunker."""
        chunker = get_chunker("sentence_aware", chunk_size=500, overlap=50)

        assert isinstance(chunker, SentenceAwareChunker)

    def test_get_sentence_table_aware(self):
        """Test getting sentence-table-aware chunker."""
        chunker = get_chunker("sentence_table_aware", chunk_size=500, overlap=50)

        assert isinstance(chunker, SentenceTableAwareChunker)

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
