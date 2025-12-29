"""Pydantic models for the agentic eval curator pipeline."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Supported document source types."""

    TXT = "txt"
    MD = "md"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"
    HTML = "html"


class Slice(str, Enum):
    """Difficulty slice categories."""

    A = "A"  # 1-hop lookup
    B = "B"  # 2-hop compositional
    C = "C"  # Hard agentic (exceptions, precedence, contradictions, table+prose)


class ReasoningType(str, Enum):
    """Types of reasoning required to answer the question."""

    FACTUAL_LOOKUP = "factual_lookup"
    COMPARISON = "comparison"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    AGGREGATION = "aggregation"
    PROCEDURAL = "procedural"
    EXCEPTION_HANDLING = "exception_handling"
    PRECEDENCE = "precedence"
    CONTRADICTION_RESOLUTION = "contradiction_resolution"


class FailureMode(str, Enum):
    """Potential failure modes for RAG systems."""

    RETRIEVAL_MISS = "retrieval_miss"
    REASONING_MISS = "reasoning_miss"
    BENCHMARK_AMBIGUITY = "benchmark_ambiguity"
    DISTRACTOR_CONFUSION = "distractor_confusion"
    MULTI_HOP_FAILURE = "multi_hop_failure"
    TABLE_PARSE_ERROR = "table_parse_error"


class CDRChunk(BaseModel):
    """Canonical Document Representation chunk."""

    doc_id: str = Field(..., description="Unique document identifier (hash of source path)")
    source_type: SourceType = Field(..., description="Original document format")
    chunk_id: str = Field(..., description="Unique chunk identifier ({doc_id}_{index})")
    text: str = Field(..., description="Chunk text content")
    page_ref: int | None = Field(default=None, description="Page number for PDFs")
    section_path: str | None = Field(default=None, description="Section hierarchy path")
    table_json: dict[str, Any] | None = Field(default=None, description="Structured table data")


class GoldEvidence(BaseModel):
    """Reference to source text that supports the correct answer."""

    doc_id: str = Field(..., description="Document containing the evidence")
    chunk_id: str = Field(..., description="Chunk containing the evidence")
    char_start: int | None = Field(default=None, description="Start character offset in chunk")
    char_end: int | None = Field(default=None, description="End character offset in chunk")
    page_ref: int | None = Field(default=None, description="Page number if applicable")


class MCQItem(BaseModel):
    """A single multiple-choice question item."""

    qid: str = Field(..., description="Unique question ID ({doc_id}_{index})")
    question: str = Field(..., description="The question text")
    options: dict[str, str] = Field(
        ..., description="Answer options keyed by A, B, C, D"
    )
    answer_key: str = Field(..., pattern="^[A-D]$", description="Correct answer (A/B/C/D)")
    gold_evidence: list[GoldEvidence] = Field(
        ..., description="Evidence spans supporting the answer"
    )
    slice: Slice = Field(..., description="Difficulty slice (A/B/C)")
    required_hops: int = Field(..., ge=1, le=3, description="Number of reasoning hops (1-3)")
    reasoning_type: ReasoningType = Field(..., description="Primary reasoning type required")
    failure_modes: list[FailureMode] = Field(
        ..., min_length=1, description="Potential failure modes"
    )


class FrozenContext(BaseModel):
    """Pre-determined retrieval context for frozen retrieval evaluation."""

    qid: str = Field(..., description="Question ID this context belongs to")
    chunks: list[dict[str, str]] = Field(
        ..., description="List of {chunk_id, text} for gold + distractor chunks"
    )


class ValidationResult(BaseModel):
    """Result of validating a single MCQ item."""

    qid: str = Field(..., description="Question ID")
    passed: bool = Field(..., description="Whether all validation rules passed")
    failed_rules: list[str] = Field(default_factory=list, description="Names of failed rules")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking warnings")


class CorpusManifestEntry(BaseModel):
    """Metadata for a single ingested document."""

    path: str = Field(..., description="Original file path")
    checksum: str = Field(..., description="SHA-256 hash of file contents")
    timestamp: str = Field(..., description="ISO format ingestion timestamp")
    chunk_count: int = Field(..., description="Number of chunks generated")
