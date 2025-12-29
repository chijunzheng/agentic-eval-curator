"""Unit tests for frozen context builder and distractor selection."""

import json
import tempfile
from pathlib import Path

import pytest

from src.models import (
    CDRChunk,
    FailureMode,
    FrozenContext,
    GoldEvidence,
    MCQItem,
    ReasoningType,
    Slice,
    SourceType,
)
from src.frozen.builder import BuildResult, FrozenContextBuilder
from src.frozen.distractors import (
    AVAILABLE_SELECTORS,
    DistractorSelector,
    RandomSelector,
    SameDocSelector,
    SemanticSelector,
    get_selector,
)
from src.frozen.pipeline import FrozenPipeline, FrozenStats


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def many_chunks() -> dict[str, CDRChunk]:
    """Provide a larger set of chunks for distractor testing."""
    chunks = {}
    # Create chunks from multiple documents
    for doc_num in range(3):
        doc_id = f"doc_{doc_num:03d}"
        for chunk_num in range(5):
            chunk_id = f"{doc_id}_{chunk_num}"
            chunks[chunk_id] = CDRChunk(
                doc_id=doc_id,
                source_type=SourceType.TXT,
                chunk_id=chunk_id,
                text=f"Content from document {doc_num}, chunk {chunk_num}. "
                     f"This is sample text for testing distractor selection.",
            )
    return chunks


@pytest.fixture
def item_with_evidence(many_chunks: dict[str, CDRChunk]) -> MCQItem:
    """Provide an MCQ item with gold evidence in the many_chunks set."""
    return MCQItem(
        qid="doc_000_q1",
        question="What is the content of document 0, chunk 0?",
        options={
            "A": "Content from document 0",
            "B": "Content from document 1",
            "C": "Content from document 2",
            "D": "Unknown content",
        },
        answer_key="A",
        gold_evidence=[
            GoldEvidence(
                doc_id="doc_000",
                chunk_id="doc_000_0",
                char_start=0,
                char_end=25,
            ),
        ],
        slice=Slice.A,
        required_hops=1,
        reasoning_type=ReasoningType.FACTUAL_LOOKUP,
        failure_modes=[FailureMode.RETRIEVAL_MISS],
    )


@pytest.fixture
def item_with_multi_evidence(many_chunks: dict[str, CDRChunk]) -> MCQItem:
    """Provide an MCQ item with multiple gold evidence chunks."""
    return MCQItem(
        qid="doc_000_q2",
        question="What appears in both chunk 0 and chunk 1 of document 0?",
        options={
            "A": "Sample text",
            "B": "Random text",
            "C": "Different text",
            "D": "No text",
        },
        answer_key="A",
        gold_evidence=[
            GoldEvidence(
                doc_id="doc_000",
                chunk_id="doc_000_0",
                char_start=0,
                char_end=25,
            ),
            GoldEvidence(
                doc_id="doc_000",
                chunk_id="doc_000_1",
                char_start=0,
                char_end=25,
            ),
        ],
        slice=Slice.B,
        required_hops=2,
        reasoning_type=ReasoningType.COMPARISON,
        failure_modes=[FailureMode.MULTI_HOP_FAILURE],
    )


@pytest.fixture
def item_with_missing_gold() -> MCQItem:
    """Provide an MCQ item with gold evidence that doesn't exist in chunks."""
    return MCQItem(
        qid="doc_999_q1",
        question="What is in the missing document?",
        options={
            "A": "Something",
            "B": "Nothing",
            "C": "Everything",
            "D": "Unknown",
        },
        answer_key="A",
        gold_evidence=[
            GoldEvidence(
                doc_id="doc_999",
                chunk_id="doc_999_0",  # This chunk doesn't exist
                char_start=0,
                char_end=10,
            ),
        ],
        slice=Slice.A,
        required_hops=1,
        reasoning_type=ReasoningType.FACTUAL_LOOKUP,
        failure_modes=[FailureMode.RETRIEVAL_MISS],
    )


# ============================================================================
# Distractor Selector Tests
# ============================================================================


class TestGetSelector:
    """Tests for the get_selector factory function."""

    def test_get_random_selector(self):
        """Test getting random selector."""
        selector = get_selector("random")
        assert isinstance(selector, RandomSelector)

    def test_get_same_doc_selector(self):
        """Test getting same doc selector."""
        selector = get_selector("same_doc")
        assert isinstance(selector, SameDocSelector)

    def test_get_semantic_selector(self):
        """Test getting semantic selector."""
        selector = get_selector("semantic")
        assert isinstance(selector, SemanticSelector)

    def test_get_unknown_selector_raises(self):
        """Test that unknown selector raises ValueError."""
        with pytest.raises(ValueError, match="Unknown distractor strategy"):
            get_selector("unknown_strategy")

    def test_available_selectors_registry(self):
        """Test that all expected selectors are in the registry."""
        assert "random" in AVAILABLE_SELECTORS
        assert "same_doc" in AVAILABLE_SELECTORS
        assert "semantic" in AVAILABLE_SELECTORS
        assert len(AVAILABLE_SELECTORS) == 3


class TestRandomSelector:
    """Tests for RandomSelector."""

    def test_select_returns_correct_count(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that selector returns the requested number of chunks."""
        selector = RandomSelector()
        distractors = selector.select(item_with_evidence, many_chunks, n=5, seed=42)
        assert len(distractors) == 5

    def test_select_excludes_gold_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that gold evidence chunks are excluded from distractors."""
        selector = RandomSelector()
        distractors = selector.select(item_with_evidence, many_chunks, n=10, seed=42)

        gold_ids = {e.chunk_id for e in item_with_evidence.gold_evidence}
        distractor_ids = {d.chunk_id for d in distractors}

        assert gold_ids.isdisjoint(distractor_ids)

    def test_select_with_seed_is_reproducible(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that selection with seed is reproducible."""
        selector = RandomSelector()
        distractors1 = selector.select(item_with_evidence, many_chunks, n=5, seed=42)
        distractors2 = selector.select(item_with_evidence, many_chunks, n=5, seed=42)

        ids1 = [d.chunk_id for d in distractors1]
        ids2 = [d.chunk_id for d in distractors2]

        assert ids1 == ids2

    def test_select_without_seed_varies(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that selection without seed can vary."""
        selector = RandomSelector()
        # Run multiple times - statistically unlikely to get same result
        results = []
        for _ in range(10):
            distractors = selector.select(item_with_evidence, many_chunks, n=5)
            ids = tuple(sorted(d.chunk_id for d in distractors))
            results.append(ids)

        # Should have at least some variation (not all identical)
        unique_results = set(results)
        assert len(unique_results) > 1

    def test_select_handles_insufficient_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test behavior when requesting more chunks than available."""
        selector = RandomSelector()
        # Request more than available (15 chunks - 1 gold = 14 available)
        distractors = selector.select(item_with_evidence, many_chunks, n=20, seed=42)

        # Should return all available (14)
        assert len(distractors) == 14

    def test_select_with_empty_chunks(self, item_with_evidence: MCQItem):
        """Test behavior with empty chunk set."""
        selector = RandomSelector()
        distractors = selector.select(item_with_evidence, {}, n=5, seed=42)
        assert len(distractors) == 0

    def test_select_returns_cdr_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that selector returns CDRChunk objects."""
        selector = RandomSelector()
        distractors = selector.select(item_with_evidence, many_chunks, n=3, seed=42)

        for chunk in distractors:
            assert isinstance(chunk, CDRChunk)


class TestSameDocSelector:
    """Tests for SameDocSelector."""

    def test_prefers_same_doc_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that selector prefers chunks from the same document."""
        selector = SameDocSelector()
        distractors = selector.select(item_with_evidence, many_chunks, n=4, seed=42)

        gold_doc_id = item_with_evidence.gold_evidence[0].doc_id
        same_doc_count = sum(1 for d in distractors if d.doc_id == gold_doc_id)

        # doc_000 has 5 chunks, 1 is gold, so 4 same-doc available
        # With n=4, all should be same-doc
        assert same_doc_count == 4

    def test_falls_back_to_other_docs(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that selector falls back to other docs when same-doc insufficient."""
        selector = SameDocSelector()
        # Request more than same-doc available (4 same-doc chunks)
        distractors = selector.select(item_with_evidence, many_chunks, n=8, seed=42)

        gold_doc_id = item_with_evidence.gold_evidence[0].doc_id
        same_doc_count = sum(1 for d in distractors if d.doc_id == gold_doc_id)
        other_doc_count = sum(1 for d in distractors if d.doc_id != gold_doc_id)

        # 4 same-doc + 4 from other docs
        assert same_doc_count == 4
        assert other_doc_count == 4

    def test_excludes_gold_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that gold chunks are excluded."""
        selector = SameDocSelector()
        distractors = selector.select(item_with_evidence, many_chunks, n=10, seed=42)

        gold_ids = {e.chunk_id for e in item_with_evidence.gold_evidence}
        distractor_ids = {d.chunk_id for d in distractors}

        assert gold_ids.isdisjoint(distractor_ids)

    def test_with_seed_is_reproducible(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test reproducibility with seed."""
        selector = SameDocSelector()
        d1 = selector.select(item_with_evidence, many_chunks, n=8, seed=42)
        d2 = selector.select(item_with_evidence, many_chunks, n=8, seed=42)

        ids1 = [d.chunk_id for d in d1]
        ids2 = [d.chunk_id for d in d2]

        assert ids1 == ids2


class TestSemanticSelector:
    """Tests for SemanticSelector (stub implementation)."""

    def test_falls_back_to_random(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that semantic selector falls back to random in v1."""
        selector = SemanticSelector()
        distractors = selector.select(item_with_evidence, many_chunks, n=5, seed=42)

        # Should return results (via fallback)
        assert len(distractors) == 5

    def test_excludes_gold_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that gold chunks are excluded even in fallback."""
        selector = SemanticSelector()
        distractors = selector.select(item_with_evidence, many_chunks, n=10, seed=42)

        gold_ids = {e.chunk_id for e in item_with_evidence.gold_evidence}
        distractor_ids = {d.chunk_id for d in distractors}

        assert gold_ids.isdisjoint(distractor_ids)

    def test_similarity_threshold_stored(self):
        """Test that similarity threshold is stored."""
        selector = SemanticSelector(similarity_threshold=0.8)
        assert selector.similarity_threshold == 0.8


# ============================================================================
# FrozenContextBuilder Tests
# ============================================================================


class TestFrozenContextBuilder:
    """Tests for FrozenContextBuilder."""

    def test_build_returns_build_result(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that build returns a BuildResult."""
        builder = FrozenContextBuilder(distractor_count=5)
        result = builder.build(item_with_evidence, many_chunks, seed=42)

        assert isinstance(result, BuildResult)
        assert isinstance(result.frozen_context, FrozenContext)

    def test_build_includes_gold_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that built context includes gold evidence chunks."""
        builder = FrozenContextBuilder(distractor_count=5)
        result = builder.build(item_with_evidence, many_chunks, seed=42)

        chunk_ids_in_context = {c["chunk_id"] for c in result.frozen_context.chunks}
        gold_ids = {e.chunk_id for e in item_with_evidence.gold_evidence}

        assert gold_ids.issubset(chunk_ids_in_context)

    def test_build_includes_correct_distractor_count(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that correct number of distractors are included."""
        distractor_count = 7
        builder = FrozenContextBuilder(distractor_count=distractor_count)
        result = builder.build(item_with_evidence, many_chunks, seed=42)

        assert result.distractor_chunk_count == distractor_count
        # Total should be gold + distractors
        assert len(result.frozen_context.chunks) == 1 + distractor_count

    def test_build_shuffles_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that chunks are shuffled (gold not always first)."""
        builder = FrozenContextBuilder(distractor_count=10)

        # Build multiple times with different seeds
        gold_first_count = 0
        for seed in range(20):
            result = builder.build(item_with_evidence, many_chunks, seed=seed)
            first_chunk_id = result.frozen_context.chunks[0]["chunk_id"]
            gold_id = item_with_evidence.gold_evidence[0].chunk_id
            if first_chunk_id == gold_id:
                gold_first_count += 1

        # Gold should not always be first (probability of 20 in a row is ~1/11^20)
        assert gold_first_count < 20

    def test_build_with_missing_gold(
        self, item_with_missing_gold: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test handling of missing gold evidence chunks."""
        builder = FrozenContextBuilder(distractor_count=5)
        result = builder.build(item_with_missing_gold, many_chunks, seed=42)

        assert len(result.missing_gold_chunks) == 1
        assert "doc_999_0" in result.missing_gold_chunks
        assert result.gold_chunk_count == 0

    def test_build_with_multi_evidence(
        self, item_with_multi_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test building with multiple gold evidence chunks."""
        builder = FrozenContextBuilder(distractor_count=5)
        result = builder.build(item_with_multi_evidence, many_chunks, seed=42)

        assert result.gold_chunk_count == 2
        chunk_ids = {c["chunk_id"] for c in result.frozen_context.chunks}
        assert "doc_000_0" in chunk_ids
        assert "doc_000_1" in chunk_ids

    def test_build_batch(
        self,
        item_with_evidence: MCQItem,
        item_with_multi_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test batch building of frozen contexts."""
        builder = FrozenContextBuilder(distractor_count=5)
        items = [item_with_evidence, item_with_multi_evidence]
        results = builder.build_batch(items, many_chunks, seed=42)

        assert len(results) == 2
        assert results[0].frozen_context.qid == item_with_evidence.qid
        assert results[1].frozen_context.qid == item_with_multi_evidence.qid

    def test_build_with_seed_reproducible(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that building with seed is reproducible."""
        builder = FrozenContextBuilder(distractor_count=5)

        result1 = builder.build(item_with_evidence, many_chunks, seed=42)
        result2 = builder.build(item_with_evidence, many_chunks, seed=42)

        ids1 = [c["chunk_id"] for c in result1.frozen_context.chunks]
        ids2 = [c["chunk_id"] for c in result2.frozen_context.chunks]

        assert ids1 == ids2

    def test_set_distractor_count(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test updating distractor count."""
        builder = FrozenContextBuilder(distractor_count=5)
        builder.set_distractor_count(8)

        result = builder.build(item_with_evidence, many_chunks, seed=42)
        assert result.distractor_chunk_count == 8

    def test_set_distractor_count_negative_raises(self):
        """Test that negative distractor count raises error."""
        builder = FrozenContextBuilder(distractor_count=5)
        with pytest.raises(ValueError, match="non-negative"):
            builder.set_distractor_count(-1)

    def test_set_selector(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test updating selector strategy."""
        builder = FrozenContextBuilder(distractor_strategy="random")
        builder.set_selector("same_doc")

        assert isinstance(builder.selector, SameDocSelector)

    def test_context_includes_text(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test that context chunks include text."""
        builder = FrozenContextBuilder(distractor_count=5)
        result = builder.build(item_with_evidence, many_chunks, seed=42)

        for chunk in result.frozen_context.chunks:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert len(chunk["text"]) > 0


# ============================================================================
# FrozenStats Tests
# ============================================================================


class TestFrozenStats:
    """Tests for FrozenStats dataclass."""

    def test_duration_calculation(self):
        """Test duration calculation."""
        from datetime import datetime, timedelta

        stats = FrozenStats()
        stats.start_time = datetime.now() - timedelta(seconds=10)
        stats.end_time = datetime.now()

        assert 9 <= stats.duration_seconds <= 11

    def test_avg_gold_per_item(self):
        """Test average gold chunks per item."""
        stats = FrozenStats(contexts_built=10, total_gold_chunks=15)
        assert stats.avg_gold_per_item == 1.5

    def test_avg_gold_per_item_zero_contexts(self):
        """Test average with zero contexts."""
        stats = FrozenStats(contexts_built=0, total_gold_chunks=0)
        assert stats.avg_gold_per_item == 0.0

    def test_avg_distractor_per_item(self):
        """Test average distractor chunks per item."""
        stats = FrozenStats(contexts_built=10, total_distractor_chunks=100)
        assert stats.avg_distractor_per_item == 10.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = FrozenStats(
            total_items=50,
            contexts_built=45,
            total_gold_chunks=50,
            total_distractor_chunks=450,
            items_with_missing_gold=5,
            chunks_loaded=1000,
        )
        d = stats.to_dict()

        assert d["total_items"] == 50
        assert d["contexts_built"] == 45
        assert d["total_gold_chunks"] == 50
        assert d["total_distractor_chunks"] == 450
        assert d["items_with_missing_gold"] == 5
        assert d["chunks_loaded"] == 1000


# ============================================================================
# FrozenPipeline Tests
# ============================================================================


class TestFrozenPipeline:
    """Tests for FrozenPipeline."""

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        pipeline = FrozenPipeline(
            validated_dir="data/validated",
            chunks_dir="data/chunks",
            output_dir="data/frozen_contexts",
            distractor_strategy="random",
            distractor_count=10,
        )

        assert pipeline.validated_dir == Path("data/validated")
        assert pipeline.chunks_dir == Path("data/chunks")
        assert pipeline.output_dir == Path("data/frozen_contexts")

    def test_run_with_empty_dirs(self, temp_dir: Path):
        """Test running pipeline with empty directories."""
        validated_dir = temp_dir / "validated"
        chunks_dir = temp_dir / "chunks"
        output_dir = temp_dir / "frozen"

        validated_dir.mkdir()
        chunks_dir.mkdir()

        pipeline = FrozenPipeline(
            validated_dir=validated_dir,
            chunks_dir=chunks_dir,
            output_dir=output_dir,
        )

        stats, contexts = pipeline.run(dry_run=True)

        assert stats.total_items == 0
        assert len(contexts) == 0

    def test_run_with_data(
        self,
        temp_dir: Path,
        item_with_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test running pipeline with actual data."""
        validated_dir = temp_dir / "validated"
        chunks_dir = temp_dir / "chunks"
        output_dir = temp_dir / "frozen"

        validated_dir.mkdir()
        chunks_dir.mkdir()

        # Write validated item
        item_file = validated_dir / "items.jsonl"
        with open(item_file, "w") as f:
            f.write(item_with_evidence.model_dump_json() + "\n")

        # Write chunks
        chunk_file = chunks_dir / "chunks.jsonl"
        with open(chunk_file, "w") as f:
            for chunk in many_chunks.values():
                f.write(chunk.model_dump_json() + "\n")

        pipeline = FrozenPipeline(
            validated_dir=validated_dir,
            chunks_dir=chunks_dir,
            output_dir=output_dir,
            distractor_count=5,
        )

        stats, contexts = pipeline.run(dry_run=False, seed=42)

        assert stats.total_items == 1
        assert stats.contexts_built == 1
        assert len(contexts) == 1

        # Check output files exist
        assert (output_dir / next(output_dir.glob("frozen_*.jsonl"))).exists()
        assert (output_dir / next(output_dir.glob("stats_*.json"))).exists()

    def test_run_dry_run(
        self,
        temp_dir: Path,
        item_with_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test dry run mode."""
        validated_dir = temp_dir / "validated"
        chunks_dir = temp_dir / "chunks"
        output_dir = temp_dir / "frozen"

        validated_dir.mkdir()
        chunks_dir.mkdir()

        # Write data
        with open(validated_dir / "items.jsonl", "w") as f:
            f.write(item_with_evidence.model_dump_json() + "\n")
        with open(chunks_dir / "chunks.jsonl", "w") as f:
            for chunk in many_chunks.values():
                f.write(chunk.model_dump_json() + "\n")

        pipeline = FrozenPipeline(
            validated_dir=validated_dir,
            chunks_dir=chunks_dir,
            output_dir=output_dir,
        )

        stats, contexts = pipeline.run(dry_run=True, seed=42)

        assert stats.contexts_built == 1
        assert len(contexts) == 1
        # Output directory should not exist in dry run
        assert not output_dir.exists()

    def test_build_single(
        self,
        temp_dir: Path,
        item_with_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test building single frozen context."""
        chunks_dir = temp_dir / "chunks"
        chunks_dir.mkdir()

        # Write chunks
        with open(chunks_dir / "chunks.jsonl", "w") as f:
            for chunk in many_chunks.values():
                f.write(chunk.model_dump_json() + "\n")

        pipeline = FrozenPipeline(
            chunks_dir=chunks_dir,
            distractor_count=5,
        )

        result = pipeline.build_single(item_with_evidence, seed=42)

        assert isinstance(result, BuildResult)
        assert result.frozen_context.qid == item_with_evidence.qid
        assert result.gold_chunk_count == 1
        assert result.distractor_chunk_count == 5

    def test_build_single_with_provided_chunks(
        self, item_with_evidence: MCQItem, many_chunks: dict[str, CDRChunk]
    ):
        """Test building single context with provided chunks."""
        pipeline = FrozenPipeline(distractor_count=3)
        result = pipeline.build_single(item_with_evidence, chunks=many_chunks, seed=42)

        assert result.frozen_context.qid == item_with_evidence.qid
        assert len(result.frozen_context.chunks) == 4  # 1 gold + 3 distractors

    def test_output_file_format(
        self,
        temp_dir: Path,
        item_with_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test that output files have correct format."""
        validated_dir = temp_dir / "validated"
        chunks_dir = temp_dir / "chunks"
        output_dir = temp_dir / "frozen"

        validated_dir.mkdir()
        chunks_dir.mkdir()

        # Write data
        with open(validated_dir / "items.jsonl", "w") as f:
            f.write(item_with_evidence.model_dump_json() + "\n")
        with open(chunks_dir / "chunks.jsonl", "w") as f:
            for chunk in many_chunks.values():
                f.write(chunk.model_dump_json() + "\n")

        pipeline = FrozenPipeline(
            validated_dir=validated_dir,
            chunks_dir=chunks_dir,
            output_dir=output_dir,
        )

        pipeline.run(dry_run=False, seed=42)

        # Read and verify output format
        frozen_file = next(output_dir.glob("frozen_*.jsonl"))
        with open(frozen_file) as f:
            line = f.readline()
            data = json.loads(line)

        assert "qid" in data
        assert "chunks" in data
        assert isinstance(data["chunks"], list)
        for chunk in data["chunks"]:
            assert "chunk_id" in chunk
            assert "text" in chunk

    def test_stats_file_format(
        self,
        temp_dir: Path,
        item_with_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test that stats file has correct format."""
        validated_dir = temp_dir / "validated"
        chunks_dir = temp_dir / "chunks"
        output_dir = temp_dir / "frozen"

        validated_dir.mkdir()
        chunks_dir.mkdir()

        # Write data
        with open(validated_dir / "items.jsonl", "w") as f:
            f.write(item_with_evidence.model_dump_json() + "\n")
        with open(chunks_dir / "chunks.jsonl", "w") as f:
            for chunk in many_chunks.values():
                f.write(chunk.model_dump_json() + "\n")

        pipeline = FrozenPipeline(
            validated_dir=validated_dir,
            chunks_dir=chunks_dir,
            output_dir=output_dir,
        )

        pipeline.run(dry_run=False, seed=42)

        # Read and verify stats format
        stats_file = next(output_dir.glob("stats_*.json"))
        with open(stats_file) as f:
            data = json.load(f)

        assert "total_items" in data
        assert "contexts_built" in data
        assert "total_gold_chunks" in data
        assert "total_distractor_chunks" in data
        assert "duration_seconds" in data


# ============================================================================
# Integration Tests
# ============================================================================


class TestFrozenModuleIntegration:
    """Integration tests for the frozen module."""

    def test_full_workflow(
        self,
        temp_dir: Path,
        item_with_evidence: MCQItem,
        item_with_multi_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test complete workflow from items to frozen contexts."""
        validated_dir = temp_dir / "validated"
        chunks_dir = temp_dir / "chunks"
        output_dir = temp_dir / "frozen"

        validated_dir.mkdir()
        chunks_dir.mkdir()

        # Write multiple items
        with open(validated_dir / "items.jsonl", "w") as f:
            f.write(item_with_evidence.model_dump_json() + "\n")
            f.write(item_with_multi_evidence.model_dump_json() + "\n")

        # Write chunks
        with open(chunks_dir / "chunks.jsonl", "w") as f:
            for chunk in many_chunks.values():
                f.write(chunk.model_dump_json() + "\n")

        # Run pipeline with same_doc strategy
        pipeline = FrozenPipeline(
            validated_dir=validated_dir,
            chunks_dir=chunks_dir,
            output_dir=output_dir,
            distractor_strategy="same_doc",
            distractor_count=5,
        )

        stats, contexts = pipeline.run(dry_run=False, seed=42)

        # Verify results
        assert stats.total_items == 2
        assert stats.contexts_built == 2
        assert len(contexts) == 2

        # Verify each context has correct structure
        for context in contexts:
            assert context.qid in [item_with_evidence.qid, item_with_multi_evidence.qid]
            assert len(context.chunks) > 0

        # Verify gold chunks are in contexts
        context1 = next(c for c in contexts if c.qid == item_with_evidence.qid)
        chunk_ids = {c["chunk_id"] for c in context1.chunks}
        assert "doc_000_0" in chunk_ids

        context2 = next(c for c in contexts if c.qid == item_with_multi_evidence.qid)
        chunk_ids = {c["chunk_id"] for c in context2.chunks}
        assert "doc_000_0" in chunk_ids
        assert "doc_000_1" in chunk_ids

    def test_different_strategies_produce_different_results(
        self,
        item_with_evidence: MCQItem,
        many_chunks: dict[str, CDRChunk],
    ):
        """Test that different strategies produce different selections."""
        random_builder = FrozenContextBuilder(
            distractor_strategy="random", distractor_count=10
        )
        same_doc_builder = FrozenContextBuilder(
            distractor_strategy="same_doc", distractor_count=10
        )

        # Use same seed for both
        random_result = random_builder.build(item_with_evidence, many_chunks, seed=42)
        same_doc_result = same_doc_builder.build(
            item_with_evidence, many_chunks, seed=42
        )

        random_ids = {c["chunk_id"] for c in random_result.frozen_context.chunks}
        same_doc_ids = {c["chunk_id"] for c in same_doc_result.frozen_context.chunks}

        # Same_doc should have more chunks from doc_000
        gold_doc_id = "doc_000"
        random_same_doc = sum(1 for cid in random_ids if cid.startswith(gold_doc_id))
        same_doc_same_doc = sum(1 for cid in same_doc_ids if cid.startswith(gold_doc_id))

        # Same_doc strategy should have more same-doc chunks
        assert same_doc_same_doc >= random_same_doc
