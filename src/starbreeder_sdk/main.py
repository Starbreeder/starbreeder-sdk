"""FastAPI app factory for Starbreeder modules.

This module exposes `create_app`, which wires a concrete module implementation into the
SDK's HTTP API. On startup it sets `app.state` with module metadata and verifies that
the module's `configs/` directory exists.

Example:
	Basic usage to run a module with Uvicorn:

	```python
	from starbreeder_sdk.main import create_app
	from my_module import MyModule
	import uvicorn

	app = create_app(MyModule())
	uvicorn.run(app, host="0.0.0.0", port=8000)
	```

"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from starbreeder_sdk.api.main import api_router
from starbreeder_sdk.module import Module

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(module: Module) -> FastAPI:
	"""Create and configure the FastAPI app for a Starbreeder module.

	Args:
		module: A concrete implementation of the `Module` protocol.

	Returns:
		FastAPI: A configured FastAPI application with all SDK routes mounted.

	Raises:
		ValueError: If the module `configs/` directory cannot be found.

	"""
	_module_name = module.module_name
	_module_dir = module.module_dir

	@asynccontextmanager
	async def lifespan(app: FastAPI):
		"""Handle application startup and shutdown events.

		On startup, this sets:
			- `app.state.module_name`
			- `app.state.module_dir`
			- `app.state.configs_dir`
			- `app.state.module`

		Yields:
			None

		Raises:
			ValueError: If `configs/` does not exist within `module_dir`.

		"""
		# === STARTUP ===
		logger.info("Module starting up...")

		# Load module name and library directory
		try:
			app.state.module_name = _module_name
			app.state.module_dir = _module_dir
			app.state.configs_dir = os.path.join(app.state.module_dir, "configs")
			app.state.module = module

			if not os.path.exists(app.state.configs_dir):
				raise ValueError(
					f"FATAL: configs directory not found at {app.state.configs_dir}"
				)

		except Exception:
			logger.exception("Module startup failed")
			raise

		yield

		# === SHUTDOWN ===
		logger.info("Module shutting down...")
		pass

	# Create the main FastAPI app instance
	app = FastAPI(
		title=f"Starbreeder - {_module_name.title()} Module", lifespan=lifespan
	)
	app.include_router(api_router)

	return app
