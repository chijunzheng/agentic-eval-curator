"""Frozen context builder for retrieval-isolated evaluation."""

import logging
import random
from dataclasses import dataclass

from src.models import CDRChunk, FrozenContext, MCQItem
from src.frozen.distractors import DistractorSelector, get_selector

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of building a frozen context for a single item."""

    frozen_context: FrozenContext
    gold_chunk_count: int
    distractor_chunk_count: int
    missing_gold_chunks: list[str]


class FrozenContextBuilder:
    """
    Builder for frozen retrieval contexts.

    Creates FrozenContext objects that include gold evidence chunks plus
    distractor chunks, shuffled to avoid position bias.
    """

    def __init__(
        self,
        distractor_strategy: str = "random",
        distractor_count: int = 10,
    ):
        """
        Initialize the frozen context builder.

        Args:
            distractor_strategy: Strategy for selecting distractors
                (random, same_doc, semantic).
            distractor_count: Number of distractor chunks to include.
        """
        self.selector = get_selector(distractor_strategy)
        self.distractor_count = distractor_count

    def build(
        self,
        item: MCQItem,
        all_chunks: dict[str, CDRChunk],
        seed: int | None = None,
    ) -> BuildResult:
        """
        Build a frozen context for a single MCQ item.

        Args:
            item: The MCQ item to build context for.
            all_chunks: Dictionary of all available chunks (chunk_id -> CDRChunk).
            seed: Optional random seed for reproducibility.

        Returns:
            BuildResult containing the frozen context and metadata.
        """
        # Collect gold evidence chunks
        gold_chunks = []
        missing_gold_chunks = []

        for evidence in item.gold_evidence:
            if evidence.chunk_id in all_chunks:
                gold_chunks.append(all_chunks[evidence.chunk_id])
            else:
                missing_gold_chunks.append(evidence.chunk_id)
                logger.warning(
                    f"Gold evidence chunk {evidence.chunk_id} not found for item {item.qid}"
                )

        # Select distractor chunks
        distractors = self.selector.select(
            item, all_chunks, self.distractor_count, seed
        )

        # Combine and shuffle
        all_context_chunks = gold_chunks + distractors

        # Shuffle to avoid position bias (gold chunks first = easy pattern)
        rng = random.Random(seed)
        rng.shuffle(all_context_chunks)

        # Build the frozen context
        chunks_data = [
            {"chunk_id": chunk.chunk_id, "text": chunk.text}
            for chunk in all_context_chunks
        ]

        frozen_context = FrozenContext(
            qid=item.qid,
            chunks=chunks_data,
        )

        return BuildResult(
            frozen_context=frozen_context,
            gold_chunk_count=len(gold_chunks),
            distractor_chunk_count=len(distractors),
            missing_gold_chunks=missing_gold_chunks,
        )

    def build_batch(
        self,
        items: list[MCQItem],
        all_chunks: dict[str, CDRChunk],
        seed: int | None = None,
    ) -> list[BuildResult]:
        """
        Build frozen contexts for multiple MCQ items.

        Args:
            items: List of MCQ items to build contexts for.
            all_chunks: Dictionary of all available chunks.
            seed: Optional random seed for reproducibility.

        Returns:
            List of BuildResult objects.
        """
        results = []

        for i, item in enumerate(items):
            # Use different seed for each item to ensure variety
            # but still reproducible when base seed is set
            item_seed = None if seed is None else seed + i
            result = self.build(item, all_chunks, item_seed)
            results.append(result)

        return results

    def set_distractor_count(self, count: int) -> None:
        """Update the distractor count."""
        if count < 0:
            raise ValueError("Distractor count must be non-negative")
        self.distractor_count = count

    def set_selector(self, strategy: str) -> None:
        """Update the distractor selection strategy."""
        self.selector = get_selector(strategy)
