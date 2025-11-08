"""Module Protocol for Starbreeder modules."""

from typing import Protocol

from starbreeder_module.core.module_config import Config


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
		"""Generate root genotypes and save them into provided directories."""
		...

	def generate(
		self,
		parent_genotype_dirs: list[str],
		child_genotype_dirs: list[str],
		config: Config,
		params: dict | None,
	) -> list[list[int]]:
		"""Create child genotypes from parent genotypes. Returns parent indices per child."""
		...

	def evaluate(
		self,
		genotype_dirs: list[str],
		phenotype_dirs: list[str],
		config: Config,
		params: dict | None,
	) -> None:
		"""Evaluate genotypes and write phenotype files to the provided directories."""
		...
