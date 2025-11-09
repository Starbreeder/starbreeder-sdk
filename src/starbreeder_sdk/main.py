"""App factory for Starbreeder module services."""

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
	"""Create and configure the FastAPI app for a Starbreeder module."""
	_module_name = module.module_name
	_module_dir = module.module_dir

	@asynccontextmanager
	async def lifespan(app: FastAPI):
		"""Handle application startup and shutdown events."""
		# === STARTUP ===
		logger.info("Module starting up...")

		# Load module name and library directory
		try:
			app.state.module_name = _module_name
			app.state.module_dir = _module_dir
			app.state.configs_dir = os.path.join(
				app.state.module_dir, "configs"
			)
			app.state.module = module

			if not os.path.exists(app.state.configs_dir):
				raise ValueError(
					"FATAL: configs directory not found at "
					f"{app.state.configs_dir}"
				)

		except Exception as e:
			raise e

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
