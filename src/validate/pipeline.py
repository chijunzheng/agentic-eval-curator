"""Validation pipeline for MCQ items."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.models import CDRChunk, MCQItem
from src.validate.rules import Rule, get_default_rules
from src.validate.validator import ValidationReport, Validator

logger = logging.getLogger(__name__)


@dataclass
class ValidationStats:
    """Statistics from a validation pipeline run."""

    total_items: int = 0
    passed_items: int = 0
    failed_items: int = 0
    files_processed: int = 0
    chunks_loaded: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        """Calculate run duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def pass_rate(self) -> float:
        """Calculate the pass rate as a percentage."""
        if self.total_items == 0:
            return 0.0
        return (self.passed_items / self.total_items) * 100


class ValidationPipeline:
    """
    Pipeline for validating generated MCQ items.

    Loads items from data/generated/, validates against rules,
    and partitions into data/validated/ (passed) and data/rejected/ (failed).
    """

    def __init__(
        self,
        generated_dir: Path | str = "data/generated",
        chunks_dir: Path | str = "data/chunks",
        validated_dir: Path | str = "data/validated",
        rejected_dir: Path | str = "data/rejected",
        rules: list[Rule] | None = None,
    ):
        """
        Initialize the validation pipeline.

        Args:
            generated_dir: Directory containing generated MCQ items (JSONL).
            chunks_dir: Directory containing CDR chunks (JSONL).
            validated_dir: Output directory for validated items.
            rejected_dir: Output directory for rejected items.
            rules: List of validation rules. If None, uses defaults.
        """
        self.generated_dir = Path(generated_dir)
        self.chunks_dir = Path(chunks_dir)
        self.validated_dir = Path(validated_dir)
        self.rejected_dir = Path(rejected_dir)
        self.validator = Validator(rules if rules is not None else get_default_rules())

    def run(self, dry_run: bool = False) -> tuple[ValidationStats, ValidationReport]:
        """
        Run the validation pipeline.

        Args:
            dry_run: If True, validate but don't write output files.

        Returns:
            Tuple of (ValidationStats, ValidationReport).
        """
        stats = ValidationStats()

        # Load all chunks for evidence verification
        chunks = self._load_all_chunks()
        stats.chunks_loaded = len(chunks)
        logger.info(f"Loaded {len(chunks)} chunks for validation")

        # Load all generated items
        items = self._load_generated_items()
        stats.total_items = len(items)
        stats.files_processed = len(list(self.generated_dir.glob("*.jsonl")))
        logger.info(f"Loaded {len(items)} items from {stats.files_processed} files")

        if not items:
            logger.warning("No items to validate")
            stats.end_time = datetime.now()
            return stats, ValidationReport()

        # Validate all items
        report = self.validator.validate_batch(items, chunks)
        stats.passed_items = report.passed_items
        stats.failed_items = report.failed_items

        logger.info(
            f"Validation complete: {report.passed_items}/{report.total_items} passed "
            f"({report.pass_rate:.1f}%)"
        )

        if report.failure_counts:
            logger.info(f"Failure breakdown: {report.failure_counts}")

        # Partition items into validated/rejected
        if not dry_run:
            passed_items = [
                item for item, result in zip(items, report.results)
                if result.passed
            ]
            failed_items = [
                item for item, result in zip(items, report.results)
                if not result.passed
            ]

            self._save_items(passed_items, self.validated_dir, "validated")
            self._save_items(failed_items, self.rejected_dir, "rejected")
            self._save_report(report)
        else:
            logger.info("Dry run - no files written")

        stats.end_time = datetime.now()
        return stats, report

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

    def _load_generated_items(self) -> list[MCQItem]:
        """Load all generated MCQ items."""
        items = []

        if not self.generated_dir.exists():
            logger.warning(f"Generated directory not found: {self.generated_dir}")
            return items

        for item_file in self.generated_dir.glob("*.jsonl"):
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

    def _save_items(
        self, items: list[MCQItem], output_dir: Path, label: str
    ) -> None:
        """Save items to output directory as JSONL."""
        if not items:
            logger.info(f"No {label} items to save")
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate batch ID from timestamp
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"{batch_id}.jsonl"

        with open(output_file, "w") as f:
            for item in items:
                f.write(item.model_dump_json() + "\n")

        logger.info(f"Saved {len(items)} {label} items to {output_file}")

    def _save_report(self, report: ValidationReport) -> None:
        """Save validation report to the validated directory."""
        self.validated_dir.mkdir(parents=True, exist_ok=True)

        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.validated_dir / f"report_{batch_id}.json"

        with open(report_file, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info(f"Saved validation report to {report_file}")

    def validate_single(
        self, item: MCQItem, chunks: dict[str, CDRChunk] | None = None
    ) -> tuple[bool, list[str]]:
        """
        Validate a single item (convenience method).

        Args:
            item: MCQ item to validate.
            chunks: Optional chunks dict. If None, loads from chunks_dir.

        Returns:
            Tuple of (passed, failed_rules).
        """
        if chunks is None:
            chunks = self._load_all_chunks()

        result = self.validator.validate(item, chunks)
        return result.passed, result.failed_rules
