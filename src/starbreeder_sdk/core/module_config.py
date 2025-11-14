"""Base configuration for modules."""

import logging
from typing import Any

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# --- Initialize config ---
class InitializeRootIndividualConfig(BaseModel):
	"""Initialize root individual configuration."""

	method: str
	params: dict[str, Any] | None = None


class InitializeConfig(BaseModel):
	"""Initialize configuration."""

	root_individuals: dict[str, InitializeRootIndividualConfig]


# --- Evaluate config ---
class EvaluatePhenotypeConfig(BaseModel):
	"""Evaluate phenotype configuration."""

	name: str
	content_type: str


class EvaluateConfig(BaseModel):
	"""Evaluate configuration."""

	phenotype: dict[str, EvaluatePhenotypeConfig]


# --- Generate config ---
class GenerateConfig(BaseModel):
	"""Generate configuration."""

	population_size: int


# --- Config ---
class Config(BaseModel):
	"""Module configuration."""

	initialize: InitializeConfig
	evaluate: EvaluateConfig
	generate: GenerateConfig


def load_config_from_file[T: BaseModel](config_path: str, config_class: type[T]) -> T:
	"""Load and validate config."""
	logger.info(f"Loading configuration from: {config_path}")
	try:
		with open(config_path) as f:
			config_data = yaml.safe_load(f)

		validated_config = config_class(**config_data)
		return validated_config

	except FileNotFoundError:
		logger.error(f"Config file not found at {config_path}")
		raise
	except Exception as e:
		logger.error(f"Failed to load or validate config {config_path}: {e}")
		raise
