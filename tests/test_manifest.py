"""Unit tests for corpus manifest."""

from pathlib import Path

from src.ingest.manifest import CorpusManifest, compute_file_checksum


class TestComputeFileChecksum:
    """Tests for compute_file_checksum function."""

    def test_checksum_same_content(self, temp_dir: Path):
        """Test that same content produces same checksum."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        content = "Hello, world!"
        file1.write_text(content)
        file2.write_text(content)

        checksum1 = compute_file_checksum(file1)
        checksum2 = compute_file_checksum(file2)

        assert checksum1 == checksum2

    def test_checksum_different_content(self, temp_dir: Path):
        """Test that different content produces different checksum."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("Content A")
        file2.write_text("Content B")

        checksum1 = compute_file_checksum(file1)
        checksum2 = compute_file_checksum(file2)

        assert checksum1 != checksum2

    def test_checksum_is_hex(self, temp_dir: Path):
        """Test that checksum is a hex string."""
        file_path = temp_dir / "test.txt"
        file_path.write_text("test")

        checksum = compute_file_checksum(file_path)

        assert all(c in "0123456789abcdef" for c in checksum)
        assert len(checksum) == 64  # SHA-256 produces 64 hex chars


class TestCorpusManifest:
    """Tests for CorpusManifest class."""

    def test_empty_manifest(self, temp_dir: Path):
        """Test creating empty manifest."""
        manifest = CorpusManifest(temp_dir / "manifest.json")

        assert len(manifest) == 0
        assert manifest.list_doc_ids() == []

    def test_load_nonexistent(self, temp_dir: Path):
        """Test loading nonexistent manifest creates empty."""
        manifest = CorpusManifest(temp_dir / "nonexistent.json")
        manifest.load()

        assert len(manifest) == 0

    def test_save_and_load(self, temp_dir: Path):
        """Test saving and loading manifest."""
        manifest_path = temp_dir / "manifest.json"

        # Create and save
        manifest1 = CorpusManifest(manifest_path)
        manifest1.update(
            doc_id="doc_123",
            path=temp_dir / "test.txt",
            checksum="abc123",
            chunk_count=5,
        )
        manifest1.save()

        # Load in new instance
        manifest2 = CorpusManifest(manifest_path)
        manifest2.load()

        assert len(manifest2) == 1
        assert "doc_123" in manifest2
        entry = manifest2.get_entry("doc_123")
        assert entry.checksum == "abc123"
        assert entry.chunk_count == 5

    def test_update_existing(self, temp_dir: Path):
        """Test updating existing entry."""
        manifest = CorpusManifest(temp_dir / "manifest.json")

        manifest.update("doc_1", Path("path1"), "hash1", 10)
        manifest.update("doc_1", Path("path1"), "hash2", 15)

        assert len(manifest) == 1
        entry = manifest.get_entry("doc_1")
        assert entry.checksum == "hash2"
        assert entry.chunk_count == 15

    def test_remove(self, temp_dir: Path):
        """Test removing entry."""
        manifest = CorpusManifest(temp_dir / "manifest.json")
        manifest.update("doc_1", Path("path"), "hash", 5)

        result = manifest.remove("doc_1")

        assert result is True
        assert len(manifest) == 0
        assert "doc_1" not in manifest

    def test_remove_nonexistent(self, temp_dir: Path):
        """Test removing nonexistent entry."""
        manifest = CorpusManifest(temp_dir / "manifest.json")

        result = manifest.remove("nonexistent")

        assert result is False

    def test_is_modified_new_file(self, temp_dir: Path):
        """Test is_modified returns True for new file."""
        manifest = CorpusManifest(temp_dir / "manifest.json")
        file_path = temp_dir / "new.txt"
        file_path.write_text("content")

        assert manifest.is_modified("doc_new", file_path) is True

    def test_is_modified_unchanged(self, temp_dir: Path):
        """Test is_modified returns False for unchanged file."""
        manifest = CorpusManifest(temp_dir / "manifest.json")
        file_path = temp_dir / "unchanged.txt"
        file_path.write_text("content")

        checksum = compute_file_checksum(file_path)
        manifest.update("doc_1", file_path, checksum, 5)

        assert manifest.is_modified("doc_1", file_path) is False

    def test_is_modified_changed(self, temp_dir: Path):
        """Test is_modified returns True for changed file."""
        manifest = CorpusManifest(temp_dir / "manifest.json")
        file_path = temp_dir / "changed.txt"
        file_path.write_text("original")

        checksum = compute_file_checksum(file_path)
        manifest.update("doc_1", file_path, checksum, 5)

        # Modify the file
        file_path.write_text("modified")

        assert manifest.is_modified("doc_1", file_path) is True

    def test_list_doc_ids(self, temp_dir: Path):
        """Test listing all doc IDs."""
        manifest = CorpusManifest(temp_dir / "manifest.json")
        manifest.update("doc_a", Path("a"), "h1", 1)
        manifest.update("doc_b", Path("b"), "h2", 2)
        manifest.update("doc_c", Path("c"), "h3", 3)

        doc_ids = manifest.list_doc_ids()

        assert set(doc_ids) == {"doc_a", "doc_b", "doc_c"}

    def test_contains(self, temp_dir: Path):
        """Test __contains__ method."""
        manifest = CorpusManifest(temp_dir / "manifest.json")
        manifest.update("doc_1", Path("path"), "hash", 5)

        assert "doc_1" in manifest
        assert "doc_2" not in manifest

    def test_get_entry_nonexistent(self, temp_dir: Path):
        """Test get_entry returns None for missing doc."""
        manifest = CorpusManifest(temp_dir / "manifest.json")

        assert manifest.get_entry("nonexistent") is None

    def test_creates_parent_dirs(self, temp_dir: Path):
        """Test that save creates parent directories."""
        manifest_path = temp_dir / "subdir" / "nested" / "manifest.json"
        manifest = CorpusManifest(manifest_path)
        manifest.update("doc_1", Path("path"), "hash", 5)

        manifest.save()

        assert manifest_path.exists()
