"""Dataset export functionality for JSONL format."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import FrozenContext, MCQItem, Slice

logger = logging.getLogger(__name__)


@dataclass
class ExportManifest:
    """Manifest metadata for an exported dataset."""

    version: str
    created_at: str
    total_items: int
    items_per_slice: dict[str, int]
    items_per_hop: dict[int, int]
    includes_frozen: bool
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "total_items": self.total_items,
            "items_per_slice": self.items_per_slice,
            "items_per_hop": self.items_per_hop,
            "includes_frozen": self.includes_frozen,
            "config": self.config,
        }


class DatasetExporter:
    """
    Export validated MCQ items and frozen contexts to JSONL datasets.

    Supports three export formats:
    - Core dataset: MCQ items only (dataset.jsonl)
    - Frozen dataset: MCQ items with frozen contexts attached (dataset_frozen.jsonl)
    - Manifest: Corpus metadata and generation config (manifest.json)
    """

    VERSION = "1.0.0"

    def __init__(self, output_dir: Path | str = "data/export"):
        """
        Initialize the exporter.

        Args:
            output_dir: Directory to write exported files.
        """
        self.output_dir = Path(output_dir)

    def export_core(
        self,
        items: list[MCQItem],
        output_path: Path | str | None = None,
    ) -> Path:
        """
        Export core dataset with MCQ items only.

        Args:
            items: List of MCQItem objects to export.
            output_path: Optional output path. If None, uses default.

        Returns:
            Path to the exported file.
        """
        if output_path is None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.output_dir / "dataset.jsonl"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(item.model_dump_json() + "\n")

        logger.info(f"Exported {len(items)} items to {output_path}")
        return output_path

    def export_frozen(
        self,
        items: list[MCQItem],
        frozen_contexts: list[FrozenContext],
        output_path: Path | str | None = None,
    ) -> Path:
        """
        Export dataset with frozen contexts attached to each item.

        Each line contains the MCQ item with an additional 'frozen_context' field
        containing the pre-determined retrieval chunks.

        Args:
            items: List of MCQItem objects to export.
            frozen_contexts: List of FrozenContext objects (must match items by qid).
            output_path: Optional output path. If None, uses default.

        Returns:
            Path to the exported file.
        """
        if output_path is None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.output_dir / "dataset_frozen.jsonl"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build context lookup by qid
        context_map = {ctx.qid: ctx for ctx in frozen_contexts}

        exported_count = 0
        missing_context = 0

        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                item_dict = item.model_dump()

                # Attach frozen context if available
                if item.qid in context_map:
                    frozen_ctx = context_map[item.qid]
                    item_dict["frozen_context"] = frozen_ctx.chunks
                    exported_count += 1
                else:
                    item_dict["frozen_context"] = None
                    missing_context += 1
                    logger.warning(f"No frozen context found for item {item.qid}")

                f.write(json.dumps(item_dict) + "\n")

        if missing_context > 0:
            logger.warning(
                f"{missing_context}/{len(items)} items have no frozen context"
            )

        logger.info(f"Exported {exported_count} items with frozen context to {output_path}")
        return output_path

    def export_manifest(
        self,
        items: list[MCQItem],
        config: dict[str, Any] | None = None,
        includes_frozen: bool = False,
        output_path: Path | str | None = None,
    ) -> Path:
        """
        Export manifest with corpus metadata and generation config.

        Args:
            items: List of MCQItem objects in the dataset.
            config: Optional config dict to include in manifest.
            includes_frozen: Whether the export includes frozen contexts.
            output_path: Optional output path. If None, uses default.

        Returns:
            Path to the exported manifest file.
        """
        if output_path is None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.output_dir / "manifest.json"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Count items per slice
        items_per_slice: dict[str, int] = {s.value: 0 for s in Slice}
        for item in items:
            items_per_slice[item.slice.value] += 1

        # Count items per hop
        items_per_hop: dict[int, int] = {1: 0, 2: 0, 3: 0}
        for item in items:
            hop = item.required_hops
            if hop in items_per_hop:
                items_per_hop[hop] += 1

        manifest = ExportManifest(
            version=self.VERSION,
            created_at=datetime.now().isoformat(),
            total_items=len(items),
            items_per_slice=items_per_slice,
            items_per_hop=items_per_hop,
            includes_frozen=includes_frozen,
            config=config or {},
        )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        logger.info(f"Exported manifest to {output_path}")
        return output_path

    def export_all(
        self,
        items: list[MCQItem],
        frozen_contexts: list[FrozenContext] | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """
        Export all dataset files (core, frozen if available, manifest).

        Args:
            items: List of MCQItem objects to export.
            frozen_contexts: Optional list of FrozenContext objects.
            config: Optional config dict to include in manifest.

        Returns:
            Dict mapping file type to output path.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        # Export core dataset
        result["core"] = self.export_core(items)

        # Export frozen dataset if contexts provided
        includes_frozen = frozen_contexts is not None and len(frozen_contexts) > 0
        if includes_frozen:
            result["frozen"] = self.export_frozen(items, frozen_contexts)

        # Export manifest
        result["manifest"] = self.export_manifest(
            items, config=config, includes_frozen=includes_frozen
        )

        return result


class ExportPipeline:
    """
    Pipeline for exporting validated datasets.

    Loads validated items and frozen contexts from their respective directories
    and exports them to the specified output directory.
    """

    def __init__(
        self,
        validated_dir: Path | str = "data/validated",
        frozen_dir: Path | str = "data/frozen_contexts",
        output_dir: Path | str = "data/export",
    ):
        """
        Initialize the export pipeline.

        Args:
            validated_dir: Directory containing validated MCQ items (JSONL).
            frozen_dir: Directory containing frozen contexts (JSONL).
            output_dir: Output directory for exported files.
        """
        self.validated_dir = Path(validated_dir)
        self.frozen_dir = Path(frozen_dir)
        self.exporter = DatasetExporter(output_dir)

    def run(
        self,
        include_frozen: bool = True,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """
        Run the export pipeline.

        Args:
            include_frozen: Whether to include frozen contexts in export.
            config: Optional config dict to include in manifest.

        Returns:
            Dict mapping file type to output path.
        """
        # Load validated items
        items = self._load_items()
        logger.info(f"Loaded {len(items)} validated items")

        if not items:
            logger.warning("No items to export")
            return {}

        # Load frozen contexts if requested
        frozen_contexts = None
        if include_frozen:
            frozen_contexts = self._load_frozen_contexts()
            logger.info(f"Loaded {len(frozen_contexts)} frozen contexts")

        # Export all
        return self.exporter.export_all(items, frozen_contexts, config)

    def _load_items(self) -> list[MCQItem]:
        """Load validated MCQ items from the validated directory."""
        items = []

        if not self.validated_dir.exists():
            logger.warning(f"Validated directory not found: {self.validated_dir}")
            return items

        for item_file in self.validated_dir.glob("*.jsonl"):
            with open(item_file, encoding="utf-8") as f:
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

    def _load_frozen_contexts(self) -> list[FrozenContext]:
        """Load frozen contexts from the frozen directory."""
        contexts = []

        if not self.frozen_dir.exists():
            logger.warning(f"Frozen directory not found: {self.frozen_dir}")
            return contexts

        for ctx_file in self.frozen_dir.glob("*.jsonl"):
            with open(ctx_file, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        context = FrozenContext(**data)
                        contexts.append(context)
                    except Exception as e:
                        logger.error(f"Failed to parse context from {ctx_file}: {e}")

        return contexts
