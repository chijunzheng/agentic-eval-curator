"""Frozen context pipeline for building retrieval-isolated evaluation sets."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.models import CDRChunk, FrozenContext, MCQItem
from src.frozen.builder import BuildResult, FrozenContextBuilder

logger = logging.getLogger(__name__)


@dataclass
class FrozenStats:
    """Statistics from a frozen context pipeline run."""

    total_items: int = 0
    contexts_built: int = 0
    total_gold_chunks: int = 0
    total_distractor_chunks: int = 0
    items_with_missing_gold: int = 0
    missing_gold_chunk_ids: list[str] = field(default_factory=list)
    chunks_loaded: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        """Calculate run duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def avg_gold_per_item(self) -> float:
        """Average gold chunks per item."""
        if self.contexts_built == 0:
            return 0.0
        return self.total_gold_chunks / self.contexts_built

    @property
    def avg_distractor_per_item(self) -> float:
        """Average distractor chunks per item."""
        if self.contexts_built == 0:
            return 0.0
        return self.total_distractor_chunks / self.contexts_built

    def to_dict(self) -> dict:
        """Convert stats to dictionary for JSON serialization."""
        return {
            "total_items": self.total_items,
            "contexts_built": self.contexts_built,
            "total_gold_chunks": self.total_gold_chunks,
            "total_distractor_chunks": self.total_distractor_chunks,
            "items_with_missing_gold": self.items_with_missing_gold,
            "missing_gold_chunk_ids": self.missing_gold_chunk_ids,
            "chunks_loaded": self.chunks_loaded,
            "duration_seconds": self.duration_seconds,
            "avg_gold_per_item": self.avg_gold_per_item,
            "avg_distractor_per_item": self.avg_distractor_per_item,
        }


class FrozenPipeline:
    """
    Pipeline for building frozen retrieval contexts.

    Loads validated items from data/validated/, loads all chunks from data/chunks/,
    builds frozen contexts with gold + distractor chunks, and outputs to
    data/frozen_contexts/.
    """

    def __init__(
        self,
        validated_dir: Path | str = "data/validated",
        chunks_dir: Path | str = "data/chunks",
        output_dir: Path | str = "data/frozen_contexts",
        distractor_strategy: str = "random",
        distractor_count: int = 10,
    ):
        """
        Initialize the frozen context pipeline.

        Args:
            validated_dir: Directory containing validated MCQ items (JSONL).
            chunks_dir: Directory containing CDR chunks (JSONL).
            output_dir: Output directory for frozen contexts.
            distractor_strategy: Strategy for selecting distractors.
            distractor_count: Number of distractor chunks per item.
        """
        self.validated_dir = Path(validated_dir)
        self.chunks_dir = Path(chunks_dir)
        self.output_dir = Path(output_dir)
        self.builder = FrozenContextBuilder(
            distractor_strategy=distractor_strategy,
            distractor_count=distractor_count,
        )

    def run(
        self, dry_run: bool = False, seed: int | None = None
    ) -> tuple[FrozenStats, list[FrozenContext]]:
        """
        Run the frozen context building pipeline.

        Args:
            dry_run: If True, build contexts but don't write output files.
            seed: Optional random seed for reproducibility.

        Returns:
            Tuple of (FrozenStats, list of FrozenContext objects).
        """
        stats = FrozenStats()

        # Load all chunks
        chunks = self._load_all_chunks()
        stats.chunks_loaded = len(chunks)
        logger.info(f"Loaded {len(chunks)} chunks")

        # Load validated items
        items = self._load_validated_items()
        stats.total_items = len(items)
        logger.info(f"Loaded {len(items)} validated items")

        if not items:
            logger.warning("No items to build frozen contexts for")
            stats.end_time = datetime.now()
            return stats, []

        if not chunks:
            logger.error("No chunks available - cannot build frozen contexts")
            stats.end_time = datetime.now()
            return stats, []

        # Build frozen contexts
        results = self.builder.build_batch(items, chunks, seed)
        contexts = []

        for result in results:
            contexts.append(result.frozen_context)
            stats.contexts_built += 1
            stats.total_gold_chunks += result.gold_chunk_count
            stats.total_distractor_chunks += result.distractor_chunk_count

            if result.missing_gold_chunks:
                stats.items_with_missing_gold += 1
                stats.missing_gold_chunk_ids.extend(result.missing_gold_chunks)

        logger.info(
            f"Built {stats.contexts_built} frozen contexts "
            f"(avg {stats.avg_gold_per_item:.1f} gold + "
            f"{stats.avg_distractor_per_item:.1f} distractors per item)"
        )

        if stats.items_with_missing_gold > 0:
            logger.warning(
                f"{stats.items_with_missing_gold} items had missing gold chunks"
            )

        # Save output
        if not dry_run:
            self._save_contexts(contexts)
            self._save_stats(stats)
        else:
            logger.info("Dry run - no files written")

        stats.end_time = datetime.now()
        return stats, contexts

    def _load_all_chunks(self) -> dict[str, CDRChunk]:
        """Load all chunks from the chunks directory."""
        chunks = {}

        if not self.chunks_dir.exists():
            logger.warning(f"Chunks directory not found: {self.chunks_dir}")
            return chunks

        for chunk_file in self.chunks_dir.glob("*.jsonl"):
            with open(chunk_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    chunk = CDRChunk(**data)
                    chunks[chunk.chunk_id] = chunk

        return chunks

    def _load_validated_items(self) -> list[MCQItem]:
        """Load all validated MCQ items."""
        items = []

        if not self.validated_dir.exists():
            logger.warning(f"Validated directory not found: {self.validated_dir}")
            return items

        for item_file in self.validated_dir.glob("*.jsonl"):
            with open(item_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        item = MCQItem(**data)
                        items.append(item)
                    except Exception as e:
                        logger.error(f"Failed to parse item from {item_file}: {e}")

        return items

    def _save_contexts(self, contexts: list[FrozenContext]) -> None:
        """Save frozen contexts to output directory as JSONL."""
        if not contexts:
            logger.info("No frozen contexts to save")
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate batch ID from timestamp
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"frozen_{batch_id}.jsonl"

        with open(output_file, "w") as f:
            for context in contexts:
                f.write(context.model_dump_json() + "\n")

        logger.info(f"Saved {len(contexts)} frozen contexts to {output_file}")

    def _save_stats(self, stats: FrozenStats) -> None:
        """Save pipeline statistics to the output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = self.output_dir / f"stats_{batch_id}.json"

        with open(stats_file, "w") as f:
            json.dump(stats.to_dict(), f, indent=2)

        logger.info(f"Saved frozen context stats to {stats_file}")

    def build_single(
        self,
        item: MCQItem,
        chunks: dict[str, CDRChunk] | None = None,
        seed: int | None = None,
    ) -> BuildResult:
        """
        Build frozen context for a single item (convenience method).

        Args:
            item: MCQ item to build context for.
            chunks: Optional chunks dict. If None, loads from chunks_dir.
            seed: Optional random seed for reproducibility.

        Returns:
            BuildResult with the frozen context and metadata.
        """
        if chunks is None:
            chunks = self._load_all_chunks()

        return self.builder.build(item, chunks, seed)
