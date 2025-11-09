"""Configuration endpoint `/config` for modules.

This router exposes a read-only endpoint that loads and validates a module
configuration file from the module's `configs/` directory.
"""

import logging
import os

from fastapi import APIRouter, Request

from starbreeder_sdk.core.module_config import Config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=Config)
async def handle_config(request: Request, config_name: str) -> Config:
	"""Return a validated configuration for the given name.

	Modules may extend `Config` and return subclasses which are still
	serialized according to the base model.

	Args:
		request: The incoming FastAPI request object. Used to access
			application state.
		config_name: The name of the configuration file to load.

	Returns:
		Config: A validated configuration model instance.

	Raises:
		HTTPException: 500 if the service is misconfigured (e.g. missing
			`app.state.configs_dir`).
		HTTPException: 404 if the configuration file is not found.
		HTTPException: 400 if the configuration file is invalid.

	"""
	try:
		configs_dir = request.app.state.configs_dir
	except AttributeError:
		raise

	config_path = os.path.join(configs_dir, config_name)

	try:
		return request.app.state.module.config(config_path)
	except Exception as e:
		logger.error(f"Failed to load or parse config {config_path}: {e}")
		raise
