"""Module Protocol for Starbreeder modules."""

from typing import Protocol

from starbreeder_sdk.core.module_config import Config


class Module(Protocol):
	"""Interface that Starbreeder modules must implement."""

	module_name: str
	module_dir: str

	def config(self, config_path: str) -> Config:
		"""Load and validate the module-specific config from a file path."""
		...

	def initialize(
		self,
		genotype_dirs_map: dict[str, str],
		config: Config,
		params: dict | None = None,
	) -> None:
		"""Generate root genotypes."""
		...

	def evaluate(
		self,
		genotype_dirs: list[str],
		phenotype_dirs: list[str],
		config: Config,
		params: dict | None,
	) -> None:
		"""Evaluate genotypes and save phenotype files."""
		...

	def generate(
		self,
		parent_genotype_dirs: list[str],
		child_genotype_dirs: list[str],
		config: Config,
		params: dict | None,
	) -> list[list[int]]:
		"""Generate child genotypes from parent genotypes."""
		...
