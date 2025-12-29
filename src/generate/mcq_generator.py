"""MCQ generation using Gemini API."""

import json
import logging
import random
from dataclasses import dataclass, field

import google.generativeai as genai

from src.config import GenerationConfig, get_gemini_api_key
from src.models import CDRChunk, FailureMode, MCQItem, ReasoningType, Slice

from .evidence import extract_evidence_spans
from .prompts import format_prompt, get_output_schema, get_required_hops

logger = logging.getLogger(__name__)


# Mapping from LLM string output to enum values
REASONING_TYPE_MAP = {
    "factual_lookup": ReasoningType.FACTUAL_LOOKUP,
    "lookup": ReasoningType.FACTUAL_LOOKUP,
    "comparison": ReasoningType.COMPARISON,
    "temporal": ReasoningType.TEMPORAL,
    "temporal_sequence": ReasoningType.TEMPORAL,
    "causal": ReasoningType.CAUSAL,
    "aggregation": ReasoningType.AGGREGATION,
    "procedural": ReasoningType.PROCEDURAL,
    "procedure_step": ReasoningType.PROCEDURAL,
    "cross_reference": ReasoningType.AGGREGATION,  # Map to closest
    "conditional_logic": ReasoningType.PROCEDURAL,
    "exception_handling": ReasoningType.EXCEPTION_HANDLING,
    "precedence": ReasoningType.PRECEDENCE,
    "precedence_rule": ReasoningType.PRECEDENCE,
    "contradiction_resolution": ReasoningType.CONTRADICTION_RESOLUTION,
    "table_prose_join": ReasoningType.AGGREGATION,
    "version_specific": ReasoningType.TEMPORAL,
    "definition": ReasoningType.FACTUAL_LOOKUP,
    "parameter_value": ReasoningType.FACTUAL_LOOKUP,
}

FAILURE_MODE_MAP = {
    "retrieval_miss": FailureMode.RETRIEVAL_MISS,
    "reasoning_miss": FailureMode.REASONING_MISS,
    "benchmark_ambiguity": FailureMode.BENCHMARK_AMBIGUITY,
    "distractor_confusion": FailureMode.DISTRACTOR_CONFUSION,
    "term_confusion": FailureMode.DISTRACTOR_CONFUSION,
    "multi_hop_failure": FailureMode.MULTI_HOP_FAILURE,
    "table_parse_error": FailureMode.TABLE_PARSE_ERROR,
    "table_misread": FailureMode.TABLE_PARSE_ERROR,
    "exception_ignored": FailureMode.REASONING_MISS,
    "procedure_order": FailureMode.REASONING_MISS,
    "version_mismatch": FailureMode.REASONING_MISS,
}


@dataclass
class GenerationResult:
    """Result of MCQ generation for a chunk group."""

    items: list[MCQItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_response: str | None = None


class MCQGenerator:
    """Generates MCQ items using Gemini API."""

    def __init__(
        self,
        config: GenerationConfig | None = None,
        api_key: str | None = None,
    ):
        """Initialize the generator.

        Args:
            config: Generation configuration. Uses defaults if not provided.
            api_key: Gemini API key. Reads from env if not provided.
        """
        self.config = config or GenerationConfig()
        self._api_key = api_key or get_gemini_api_key()
        self._model: genai.GenerativeModel | None = None
        self._qid_counter = 0

    def _get_model(self) -> genai.GenerativeModel:
        """Get or create the Gemini model client."""
        if self._model is None:
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(
                model_name=self.config.model,
                generation_config=genai.GenerationConfig(
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
        return self._model

    def generate(
        self,
        chunks: list[CDRChunk],
        slice_type: Slice,
        num_questions: int | None = None,
        seed: int | None = None,
    ) -> GenerationResult:
        """Generate MCQ items from chunks.

        Args:
            chunks: Source chunks to generate questions from.
            slice_type: Difficulty slice (A, B, or C).
            num_questions: Number of questions to generate. Defaults to config value.
            seed: Random seed for reproducibility.

        Returns:
            GenerationResult with items and any errors.
        """
        if not chunks:
            return GenerationResult(errors=["No chunks provided"])

        if seed is not None:
            random.seed(seed)

        num_q = num_questions or self.config.items_per_chunk_group
        system_prompt, user_prompt = format_prompt(slice_type, chunks, num_q)

        try:
            model = self._get_model()
            response = model.generate_content(
                [
                    {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
                ]
            )
            raw_text = response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return GenerationResult(errors=[f"API error: {str(e)}"])

        return self._parse_response(raw_text, chunks, slice_type)

    def _parse_response(
        self,
        raw_text: str,
        chunks: list[CDRChunk],
        slice_type: Slice,
    ) -> GenerationResult:
        """Parse Gemini response into MCQItem objects.

        Args:
            raw_text: Raw JSON response from Gemini.
            chunks: Source chunks for evidence extraction.
            slice_type: The slice type for labeling.

        Returns:
            GenerationResult with parsed items.
        """
        result = GenerationResult(raw_response=raw_text)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            result.errors.append(f"Failed to parse JSON: {e}")
            return result

        questions = data.get("questions", [])
        if not isinstance(questions, list):
            result.errors.append("Response 'questions' is not a list")
            return result

        # Use first chunk's doc_id for QID generation
        base_doc_id = chunks[0].doc_id if chunks else "unknown"

        for i, q in enumerate(questions):
            try:
                item = self._parse_question(q, chunks, slice_type, base_doc_id)
                if item:
                    result.items.append(item)
            except Exception as e:
                result.errors.append(f"Error parsing question {i}: {e}")

        return result

    def _parse_question(
        self,
        q: dict,
        chunks: list[CDRChunk],
        slice_type: Slice,
        base_doc_id: str,
    ) -> MCQItem | None:
        """Parse a single question dict into an MCQItem.

        Args:
            q: Question dict from LLM response.
            chunks: Source chunks.
            slice_type: The slice type.
            base_doc_id: Base document ID for QID generation.

        Returns:
            MCQItem or None if parsing fails.
        """
        # Validate required fields
        question = q.get("question")
        options = q.get("options", {})
        answer_key = q.get("answer_key")

        if not question or not options or not answer_key:
            return None

        # Validate options structure
        if not all(key in options for key in ["A", "B", "C", "D"]):
            return None

        if answer_key not in ["A", "B", "C", "D"]:
            return None

        # Extract evidence
        gold_evidence_raw = q.get("gold_evidence", [])
        gold_evidence = extract_evidence_spans(gold_evidence_raw, chunks)

        # At least one evidence span required
        if not gold_evidence:
            return None

        # Parse reasoning type
        reasoning_type_str = q.get("reasoning_type", "factual_lookup").lower()
        reasoning_type = REASONING_TYPE_MAP.get(
            reasoning_type_str, ReasoningType.FACTUAL_LOOKUP
        )

        # Parse failure modes
        failure_modes_raw = q.get("failure_modes", ["retrieval_miss"])
        failure_modes = []
        for fm in failure_modes_raw:
            fm_lower = fm.lower() if isinstance(fm, str) else str(fm).lower()
            mapped = FAILURE_MODE_MAP.get(fm_lower)
            if mapped:
                failure_modes.append(mapped)

        # Ensure at least one failure mode
        if not failure_modes:
            failure_modes = [FailureMode.RETRIEVAL_MISS]

        # Generate stable QID
        self._qid_counter += 1
        qid = f"{base_doc_id}_q{self._qid_counter}"

        return MCQItem(
            qid=qid,
            question=question,
            options=options,
            answer_key=answer_key,
            gold_evidence=gold_evidence,
            slice=slice_type,
            required_hops=get_required_hops(slice_type),
            reasoning_type=reasoning_type,
            failure_modes=failure_modes,
        )

    def reset_qid_counter(self) -> None:
        """Reset the QID counter (useful for testing)."""
        self._qid_counter = 0
