"""Unit tests for CDR conversion."""

from pathlib import Path

import pytest

from src.ingest.cdr import (
    CDRConverter,
    generate_chunk_id,
    generate_doc_id,
    get_source_type,
)
from src.models import SourceType


class TestGenerateDocId:
    """Tests for generate_doc_id function."""

    def test_stable_id(self, temp_dir: Path):
        """Test that same path produces same ID."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        id1 = generate_doc_id(file_path)
        id2 = generate_doc_id(file_path)

        assert id1 == id2

    def test_different_paths_different_ids(self, temp_dir: Path):
        """Test that different paths produce different IDs."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.touch()
        file2.touch()

        id1 = generate_doc_id(file1)
        id2 = generate_doc_id(file2)

        assert id1 != id2

    def test_id_format(self, temp_dir: Path):
        """Test that ID has expected format."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        doc_id = generate_doc_id(file_path)

        assert doc_id.startswith("doc_")
        assert len(doc_id) == 16  # "doc_" + 12 hex chars


class TestGenerateChunkId:
    """Tests for generate_chunk_id function."""

    def test_chunk_id_format(self):
        """Test chunk ID format."""
        chunk_id = generate_chunk_id("doc_abc123", 0)

        assert chunk_id == "doc_abc123_0"

    def test_chunk_id_sequential(self):
        """Test sequential chunk IDs."""
        ids = [generate_chunk_id("doc_abc123", i) for i in range(3)]

        assert ids == ["doc_abc123_0", "doc_abc123_1", "doc_abc123_2"]


class TestGetSourceType:
    """Tests for get_source_type function."""

    def test_txt_extension(self, temp_dir: Path):
        """Test .txt extension."""
        file_path = temp_dir / "test.txt"
        assert get_source_type(file_path) == SourceType.TXT

    def test_md_extension(self, temp_dir: Path):
        """Test .md extension."""
        file_path = temp_dir / "test.md"
        assert get_source_type(file_path) == SourceType.MD

    def test_pdf_extension(self, temp_dir: Path):
        """Test .pdf extension."""
        file_path = temp_dir / "test.pdf"
        assert get_source_type(file_path) == SourceType.PDF

    def test_csv_extension(self, temp_dir: Path):
        """Test .csv extension."""
        file_path = temp_dir / "test.csv"
        assert get_source_type(file_path) == SourceType.CSV

    def test_json_extension(self, temp_dir: Path):
        """Test .json extension."""
        file_path = temp_dir / "test.json"
        assert get_source_type(file_path) == SourceType.JSON

    def test_html_extension(self, temp_dir: Path):
        """Test .html extension."""
        file_path = temp_dir / "test.html"
        assert get_source_type(file_path) == SourceType.HTML

    def test_uppercase_extension(self, temp_dir: Path):
        """Test uppercase extension handling."""
        file_path = temp_dir / "test.TXT"
        assert get_source_type(file_path) == SourceType.TXT

    def test_unsupported_extension(self, temp_dir: Path):
        """Test unsupported extension raises error."""
        file_path = temp_dir / "test.xyz"

        with pytest.raises(ValueError, match="Unsupported file extension"):
            get_source_type(file_path)


class TestCDRConverter:
    """Tests for CDRConverter class."""

    def test_converter_init(self, temp_dir: Path):
        """Test converter initialization."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        converter = CDRConverter(file_path)

        assert converter.file_path == file_path
        assert converter.doc_id.startswith("doc_")
        assert converter.source_type == SourceType.TXT

    def test_to_cdr_simple(self, temp_dir: Path):
        """Test converting text segments to CDR chunks."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        converter = CDRConverter(file_path)
        segments = ["Chunk 0 text", "Chunk 1 text", "Chunk 2 text"]

        chunks = converter.to_cdr(segments)

        assert len(chunks) == 3
        assert chunks[0].text == "Chunk 0 text"
        assert chunks[0].chunk_id == f"{converter.doc_id}_0"
        assert chunks[1].chunk_id == f"{converter.doc_id}_1"
        assert chunks[2].chunk_id == f"{converter.doc_id}_2"

    def test_to_cdr_with_page_refs(self, temp_dir: Path):
        """Test CDR conversion with page references."""
        file_path = temp_dir / "test.pdf"
        file_path.touch()

        converter = CDRConverter(file_path)
        segments = ["Page 1 content", "Page 2 content"]
        page_refs = [1, 2]

        chunks = converter.to_cdr(segments, page_refs=page_refs)

        assert chunks[0].page_ref == 1
        assert chunks[1].page_ref == 2

    def test_to_cdr_with_section_paths(self, temp_dir: Path):
        """Test CDR conversion with section paths."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        converter = CDRConverter(file_path)
        segments = ["Section 1", "Section 1.1"]
        section_paths = ["1", "1.1"]

        chunks = converter.to_cdr(segments, section_paths=section_paths)

        assert chunks[0].section_path == "1"
        assert chunks[1].section_path == "1.1"

    def test_to_cdr_with_table_json(self, temp_dir: Path):
        """Test CDR conversion with table JSON."""
        file_path = temp_dir / "test.csv"
        file_path.touch()

        converter = CDRConverter(file_path)
        segments = ["A | B"]
        table_jsons = [{"data": [["A", "B"]]}]

        chunks = converter.to_cdr(segments, table_jsons=table_jsons)

        assert chunks[0].table_json == {"data": [["A", "B"]]}

    def test_to_cdr_length_mismatch(self, temp_dir: Path):
        """Test error when metadata lengths don't match."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        converter = CDRConverter(file_path)
        segments = ["A", "B", "C"]
        page_refs = [1, 2]  # Wrong length

        with pytest.raises(ValueError, match="page_refs length"):
            converter.to_cdr(segments, page_refs=page_refs)

    def test_to_cdr_empty(self, temp_dir: Path):
        """Test converting empty segments."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        converter = CDRConverter(file_path)
        chunks = converter.to_cdr([])

        assert len(chunks) == 0


class TestDocIdStability:
    """Tests for doc_id stability across runs."""

    def test_same_path_same_id(self, temp_dir: Path):
        """Test that same path always produces same doc_id."""
        file_path = temp_dir / "stable.txt"
        file_path.touch()

        ids = [generate_doc_id(file_path) for _ in range(10)]

        assert all(id == ids[0] for id in ids)

    def test_relative_vs_absolute(self, temp_dir: Path):
        """Test that doc_id uses absolute path."""
        file_path = temp_dir / "test.txt"
        file_path.touch()

        # Create relative path
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            relative_path = Path("test.txt")

            id_absolute = generate_doc_id(file_path)
            id_relative = generate_doc_id(relative_path)

            # Both should produce same ID (both resolve to same absolute path)
            assert id_absolute == id_relative
        finally:
            os.chdir(original_cwd)
