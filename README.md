# Starbreeder Software Development Kit (SDK)

The official Python SDK for building custom modules for the Starbreeder platform.

This package provides:
- A small, well-defined Python protocol (`Module`) your module implements.
- A pre-wired FastAPI app factory (`create_app`) that mounts production-ready routes.
- Utilities for safe, concurrent file transfer and temporary filesystem work.

You focus on evolutionary logic; the SDK handles HTTP, concurrency, and object store I/O.

## Quickstart

1) Implement the `Module` protocol:

```python
from starbreeder_sdk.module import Module
from starbreeder_sdk.core.module_config import Config

class MyModule(Module):
	module_name = "my-module"
	module_dir = "/abs/path/to/my-module"  # contains a `configs/` dir

	def config(self, config_path: str) -> Config:
		# Parse and validate config (you may subclass `Config`)
		return Config.model_validate_json(open(config_path).read())

	def initialize(self, genotype_dirs_map: dict[str, str], config: Config, params: dict | None = None) -> None:
		# Write root genotypes into `genotype/` under each provided directory
		pass

	def evaluate(self, genotype_dirs: list[str], phenotype_dirs: list[str], config: Config, params: dict | None) -> None:
		# Read genotypes; write phenotype artifacts as declared by config
		pass

	def generate(self, parent_genotype_dirs: list[str], child_genotype_dirs: list[str], config: Config, params: dict | None) -> list[list[int]]:
		# Write child genotypes; return parent indices for each child
		return [[0]] * len(child_genotype_dirs)
```

2) Create and run the app:

```python
from starbreeder_sdk.main import create_app
from my_module import MyModule
import uvicorn

app = create_app(MyModule())
uvicorn.run(app, host="0.0.0.0", port=8000)
```

Your module directory must contain a `configs/` folder with configuration files.

## Endpoints

All endpoints are mounted under `/`:

- GET `/health`  
  Returns `{ "module_name": "<name>", "status": "running" }`.

- GET `/config?config_name=<filename>`  
  Loads and validates a config file from `configs/`. Returns the validated model (modules may extend `Config`).

- POST `/initialize`  
  Creates root genotypes and uploads them. The request must contain a `config_name` and a list of `root_individuals` whose keys match the config’s declared root individuals.

- POST `/evaluate`  
  Downloads genotypes, evaluates them via `module.evaluate`, uploads phenotype artifacts, and returns per‑individual statuses.

- POST `/generate`  
  Downloads parents, calls `module.generate` to produce child genotypes, uploads them, and returns parentage per child.

Requests use pre-signed URLs for object storage. Large file transfers are streamed; CPU-bound work is executed off the event loop.

## Conventions

- Docstrings: Google style (Args, Returns, Raises, Notes).
- Paths: All filesystem paths are absolute and created in SDK-managed temp directories.
- Config: Modules may subclass `Config` to add fields while remaining compatible with the SDK.
