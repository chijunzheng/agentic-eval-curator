"""Distractor selection strategies for frozen context building."""

import logging
import random
from abc import ABC, abstractmethod

from src.models import CDRChunk, MCQItem

logger = logging.getLogger(__name__)


class DistractorSelector(ABC):
    """Base class for distractor selection strategies."""

    @abstractmethod
    def select(
        self,
        item: MCQItem,
        all_chunks: dict[str, CDRChunk],
        n: int,
        seed: int | None = None,
    ) -> list[CDRChunk]:
        """
        Select n distractor chunks for a given MCQ item.

        Args:
            item: The MCQ item to select distractors for.
            all_chunks: Dictionary of all available chunks (chunk_id -> CDRChunk).
            n: Number of distractor chunks to select.
            seed: Optional random seed for reproducibility.

        Returns:
            List of selected distractor chunks.
        """
        pass

    def _get_gold_chunk_ids(self, item: MCQItem) -> set[str]:
        """Get the set of gold evidence chunk IDs for an item."""
        return {evidence.chunk_id for evidence in item.gold_evidence}

    def _get_candidate_chunks(
        self, item: MCQItem, all_chunks: dict[str, CDRChunk]
    ) -> list[CDRChunk]:
        """Get chunks that can be used as distractors (excluding gold chunks)."""
        gold_ids = self._get_gold_chunk_ids(item)
        return [
            chunk for chunk_id, chunk in all_chunks.items()
            if chunk_id not in gold_ids
        ]


class RandomSelector(DistractorSelector):
    """Randomly sample n chunks excluding gold evidence chunks."""

    def select(
        self,
        item: MCQItem,
        all_chunks: dict[str, CDRChunk],
        n: int,
        seed: int | None = None,
    ) -> list[CDRChunk]:
        """
        Randomly select n distractor chunks.

        Args:
            item: The MCQ item to select distractors for.
            all_chunks: Dictionary of all available chunks.
            n: Number of distractor chunks to select.
            seed: Optional random seed for reproducibility.

        Returns:
            List of randomly selected distractor chunks.
        """
        candidates = self._get_candidate_chunks(item, all_chunks)

        if not candidates:
            logger.warning(f"No candidate chunks available for item {item.qid}")
            return []

        if len(candidates) <= n:
            logger.warning(
                f"Only {len(candidates)} candidate chunks available for item {item.qid}, "
                f"requested {n}"
            )
            return candidates

        rng = random.Random(seed)
        return rng.sample(candidates, n)


class SameDocSelector(DistractorSelector):
    """
    Prefer chunks from the same document as gold evidence.

    This tests intra-document filtering and reasoning capabilities.
    Falls back to random selection if same-doc chunks are insufficient.
    """

    def select(
        self,
        item: MCQItem,
        all_chunks: dict[str, CDRChunk],
        n: int,
        seed: int | None = None,
    ) -> list[CDRChunk]:
        """
        Select distractor chunks, preferring those from the same document.

        Args:
            item: The MCQ item to select distractors for.
            all_chunks: Dictionary of all available chunks.
            n: Number of distractor chunks to select.
            seed: Optional random seed for reproducibility.

        Returns:
            List of selected distractor chunks (same-doc preferred).
        """
        rng = random.Random(seed)
        gold_ids = self._get_gold_chunk_ids(item)
        gold_doc_ids = {evidence.doc_id for evidence in item.gold_evidence}

        # Partition candidates into same-doc and other-doc
        same_doc_chunks = []
        other_doc_chunks = []

        for chunk_id, chunk in all_chunks.items():
            if chunk_id in gold_ids:
                continue
            if chunk.doc_id in gold_doc_ids:
                same_doc_chunks.append(chunk)
            else:
                other_doc_chunks.append(chunk)

        selected = []

        # First, try to fill from same-doc chunks
        if same_doc_chunks:
            rng.shuffle(same_doc_chunks)
            same_doc_count = min(len(same_doc_chunks), n)
            selected.extend(same_doc_chunks[:same_doc_count])

        # If we still need more, fill from other-doc chunks
        remaining = n - len(selected)
        if remaining > 0 and other_doc_chunks:
            rng.shuffle(other_doc_chunks)
            other_count = min(len(other_doc_chunks), remaining)
            selected.extend(other_doc_chunks[:other_count])

        if len(selected) < n:
            logger.warning(
                f"Only {len(selected)} distractor chunks available for item {item.qid}, "
                f"requested {n}"
            )

        return selected


class SemanticSelector(DistractorSelector):
    """
    Select chunks with high embedding similarity to gold but different content.

    This creates harder distractors that test the model's reasoning rather than
    just keyword matching. This is a stub implementation for v1 that falls back
    to random selection. Full implementation would require embedding model.
    """

    def __init__(self, similarity_threshold: float = 0.7):
        """
        Initialize the semantic selector.

        Args:
            similarity_threshold: Minimum similarity score for semantic distractors.
        """
        self.similarity_threshold = similarity_threshold

    def select(
        self,
        item: MCQItem,
        all_chunks: dict[str, CDRChunk],
        n: int,
        seed: int | None = None,
    ) -> list[CDRChunk]:
        """
        Select semantically similar distractor chunks.

        Note: This is a stub implementation that falls back to random selection.
        Full implementation would compute embedding similarities.

        Args:
            item: The MCQ item to select distractors for.
            all_chunks: Dictionary of all available chunks.
            n: Number of distractor chunks to select.
            seed: Optional random seed for reproducibility.

        Returns:
            List of selected distractor chunks.
        """
        logger.info(
            f"SemanticSelector: Using fallback random selection for item {item.qid}. "
            "Full semantic implementation requires embedding model."
        )
        # Fallback to random selection for v1
        random_selector = RandomSelector()
        return random_selector.select(item, all_chunks, n, seed)


# Registry of available selectors
AVAILABLE_SELECTORS: dict[str, type[DistractorSelector]] = {
    "random": RandomSelector,
    "same_doc": SameDocSelector,
    "semantic": SemanticSelector,
}


def get_selector(strategy_name: str) -> DistractorSelector:
    """
    Factory function to get a distractor selector by name.

    Args:
        strategy_name: Name of the selection strategy.

    Returns:
        Instance of the corresponding DistractorSelector.

    Raises:
        ValueError: If the strategy name is not recognized.
    """
    if strategy_name not in AVAILABLE_SELECTORS:
        raise ValueError(
            f"Unknown distractor strategy: {strategy_name}. "
            f"Available strategies: {list(AVAILABLE_SELECTORS.keys())}"
        )

    return AVAILABLE_SELECTORS[strategy_name]()
