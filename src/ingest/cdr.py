"""Canonical Document Representation conversion utilities."""

import hashlib
from pathlib import Path

from src.models import CDRChunk, SourceType


def generate_doc_id(file_path: Path) -> str:
    """Generate a stable document ID from file path.

    Uses SHA-256 hash of the absolute path to ensure stability across runs.

    Args:
        file_path: Path to the source document.

    Returns:
        Hex string document ID (first 12 characters of hash).
    """
    path_str = str(file_path.resolve())
    hash_digest = hashlib.sha256(path_str.encode()).hexdigest()
    return f"doc_{hash_digest[:12]}"


def generate_chunk_id(doc_id: str, index: int) -> str:
    """Generate a stable chunk ID.

    Args:
        doc_id: Parent document ID.
        index: Zero-based chunk index.

    Returns:
        Chunk ID in format {doc_id}_{index}.
    """
    return f"{doc_id}_{index}"


def get_source_type(file_path: Path) -> SourceType:
    """Determine source type from file extension.

    Args:
        file_path: Path to the document.

    Returns:
        SourceType enum value.

    Raises:
        ValueError: If file extension is not supported.
    """
    extension = file_path.suffix.lower().lstrip(".")
    try:
        return SourceType(extension)
    except ValueError:
        supported = ", ".join(st.value for st in SourceType)
        raise ValueError(
            f"Unsupported file extension: {file_path.suffix}. "
            f"Supported: {supported}"
        )


class CDRConverter:
    """Convert parsed document text into CDR chunks."""

    def __init__(self, file_path: Path):
        """Initialize converter for a specific file.

        Args:
            file_path: Path to the source document.
        """
        self.file_path = file_path
        self.doc_id = generate_doc_id(file_path)
        self.source_type = get_source_type(file_path)

    def to_cdr(
        self,
        text_segments: list[str],
        page_refs: list[int | None] | None = None,
        section_paths: list[str | None] | None = None,
        table_jsons: list[dict | None] | None = None,
    ) -> list[CDRChunk]:
        """Convert text segments to CDR chunks.

        Args:
            text_segments: List of text strings, one per chunk.
            page_refs: Optional list of page numbers (same length as text_segments).
            section_paths: Optional list of section paths.
            table_jsons: Optional list of table JSON data.

        Returns:
            List of CDRChunk objects.
        """
        n = len(text_segments)

        # Default to None lists if not provided
        if page_refs is None:
            page_refs = [None] * n
        if section_paths is None:
            section_paths = [None] * n
        if table_jsons is None:
            table_jsons = [None] * n

        # Validate lengths match
        if len(page_refs) != n:
            raise ValueError(f"page_refs length ({len(page_refs)}) != text_segments length ({n})")
        if len(section_paths) != n:
            raise ValueError(f"section_paths length ({len(section_paths)}) != text_segments length ({n})")
        if len(table_jsons) != n:
            raise ValueError(f"table_jsons length ({len(table_jsons)}) != text_segments length ({n})")

        chunks = []
        for i, text in enumerate(text_segments):
            chunk = CDRChunk(
                doc_id=self.doc_id,
                source_type=self.source_type,
                chunk_id=generate_chunk_id(self.doc_id, i),
                text=text,
                page_ref=page_refs[i],
                section_path=section_paths[i],
                table_json=table_jsons[i],
            )
            chunks.append(chunk)

        return chunks
