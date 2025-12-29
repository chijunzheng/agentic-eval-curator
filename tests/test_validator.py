"""Unit tests for validation rules, validator, and pipeline."""

import json
import tempfile
from pathlib import Path

import pytest

from src.models import (
    CDRChunk,
    FailureMode,
    GoldEvidence,
    MCQItem,
    ReasoningType,
    Slice,
    SourceType,
)
from src.validate.pipeline import ValidationPipeline, ValidationStats
from src.validate.rules import (
    AVAILABLE_RULES,
    AmbiguityRule,
    EvidenceCountRule,
    EvidenceExistsRule,
    HopCountRule,
    OptionsCompleteRule,
    SingleAnswerRule,
    get_default_rules,
    get_rule,
)
from src.validate.validator import ValidationReport, Validator


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def chunks_dict() -> dict[str, CDRChunk]:
    """Provide chunks as a dictionary for validation."""
    return {
        "doc_abc123_0": CDRChunk(
            doc_id="doc_abc123",
            source_type=SourceType.TXT,
            chunk_id="doc_abc123_0",
            text="The 3GPP Release 18 specification defines the maximum UE transmit power as 23 dBm for FR1 bands.",
        ),
        "doc_abc123_1": CDRChunk(
            doc_id="doc_abc123",
            source_type=SourceType.TXT,
            chunk_id="doc_abc123_1",
            text="For FR2 bands, the maximum transmit power is reduced to 22 dBm due to thermal constraints.",
        ),
        "doc_def456_0": CDRChunk(
            doc_id="doc_def456",
            source_type=SourceType.PDF,
            chunk_id="doc_def456_0",
            text="O-RAN fronthaul interface uses eCPRI protocol for communication between O-DU and O-RU.",
            page_ref=42,
        ),
    }


@pytest.fixture
def valid_mcq_item() -> MCQItem:
    """Provide a valid MCQ item that passes all rules."""
    return MCQItem(
        qid="doc_abc123_q1",
        question="What is the maximum UE transmit power for FR1 bands?",
        options={
            "A": "20 dBm",
            "B": "23 dBm",
            "C": "26 dBm",
            "D": "30 dBm",
        },
        answer_key="B",
        gold_evidence=[
            GoldEvidence(
                doc_id="doc_abc123",
                chunk_id="doc_abc123_0",
                char_start=70,
                char_end=76,
            )
        ],
        slice=Slice.A,
        required_hops=1,
        reasoning_type=ReasoningType.FACTUAL_LOOKUP,
        failure_modes=[FailureMode.RETRIEVAL_MISS],
    )


@pytest.fixture
def two_hop_mcq_item() -> MCQItem:
    """Provide a valid 2-hop MCQ item."""
    return MCQItem(
        qid="doc_abc123_q2",
        question="What is the difference in max transmit power between FR1 and FR2 bands?",
        options={
            "A": "0 dBm",
            "B": "1 dBm",
            "C": "2 dBm",
            "D": "3 dBm",
        },
        answer_key="B",
        gold_evidence=[
            GoldEvidence(
                doc_id="doc_abc123",
                chunk_id="doc_abc123_0",
                char_start=70,
                char_end=76,
            ),
            GoldEvidence(
                doc_id="doc_abc123",
                chunk_id="doc_abc123_1",
                char_start=45,
                char_end=51,
            ),
        ],
        slice=Slice.B,
        required_hops=2,
        reasoning_type=ReasoningType.COMPARISON,
        failure_modes=[FailureMode.MULTI_HOP_FAILURE],
    )


# ============================================================================
# SingleAnswerRule Tests
# ============================================================================


class TestSingleAnswerRule:
    """Tests for SingleAnswerRule."""

    def test_valid_answer_key_a(self, chunks_dict):
        """Test that answer_key A is valid."""
        rule = SingleAnswerRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is True
        assert msg == ""

    def test_valid_answer_key_d(self, chunks_dict):
        """Test that answer_key D is valid."""
        rule = SingleAnswerRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="D",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is True

    def test_rule_name(self):
        """Test rule name property."""
        rule = SingleAnswerRule()
        assert rule.name == "SingleAnswer"


# ============================================================================
# OptionsCompleteRule Tests
# ============================================================================


class TestOptionsCompleteRule:
    """Tests for OptionsCompleteRule."""

    def test_all_options_present(self, chunks_dict, valid_mcq_item):
        """Test that all options A-D present passes."""
        rule = OptionsCompleteRule()
        passed, msg = rule.validate(valid_mcq_item, chunks_dict)
        assert passed is True
        assert msg == ""

    def test_missing_option(self, chunks_dict):
        """Test that missing option fails."""
        rule = OptionsCompleteRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c"},  # Missing D
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "Missing options" in msg
        assert "D" in msg

    def test_empty_option(self, chunks_dict):
        """Test that empty option fails."""
        rule = OptionsCompleteRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "", "C": "c", "D": "d"},  # Empty B
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "Empty options" in msg
        assert "B" in msg

    def test_whitespace_only_option(self, chunks_dict):
        """Test that whitespace-only option is considered empty."""
        rule = OptionsCompleteRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "   ", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "Empty options" in msg

    def test_rule_name(self):
        """Test rule name property."""
        rule = OptionsCompleteRule()
        assert rule.name == "OptionsComplete"


# ============================================================================
# EvidenceExistsRule Tests
# ============================================================================


class TestEvidenceExistsRule:
    """Tests for EvidenceExistsRule."""

    def test_valid_evidence(self, chunks_dict, valid_mcq_item):
        """Test that valid evidence passes."""
        rule = EvidenceExistsRule()
        passed, msg = rule.validate(valid_mcq_item, chunks_dict)
        assert passed is True
        assert msg == ""

    def test_no_evidence(self, chunks_dict):
        """Test that no evidence fails."""
        rule = EvidenceExistsRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[],  # No evidence
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "No gold evidence" in msg

    def test_chunk_not_found(self, chunks_dict):
        """Test that missing chunk fails."""
        rule = EvidenceExistsRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(doc_id="doc_abc123", chunk_id="nonexistent_chunk")
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "not found" in msg

    def test_doc_id_mismatch(self, chunks_dict):
        """Test that doc_id mismatch fails."""
        rule = EvidenceExistsRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(
                    doc_id="wrong_doc_id", chunk_id="doc_abc123_0"  # Mismatched
                )
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "doc_id mismatch" in msg

    def test_char_offset_out_of_bounds(self, chunks_dict):
        """Test that char offset beyond chunk length fails."""
        rule = EvidenceExistsRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(
                    doc_id="doc_abc123",
                    chunk_id="doc_abc123_0",
                    char_start=0,
                    char_end=10000,  # Way beyond chunk length
                )
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "exceeds chunk length" in msg

    def test_negative_char_start(self, chunks_dict):
        """Test that negative char_start fails."""
        rule = EvidenceExistsRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(
                    doc_id="doc_abc123",
                    chunk_id="doc_abc123_0",
                    char_start=-5,
                    char_end=10,
                )
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "negative" in msg

    def test_start_greater_than_end(self, chunks_dict):
        """Test that char_start >= char_end fails."""
        rule = EvidenceExistsRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(
                    doc_id="doc_abc123",
                    chunk_id="doc_abc123_0",
                    char_start=50,
                    char_end=40,  # Start > end
                )
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "char_start" in msg

    def test_evidence_without_offsets(self, chunks_dict):
        """Test that evidence without char offsets still passes."""
        rule = EvidenceExistsRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(
                    doc_id="doc_abc123",
                    chunk_id="doc_abc123_0",
                    # No char_start/char_end
                )
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is True

    def test_rule_name(self):
        """Test rule name property."""
        rule = EvidenceExistsRule()
        assert rule.name == "EvidenceExists"


# ============================================================================
# AmbiguityRule Tests
# ============================================================================


class TestAmbiguityRule:
    """Tests for AmbiguityRule."""

    def test_distinct_options_pass(self, chunks_dict, valid_mcq_item):
        """Test that distinct options pass."""
        rule = AmbiguityRule()
        passed, msg = rule.validate(valid_mcq_item, chunks_dict)
        assert passed is True
        assert msg == ""

    def test_similar_options_fail(self, chunks_dict):
        """Test that very similar options fail."""
        rule = AmbiguityRule(similarity_threshold=0.8)
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={
                "A": "The maximum power is 23 dBm",
                "B": "The maximum power is 23 dBm exactly",  # Very similar to A
                "C": "Something completely different",
                "D": "Another different option",
            },
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "too similar" in msg

    def test_custom_threshold(self, chunks_dict):
        """Test custom similarity threshold."""
        # With a very high threshold, similar options should pass
        rule = AmbiguityRule(similarity_threshold=0.99)
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={
                "A": "The power is 23 dBm",
                "B": "The power is 24 dBm",  # Similar but not 99%
                "C": "Different",
                "D": "Also different",
            },
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is True

    def test_case_insensitive_comparison(self, chunks_dict):
        """Test that comparison is case-insensitive."""
        rule = AmbiguityRule(similarity_threshold=0.9)
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={
                "A": "THE ANSWER",
                "B": "the answer",  # Same text, different case
                "C": "Something else",
                "D": "Different",
            },
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False

    def test_rule_name(self):
        """Test rule name property."""
        rule = AmbiguityRule()
        assert rule.name == "Ambiguity"


# ============================================================================
# HopCountRule Tests
# ============================================================================


class TestHopCountRule:
    """Tests for HopCountRule."""

    def test_slice_a_one_hop(self, chunks_dict, valid_mcq_item):
        """Test Slice A with 1 hop passes."""
        rule = HopCountRule()
        passed, msg = rule.validate(valid_mcq_item, chunks_dict)
        assert passed is True

    def test_slice_a_two_hops_fail(self, chunks_dict):
        """Test Slice A with 2 hops fails."""
        rule = HopCountRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=2,  # Invalid for Slice A
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "inconsistent" in msg

    def test_slice_b_two_hops(self, chunks_dict, two_hop_mcq_item):
        """Test Slice B with 2 hops passes."""
        rule = HopCountRule()
        passed, msg = rule.validate(two_hop_mcq_item, chunks_dict)
        assert passed is True

    def test_slice_c_two_hops(self, chunks_dict):
        """Test Slice C with 2 hops passes."""
        rule = HopCountRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0"),
                GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_1"),
            ],
            slice=Slice.C,
            required_hops=2,
            reasoning_type=ReasoningType.EXCEPTION_HANDLING,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is True

    def test_slice_c_three_hops(self, chunks_dict):
        """Test Slice C with 3 hops passes."""
        rule = HopCountRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0"),
                GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_1"),
                GoldEvidence(doc_id="doc_def456", chunk_id="doc_def456_0"),
            ],
            slice=Slice.C,
            required_hops=3,
            reasoning_type=ReasoningType.EXCEPTION_HANDLING,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is True

    def test_rule_name(self):
        """Test rule name property."""
        rule = HopCountRule()
        assert rule.name == "HopCount"


# ============================================================================
# EvidenceCountRule Tests
# ============================================================================


class TestEvidenceCountRule:
    """Tests for EvidenceCountRule."""

    def test_sufficient_evidence(self, chunks_dict, valid_mcq_item):
        """Test that sufficient evidence passes."""
        rule = EvidenceCountRule()
        passed, msg = rule.validate(valid_mcq_item, chunks_dict)
        assert passed is True

    def test_insufficient_evidence(self, chunks_dict):
        """Test that insufficient evidence fails."""
        rule = EvidenceCountRule()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c", "D": "d"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")
            ],  # Only 1 evidence for 2-hop
            slice=Slice.B,
            required_hops=2,
            reasoning_type=ReasoningType.COMPARISON,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        passed, msg = rule.validate(item, chunks_dict)
        assert passed is False
        assert "Insufficient evidence" in msg

    def test_multiple_evidence_for_multi_hop(self, chunks_dict, two_hop_mcq_item):
        """Test that multiple evidence passes for multi-hop."""
        rule = EvidenceCountRule()
        passed, msg = rule.validate(two_hop_mcq_item, chunks_dict)
        assert passed is True

    def test_rule_name(self):
        """Test rule name property."""
        rule = EvidenceCountRule()
        assert rule.name == "EvidenceCount"


# ============================================================================
# Rule Factory Tests
# ============================================================================


class TestRuleFactory:
    """Tests for rule factory functions."""

    def test_get_default_rules(self):
        """Test getting default rules."""
        rules = get_default_rules()
        assert len(rules) == 6
        names = [r.name for r in rules]
        assert "SingleAnswer" in names
        assert "OptionsComplete" in names
        assert "EvidenceExists" in names
        assert "Ambiguity" in names
        assert "HopCount" in names
        assert "EvidenceCount" in names

    def test_get_rule_by_name(self):
        """Test getting rule by name."""
        rule = get_rule("Ambiguity")
        assert isinstance(rule, AmbiguityRule)

    def test_get_rule_with_kwargs(self):
        """Test getting rule with custom parameters."""
        rule = get_rule("Ambiguity", similarity_threshold=0.9)
        assert isinstance(rule, AmbiguityRule)
        assert rule.similarity_threshold == 0.9

    def test_get_rule_unknown(self):
        """Test that unknown rule raises error."""
        with pytest.raises(ValueError, match="Unknown rule"):
            get_rule("NonexistentRule")

    def test_available_rules(self):
        """Test that AVAILABLE_RULES contains expected rules."""
        assert "SingleAnswer" in AVAILABLE_RULES
        assert "OptionsComplete" in AVAILABLE_RULES
        assert "EvidenceExists" in AVAILABLE_RULES
        assert "Ambiguity" in AVAILABLE_RULES
        assert "HopCount" in AVAILABLE_RULES
        assert "EvidenceCount" in AVAILABLE_RULES


# ============================================================================
# Validator Tests
# ============================================================================


class TestValidator:
    """Tests for Validator class."""

    def test_validate_valid_item(self, chunks_dict, valid_mcq_item):
        """Test validating a valid item."""
        validator = Validator()
        result = validator.validate(valid_mcq_item, chunks_dict)
        assert result.passed is True
        assert result.qid == valid_mcq_item.qid
        assert len(result.failed_rules) == 0

    def test_validate_invalid_item(self, chunks_dict):
        """Test validating an invalid item."""
        validator = Validator()
        item = MCQItem(
            qid="q1",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c"},  # Missing D
            answer_key="A",
            gold_evidence=[
                GoldEvidence(doc_id="doc_abc123", chunk_id="nonexistent")  # Invalid
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        result = validator.validate(item, chunks_dict)
        assert result.passed is False
        assert len(result.failed_rules) > 0

    def test_validate_batch(self, chunks_dict, valid_mcq_item, two_hop_mcq_item):
        """Test batch validation."""
        validator = Validator()
        items = [valid_mcq_item, two_hop_mcq_item]
        report = validator.validate_batch(items, chunks_dict)

        assert report.total_items == 2
        assert report.passed_items == 2
        assert report.failed_items == 0
        assert len(report.results) == 2

    def test_validate_batch_with_failures(self, chunks_dict, valid_mcq_item):
        """Test batch validation with some failures."""
        validator = Validator()
        invalid_item = MCQItem(
            qid="q_invalid",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c"},  # Missing D
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        items = [valid_mcq_item, invalid_item]
        report = validator.validate_batch(items, chunks_dict)

        assert report.total_items == 2
        assert report.passed_items == 1
        assert report.failed_items == 1
        assert "OptionsComplete" in report.failure_counts

    def test_custom_rules(self, chunks_dict, valid_mcq_item):
        """Test validator with custom rules."""
        # Only use SingleAnswer rule
        validator = Validator(rules=[SingleAnswerRule()])
        result = validator.validate(valid_mcq_item, chunks_dict)
        assert result.passed is True

    def test_add_rule(self):
        """Test adding a rule to validator."""
        validator = Validator(rules=[])
        assert len(validator.rules) == 0
        validator.add_rule(SingleAnswerRule())
        assert len(validator.rules) == 1

    def test_remove_rule(self):
        """Test removing a rule from validator."""
        validator = Validator()
        initial_count = len(validator.rules)
        removed = validator.remove_rule("Ambiguity")
        assert removed is True
        assert len(validator.rules) == initial_count - 1

    def test_remove_nonexistent_rule(self):
        """Test removing a rule that doesn't exist."""
        validator = Validator()
        removed = validator.remove_rule("NonexistentRule")
        assert removed is False

    def test_get_rule_names(self):
        """Test getting list of rule names."""
        validator = Validator()
        names = validator.get_rule_names()
        assert "SingleAnswer" in names
        assert "OptionsComplete" in names

    def test_pass_rate(self, chunks_dict, valid_mcq_item):
        """Test pass rate calculation."""
        validator = Validator()
        invalid_item = MCQItem(
            qid="q_invalid",
            question="Test?",
            options={"A": "a", "B": "b", "C": "c"},
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc_abc123", chunk_id="doc_abc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        items = [valid_mcq_item, invalid_item]
        report = validator.validate_batch(items, chunks_dict)
        assert report.pass_rate == 50.0

    def test_empty_batch(self, chunks_dict):
        """Test batch validation with empty list."""
        validator = Validator()
        report = validator.validate_batch([], chunks_dict)
        assert report.total_items == 0
        assert report.pass_rate == 0.0


# ============================================================================
# ValidationReport Tests
# ============================================================================


class TestValidationReport:
    """Tests for ValidationReport class."""

    def test_to_dict(self):
        """Test report serialization."""
        report = ValidationReport(
            total_items=10,
            passed_items=8,
            failed_items=2,
            failure_counts={"OptionsComplete": 2},
        )
        d = report.to_dict()
        assert d["total_items"] == 10
        assert d["passed_items"] == 8
        assert d["pass_rate"] == 80.0
        assert "failure_counts" in d

    def test_get_failed_qids(self):
        """Test getting failed QIDs."""
        from src.models import ValidationResult

        report = ValidationReport()
        report.results = [
            ValidationResult(qid="q1", passed=True, failed_rules=[]),
            ValidationResult(
                qid="q2", passed=False, failed_rules=["OptionsComplete"]
            ),
            ValidationResult(qid="q3", passed=True, failed_rules=[]),
        ]
        failed = report.get_failed_qids()
        assert failed == ["q2"]

    def test_get_passed_qids(self):
        """Test getting passed QIDs."""
        from src.models import ValidationResult

        report = ValidationReport()
        report.results = [
            ValidationResult(qid="q1", passed=True, failed_rules=[]),
            ValidationResult(
                qid="q2", passed=False, failed_rules=["OptionsComplete"]
            ),
            ValidationResult(qid="q3", passed=True, failed_rules=[]),
        ]
        passed = report.get_passed_qids()
        assert passed == ["q1", "q3"]


# ============================================================================
# ValidationPipeline Tests
# ============================================================================


class TestValidationPipeline:
    """Tests for ValidationPipeline class."""

    def test_pipeline_initialization(self, temp_dir):
        """Test pipeline initialization with custom directories."""
        pipeline = ValidationPipeline(
            generated_dir=temp_dir / "generated",
            chunks_dir=temp_dir / "chunks",
            validated_dir=temp_dir / "validated",
            rejected_dir=temp_dir / "rejected",
        )
        assert pipeline.generated_dir == temp_dir / "generated"
        assert pipeline.chunks_dir == temp_dir / "chunks"

    def test_pipeline_run_empty(self, temp_dir):
        """Test pipeline run with empty directories."""
        (temp_dir / "generated").mkdir()
        (temp_dir / "chunks").mkdir()

        pipeline = ValidationPipeline(
            generated_dir=temp_dir / "generated",
            chunks_dir=temp_dir / "chunks",
            validated_dir=temp_dir / "validated",
            rejected_dir=temp_dir / "rejected",
        )
        stats, report = pipeline.run(dry_run=True)
        assert stats.total_items == 0

    def test_pipeline_run_with_items(self, temp_dir):
        """Test pipeline run with actual items."""
        # Setup directories
        generated_dir = temp_dir / "generated"
        chunks_dir = temp_dir / "chunks"
        validated_dir = temp_dir / "validated"
        rejected_dir = temp_dir / "rejected"

        generated_dir.mkdir()
        chunks_dir.mkdir()

        # Create chunk file
        chunk = CDRChunk(
            doc_id="doc123",
            source_type=SourceType.TXT,
            chunk_id="doc123_0",
            text="Test content with some information.",
        )
        with open(chunks_dir / "doc123.jsonl", "w") as f:
            f.write(chunk.model_dump_json() + "\n")

        # Create valid item with distinct options (to pass AmbiguityRule)
        valid_item = MCQItem(
            qid="doc123_q1",
            question="Test question?",
            options={
                "A": "The correct answer is here",
                "B": "Something completely different",
                "C": "Another unrelated choice",
                "D": "Yet another distinct option",
            },
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc123", chunk_id="doc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        with open(generated_dir / "batch1.jsonl", "w") as f:
            f.write(valid_item.model_dump_json() + "\n")

        # Run pipeline
        pipeline = ValidationPipeline(
            generated_dir=generated_dir,
            chunks_dir=chunks_dir,
            validated_dir=validated_dir,
            rejected_dir=rejected_dir,
        )
        stats, report = pipeline.run(dry_run=False)

        assert stats.total_items == 1
        assert stats.passed_items == 1
        assert validated_dir.exists()
        assert len(list(validated_dir.glob("*.jsonl"))) == 1

    def test_pipeline_dry_run(self, temp_dir):
        """Test that dry_run doesn't create files."""
        generated_dir = temp_dir / "generated"
        chunks_dir = temp_dir / "chunks"
        validated_dir = temp_dir / "validated"

        generated_dir.mkdir()
        chunks_dir.mkdir()

        # Create chunk
        chunk = CDRChunk(
            doc_id="doc123",
            source_type=SourceType.TXT,
            chunk_id="doc123_0",
            text="Test content.",
        )
        with open(chunks_dir / "doc123.jsonl", "w") as f:
            f.write(chunk.model_dump_json() + "\n")

        # Create item with distinct options
        item = MCQItem(
            qid="doc123_q1",
            question="Test?",
            options={
                "A": "First distinct answer",
                "B": "Second completely different",
                "C": "Third unrelated option",
                "D": "Fourth separate choice",
            },
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc123", chunk_id="doc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )
        with open(generated_dir / "batch1.jsonl", "w") as f:
            f.write(item.model_dump_json() + "\n")

        pipeline = ValidationPipeline(
            generated_dir=generated_dir,
            chunks_dir=chunks_dir,
            validated_dir=validated_dir,
        )
        stats, report = pipeline.run(dry_run=True)

        assert stats.total_items == 1
        assert not validated_dir.exists()

    def test_validate_single(self, temp_dir):
        """Test single item validation."""
        chunks_dir = temp_dir / "chunks"
        chunks_dir.mkdir()

        chunk = CDRChunk(
            doc_id="doc123",
            source_type=SourceType.TXT,
            chunk_id="doc123_0",
            text="Test content.",
        )
        with open(chunks_dir / "doc123.jsonl", "w") as f:
            f.write(chunk.model_dump_json() + "\n")

        pipeline = ValidationPipeline(chunks_dir=chunks_dir)

        item = MCQItem(
            qid="doc123_q1",
            question="Test?",
            options={
                "A": "First distinct answer",
                "B": "Second completely different",
                "C": "Third unrelated option",
                "D": "Fourth separate choice",
            },
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="doc123", chunk_id="doc123_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )

        passed, failures = pipeline.validate_single(item)
        assert passed is True
        assert len(failures) == 0


# ============================================================================
# ValidationStats Tests
# ============================================================================


class TestValidationStats:
    """Tests for ValidationStats class."""

    def test_pass_rate_calculation(self):
        """Test pass rate calculation."""
        stats = ValidationStats(total_items=100, passed_items=75, failed_items=25)
        assert stats.pass_rate == 75.0

    def test_pass_rate_zero_items(self):
        """Test pass rate with zero items."""
        stats = ValidationStats()
        assert stats.pass_rate == 0.0

    def test_duration(self):
        """Test duration calculation."""
        from datetime import datetime, timedelta

        start = datetime.now()
        stats = ValidationStats(start_time=start)
        stats.end_time = start + timedelta(seconds=5)
        assert stats.duration_seconds == 5.0
