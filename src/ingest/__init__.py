"""Document ingestion pipeline: parsing, chunking, CDR conversion."""

from src.ingest.cdr import CDRConverter, generate_chunk_id, generate_doc_id, get_source_type
from src.ingest.chunker import (
    BaseChunker,
    ChunkMetadata,
    FixedWindowChunker,
    SemanticChunker,
    TableAwareChunker,
    get_chunker,
)
from src.ingest.manifest import CorpusManifest, compute_file_checksum
from src.ingest.parsers import (
    BaseParser,
    CSVParser,
    HTMLParser,
    JSONParser,
    ParseResult,
    PDFParser,
    TextParser,
    get_parser,
)
from src.ingest.pipeline import IngestPipeline, IngestStats

__all__ = [
    # CDR
    "CDRConverter",
    "generate_doc_id",
    "generate_chunk_id",
    "get_source_type",
    # Parsers
    "BaseParser",
    "TextParser",
    "PDFParser",
    "CSVParser",
    "JSONParser",
    "HTMLParser",
    "ParseResult",
    "get_parser",
    # Chunker
    "BaseChunker",
    "ChunkMetadata",
    "FixedWindowChunker",
    "SemanticChunker",
    "TableAwareChunker",
    "get_chunker",
    # Manifest
    "CorpusManifest",
    "compute_file_checksum",
    # Pipeline
    "IngestPipeline",
    "IngestStats",
]
