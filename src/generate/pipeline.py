"""Generation pipeline orchestration."""

import json
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.config import PipelineConfig
from src.models import CDRChunk, MCQItem, Slice

from .mcq_generator import MCQGenerator

logger = logging.getLogger(__name__)


@dataclass
class GenerationStats:
    """Statistics from a generation run."""

    chunks_processed: int = 0
    items_generated: int = 0
    items_per_slice: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    batch_id: str = ""


class GenerationPipeline:
    """Orchestrate MCQ generation from chunked documents."""

    def __init__(self, config: PipelineConfig):
        """Initialize generation pipeline.

        Args:
            config: Pipeline configuration.
        """
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.chunks_dir = self.data_dir / "chunks"
        self.generated_dir = self.data_dir / "generated"
        self._generator: MCQGenerator | None = None

    def _get_generator(self) -> MCQGenerator:
        """Get or create the MCQ generator."""
        if self._generator is None:
            self._generator = MCQGenerator(config=self.config.generation)
        return self._generator

    def run(
        self,
        slice_type: Slice | None = None,
        dry_run: bool = False,
        seed: int | None = None,
        chunk_group_size: int = 3,
    ) -> GenerationStats:
        """Run the generation pipeline.

        Args:
            slice_type: Generate for specific slice (A/B/C) or all if None.
            dry_run: If True, don't write any files.
            seed: Random seed for reproducibility.
            chunk_group_size: Number of chunks to group for generation.

        Returns:
            GenerationStats with processing results.
        """
        # Use config seed if not overridden
        effective_seed = seed if seed is not None else self.config.seed
        if effective_seed is not None:
            random.seed(effective_seed)

        batch_id = self._generate_batch_id()
        stats = GenerationStats(batch_id=batch_id)

        # Determine which slices to generate
        slices = [slice_type] if slice_type else list(Slice)

        # Initialize slice counters
        for s in Slice:
            stats.items_per_slice[s.value] = 0

        # Load all chunks
        chunks = self._load_all_chunks()
        if not chunks:
            stats.errors.append("No chunks found in data/chunks/")
            return stats

        logger.info(f"Loaded {len(chunks)} chunks for generation")
        stats.chunks_processed = len(chunks)

        # Ensure output directory exists
        if not dry_run:
            self.generated_dir.mkdir(parents=True, exist_ok=True)

        all_items: list[MCQItem] = []
        generator = self._get_generator()

        # Group chunks by doc_id for generation
        chunks_by_doc = self._group_chunks_by_doc(chunks)

        for doc_id, doc_chunks in chunks_by_doc.items():
            # Create overlapping groups of chunks
            chunk_groups = self._create_chunk_groups(doc_chunks, chunk_group_size)

            for group in chunk_groups:
                for target_slice in slices:
                    # Adjust number of questions based on slice
                    # Slice A: more questions (simpler), Slice C: fewer (harder)
                    num_questions = self._get_questions_per_group(target_slice)

                    result = generator.generate(
                        chunks=group,
                        slice_type=target_slice,
                        num_questions=num_questions,
                        seed=effective_seed,
                    )

                    for item in result.items:
                        all_items.append(item)
                        stats.items_generated += 1
                        stats.items_per_slice[target_slice.value] += 1

                    for error in result.errors:
                        stats.errors.append(f"[{doc_id}] {error}")

        # Save generated items
        if not dry_run and all_items:
            self._save_items(batch_id, all_items)

        logger.info(
            f"Generation complete: {stats.items_generated} items across "
            f"{len(slices)} slices"
        )

        return stats

    def _generate_batch_id(self) -> str:
        """Generate a unique batch ID for this generation run."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"{timestamp}_{short_uuid}"

    def _load_all_chunks(self) -> list[CDRChunk]:
        """Load all chunks from the chunks directory.

        Returns:
            List of all CDRChunk objects.
        """
        chunks = []

        if not self.chunks_dir.exists():
            return chunks

        for chunk_file in self.chunks_dir.glob("*.jsonl"):
            try:
                with open(chunk_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            chunks.append(CDRChunk(**data))
            except Exception as e:
                logger.error(f"Error loading {chunk_file}: {e}")

        return chunks

    def _group_chunks_by_doc(
        self, chunks: list[CDRChunk]
    ) -> dict[str, list[CDRChunk]]:
        """Group chunks by their document ID.

        Args:
            chunks: List of chunks to group.

        Returns:
            Dictionary mapping doc_id to list of chunks.
        """
        by_doc: dict[str, list[CDRChunk]] = {}
        for chunk in chunks:
            if chunk.doc_id not in by_doc:
                by_doc[chunk.doc_id] = []
            by_doc[chunk.doc_id].append(chunk)

        # Sort chunks within each doc by chunk_id for consistency
        for doc_id in by_doc:
            by_doc[doc_id].sort(key=lambda c: c.chunk_id)

        return by_doc

    def _create_chunk_groups(
        self,
        chunks: list[CDRChunk],
        group_size: int,
    ) -> list[list[CDRChunk]]:
        """Create overlapping groups of chunks for generation.

        Args:
            chunks: List of chunks from a single document.
            group_size: Number of chunks per group.

        Returns:
            List of chunk groups.
        """
        if len(chunks) <= group_size:
            return [chunks]

        groups = []
        # Create overlapping windows
        step = max(1, group_size // 2)  # 50% overlap
        for i in range(0, len(chunks) - group_size + 1, step):
            groups.append(chunks[i : i + group_size])

        # Add final group if not covered
        if groups and groups[-1][-1] != chunks[-1]:
            groups.append(chunks[-group_size:])

        return groups

    def _get_questions_per_group(self, slice_type: Slice) -> int:
        """Get number of questions to generate per chunk group for a slice.

        Args:
            slice_type: The difficulty slice.

        Returns:
            Number of questions to generate.
        """
        base = self.config.generation.items_per_chunk_group
        # Slice A: 100%, Slice B: 66%, Slice C: 50%
        multipliers = {
            Slice.A: 1.0,
            Slice.B: 0.66,
            Slice.C: 0.5,
        }
        return max(1, int(base * multipliers[slice_type]))

    def _save_items(self, batch_id: str, items: list[MCQItem]) -> None:
        """Save generated items to JSONL file.

        Args:
            batch_id: Unique batch identifier.
            items: List of MCQItem objects to save.
        """
        output_path = self.generated_dir / f"{batch_id}.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(item.model_dump_json() + "\n")
        logger.info(f"Saved {len(items)} items to {output_path}")

    def load_generated_items(self, batch_id: str | None = None) -> list[MCQItem]:
        """Load generated items from disk.

        Args:
            batch_id: If provided, load only this batch.
                     If None, load all generated items.

        Returns:
            List of MCQItem objects.
        """
        items = []

        if not self.generated_dir.exists():
            return items

        if batch_id:
            item_file = self.generated_dir / f"{batch_id}.jsonl"
            if item_file.exists():
                items.extend(self._load_item_file(item_file))
        else:
            for item_file in self.generated_dir.glob("*.jsonl"):
                items.extend(self._load_item_file(item_file))

        return items

    def _load_item_file(self, file_path: Path) -> list[MCQItem]:
        """Load items from a single JSONL file.

        Args:
            file_path: Path to JSONL file.

        Returns:
            List of MCQItem objects.
        """
        items = []
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    items.append(MCQItem(**data))
        return items
