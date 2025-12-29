"""MCQ generation using Gemini API."""

from .evidence import (
    extract_evidence_spans,
    find_span_in_chunk,
    get_evidence_text,
    validate_evidence_spans,
)
from .mcq_generator import GenerationResult, MCQGenerator
from .pipeline import GenerationPipeline, GenerationStats
from .prompts import (
    OUTPUT_SCHEMA,
    SLICE_A_PROMPT,
    SLICE_B_PROMPT,
    SLICE_C_PROMPT,
    SYSTEM_PROMPT,
    format_chunk_data,
    format_prompt,
    get_output_schema,
    get_required_hops,
)

__all__ = [
    # Evidence
    "extract_evidence_spans",
    "find_span_in_chunk",
    "get_evidence_text",
    "validate_evidence_spans",
    # Generator
    "GenerationResult",
    "MCQGenerator",
    # Pipeline
    "GenerationPipeline",
    "GenerationStats",
    # Prompts
    "OUTPUT_SCHEMA",
    "SLICE_A_PROMPT",
    "SLICE_B_PROMPT",
    "SLICE_C_PROMPT",
    "SYSTEM_PROMPT",
    "format_chunk_data",
    "format_prompt",
    "get_output_schema",
    "get_required_hops",
]
