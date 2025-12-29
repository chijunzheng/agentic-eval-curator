"""Tests for MCQ generation with mocked Gemini API."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.config import GenerationConfig
from src.generate.mcq_generator import (
    FAILURE_MODE_MAP,
    REASONING_TYPE_MAP,
    GenerationResult,
    MCQGenerator,
)
from src.generate.prompts import format_chunk_data, format_prompt, get_required_hops
from src.models import CDRChunk, FailureMode, ReasoningType, Slice, SourceType


@pytest.fixture
def sample_chunks() -> list[CDRChunk]:
    """Sample chunks for testing."""
    return [
        CDRChunk(
            doc_id="test_doc",
            source_type=SourceType.TXT,
            chunk_id="test_doc_0",
            text="Timer T300 has a default value of 1000ms. It is started upon RRCSetupRequest transmission.",
        ),
        CDRChunk(
            doc_id="test_doc",
            source_type=SourceType.TXT,
            chunk_id="test_doc_1",
            text="If the UE does not receive RRCSetup within T300, it shall abort the connection attempt.",
        ),
    ]


@pytest.fixture
def valid_api_response() -> str:
    """Valid JSON response from API."""
    return json.dumps({
        "questions": [
            {
                "question": "What is the default value of Timer T300?",
                "options": {
                    "A": "500ms",
                    "B": "1000ms",
                    "C": "1500ms",
                    "D": "2000ms",
                },
                "answer_key": "B",
                "gold_evidence": [
                    {
                        "chunk_id": "test_doc_0",
                        "text_span": "default value of 1000ms",
                    }
                ],
                "reasoning_type": "factual_lookup",
                "failure_modes": ["retrieval_miss", "distractor_confusion"],
            }
        ]
    })


@pytest.fixture
def multi_question_response() -> str:
    """Response with multiple questions."""
    return json.dumps({
        "questions": [
            {
                "question": "What is Timer T300's default value?",
                "options": {"A": "500ms", "B": "1000ms", "C": "1500ms", "D": "2000ms"},
                "answer_key": "B",
                "gold_evidence": [{"chunk_id": "test_doc_0", "text_span": "1000ms"}],
                "reasoning_type": "lookup",
                "failure_modes": ["retrieval_miss"],
            },
            {
                "question": "What happens if RRCSetup is not received within T300?",
                "options": {
                    "A": "UE retries",
                    "B": "UE aborts connection",
                    "C": "Timer restarts",
                    "D": "UE waits indefinitely",
                },
                "answer_key": "B",
                "gold_evidence": [{"chunk_id": "test_doc_1", "text_span": "abort the connection attempt"}],
                "reasoning_type": "conditional_logic",
                "failure_modes": ["reasoning_miss"],
            },
        ]
    })


class TestPrompts:
    """Tests for prompt formatting."""

    def test_format_chunk_data_single(self, sample_chunks: list[CDRChunk]):
        """Format single chunk."""
        result = format_chunk_data([sample_chunks[0]])

        assert "test_doc_0" in result
        assert "Timer T300" in result

    def test_format_chunk_data_multiple(self, sample_chunks: list[CDRChunk]):
        """Format multiple chunks with separator."""
        result = format_chunk_data(sample_chunks)

        assert "test_doc_0" in result
        assert "test_doc_1" in result
        assert "---" in result  # Separator

    def test_format_chunk_data_with_metadata(self):
        """Include page_ref and section_path in format."""
        chunk = CDRChunk(
            doc_id="doc",
            source_type=SourceType.PDF,
            chunk_id="doc_0",
            text="Content here",
            page_ref=42,
            section_path="3.1.2",
        )
        result = format_chunk_data([chunk])

        assert "[PAGE: 42]" in result
        assert "[SECTION: 3.1.2]" in result

    def test_format_prompt_slice_a(self, sample_chunks: list[CDRChunk]):
        """Format Slice A prompt."""
        system, user = format_prompt(Slice.A, sample_chunks, num_questions=3)

        assert "1-hop" in user.lower()
        assert "factual" in user.lower() or "lookup" in user.lower()
        assert "3 questions" in user or "{num_questions}" not in user

    def test_format_prompt_slice_b(self, sample_chunks: list[CDRChunk]):
        """Format Slice B prompt."""
        system, user = format_prompt(Slice.B, sample_chunks, num_questions=2)

        assert "2-hop" in user.lower()
        assert "compositional" in user.lower() or "combining" in user.lower()

    def test_format_prompt_slice_c(self, sample_chunks: list[CDRChunk]):
        """Format Slice C prompt."""
        system, user = format_prompt(Slice.C, sample_chunks, num_questions=1)

        assert "exception" in user.lower() or "precedence" in user.lower()
        assert "agentic" in user.lower() or "edge case" in user.lower()

    def test_get_required_hops(self):
        """Get correct hop counts for each slice."""
        assert get_required_hops(Slice.A) == 1
        assert get_required_hops(Slice.B) == 2
        assert get_required_hops(Slice.C) == 3


class TestMCQGenerator:
    """Tests for MCQ generator with mocked API."""

    @patch("src.generate.mcq_generator.genai")
    def test_generate_basic(
        self,
        mock_genai,
        sample_chunks: list[CDRChunk],
        valid_api_response: str,
    ):
        """Generate MCQ items from chunks."""
        # Setup mock
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = valid_api_response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert isinstance(result, GenerationResult)
        assert len(result.items) == 1
        assert result.items[0].question == "What is the default value of Timer T300?"
        assert result.items[0].answer_key == "B"
        assert result.items[0].slice == Slice.A
        assert result.items[0].required_hops == 1

    @patch("src.generate.mcq_generator.genai")
    def test_generate_multiple_questions(
        self,
        mock_genai,
        sample_chunks: list[CDRChunk],
        multi_question_response: str,
    ):
        """Generate multiple questions per chunk group."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = multi_question_response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.B, num_questions=2)

        assert len(result.items) == 2
        assert result.items[0].slice == Slice.B
        assert result.items[1].slice == Slice.B

    @patch("src.generate.mcq_generator.genai")
    def test_qid_generation(
        self,
        mock_genai,
        sample_chunks: list[CDRChunk],
        valid_api_response: str,
    ):
        """Generate stable QIDs based on doc_id."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = valid_api_response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert result.items[0].qid.startswith("test_doc_")
        assert "_q" in result.items[0].qid

    @patch("src.generate.mcq_generator.genai")
    def test_evidence_extraction(
        self,
        mock_genai,
        sample_chunks: list[CDRChunk],
        valid_api_response: str,
    ):
        """Extract gold evidence spans correctly."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = valid_api_response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert len(result.items[0].gold_evidence) == 1
        evidence = result.items[0].gold_evidence[0]
        assert evidence.chunk_id == "test_doc_0"
        assert evidence.char_start is not None
        assert evidence.char_end is not None

    @patch("src.generate.mcq_generator.genai")
    def test_reasoning_type_mapping(
        self,
        mock_genai,
        sample_chunks: list[CDRChunk],
    ):
        """Map LLM reasoning types to enums."""
        response = json.dumps({
            "questions": [
                {
                    "question": "Test?",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                    "answer_key": "A",
                    "gold_evidence": [{"chunk_id": "test_doc_0", "text_span": "Timer"}],
                    "reasoning_type": "exception_handling",
                    "failure_modes": ["reasoning_miss"],
                }
            ]
        })

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.C)

        assert result.items[0].reasoning_type == ReasoningType.EXCEPTION_HANDLING

    @patch("src.generate.mcq_generator.genai")
    def test_failure_mode_mapping(
        self,
        mock_genai,
        sample_chunks: list[CDRChunk],
        valid_api_response: str,
    ):
        """Map LLM failure modes to enums."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = valid_api_response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert FailureMode.RETRIEVAL_MISS in result.items[0].failure_modes
        assert FailureMode.DISTRACTOR_CONFUSION in result.items[0].failure_modes

    @patch("src.generate.mcq_generator.genai")
    def test_api_error_handling(self, mock_genai, sample_chunks: list[CDRChunk]):
        """Handle API errors gracefully."""
        mock_genai.GenerativeModel.side_effect = Exception("API Error")

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert len(result.items) == 0
        assert len(result.errors) > 0
        assert "API error" in result.errors[0]

    @patch("src.generate.mcq_generator.genai")
    def test_invalid_json_handling(self, mock_genai, sample_chunks: list[CDRChunk]):
        """Handle invalid JSON response."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "not valid json"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert len(result.items) == 0
        assert len(result.errors) > 0
        assert "JSON" in result.errors[0]

    @patch("src.generate.mcq_generator.genai")
    def test_missing_required_fields(self, mock_genai, sample_chunks: list[CDRChunk]):
        """Skip questions with missing required fields."""
        response = json.dumps({
            "questions": [
                {
                    "question": "Valid question?",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                    "answer_key": "A",
                    "gold_evidence": [{"chunk_id": "test_doc_0", "text_span": "Timer"}],
                    "reasoning_type": "lookup",
                    "failure_modes": ["retrieval_miss"],
                },
                {
                    # Missing question field
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                    "answer_key": "A",
                },
            ]
        })

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert len(result.items) == 1  # Only valid question

    @patch("src.generate.mcq_generator.genai")
    def test_invalid_answer_key(self, mock_genai, sample_chunks: list[CDRChunk]):
        """Skip questions with invalid answer key."""
        response = json.dumps({
            "questions": [
                {
                    "question": "Test?",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                    "answer_key": "E",  # Invalid
                    "gold_evidence": [{"chunk_id": "test_doc_0", "text_span": "Timer"}],
                    "reasoning_type": "lookup",
                    "failure_modes": ["retrieval_miss"],
                }
            ]
        })

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")
        result = generator.generate(sample_chunks, Slice.A)

        assert len(result.items) == 0

    @patch("src.generate.mcq_generator.genai")
    def test_empty_chunks(self, mock_genai):
        """Handle empty chunk list."""
        generator = MCQGenerator(api_key="test_key")
        result = generator.generate([], Slice.A)

        assert len(result.items) == 0
        assert len(result.errors) > 0
        assert "No chunks" in result.errors[0]

    @patch("src.generate.mcq_generator.genai")
    def test_reset_qid_counter(
        self,
        mock_genai,
        sample_chunks: list[CDRChunk],
        valid_api_response: str,
    ):
        """Reset QID counter between runs."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = valid_api_response
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        generator = MCQGenerator(api_key="test_key")

        # First generation
        result1 = generator.generate(sample_chunks, Slice.A)
        qid1 = result1.items[0].qid

        # Second generation without reset
        result2 = generator.generate(sample_chunks, Slice.A)
        qid2 = result2.items[0].qid
        assert qid1 != qid2

        # Reset and generate again
        generator.reset_qid_counter()
        result3 = generator.generate(sample_chunks, Slice.A)
        qid3 = result3.items[0].qid
        assert qid3 == qid1

    def test_config_defaults(self):
        """Use default config if not provided."""
        with patch("src.generate.mcq_generator.get_gemini_api_key", return_value="test"):
            generator = MCQGenerator()
            assert generator.config.model == "gemini-2.5-flash"
            assert generator.config.temperature == 0.7


class TestReasoningTypeMap:
    """Tests for reasoning type mapping."""

    def test_all_expected_types_mapped(self):
        """Ensure all expected LLM outputs are mapped."""
        expected_keys = [
            "factual_lookup", "lookup", "comparison", "temporal",
            "causal", "aggregation", "procedural", "exception_handling",
            "precedence", "contradiction_resolution", "definition",
        ]
        for key in expected_keys:
            assert key in REASONING_TYPE_MAP


class TestFailureModeMap:
    """Tests for failure mode mapping."""

    def test_all_expected_modes_mapped(self):
        """Ensure all expected LLM outputs are mapped."""
        expected_keys = [
            "retrieval_miss", "reasoning_miss", "benchmark_ambiguity",
            "distractor_confusion", "multi_hop_failure", "table_parse_error",
        ]
        for key in expected_keys:
            assert key in FAILURE_MODE_MAP
