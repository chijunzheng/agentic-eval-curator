"""Prompt templates for MCQ generation by slice."""

from typing import Any

from src.models import CDRChunk, Slice


# Output schema for Gemini JSON mode
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "object",
                        "properties": {
                            "A": {"type": "string"},
                            "B": {"type": "string"},
                            "C": {"type": "string"},
                            "D": {"type": "string"},
                        },
                        "required": ["A", "B", "C", "D"],
                    },
                    "answer_key": {"type": "string", "enum": ["A", "B", "C", "D"]},
                    "gold_evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "text_span": {"type": "string"},
                            },
                            "required": ["chunk_id", "text_span"],
                        },
                    },
                    "reasoning_type": {"type": "string"},
                    "failure_modes": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "question",
                    "options",
                    "answer_key",
                    "gold_evidence",
                    "reasoning_type",
                    "failure_modes",
                ],
            },
        }
    },
    "required": ["questions"],
}

# System prompt shared across all slices
SYSTEM_PROMPT = """You are an expert benchmark creator for evaluating RAG (Retrieval-Augmented Generation) systems. Your task is to generate high-quality multiple-choice questions (MCQs) from technical documentation.

Each question must:
1. Have exactly 4 options (A, B, C, D) with ONE correct answer
2. Include gold evidence spans that directly support the correct answer
3. Have plausible distractors that are wrong but sound reasonable
4. Be unambiguous - the correct answer must be clearly supported by the source text

Quality guidelines for distractors:
- Must be plausible (sound reasonable to someone unfamiliar with the content)
- Must be distinct from the correct answer (not too similar)
- Should map to potential failure modes (e.g., term confusion, procedure order mix-up)
- Must have consistent grammatical structure with the correct answer
- Avoid "None of the above" or "All of the above"

Output your response as valid JSON matching the required schema."""


# Slice A: 1-hop factual lookup
SLICE_A_PROMPT = """Generate {num_questions} 1-hop factual lookup questions from the following document chunk(s).

1-hop questions test DIRECT fact retrieval from a single location:
- Definitions: "What is the definition of X?"
- Parameter values: "What is the default value of Y?"
- Acronym expansions: "What does ABC stand for?"
- Simple lookups: "Which entity performs action Z?"

Requirements:
- Evidence should be a SINGLE contiguous span from ONE chunk
- The answer must be explicitly stated in the text (no inference required)
- Distractors should be plausible alternatives (e.g., different parameter values, similar terms)

Reasoning types to use: factual_lookup, comparison, procedural
Failure modes to label: retrieval_miss, reasoning_miss, distractor_confusion

CHUNK DATA:
{chunk_data}

Generate {num_questions} questions in the required JSON format."""


# Slice B: 2-hop compositional reasoning
SLICE_B_PROMPT = """Generate {num_questions} 2-hop compositional reasoning questions from the following document chunk(s).

2-hop questions require COMBINING information from 2 different locations:
- Cross-reference: "If X is configured as Y, what is the result of Z?"
- Multi-step procedures: "After A sends message B to C, what does C respond?"
- Combined constraints: "Given constraint X from section 1 and constraint Y from section 2, what is allowed?"

Requirements:
- Evidence should come from 2 DIFFERENT chunks or 2 distinct parts of the same chunk
- The answer requires synthesizing both pieces of information
- Distractors may be correct for ONE chunk but wrong when both are considered

Reasoning types to use: cross_reference, temporal, causal, procedural
Failure modes to label: retrieval_miss, reasoning_miss, multi_hop_failure

CHUNK DATA:
{chunk_data}

Generate {num_questions} questions in the required JSON format."""


# Slice C: Hard agentic (exceptions, precedence, contradictions)
SLICE_C_PROMPT = """Generate {num_questions} hard agentic questions from the following document chunk(s).

Hard agentic questions test handling of EXCEPTIONS, PRECEDENCE, and EDGE CASES:
- Exception handling: "If both X and Y apply, but exception Z is triggered, what happens?"
- Precedence rules: "When rule A conflicts with rule B, which takes priority?"
- Conditional overrides: "The table shows A, but the note says B when condition C is met. What is correct?"
- Table+prose joins: "Combining the value from table row X with the procedure in paragraph Y, what is the result?"
- Version-specific behavior: "In Release X, procedure A was replaced by B. What is the current behavior?"

Requirements:
- Evidence typically comes from 2-3 chunks including exception clauses, notes, or override conditions
- Distractors should be "almost right" - correct for the general case but wrong for the exception
- Questions should target scenarios where simple retrieval would give the wrong answer

Reasoning types to use: exception_handling, precedence, contradiction_resolution, causal, temporal
Failure modes to label: exception_ignored, reasoning_miss, table_parse_error, multi_hop_failure

CHUNK DATA:
{chunk_data}

Generate {num_questions} questions in the required JSON format."""


SLICE_PROMPTS = {
    Slice.A: SLICE_A_PROMPT,
    Slice.B: SLICE_B_PROMPT,
    Slice.C: SLICE_C_PROMPT,
}


def format_chunk_data(chunks: list[CDRChunk]) -> str:
    """Format chunks into a string for prompt inclusion.

    Args:
        chunks: List of CDRChunk objects to format.

    Returns:
        Formatted string with chunk IDs and text.
    """
    formatted_parts = []
    for chunk in chunks:
        header = f"[CHUNK_ID: {chunk.chunk_id}]"
        if chunk.page_ref is not None:
            header += f" [PAGE: {chunk.page_ref}]"
        if chunk.section_path:
            header += f" [SECTION: {chunk.section_path}]"
        formatted_parts.append(f"{header}\n{chunk.text}")
    return "\n\n---\n\n".join(formatted_parts)


def format_prompt(
    slice_type: Slice,
    chunks: list[CDRChunk],
    num_questions: int = 3,
) -> tuple[str, str]:
    """Format a prompt for MCQ generation.

    Args:
        slice_type: The difficulty slice (A, B, or C).
        chunks: List of chunks to use as source material.
        num_questions: Number of questions to generate.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    chunk_data = format_chunk_data(chunks)
    user_template = SLICE_PROMPTS[slice_type]
    user_prompt = user_template.format(
        num_questions=num_questions,
        chunk_data=chunk_data,
    )
    return SYSTEM_PROMPT, user_prompt


def get_required_hops(slice_type: Slice) -> int:
    """Get the required hops for a slice type.

    Args:
        slice_type: The difficulty slice.

    Returns:
        Number of required hops (1, 2, or 3).
    """
    return {
        Slice.A: 1,
        Slice.B: 2,
        Slice.C: 3,  # Slice C is 2-3 hops, we use 3 as default
    }[slice_type]


def get_output_schema() -> dict[str, Any]:
    """Get the JSON output schema for Gemini.

    Returns:
        Schema dictionary for structured output.
    """
    return OUTPUT_SCHEMA
