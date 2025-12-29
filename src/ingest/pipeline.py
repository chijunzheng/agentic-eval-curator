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

    def __init__(self, config: PipelineConfig):
        """Initialize ingestion pipeline.

        Args:
            config: Pipeline configuration.
        """
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.chunks_dir = self.data_dir / "chunks"
        self.manifest = CorpusManifest(self.data_dir / "corpus_manifest.json")

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
        chunker = get_chunker(
            strategy=self.config.chunking.strategy,
            chunk_size=self.config.chunking.chunk_size,
            overlap=self.config.chunking.chunk_overlap,
        )

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
        # Parse document
        parser = get_parser(file_path)
        parse_result = parser.parse(file_path)

        # Chunk content
        chunk_metadata_list = chunker.chunk(parse_result)

        # Convert to CDR
        converter = CDRConverter(file_path)
        chunks = converter.to_cdr(
            text_segments=[cm.text for cm in chunk_metadata_list],
            page_refs=[cm.page_ref for cm in chunk_metadata_list],
            section_paths=[cm.section_path for cm in chunk_metadata_list],
            table_jsons=[cm.table_json for cm in chunk_metadata_list],
        )

        return chunks

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
