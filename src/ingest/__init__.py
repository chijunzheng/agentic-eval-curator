"""Document ingestion pipeline: parsing, chunking, CDR conversion."""

from src.ingest.cdr import CDRConverter, generate_chunk_id, generate_doc_id, get_source_type
from src.ingest.chunker import (
    BaseChunker,
    ChunkMetadata,
    FixedWindowChunker,
    SemanticChunker,
    SemanticTableAwareChunker,
    SentenceAwareChunker,
    SentenceTableAwareChunker,
    TableAwareChunker,
    get_chunker,
)
from src.ingest.manifest import CorpusManifest, compute_file_checksum
from src.ingest.parsers import (
    BaseParser,
    CSVParser,
    DocxParser,
    HTMLParser,
    JSONParser,
    ParseResult,
    PDFParser,
    TextParser,
    XlsxParser,
    YangParser,
    get_parser,
)
from src.ingest.pipeline import IngestPipeline, IngestStats
from src.ingest.preprocessor import (
    DocumentPreprocessor,
    PreprocessorConfig,
    get_preprocessor,
)

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
    "DocxParser",
    "XlsxParser",
    "YangParser",
    "ParseResult",
    "get_parser",
    # Preprocessor
    "DocumentPreprocessor",
    "PreprocessorConfig",
    "get_preprocessor",
    # Chunker
    "BaseChunker",
    "ChunkMetadata",
    "FixedWindowChunker",
    "SemanticChunker",
    "SemanticTableAwareChunker",
    "SentenceAwareChunker",
    "SentenceTableAwareChunker",
    "TableAwareChunker",
    "get_chunker",
    # Manifest
    "CorpusManifest",
    "compute_file_checksum",
    # Pipeline
    "IngestPipeline",
    "IngestStats",
]
