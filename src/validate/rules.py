"""Validation rules for MCQ items."""

from abc import ABC, abstractmethod
from difflib import SequenceMatcher

from src.models import CDRChunk, MCQItem


class Rule(ABC):
    """Base class for validation rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the rule name for reporting."""
        ...

    @abstractmethod
    def validate(self, item: MCQItem, chunks: dict[str, CDRChunk]) -> tuple[bool, str]:
        """
        Validate an MCQ item against this rule.

        Args:
            item: The MCQ item to validate.
            chunks: Dictionary mapping chunk_id to CDRChunk for evidence verification.

        Returns:
            Tuple of (passed, message). Message explains failure if passed=False.
        """
        ...


class SingleAnswerRule(Rule):
    """Verify exactly one answer is marked correct (A, B, C, or D)."""

    @property
    def name(self) -> str:
        return "SingleAnswer"

    def validate(self, item: MCQItem, chunks: dict[str, CDRChunk]) -> tuple[bool, str]:
        valid_keys = {"A", "B", "C", "D"}

        if item.answer_key not in valid_keys:
            return False, f"Invalid answer_key '{item.answer_key}', must be A/B/C/D"

        return True, ""


class OptionsCompleteRule(Rule):
    """Verify all 4 options (A-D) are present and non-empty."""

    @property
    def name(self) -> str:
        return "OptionsComplete"

    def validate(self, item: MCQItem, chunks: dict[str, CDRChunk]) -> tuple[bool, str]:
        required_keys = {"A", "B", "C", "D"}
        missing = required_keys - set(item.options.keys())

        if missing:
            return False, f"Missing options: {sorted(missing)}"

        empty = [k for k in required_keys if not item.options.get(k, "").strip()]
        if empty:
            return False, f"Empty options: {sorted(empty)}"

        return True, ""


class EvidenceExistsRule(Rule):
    """Verify gold evidence spans exist in referenced chunks."""

    @property
    def name(self) -> str:
        return "EvidenceExists"

    def validate(self, item: MCQItem, chunks: dict[str, CDRChunk]) -> tuple[bool, str]:
        if not item.gold_evidence:
            return False, "No gold evidence provided"

        errors = []
        for i, evidence in enumerate(item.gold_evidence):
            chunk = chunks.get(evidence.chunk_id)

            if chunk is None:
                errors.append(f"Evidence[{i}]: chunk_id '{evidence.chunk_id}' not found")
                continue

            if evidence.doc_id != chunk.doc_id:
                errors.append(
                    f"Evidence[{i}]: doc_id mismatch "
                    f"(evidence={evidence.doc_id}, chunk={chunk.doc_id})"
                )
                continue

            # Validate character offsets if provided
            if evidence.char_start is not None and evidence.char_end is not None:
                text_len = len(chunk.text)

                if evidence.char_start < 0:
                    errors.append(f"Evidence[{i}]: char_start ({evidence.char_start}) is negative")
                elif evidence.char_end > text_len:
                    errors.append(
                        f"Evidence[{i}]: char_end ({evidence.char_end}) exceeds "
                        f"chunk length ({text_len})"
                    )
                elif evidence.char_start >= evidence.char_end:
                    errors.append(
                        f"Evidence[{i}]: char_start ({evidence.char_start}) >= "
                        f"char_end ({evidence.char_end})"
                    )

        if errors:
            return False, "; ".join(errors)

        return True, ""


class AmbiguityRule(Rule):
    """
    Flag items where distractors are too similar to the correct answer.

    Uses basic string similarity (SequenceMatcher ratio) to detect
    potentially ambiguous options that could confuse evaluators.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize the ambiguity rule.

        Args:
            similarity_threshold: Similarity ratio (0-1) above which options
                are considered too similar. Default 0.85.
        """
        self.similarity_threshold = similarity_threshold

    @property
    def name(self) -> str:
        return "Ambiguity"

    def validate(self, item: MCQItem, chunks: dict[str, CDRChunk]) -> tuple[bool, str]:
        correct_answer = item.options.get(item.answer_key, "")
        if not correct_answer:
            # OptionsCompleteRule will catch this
            return True, ""

        similar_pairs = []
        correct_normalized = self._normalize(correct_answer)

        for key, option in item.options.items():
            if key == item.answer_key:
                continue

            option_normalized = self._normalize(option)
            similarity = SequenceMatcher(
                None, correct_normalized, option_normalized
            ).ratio()

            if similarity >= self.similarity_threshold:
                similar_pairs.append(
                    f"{key} (similarity={similarity:.2f})"
                )

        if similar_pairs:
            return False, f"Distractors too similar to correct answer: {', '.join(similar_pairs)}"

        return True, ""

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        return text.lower().strip()


class HopCountRule(Rule):
    """Verify required_hops is consistent with slice assignment."""

    @property
    def name(self) -> str:
        return "HopCount"

    def validate(self, item: MCQItem, chunks: dict[str, CDRChunk]) -> tuple[bool, str]:
        slice_hop_ranges = {
            "A": (1, 1),  # Slice A: exactly 1 hop
            "B": (2, 2),  # Slice B: exactly 2 hops
            "C": (2, 3),  # Slice C: 2-3 hops
        }

        min_hops, max_hops = slice_hop_ranges.get(item.slice.value, (1, 3))

        if not (min_hops <= item.required_hops <= max_hops):
            return False, (
                f"required_hops ({item.required_hops}) inconsistent with "
                f"slice {item.slice.value} (expected {min_hops}-{max_hops})"
            )

        return True, ""


class EvidenceCountRule(Rule):
    """Verify evidence count matches required hops (each hop should have evidence)."""

    @property
    def name(self) -> str:
        return "EvidenceCount"

    def validate(self, item: MCQItem, chunks: dict[str, CDRChunk]) -> tuple[bool, str]:
        evidence_count = len(item.gold_evidence)

        if evidence_count < item.required_hops:
            return False, (
                f"Insufficient evidence: {evidence_count} spans for "
                f"{item.required_hops}-hop question (expected >= {item.required_hops})"
            )

        return True, ""


# Registry of all available rules
AVAILABLE_RULES: dict[str, type[Rule]] = {
    "SingleAnswer": SingleAnswerRule,
    "OptionsComplete": OptionsCompleteRule,
    "EvidenceExists": EvidenceExistsRule,
    "Ambiguity": AmbiguityRule,
    "HopCount": HopCountRule,
    "EvidenceCount": EvidenceCountRule,
}


def get_default_rules() -> list[Rule]:
    """Get the default set of validation rules."""
    return [
        SingleAnswerRule(),
        OptionsCompleteRule(),
        EvidenceExistsRule(),
        AmbiguityRule(),
        HopCountRule(),
        EvidenceCountRule(),
    ]


def get_rule(name: str, **kwargs) -> Rule:
    """
    Get a validation rule by name.

    Args:
        name: Rule name from AVAILABLE_RULES.
        **kwargs: Arguments to pass to rule constructor.

    Returns:
        Instantiated Rule object.

    Raises:
        ValueError: If rule name is not recognized.
    """
    if name not in AVAILABLE_RULES:
        raise ValueError(f"Unknown rule: {name}. Available: {list(AVAILABLE_RULES.keys())}")

    return AVAILABLE_RULES[name](**kwargs)
