"""Integration tests for CLI commands."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.cli import main, ingest, validate, build_frozen, export, status
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


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_docs_dir(temp_dir: Path) -> Path:
    """Create a directory with sample documents for ingestion."""
    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()

    # Create sample text file
    (docs_dir / "sample1.txt").write_text(
        "This is a sample document about telecommunications.\n"
        "It discusses 5G NR specifications.\n\n"
        "The maximum transmit power for FR1 bands is 23 dBm.\n"
        "For FR2 bands, the power limit is 22 dBm due to thermal constraints.\n"
    )

    # Create sample markdown file
    (docs_dir / "sample2.md").write_text(
        "# O-RAN Architecture\n\n"
        "The O-RAN fronthaul interface uses eCPRI protocol.\n\n"
        "## Components\n\n"
        "- O-DU: Distributed Unit\n"
        "- O-RU: Radio Unit\n"
    )

    return docs_dir


@pytest.fixture
def data_dir_with_chunks(temp_dir: Path) -> Path:
    """Create a data directory with pre-populated chunks."""
    data_dir = temp_dir / "data"
    chunks_dir = data_dir / "chunks"
    chunks_dir.mkdir(parents=True)

    # Create sample chunks
    chunks = [
        CDRChunk(
            doc_id="doc1",
            source_type=SourceType.TXT,
            chunk_id="doc1_0",
            text="The maximum UE transmit power is 23 dBm for FR1 bands.",
        ),
        CDRChunk(
            doc_id="doc1",
            source_type=SourceType.TXT,
            chunk_id="doc1_1",
            text="For FR2 bands, the power limit is 22 dBm.",
        ),
    ]

    with open(chunks_dir / "doc1.jsonl", "w") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")

    return data_dir


@pytest.fixture
def data_dir_with_generated(temp_dir: Path) -> Path:
    """Create a data directory with generated items and chunks."""
    data_dir = temp_dir / "data"
    chunks_dir = data_dir / "chunks"
    generated_dir = data_dir / "generated"
    chunks_dir.mkdir(parents=True)
    generated_dir.mkdir(parents=True)

    # Create chunks
    chunks = [
        CDRChunk(
            doc_id="doc1",
            source_type=SourceType.TXT,
            chunk_id="doc1_0",
            text="The maximum UE transmit power is 23 dBm for FR1 bands.",
        ),
    ]

    with open(chunks_dir / "doc1.jsonl", "w") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")

    # Create generated items (some valid, some invalid)
    items = [
        # Valid item
        MCQItem(
            qid="doc1_q1",
            question="What is the maximum power for FR1?",
            options={"A": "20 dBm", "B": "23 dBm", "C": "26 dBm", "D": "30 dBm"},
            answer_key="B",
            gold_evidence=[
                GoldEvidence(doc_id="doc1", chunk_id="doc1_0", char_start=28, char_end=34)
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        ),
    ]

    with open(generated_dir / "batch1.jsonl", "w") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")

    return data_dir


@pytest.fixture
def data_dir_with_validated(temp_dir: Path) -> Path:
    """Create a data directory with validated items, chunks, and frozen contexts."""
    data_dir = temp_dir / "data"
    chunks_dir = data_dir / "chunks"
    validated_dir = data_dir / "validated"
    frozen_dir = data_dir / "frozen_contexts"
    chunks_dir.mkdir(parents=True)
    validated_dir.mkdir(parents=True)
    frozen_dir.mkdir(parents=True)

    # Create chunks
    chunks = [
        CDRChunk(
            doc_id="doc1",
            source_type=SourceType.TXT,
            chunk_id="doc1_0",
            text="The maximum UE transmit power is 23 dBm for FR1 bands.",
        ),
        CDRChunk(
            doc_id="doc1",
            source_type=SourceType.TXT,
            chunk_id="doc1_1",
            text="For FR2 bands, the power limit is 22 dBm.",
        ),
    ]

    with open(chunks_dir / "doc1.jsonl", "w") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")

    # Create validated items
    items = [
        MCQItem(
            qid="doc1_q1",
            question="What is the maximum power for FR1?",
            options={"A": "20 dBm", "B": "23 dBm", "C": "26 dBm", "D": "30 dBm"},
            answer_key="B",
            gold_evidence=[
                GoldEvidence(doc_id="doc1", chunk_id="doc1_0", char_start=28, char_end=34)
            ],
            slice=Slice.A,
            required_hops=1,
            reasoning_type=ReasoningType.FACTUAL_LOOKUP,
            failure_modes=[FailureMode.RETRIEVAL_MISS],
        ),
    ]

    with open(validated_dir / "batch1.jsonl", "w") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")

    # Create frozen contexts
    contexts = [
        FrozenContext(
            qid="doc1_q1",
            chunks=[
                {"chunk_id": "doc1_0", "text": "The maximum UE transmit power is 23 dBm."},
                {"chunk_id": "doc1_1", "text": "Distractor text."},
            ],
        ),
    ]

    with open(frozen_dir / "frozen1.jsonl", "w") as f:
        for ctx in contexts:
            f.write(ctx.model_dump_json() + "\n")

    return data_dir


# ============================================================================
# Main CLI Group Tests
# ============================================================================


class TestMainGroup:
    """Tests for the main CLI group."""

    def test_help(self, runner):
        """Test --help shows usage information."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "RAG Benchmark Curator" in result.output
        assert "ingest" in result.output
        assert "generate" in result.output
        assert "validate" in result.output
        assert "build-frozen" in result.output
        assert "export" in result.output

    def test_version(self, runner):
        """Test --version shows version."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ============================================================================
# Ingest Command Tests
# ============================================================================


class TestIngestCommand:
    """Tests for the ingest command."""

    def test_help(self, runner):
        """Test ingest --help."""
        result = runner.invoke(main, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "--input-dir" in result.output
        assert "--incremental" in result.output
        assert "--dry-run" in result.output

    def test_ingest_dry_run(self, runner, sample_docs_dir, temp_dir):
        """Test ingest with --dry-run doesn't write files."""
        # Create a config that uses temp_dir as data_dir
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["ingest", "-i", str(sample_docs_dir), "-c", str(config_path), "--dry-run"],
        )

        # Should succeed
        assert "Dry run" in result.output
        assert "Files processed:" in result.output

        # No output files should exist
        assert not (temp_dir / "data" / "chunks").exists()

    def test_ingest_creates_chunks(self, runner, sample_docs_dir, temp_dir):
        """Test ingest creates chunk files."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["ingest", "-i", str(sample_docs_dir), "-c", str(config_path)],
        )

        assert "Ingestion Summary" in result.output

        # Chunks directory should exist
        chunks_dir = temp_dir / "data" / "chunks"
        assert chunks_dir.exists()

        # Should have JSONL files
        jsonl_files = list(chunks_dir.glob("*.jsonl"))
        assert len(jsonl_files) >= 1

    def test_ingest_missing_input_dir(self, runner):
        """Test ingest fails when input dir doesn't exist."""
        result = runner.invoke(
            main,
            ["ingest", "-i", "/nonexistent/path"],
        )

        assert result.exit_code != 0

    def test_ingest_incremental_flag(self, runner, sample_docs_dir, temp_dir):
        """Test incremental flag is recognized."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["ingest", "-i", str(sample_docs_dir), "-c", str(config_path), "--incremental"],
        )

        assert "Incremental mode" in result.output

    def test_ingest_with_seed(self, runner, sample_docs_dir, temp_dir):
        """Test ingest with --seed option."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["ingest", "-i", str(sample_docs_dir), "-c", str(config_path), "--seed", "42"],
        )

        # Should complete without error
        assert "Ingestion Summary" in result.output


# ============================================================================
# Generate Command Tests
# ============================================================================


class TestGenerateCommand:
    """Tests for the generate command."""

    def test_help(self, runner):
        """Test generate --help."""
        result = runner.invoke(main, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--slice" in result.output
        assert "--dry-run" in result.output
        assert "--seed" in result.output

    def test_generate_dry_run_no_chunks(self, runner, temp_dir):
        """Test generate --dry-run with no chunks shows error."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["generate", "-c", str(config_path), "--dry-run"],
        )

        # Should report no chunks found
        assert "Chunks processed:  0" in result.output or "No chunks found" in result.output

    def test_generate_slice_option(self, runner, temp_dir):
        """Test generate with --slice option."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["generate", "-c", str(config_path), "--slice", "A", "--dry-run"],
        )

        # Should show slice A
        assert "Slice: A" in result.output


# ============================================================================
# Validate Command Tests
# ============================================================================


class TestValidateCommand:
    """Tests for the validate command."""

    def test_help(self, runner):
        """Test validate --help."""
        result = runner.invoke(main, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output
        assert "--config" in result.output

    def test_validate_dry_run(self, runner, data_dir_with_generated):
        """Test validate --dry-run."""
        config_path = data_dir_with_generated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_generated}\n")

        result = runner.invoke(
            main,
            ["validate", "-c", str(config_path), "--dry-run"],
        )

        assert "Validation Summary" in result.output
        assert "Dry run" in result.output

    def test_validate_creates_output(self, runner, data_dir_with_generated):
        """Test validate creates validated and rejected directories."""
        config_path = data_dir_with_generated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_generated}\n")

        result = runner.invoke(
            main,
            ["validate", "-c", str(config_path)],
        )

        assert "Validation Summary" in result.output

        # Should create validated directory
        validated_dir = data_dir_with_generated / "validated"
        assert validated_dir.exists()


# ============================================================================
# Build-Frozen Command Tests
# ============================================================================


class TestBuildFrozenCommand:
    """Tests for the build-frozen command."""

    def test_help(self, runner):
        """Test build-frozen --help."""
        result = runner.invoke(main, ["build-frozen", "--help"])
        assert result.exit_code == 0
        assert "--distractor-strategy" in result.output
        assert "--distractor-count" in result.output
        assert "--dry-run" in result.output
        assert "--seed" in result.output

    def test_build_frozen_dry_run(self, runner, data_dir_with_validated):
        """Test build-frozen --dry-run."""
        config_path = data_dir_with_validated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_validated}\n")

        result = runner.invoke(
            main,
            ["build-frozen", "-c", str(config_path), "--dry-run"],
        )

        assert "Frozen Context Summary" in result.output
        assert "Dry run" in result.output

    def test_build_frozen_strategy_option(self, runner, data_dir_with_validated):
        """Test build-frozen with --distractor-strategy."""
        config_path = data_dir_with_validated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_validated}\n")

        result = runner.invoke(
            main,
            [
                "build-frozen",
                "-c",
                str(config_path),
                "--distractor-strategy",
                "same_doc",
                "--dry-run",
            ],
        )

        assert "Strategy: same_doc" in result.output

    def test_build_frozen_count_option(self, runner, data_dir_with_validated):
        """Test build-frozen with --distractor-count."""
        config_path = data_dir_with_validated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_validated}\n")

        result = runner.invoke(
            main,
            ["build-frozen", "-c", str(config_path), "-n", "5", "--dry-run"],
        )

        assert "Distractor count: 5" in result.output


# ============================================================================
# Export Command Tests
# ============================================================================


class TestExportCommand:
    """Tests for the export command."""

    def test_help(self, runner):
        """Test export --help."""
        result = runner.invoke(main, ["export", "--help"])
        assert result.exit_code == 0
        assert "--output-dir" in result.output
        assert "--include-frozen" in result.output
        assert "--no-frozen" in result.output

    def test_export_with_frozen(self, runner, data_dir_with_validated):
        """Test export with frozen contexts."""
        config_path = data_dir_with_validated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_validated}\n")

        output_dir = data_dir_with_validated.parent / "export"

        result = runner.invoke(
            main,
            ["export", "-c", str(config_path), "-o", str(output_dir), "--include-frozen"],
        )

        assert "Export Summary" in result.output
        assert "Export complete" in result.output

        # Check files exist
        assert (output_dir / "dataset.jsonl").exists()
        assert (output_dir / "dataset_frozen.jsonl").exists()
        assert (output_dir / "manifest.json").exists()

    def test_export_without_frozen(self, runner, data_dir_with_validated):
        """Test export without frozen contexts."""
        config_path = data_dir_with_validated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_validated}\n")

        output_dir = data_dir_with_validated.parent / "export"

        result = runner.invoke(
            main,
            ["export", "-c", str(config_path), "-o", str(output_dir), "--no-frozen"],
        )

        assert "Excluding frozen contexts" in result.output
        assert "Export Summary" in result.output

        # dataset_frozen.jsonl should not exist
        assert (output_dir / "dataset.jsonl").exists()
        assert not (output_dir / "dataset_frozen.jsonl").exists()

    def test_export_empty_validated(self, runner, temp_dir):
        """Test export with no validated items."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["export", "-c", str(config_path)],
        )

        assert "No items to export" in result.output
        assert result.exit_code == 1


# ============================================================================
# Status Command Tests
# ============================================================================


class TestStatusCommand:
    """Tests for the status command."""

    def test_help(self, runner):
        """Test status --help."""
        result = runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0

    def test_status_empty_data_dir(self, runner, temp_dir):
        """Test status with empty data directory."""
        config_path = temp_dir / "config.yaml"
        config_path.write_text(f"data_dir: {temp_dir / 'data'}\n")

        result = runner.invoke(
            main,
            ["status", "-c", str(config_path)],
        )

        assert "Data directory" in result.output
        # Should show (not found) for missing directories
        assert "(not found)" in result.output

    def test_status_with_data(self, runner, data_dir_with_validated):
        """Test status with populated data directory."""
        config_path = data_dir_with_validated.parent / "config.yaml"
        config_path.write_text(f"data_dir: {data_dir_with_validated}\n")

        result = runner.invoke(
            main,
            ["status", "-c", str(config_path)],
        )

        assert "Data directory" in result.output
        assert "CDR chunks:" in result.output
        assert "Validated items:" in result.output
        # Should show file counts
        assert "Files:" in result.output


# ============================================================================
# Config Loading Tests
# ============================================================================


class TestConfigLoading:
    """Tests for configuration loading across commands."""

    def test_missing_config_uses_defaults(self, runner, sample_docs_dir):
        """Test commands work without explicit config file."""
        result = runner.invoke(
            main,
            ["ingest", "-i", str(sample_docs_dir), "--dry-run"],
        )

        # Should work with defaults
        assert "Dry run" in result.output

    def test_invalid_config_path(self, runner, sample_docs_dir):
        """Test commands fail gracefully with invalid config path."""
        result = runner.invoke(
            main,
            ["ingest", "-i", str(sample_docs_dir), "-c", "/nonexistent/config.yaml"],
        )

        assert result.exit_code != 0

    def test_custom_config_values(self, runner, sample_docs_dir, temp_dir):
        """Test custom config values are applied."""
        config_path = temp_dir / "custom_config.yaml"
        config_path.write_text(
            f"""
data_dir: {temp_dir / 'data'}
chunking:
  strategy: semantic
  chunk_size: 256
  chunk_overlap: 25
"""
        )

        result = runner.invoke(
            main,
            ["ingest", "-i", str(sample_docs_dir), "-c", str(config_path)],
        )

        # Should complete without error
        assert "Ingestion Summary" in result.output
