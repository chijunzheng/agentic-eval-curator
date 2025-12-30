"""Tests for the export module."""

import json
from pathlib import Path

import pytest

from src.export.exporter import DatasetExporter, ExportManifest, ExportPipeline
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


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_items() -> list[MCQItem]:
    """Provide a list of sample MCQ items for testing."""
    return [
        MCQItem(
            qid="doc1_q1",
            question="What is the maximum UE transmit power for FR1 bands?",
            options={"A": "20 dBm", "B": "23 dBm", "C": "26 dBm", "D": "30 dBm"},
            answer_key="B",
            gold_evidence=[
                GoldEvidence(doc_id="doc1", chunk_id="doc1_0", char_start=10, char_end=20)
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        ),
        MCQItem(
            qid="doc1_q2",
            question="What is the difference between FR1 and FR2 power limits?",
            options={"A": "1 dBm", "B": "2 dBm", "C": "3 dBm", "D": "5 dBm"},
            answer_key="A",
            gold_evidence=[
                GoldEvidence(doc_id="doc1", chunk_id="doc1_0", char_start=10, char_end=20),
                GoldEvidence(doc_id="doc1", chunk_id="doc1_1", char_start=5, char_end=15),
            ],
            slice=Slice.B,
            required_hops=2,
            reasoning_type=ReasoningType.COMPARISON,
            failure_modes=[FailureMode.MULTI_HOP_FAILURE],
        ),
        MCQItem(
            qid="doc2_q1",
            question="Which protocol does O-RAN fronthaul use?",
            options={"A": "CPRI", "B": "eCPRI", "C": "HTTP", "D": "gRPC"},
            answer_key="B",
            gold_evidence=[
                GoldEvidence(doc_id="doc2", chunk_id="doc2_0", char_start=0, char_end=50)
            ],
            slice=Slice.C,
            required_hops=2,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS, FailureMode.REASONING_MISS],
        ),
    ]


@pytest.fixture
def sample_frozen_contexts() -> list[FrozenContext]:
    """Provide sample frozen contexts matching sample_items."""
    return [
        FrozenContext(
            qid="doc1_q1",
            chunks=[
                {"chunk_id": "doc1_0", "text": "Gold chunk 1 text"},
                {"chunk_id": "doc1_5", "text": "Distractor chunk text"},
            ],
        ),
        FrozenContext(
            qid="doc1_q2",
            chunks=[
                {"chunk_id": "doc1_0", "text": "Gold chunk 1 text"},
                {"chunk_id": "doc1_1", "text": "Gold chunk 2 text"},
                {"chunk_id": "doc1_3", "text": "Distractor chunk text"},
            ],
        ),
        FrozenContext(
            qid="doc2_q1",
            chunks=[
                {"chunk_id": "doc2_0", "text": "Gold chunk text"},
                {"chunk_id": "doc2_1", "text": "Distractor 1"},
                {"chunk_id": "doc2_2", "text": "Distractor 2"},
            ],
        ),
    ]


# ============================================================================
# DatasetExporter Tests
# ============================================================================


class TestDatasetExporter:
    """Tests for DatasetExporter class."""

    def test_init_default(self, temp_dir):
        """Test default initialization."""
        exporter = DatasetExporter()
        assert exporter.output_dir == Path("data/export")

    def test_init_custom_dir(self, temp_dir):
        """Test initialization with custom output dir."""
        exporter = DatasetExporter(temp_dir / "custom")
        assert exporter.output_dir == temp_dir / "custom"

    def test_export_core_creates_jsonl(self, temp_dir, sample_items):
        """Test core export creates valid JSONL file."""
        exporter = DatasetExporter(temp_dir)
        output_path = exporter.export_core(sample_items)

        assert output_path.exists()
        assert output_path.name == "dataset.jsonl"

        # Verify content
        with open(output_path) as f:
            lines = [line for line in f if line.strip()]

        assert len(lines) == 3

        # Verify each line is valid JSON and has expected fields
        for line in lines:
            item = json.loads(line)
            assert "qid" in item
            assert "question" in item
            assert "options" in item
            assert "answer_key" in item
            assert "gold_evidence" in item
            assert "slice" in item

    def test_export_core_custom_path(self, temp_dir, sample_items):
        """Test export to custom path."""
        exporter = DatasetExporter(temp_dir)
        custom_path = temp_dir / "custom" / "my_dataset.jsonl"
        output_path = exporter.export_core(sample_items, output_path=custom_path)

        assert output_path == custom_path
        assert output_path.exists()

    def test_export_core_empty_items(self, temp_dir):
        """Test export with empty items list."""
        exporter = DatasetExporter(temp_dir)
        output_path = exporter.export_core([])

        assert output_path.exists()
        with open(output_path) as f:
            content = f.read()
        assert content == ""

    def test_export_frozen_includes_context(self, temp_dir, sample_items, sample_frozen_contexts):
        """Test frozen export includes frozen context field."""
        exporter = DatasetExporter(temp_dir)
        output_path = exporter.export_frozen(sample_items, sample_frozen_contexts)

        assert output_path.exists()
        assert output_path.name == "dataset_frozen.jsonl"

        with open(output_path) as f:
            lines = [line for line in f if line.strip()]

        assert len(lines) == 3

        for line in lines:
            item = json.loads(line)
            assert "frozen_context" in item
            if item["frozen_context"] is not None:
                assert isinstance(item["frozen_context"], list)
                for chunk in item["frozen_context"]:
                    assert "chunk_id" in chunk
                    assert "text" in chunk

    def test_export_frozen_missing_context_warning(self, temp_dir, sample_items):
        """Test that missing contexts produce warnings and null values."""
        exporter = DatasetExporter(temp_dir)

        # Provide only one context for three items
        partial_contexts = [
            FrozenContext(
                qid="doc1_q1",
                chunks=[{"chunk_id": "doc1_0", "text": "Gold chunk"}],
            )
        ]

        output_path = exporter.export_frozen(sample_items, partial_contexts)

        with open(output_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        # First item should have context
        assert lines[0]["frozen_context"] is not None
        # Other items should have null context
        assert lines[1]["frozen_context"] is None
        assert lines[2]["frozen_context"] is None

    def test_export_frozen_custom_path(self, temp_dir, sample_items, sample_frozen_contexts):
        """Test frozen export to custom path."""
        exporter = DatasetExporter(temp_dir)
        custom_path = temp_dir / "output" / "frozen.jsonl"
        output_path = exporter.export_frozen(
            sample_items, sample_frozen_contexts, output_path=custom_path
        )

        assert output_path == custom_path
        assert output_path.exists()

    def test_export_manifest_structure(self, temp_dir, sample_items):
        """Test manifest export has correct structure."""
        exporter = DatasetExporter(temp_dir)
        output_path = exporter.export_manifest(sample_items)

        assert output_path.exists()
        assert output_path.name == "manifest.json"

        with open(output_path) as f:
            manifest = json.load(f)

        assert manifest["version"] == "1.0.0"
        assert "created_at" in manifest
        assert manifest["total_items"] == 3
        assert manifest["includes_frozen"] is False

    def test_export_manifest_slice_counts(self, temp_dir, sample_items):
        """Test manifest correctly counts items per slice."""
        exporter = DatasetExporter(temp_dir)
        output_path = exporter.export_manifest(sample_items)

        with open(output_path) as f:
            manifest = json.load(f)

        # sample_items has: 1 Slice A, 1 Slice B, 1 Slice C
        assert manifest["items_per_slice"]["A"] == 1
        assert manifest["items_per_slice"]["B"] == 1
        assert manifest["items_per_slice"]["C"] == 1

    def test_export_manifest_hop_counts(self, temp_dir, sample_items):
        """Test manifest correctly counts items per hop count."""
        exporter = DatasetExporter(temp_dir)
        output_path = exporter.export_manifest(sample_items)

        with open(output_path) as f:
            manifest = json.load(f)

        # sample_items has: 1 x 1-hop, 2 x 2-hop
        assert manifest["items_per_hop"]["1"] == 1
        assert manifest["items_per_hop"]["2"] == 2
        assert manifest["items_per_hop"]["3"] == 0

    def test_export_manifest_with_config(self, temp_dir, sample_items):
        """Test manifest includes provided config."""
        exporter = DatasetExporter(temp_dir)
        config = {"chunking": {"strategy": "fixed_window"}, "model": "gemini-2.5-flash"}

        output_path = exporter.export_manifest(sample_items, config=config)

        with open(output_path) as f:
            manifest = json.load(f)

        assert manifest["config"] == config

    def test_export_manifest_includes_frozen_flag(self, temp_dir, sample_items):
        """Test manifest correctly sets includes_frozen flag."""
        exporter = DatasetExporter(temp_dir)

        # Without frozen
        path1 = exporter.export_manifest(sample_items, includes_frozen=False)
        with open(path1) as f:
            assert json.load(f)["includes_frozen"] is False

        # With frozen
        path2 = temp_dir / "manifest_frozen.json"
        exporter.export_manifest(sample_items, includes_frozen=True, output_path=path2)
        with open(path2) as f:
            assert json.load(f)["includes_frozen"] is True

    def test_export_manifest_custom_path(self, temp_dir, sample_items):
        """Test manifest export to custom path."""
        exporter = DatasetExporter(temp_dir)
        custom_path = temp_dir / "meta" / "info.json"
        output_path = exporter.export_manifest(sample_items, output_path=custom_path)

        assert output_path == custom_path
        assert output_path.exists()

    def test_export_all_without_frozen(self, temp_dir, sample_items):
        """Test export_all without frozen contexts."""
        exporter = DatasetExporter(temp_dir)
        results = exporter.export_all(sample_items)

        assert "core" in results
        assert "manifest" in results
        assert "frozen" not in results

        assert results["core"].exists()
        assert results["manifest"].exists()

    def test_export_all_with_frozen(self, temp_dir, sample_items, sample_frozen_contexts):
        """Test export_all with frozen contexts."""
        exporter = DatasetExporter(temp_dir)
        results = exporter.export_all(sample_items, frozen_contexts=sample_frozen_contexts)

        assert "core" in results
        assert "frozen" in results
        assert "manifest" in results

        assert results["core"].exists()
        assert results["frozen"].exists()
        assert results["manifest"].exists()

        # Verify manifest knows about frozen
        with open(results["manifest"]) as f:
            manifest = json.load(f)
        assert manifest["includes_frozen"] is True

    def test_export_all_with_config(self, temp_dir, sample_items):
        """Test export_all includes config in manifest."""
        exporter = DatasetExporter(temp_dir)
        config = {"test_key": "test_value"}
        results = exporter.export_all(sample_items, config=config)

        with open(results["manifest"]) as f:
            manifest = json.load(f)
        assert manifest["config"] == config


# ============================================================================
# ExportManifest Tests
# ============================================================================


class TestExportManifest:
    """Tests for ExportManifest dataclass."""

    def test_to_dict(self):
        """Test manifest serialization to dict."""
        manifest = ExportManifest(
            version="1.0.0",
            created_at="2024-01-01T00:00:00",
            total_items=10,
            items_per_slice={"A": 5, "B": 3, "C": 2},
            items_per_hop={1: 5, 2: 4, 3: 1},
            includes_frozen=True,
            config={"key": "value"},
        )

        result = manifest.to_dict()

        assert result["version"] == "1.0.0"
        assert result["created_at"] == "2024-01-01T00:00:00"
        assert result["total_items"] == 10
        assert result["items_per_slice"] == {"A": 5, "B": 3, "C": 2}
        assert result["items_per_hop"] == {1: 5, 2: 4, 3: 1}
        assert result["includes_frozen"] is True
        assert result["config"] == {"key": "value"}


# ============================================================================
# ExportPipeline Tests
# ============================================================================


class TestExportPipeline:
    """Tests for ExportPipeline class."""

    def test_init_default(self):
        """Test default initialization."""
        pipeline = ExportPipeline()
        assert pipeline.validated_dir == Path("data/validated")
        assert pipeline.frozen_dir == Path("data/frozen_contexts")

    def test_init_custom_dirs(self, temp_dir):
        """Test initialization with custom directories."""
        pipeline = ExportPipeline(
            validated_dir=temp_dir / "val",
            frozen_dir=temp_dir / "frozen",
            output_dir=temp_dir / "out",
        )
        assert pipeline.validated_dir == temp_dir / "val"
        assert pipeline.frozen_dir == temp_dir / "frozen"

    def test_run_empty_validated_dir(self, temp_dir):
        """Test run with empty validated directory."""
        pipeline = ExportPipeline(
            validated_dir=temp_dir / "empty",
            output_dir=temp_dir / "out",
        )

        results = pipeline.run()
        assert results == {}

    def test_run_loads_validated_items(self, temp_dir, sample_items):
        """Test run loads items from validated directory."""
        # Setup validated directory with items
        validated_dir = temp_dir / "validated"
        validated_dir.mkdir()

        items_file = validated_dir / "batch.jsonl"
        with open(items_file, "w") as f:
            for item in sample_items:
                f.write(item.model_dump_json() + "\n")

        # Run export
        pipeline = ExportPipeline(
            validated_dir=validated_dir,
            frozen_dir=temp_dir / "frozen",  # Non-existent
            output_dir=temp_dir / "export",
        )

        results = pipeline.run(include_frozen=False)

        assert "core" in results
        assert "manifest" in results

        # Verify items were loaded
        with open(results["core"]) as f:
            lines = [line for line in f if line.strip()]
        assert len(lines) == 3

    def test_run_loads_frozen_contexts(self, temp_dir, sample_items, sample_frozen_contexts):
        """Test run loads frozen contexts when requested."""
        # Setup directories
        validated_dir = temp_dir / "validated"
        validated_dir.mkdir()
        frozen_dir = temp_dir / "frozen"
        frozen_dir.mkdir()

        # Write items
        with open(validated_dir / "items.jsonl", "w") as f:
            for item in sample_items:
                f.write(item.model_dump_json() + "\n")

        # Write contexts
        with open(frozen_dir / "contexts.jsonl", "w") as f:
            for ctx in sample_frozen_contexts:
                f.write(ctx.model_dump_json() + "\n")

        # Run export
        pipeline = ExportPipeline(
            validated_dir=validated_dir,
            frozen_dir=frozen_dir,
            output_dir=temp_dir / "export",
        )

        results = pipeline.run(include_frozen=True)

        assert "frozen" in results

        # Verify frozen contexts were included
        with open(results["frozen"]) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        for item in lines:
            assert "frozen_context" in item

    def test_run_skips_frozen_when_disabled(self, temp_dir, sample_items, sample_frozen_contexts):
        """Test run skips frozen export when include_frozen=False."""
        # Setup directories with both items and contexts
        validated_dir = temp_dir / "validated"
        validated_dir.mkdir()
        frozen_dir = temp_dir / "frozen"
        frozen_dir.mkdir()

        with open(validated_dir / "items.jsonl", "w") as f:
            for item in sample_items:
                f.write(item.model_dump_json() + "\n")

        with open(frozen_dir / "contexts.jsonl", "w") as f:
            for ctx in sample_frozen_contexts:
                f.write(ctx.model_dump_json() + "\n")

        pipeline = ExportPipeline(
            validated_dir=validated_dir,
            frozen_dir=frozen_dir,
            output_dir=temp_dir / "export",
        )

        results = pipeline.run(include_frozen=False)

        assert "frozen" not in results
        assert "core" in results

    def test_run_includes_config_in_manifest(self, temp_dir, sample_items):
        """Test run includes config in manifest."""
        validated_dir = temp_dir / "validated"
        validated_dir.mkdir()

        with open(validated_dir / "items.jsonl", "w") as f:
            for item in sample_items:
                f.write(item.model_dump_json() + "\n")

        pipeline = ExportPipeline(
            validated_dir=validated_dir,
            output_dir=temp_dir / "export",
        )

        config = {"model": "gemini-2.5-flash", "chunk_size": 512}
        results = pipeline.run(include_frozen=False, config=config)

        with open(results["manifest"]) as f:
            manifest = json.load(f)

        assert manifest["config"] == config

    def test_load_items_skips_empty_lines(self, temp_dir):
        """Test item loading skips empty lines."""
        validated_dir = temp_dir / "validated"
        validated_dir.mkdir()

        item = MCQItem(
            qid="test_q1",
            question="Test?",
            options={"A": "1", "B": "2", "C": "3", "D": "4"},
            answer_key="A",
            gold_evidence=[GoldEvidence(doc_id="d", chunk_id="d_0")],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        )

        with open(validated_dir / "items.jsonl", "w") as f:
            f.write("\n")  # Empty line
            f.write(item.model_dump_json() + "\n")
            f.write("   \n")  # Whitespace line
            f.write(item.model_dump_json() + "\n")

        pipeline = ExportPipeline(validated_dir=validated_dir, output_dir=temp_dir / "out")
        items = pipeline._load_items()

        assert len(items) == 2

    def test_load_items_handles_invalid_json(self, temp_dir):
        """Test item loading handles invalid JSON gracefully."""
        validated_dir = temp_dir / "validated"
        validated_dir.mkdir()

        with open(validated_dir / "items.jsonl", "w") as f:
            f.write("not valid json\n")
            f.write('{"incomplete": "json\n')

        pipeline = ExportPipeline(validated_dir=validated_dir, output_dir=temp_dir / "out")
        items = pipeline._load_items()

        # Should return empty list without crashing
        assert len(items) == 0

    def test_load_frozen_skips_empty_lines(self, temp_dir):
        """Test frozen context loading skips empty lines."""
        frozen_dir = temp_dir / "frozen"
        frozen_dir.mkdir()

        ctx = FrozenContext(qid="q1", chunks=[{"chunk_id": "c1", "text": "text"}])

        with open(frozen_dir / "contexts.jsonl", "w") as f:
            f.write("\n")
            f.write(ctx.model_dump_json() + "\n")
            f.write("\n")

        pipeline = ExportPipeline(frozen_dir=frozen_dir, output_dir=temp_dir / "out")
        contexts = pipeline._load_frozen_contexts()

        assert len(contexts) == 1

    def test_load_frozen_handles_invalid_json(self, temp_dir):
        """Test frozen loading handles invalid JSON gracefully."""
        frozen_dir = temp_dir / "frozen"
        frozen_dir.mkdir()

        with open(frozen_dir / "contexts.jsonl", "w") as f:
            f.write("invalid\n")

        pipeline = ExportPipeline(frozen_dir=frozen_dir, output_dir=temp_dir / "out")
        contexts = pipeline._load_frozen_contexts()

        assert len(contexts) == 0
