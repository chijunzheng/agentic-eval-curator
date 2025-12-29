"""Corpus manifest management for incremental ingestion."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.models import CorpusManifestEntry


class CorpusManifest:
    """Track ingested documents for incremental processing.

    Stores metadata about each ingested document including file hash,
    timestamp, and chunk count to enable skipping unchanged files.
    """

    DEFAULT_PATH = Path("data/corpus_manifest.json")

    def __init__(self, manifest_path: Path | None = None):
        """Initialize corpus manifest.

        Args:
            manifest_path: Path to manifest JSON file. Uses default if None.
        """
        self.manifest_path = manifest_path or self.DEFAULT_PATH
        self._entries: dict[str, CorpusManifestEntry] = {}

    def load(self) -> None:
        """Load manifest from disk.

        Creates empty manifest if file doesn't exist.
        """
        if self.manifest_path.exists():
            with open(self.manifest_path, encoding="utf-8") as f:
                data = json.load(f)

            self._entries = {
                doc_id: CorpusManifestEntry(**entry)
                for doc_id, entry in data.items()
            }
        else:
            self._entries = {}

    def save(self) -> None:
        """Save manifest to disk.

        Creates parent directories if they don't exist.
        """
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            doc_id: entry.model_dump()
            for doc_id, entry in self._entries.items()
        }

        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_entry(self, doc_id: str) -> CorpusManifestEntry | None:
        """Get manifest entry for a document.

        Args:
            doc_id: Document identifier.

        Returns:
            CorpusManifestEntry if exists, None otherwise.
        """
        return self._entries.get(doc_id)

    def update(
        self,
        doc_id: str,
        path: Path,
        checksum: str,
        chunk_count: int,
    ) -> None:
        """Update or add manifest entry for a document.

        Args:
            doc_id: Document identifier.
            path: Original file path.
            checksum: SHA-256 hash of file contents.
            chunk_count: Number of chunks generated.
        """
        self._entries[doc_id] = CorpusManifestEntry(
            path=str(path),
            checksum=checksum,
            timestamp=datetime.now(timezone.utc).isoformat(),
            chunk_count=chunk_count,
        )

    def remove(self, doc_id: str) -> bool:
        """Remove a document from the manifest.

        Args:
            doc_id: Document identifier.

        Returns:
            True if document was removed, False if not found.
        """
        if doc_id in self._entries:
            del self._entries[doc_id]
            return True
        return False

    def is_modified(self, doc_id: str, file_path: Path) -> bool:
        """Check if a file has been modified since last ingestion.

        Args:
            doc_id: Document identifier.
            file_path: Path to the file.

        Returns:
            True if file is new or modified, False if unchanged.
        """
        entry = self._entries.get(doc_id)
        if entry is None:
            return True  # New file

        current_checksum = compute_file_checksum(file_path)
        return current_checksum != entry.checksum

    def list_doc_ids(self) -> list[str]:
        """Get all document IDs in the manifest.

        Returns:
            List of document IDs.
        """
        return list(self._entries.keys())

    def __len__(self) -> int:
        """Return number of documents in manifest."""
        return len(self._entries)

    def __contains__(self, doc_id: str) -> bool:
        """Check if document ID is in manifest."""
        return doc_id in self._entries


def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file.

    Args:
        file_path: Path to the file.

    Returns:
        Hex string of SHA-256 hash.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
