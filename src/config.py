"""Configuration loading and validation."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class ChunkingConfig(BaseModel):
    """Configuration for document chunking."""

    strategy: str = Field(default="fixed_window", description="Chunking strategy name")
    chunk_size: int = Field(default=512, description="Target chunk size in tokens/chars")
    chunk_overlap: int = Field(default=50, description="Overlap between chunks")


class GenerationConfig(BaseModel):
    """Configuration for MCQ generation."""

    model: str = Field(default="gemini-2.5-flash", description="Gemini model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096)
    items_per_chunk_group: int = Field(default=3, description="Target MCQ items per chunk group")


class FrozenConfig(BaseModel):
    """Configuration for frozen context building."""

    distractor_count: int = Field(default=10, description="Number of distractor chunks")
    distractor_strategy: str = Field(default="random", description="Distractor selection strategy")


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration."""

    data_dir: Path = Field(default=Path("data"), description="Base data directory")
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    frozen: FrozenConfig = Field(default_factory=FrozenConfig)
    seed: int | None = Field(default=None, description="Random seed for reproducibility")


def load_config(config_path: Path | None = None, overrides: dict[str, Any] | None = None) -> PipelineConfig:
    """Load configuration from YAML file with optional overrides.

    Args:
        config_path: Path to YAML config file. If None, uses defaults.
        overrides: Dictionary of values to override after loading.

    Returns:
        Validated PipelineConfig instance.
    """
    load_dotenv()

    config_dict: dict[str, Any] = {}

    if config_path and config_path.exists():
        with open(config_path) as f:
            config_dict = yaml.safe_load(f) or {}

    if overrides:
        _deep_merge(config_dict, overrides)

    return PipelineConfig(**config_dict)


def get_gemini_api_key() -> str:
    """Get Gemini API key from environment."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    return key


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override dict into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
