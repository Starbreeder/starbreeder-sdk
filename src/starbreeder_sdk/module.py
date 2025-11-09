"""Module protocol for Starbreeder modules.

This file defines the interface a Starbreeder module must implement to plug
into the SDK web service. A concrete module provides its own evolutionary
logic while the SDK handles HTTP I/O, concurrency, and object-store
integration.

Notes:
	- Implementations may subclass `Config` to add module-specific fields.
	- All file-system paths are absolute and refer to temporary working
		directories created by the SDK.
	- Implementations MUST be thread-safe for blocking work or strictly
		perform blocking work only on the thread they are invoked on.

"""

from typing import Protocol

from starbreeder_sdk.core.module_config import Config


class Module(Protocol):
	"""Interface that Starbreeder modules must implement.

	Attributes:
		module_name: Human-readable, short module name (e.g. "lenia").
		module_dir: Absolute path to the module's root directory that contains
			a `configs/` subdirectory with configuration files.

	"""

	module_name: str
	module_dir: str

	def config(self, config_path: str) -> Config:
		"""Load and validate a module configuration.

		Args:
			config_path: Absolute path to a module config file to parse and
				validate.

		Returns:
			Config: A validated configuration instance (or subclass).

		Raises:
			FileNotFoundError: If `config_path` does not exist.
			Exception: If parsing or validation fails.

		"""
		...

	def initialize(
		self,
		genotype_dirs_map: dict[str, str],
		config: Config,
		params: dict | None = None,
	) -> None:
		"""Generate root genotypes.

		The implementation must write genotype files to the provided
		per-root directories. The key for `genotype_dirs_map` is a root key
		declared in the configuration.

		Args:
			genotype_dirs_map: Mapping of root keys to absolute directories
				where genotype files MUST be written under `genotype/`.
			config: The validated configuration object.
			params: Optional free-form parameters.

		Raises:
			Exception: If generation fails for any root.

		"""
		...

	def evaluate(
		self,
		genotype_dirs: list[str],
		phenotype_dirs: list[str],
		config: Config,
		params: dict | None,
	) -> None:
		"""Evaluate genotypes.

		The implementation must read each genotype directory and write all
		required phenotype files into the corresponding phenotype directory as
		described by `config.evaluate.phenotype`.

		Args:
			genotype_dirs: Absolute paths to genotype directories (input).
			phenotype_dirs: Absolute paths to phenotype directories (output).
				Must be one-to-one aligned with `genotype_dirs`.
			config: The validated configuration object.
			params: Optional free-form parameters.

		Returns:
			None

		Raises:
			Exception: If evaluation fails for any individual.

		"""
		...

	def generate(
		self,
		parent_genotype_dirs: list[str],
		child_genotype_dirs: list[str],
		config: Config,
		params: dict | None,
	) -> list[list[int]]:
		"""Generate child genotypes from parent genotypes.

		The implementation must write each child's genotype files into the
		corresponding directory in `child_genotype_dirs`. It must also return,
		for each child, the indices of parent(s) used to produce it.

		Args:
			parent_genotype_dirs: Absolute paths to parent genotype
				directories.
			child_genotype_dirs: Absolute paths where child genotype files must
				be written.
			config: The validated configuration object.
			params: Optional free-form parameters.

		Returns:
			list[list[int]]: For each child index i, a list of indices into
			`parent_genotype_dirs` indicating the child's parentage.

		Raises:
			Exception: If generation fails or outputs are incomplete.

		"""
		...
