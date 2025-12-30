"""Command-line interface for the RAG Benchmark Curator."""

import logging
import sys
from pathlib import Path

import click

from src.config import PipelineConfig, load_config
from src.models import Slice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_config(config_path: str | None, overrides: dict | None = None) -> PipelineConfig:
    """Load configuration from file with optional overrides."""
    path = Path(config_path) if config_path else None
    return load_config(path, overrides)


@click.group()
@click.version_option(version="0.1.0", prog_name="rag-bench")
def main():
    """RAG Benchmark Curator - Generate MCQ evaluation datasets from documents.

    A CLI tool for ingesting documents, generating MCQ items with gold evidence,
    validating items, building frozen retrieval contexts, and exporting datasets.
    """
    pass


@main.command()
@click.option(
    "--input-dir", "-i",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing source documents to ingest.",
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to YAML configuration file.",
)
@click.option(
    "--incremental",
    is_flag=True,
    default=False,
    help="Skip files that haven't changed since last ingestion.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Process files but don't write output.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility.",
)
def ingest(
    input_dir: Path,
    config: str | None,
    incremental: bool,
    dry_run: bool,
    seed: int | None,
):
    """Ingest documents and convert to CDR chunks.

    Parses documents from INPUT_DIR, splits them into chunks, and saves
    as JSONL files in data/chunks/.

    Supported formats: PDF, TXT, MD, CSV, JSON, HTML
    """
    from src.ingest.pipeline import IngestPipeline

    overrides = {}
    if seed is not None:
        overrides["seed"] = seed

    cfg = get_config(config, overrides if overrides else None)
    pipeline = IngestPipeline(cfg)

    click.echo(f"Ingesting documents from {input_dir}")
    if incremental:
        click.echo("Incremental mode: skipping unchanged files")
    if dry_run:
        click.echo("Dry run: no files will be written")

    stats = pipeline.run(input_dir, incremental=incremental, dry_run=dry_run)

    click.echo("")
    click.echo("=== Ingestion Summary ===")
    click.echo(f"Files processed: {stats.files_processed}")
    click.echo(f"Files skipped:   {stats.files_skipped}")
    click.echo(f"Files failed:    {stats.files_failed}")
    click.echo(f"Chunks created:  {stats.chunks_created}")

    if stats.errors:
        click.echo("")
        click.echo("Errors:")
        for error in stats.errors[:10]:  # Limit output
            click.echo(f"  - {error}")
        if len(stats.errors) > 10:
            click.echo(f"  ... and {len(stats.errors) - 10} more")

    sys.exit(1 if stats.files_failed > 0 else 0)


@main.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to YAML configuration file.",
)
@click.option(
    "--slice", "-s",
    type=click.Choice(["A", "B", "C", "all"]),
    default="all",
    help="Generate for specific slice or all.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generate but don't write output.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility.",
)
def generate(
    config: str | None,
    slice: str,
    dry_run: bool,
    seed: int | None,
):
    """Generate MCQ items from ingested chunks.

    Reads chunks from data/chunks/ and generates MCQ items using the
    configured LLM. Outputs to data/generated/.

    Requires GEMINI_API_KEY environment variable to be set.
    """
    from src.generate.pipeline import GenerationPipeline

    overrides = {}
    if seed is not None:
        overrides["seed"] = seed

    cfg = get_config(config, overrides if overrides else None)

    # Parse slice
    slice_type = None
    if slice != "all":
        slice_type = Slice(slice)

    pipeline = GenerationPipeline(cfg)

    click.echo("Generating MCQ items...")
    if slice_type:
        click.echo(f"Slice: {slice_type.value}")
    else:
        click.echo("Slice: all (A, B, C)")
    if dry_run:
        click.echo("Dry run: no files will be written")

    stats = pipeline.run(slice_type=slice_type, dry_run=dry_run, seed=seed)

    click.echo("")
    click.echo("=== Generation Summary ===")
    click.echo(f"Batch ID:          {stats.batch_id}")
    click.echo(f"Chunks processed:  {stats.chunks_processed}")
    click.echo(f"Items generated:   {stats.items_generated}")
    click.echo(f"Items per slice:")
    for s, count in stats.items_per_slice.items():
        click.echo(f"  Slice {s}: {count}")

    if stats.errors:
        click.echo("")
        click.echo("Errors:")
        for error in stats.errors[:10]:
            click.echo(f"  - {error}")
        if len(stats.errors) > 10:
            click.echo(f"  ... and {len(stats.errors) - 10} more")

    sys.exit(0)


@main.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to YAML configuration file.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Validate but don't write output.",
)
def validate(
    config: str | None,
    dry_run: bool,
):
    """Validate generated MCQ items against quality rules.

    Reads items from data/generated/, validates against rules, and
    partitions into data/validated/ (passed) and data/rejected/ (failed).

    Validation rules:
    - Single correct answer (A/B/C/D)
    - All options present and non-empty
    - Gold evidence exists in referenced chunks
    - No ambiguous distractors
    - Hop count consistent with slice
    - Evidence count matches required hops
    """
    from src.validate.pipeline import ValidationPipeline

    cfg = get_config(config)

    pipeline = ValidationPipeline(
        generated_dir=cfg.data_dir / "generated",
        chunks_dir=cfg.data_dir / "chunks",
        validated_dir=cfg.data_dir / "validated",
        rejected_dir=cfg.data_dir / "rejected",
    )

    click.echo("Validating MCQ items...")
    if dry_run:
        click.echo("Dry run: no files will be written")

    stats, report = pipeline.run(dry_run=dry_run)

    click.echo("")
    click.echo("=== Validation Summary ===")
    click.echo(f"Files processed:  {stats.files_processed}")
    click.echo(f"Chunks loaded:    {stats.chunks_loaded}")
    click.echo(f"Total items:      {stats.total_items}")
    click.echo(f"Passed:           {stats.passed_items} ({stats.pass_rate:.1f}%)")
    click.echo(f"Failed:           {stats.failed_items}")
    click.echo(f"Duration:         {stats.duration_seconds:.1f}s")

    if report.failure_counts:
        click.echo("")
        click.echo("Failure breakdown:")
        for rule, count in sorted(report.failure_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {rule}: {count}")

    sys.exit(0 if stats.failed_items == 0 else 1)


@main.command("build-frozen")
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to YAML configuration file.",
)
@click.option(
    "--distractor-strategy",
    type=click.Choice(["random", "same_doc", "semantic"]),
    default=None,
    help="Strategy for selecting distractor chunks.",
)
@click.option(
    "--distractor-count", "-n",
    type=int,
    default=None,
    help="Number of distractor chunks per item.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Build contexts but don't write output.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility.",
)
def build_frozen(
    config: str | None,
    distractor_strategy: str | None,
    distractor_count: int | None,
    dry_run: bool,
    seed: int | None,
):
    """Build frozen retrieval contexts for validated items.

    Reads validated items from data/validated/, combines gold evidence
    chunks with distractor chunks, and outputs to data/frozen_contexts/.

    The frozen context ensures identical retrieval for comparing
    naive RAG vs agentic RAG reasoning capabilities.
    """
    from src.frozen.pipeline import FrozenPipeline

    overrides: dict = {}
    if seed is not None:
        overrides["seed"] = seed
    if distractor_strategy is not None:
        overrides.setdefault("frozen", {})["distractor_strategy"] = distractor_strategy
    if distractor_count is not None:
        overrides.setdefault("frozen", {})["distractor_count"] = distractor_count

    cfg = get_config(config, overrides if overrides else None)

    pipeline = FrozenPipeline(
        validated_dir=cfg.data_dir / "validated",
        chunks_dir=cfg.data_dir / "chunks",
        output_dir=cfg.data_dir / "frozen_contexts",
        distractor_strategy=cfg.frozen.distractor_strategy,
        distractor_count=cfg.frozen.distractor_count,
    )

    click.echo("Building frozen contexts...")
    click.echo(f"Strategy: {cfg.frozen.distractor_strategy}")
    click.echo(f"Distractor count: {cfg.frozen.distractor_count}")
    if dry_run:
        click.echo("Dry run: no files will be written")

    stats, contexts = pipeline.run(dry_run=dry_run, seed=seed)

    click.echo("")
    click.echo("=== Frozen Context Summary ===")
    click.echo(f"Total items:          {stats.total_items}")
    click.echo(f"Contexts built:       {stats.contexts_built}")
    click.echo(f"Chunks loaded:        {stats.chunks_loaded}")
    click.echo(f"Avg gold per item:    {stats.avg_gold_per_item:.1f}")
    click.echo(f"Avg distractor:       {stats.avg_distractor_per_item:.1f}")
    click.echo(f"Duration:             {stats.duration_seconds:.1f}s")

    if stats.items_with_missing_gold > 0:
        click.echo("")
        click.echo(f"Warning: {stats.items_with_missing_gold} items had missing gold chunks")

    sys.exit(0)


@main.command()
@click.option(
    "--output-dir", "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output directory for exported files.",
)
@click.option(
    "--include-frozen/--no-frozen",
    default=True,
    help="Include frozen contexts in export.",
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to YAML configuration file.",
)
def export(
    output_dir: Path | None,
    include_frozen: bool,
    config: str | None,
):
    """Export validated dataset to JSONL files.

    Exports:
    - dataset.jsonl: Core MCQ items
    - dataset_frozen.jsonl: Items with frozen contexts (if --include-frozen)
    - manifest.json: Corpus metadata and item counts per slice

    Default output directory: data/export/
    """
    from src.export.exporter import ExportPipeline

    cfg = get_config(config)

    effective_output_dir = output_dir or (cfg.data_dir / "export")

    pipeline = ExportPipeline(
        validated_dir=cfg.data_dir / "validated",
        frozen_dir=cfg.data_dir / "frozen_contexts",
        output_dir=effective_output_dir,
    )

    click.echo(f"Exporting dataset to {effective_output_dir}")
    if include_frozen:
        click.echo("Including frozen contexts")
    else:
        click.echo("Excluding frozen contexts")

    # Build config dict for manifest
    config_dict = {
        "chunking": cfg.chunking.model_dump(),
        "generation": cfg.generation.model_dump(),
        "frozen": cfg.frozen.model_dump(),
    }

    results = pipeline.run(include_frozen=include_frozen, config=config_dict)

    if not results:
        click.echo("No items to export.")
        sys.exit(1)

    click.echo("")
    click.echo("=== Export Summary ===")
    for file_type, path in results.items():
        click.echo(f"  {file_type}: {path}")

    click.echo("")
    click.echo("Export complete!")
    sys.exit(0)


@main.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to YAML configuration file.",
)
def status(config: str | None):
    """Show pipeline status and data directory contents.

    Displays counts of chunks, generated items, validated items,
    rejected items, and frozen contexts.
    """
    import json

    cfg = get_config(config)

    data_dir = Path(cfg.data_dir)

    click.echo(f"Data directory: {data_dir}")
    click.echo("")

    # Count files in each directory
    directories = {
        "chunks": "CDR chunks",
        "generated": "Generated items",
        "validated": "Validated items",
        "rejected": "Rejected items",
        "frozen_contexts": "Frozen contexts",
        "export": "Exported files",
    }

    for subdir, label in directories.items():
        path = data_dir / subdir
        if path.exists():
            jsonl_files = list(path.glob("*.jsonl"))
            json_files = list(path.glob("*.json"))

            # Count lines (items) in JSONL files
            item_count = 0
            for f in jsonl_files:
                with open(f) as fp:
                    item_count += sum(1 for line in fp if line.strip())

            click.echo(f"{label}:")
            click.echo(f"  Files: {len(jsonl_files)} JSONL, {len(json_files)} JSON")
            if jsonl_files:
                click.echo(f"  Items: {item_count}")
        else:
            click.echo(f"{label}: (not found)")
        click.echo("")

    # Show manifest info if exists
    manifest_path = data_dir / "corpus_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
        click.echo(f"Corpus manifest: {len(manifest)} documents tracked")


if __name__ == "__main__":
    main()
