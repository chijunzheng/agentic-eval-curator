"""Ingestion pipeline orchestration."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.config import PipelineConfig
from src.ingest.cdr import CDRConverter, generate_doc_id
from src.ingest.chunker import get_chunker
from src.ingest.manifest import CorpusManifest, compute_file_checksum
from src.ingest.parsers import get_parser
from src.ingest.preprocessor import DocumentPreprocessor, PreprocessorConfig
from src.models import CDRChunk, SourceType

logger = logging.getLogger(__name__)


@dataclass
class IngestStats:
    """Statistics from an ingestion run."""

    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    chunks_created: int = 0
    errors: list[str] = field(default_factory=list)


class IngestPipeline:
    """Orchestrate document parsing, chunking, and CDR conversion."""

    SUPPORTED_EXTENSIONS = {f".{st.value}" for st in SourceType}

    def __init__(
        self,
        config: PipelineConfig,
        enable_preprocessing: bool = True,
        use_unstructured_chunker: bool = False,
    ):
        """Initialize ingestion pipeline.

        Args:
            config: Pipeline configuration.
            enable_preprocessing: Whether to preprocess documents before chunking.
            use_unstructured_chunker: Whether to use unstructured.io for chunking.
        """
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.chunks_dir = self.data_dir / "chunks"
        self.manifest = CorpusManifest(self.data_dir / "corpus_manifest.json")
        self.enable_preprocessing = enable_preprocessing
        self.use_unstructured_chunker = use_unstructured_chunker

        # Initialize preprocessor (needed for fallback when using unstructured)
        if enable_preprocessing:
            self.preprocessor = DocumentPreprocessor(PreprocessorConfig(
                remove_toc=True,
                remove_headers_footers=True,
                repair_hyphenation=True,
                remove_page_numbers=True,
                remove_boilerplate=True,
                normalize_whitespace=True,
            ))
        else:
            self.preprocessor = None

    def run(
        self,
        input_dir: Path,
        incremental: bool = False,
        dry_run: bool = False,
    ) -> IngestStats:
        """Run the ingestion pipeline on a directory.

        Args:
            input_dir: Directory containing source documents.
            incremental: If True, skip unchanged files.
            dry_run: If True, don't write any files.

        Returns:
            IngestStats with processing results.
        """
        stats = IngestStats()

        if not input_dir.exists():
            raise ValueError(f"Input directory does not exist: {input_dir}")

        # Load manifest for incremental processing
        if incremental:
            self.manifest.load()

        # Ensure output directory exists
        if not dry_run:
            self.chunks_dir.mkdir(parents=True, exist_ok=True)

        # Find all supported files
        files = self._find_documents(input_dir)
        logger.info(f"Found {len(files)} documents in {input_dir}")

        # Get chunker
        if self.use_unstructured_chunker:
            from src.ingest.unstructured_chunker import UnstructuredChunker
            chunker = UnstructuredChunker(
                max_characters=self.config.chunking.chunk_size * 3,  # Allow larger chunks
                new_after_n_chars=self.config.chunking.chunk_size,
                combine_text_under_n_chars=200,
                overlap=self.config.chunking.chunk_overlap,
            )
            # Also create fallback chunker for unsupported file types
            self._fallback_chunker = get_chunker(
                strategy=self.config.chunking.strategy,
                chunk_size=self.config.chunking.chunk_size,
                overlap=self.config.chunking.chunk_overlap,
            )
        else:
            chunker = get_chunker(
                strategy=self.config.chunking.strategy,
                chunk_size=self.config.chunking.chunk_size,
                overlap=self.config.chunking.chunk_overlap,
            )
            self._fallback_chunker = None

        for file_path in files:
            doc_id = generate_doc_id(file_path)

            # Check if file should be skipped (incremental mode)
            if incremental and not self.manifest.is_modified(doc_id, file_path):
                logger.debug(f"Skipping unchanged file: {file_path}")
                stats.files_skipped += 1
                continue

            try:
                chunks = self._process_file(file_path, chunker)

                if not dry_run:
                    self._save_chunks(doc_id, chunks)
                    checksum = compute_file_checksum(file_path)
                    self.manifest.update(
                        doc_id=doc_id,
                        path=file_path,
                        checksum=checksum,
                        chunk_count=len(chunks),
                    )

                stats.files_processed += 1
                stats.chunks_created += len(chunks)
                logger.info(f"Processed {file_path}: {len(chunks)} chunks")

            except Exception as e:
                error_msg = f"Failed to process {file_path}: {e}"
                logger.error(error_msg)
                stats.errors.append(error_msg)
                stats.files_failed += 1

        # Save manifest
        if not dry_run and (stats.files_processed > 0 or incremental):
            self.manifest.save()

        return stats

    def _find_documents(self, input_dir: Path) -> list[Path]:
        """Find all supported documents in a directory.

        Args:
            input_dir: Directory to search.

        Returns:
            List of file paths with supported extensions.
        """
        files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            files.extend(input_dir.rglob(f"*{ext}"))
        return sorted(files)

    def _process_file(self, file_path: Path, chunker) -> list[CDRChunk]:
        """Process a single file into CDR chunks.

        Args:
            file_path: Path to the document.
            chunker: Chunker instance to use.

        Returns:
            List of CDRChunk objects.
        """
        # For unstructured chunker, use direct file chunking
        # But fall back to default chunker for unsupported file types
        use_unstructured = self.use_unstructured_chunker and hasattr(chunker, 'chunk_file')

        if use_unstructured:
            # Check if file type is supported by unstructured
            ext = file_path.suffix.lower()
            unsupported_extensions = {'.yang'}  # Add more as needed
            if ext in unsupported_extensions:
                use_unstructured = False
                logger.debug(f"Falling back to default chunker for {ext} file: {file_path}")

        if use_unstructured:
            try:
                chunk_metadata_list = chunker.chunk_file(file_path)
            except Exception as e:
                # Fall back to default chunker on error
                logger.warning(f"Unstructured failed for {file_path}, falling back: {e}")
                use_unstructured = False

        if not use_unstructured:
            # Parse document
            parser = get_parser(file_path)
            parse_result = parser.parse(file_path)

            # Preprocess text if enabled
            if self.preprocessor and parse_result.text:
                # Create a new ParseResult with preprocessed text
                from src.ingest.parsers import ParseResult
                preprocessed_text = self.preprocessor.preprocess(
                    parse_result.text,
                    page_texts=parse_result.page_texts,
                )
                parse_result = ParseResult(
                    text=preprocessed_text,
                    page_texts=parse_result.page_texts,
                    tables=parse_result.tables,
                )

            # Chunk content - use fallback chunker if available
            fallback = self._fallback_chunker if hasattr(self, '_fallback_chunker') and self._fallback_chunker else chunker
            chunk_metadata_list = fallback.chunk(parse_result)

        # Apply preprocessing to chunk text (catches unstructured chunker output too)
        if self.preprocessor:
            chunk_metadata_list = self._preprocess_chunks(chunk_metadata_list)

        # Convert to CDR
        converter = CDRConverter(file_path)
        chunks = converter.to_cdr(
            text_segments=[cm.text for cm in chunk_metadata_list],
            page_refs=[cm.page_ref for cm in chunk_metadata_list],
            section_paths=[cm.section_path for cm in chunk_metadata_list],
            table_jsons=[cm.table_json for cm in chunk_metadata_list],
        )

        return chunks

    def _preprocess_chunks(self, chunks: list) -> list:
        """Apply preprocessing to chunk text to remove boilerplate.

        Args:
            chunks: List of ChunkMetadata objects.

        Returns:
            List of ChunkMetadata with cleaned text.
        """
        import re
        from src.ingest.chunker import ChunkMetadata

        # Minimum requirements for a valid chunk
        MIN_CHUNK_LENGTH = 20  # Minimum characters
        MIN_ALPHA_RATIO = 0.3  # At least 30% alphabetic characters

        cleaned_chunks = []
        for chunk in chunks:
            # Preprocess the chunk text
            cleaned_text = self.preprocessor.preprocess(chunk.text, page_texts=None)

            # Skip empty chunks after preprocessing
            if not cleaned_text or not cleaned_text.strip():
                logger.debug("Skipping empty chunk after preprocessing")
                continue

            cleaned_text = cleaned_text.strip()

            # Skip chunks that are too short
            if len(cleaned_text) < MIN_CHUNK_LENGTH:
                logger.debug(f"Skipping short chunk ({len(cleaned_text)} chars): {cleaned_text[:50]!r}")
                continue

            # Skip chunks with insufficient alphabetic content
            # (catches things like "2 2.1 2.2" or "_____ 3")
            alpha_chars = sum(1 for c in cleaned_text if c.isalpha())
            alpha_ratio = alpha_chars / len(cleaned_text) if cleaned_text else 0
            if alpha_ratio < MIN_ALPHA_RATIO:
                logger.debug(f"Skipping low-alpha chunk ({alpha_ratio:.1%}): {cleaned_text[:50]!r}")
                continue

            # Create new chunk with cleaned text
            cleaned_chunks.append(ChunkMetadata(
                text=cleaned_text,
                page_ref=chunk.page_ref,
                section_path=chunk.section_path,
                table_json=chunk.table_json,
            ))

        return cleaned_chunks

    def _save_chunks(self, doc_id: str, chunks: list[CDRChunk]) -> None:
        """Save chunks to JSONL file.

        Args:
            doc_id: Document identifier.
            chunks: List of chunks to save.
        """
        output_path = self.chunks_dir / f"{doc_id}.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(chunk.model_dump_json() + "\n")

    def load_chunks(self, doc_id: str | None = None) -> list[CDRChunk]:
        """Load chunks from disk.

        Args:
            doc_id: If provided, load only this document's chunks.
                   If None, load all chunks.

        Returns:
            List of CDRChunk objects.
        """
        chunks = []

        if doc_id:
            chunk_file = self.chunks_dir / f"{doc_id}.jsonl"
            if chunk_file.exists():
                chunks.extend(self._load_chunk_file(chunk_file))
        else:
            for chunk_file in self.chunks_dir.glob("*.jsonl"):
                chunks.extend(self._load_chunk_file(chunk_file))

        return chunks

    def _load_chunk_file(self, file_path: Path) -> list[CDRChunk]:
        """Load chunks from a single JSONL file.

        Args:
            file_path: Path to JSONL file.

        Returns:
            List of CDRChunk objects.
        """
        chunks = []
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    chunks.append(CDRChunk(**data))
        return chunks
