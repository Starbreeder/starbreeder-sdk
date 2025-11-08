"""API endpoint for /config."""

import logging
import os

from fastapi import APIRouter, Request

from starbreeder_module.core.module_config import Config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=Config)
async def handle_config(request: Request, config_name: str) -> Config:
	"""Handle the `/config` endpoint.

	Returns the validated config model; modules may extend Config.

	Args:
		request: The incoming FastAPI request object, used to access application state.
		config_name: The name of the configuration file to load.

	Returns:
		The validated configuration model instance (serializes to JSON automatically).

	Raises:
		HTTPException: With a 500 status code if the module is not properly configured.
		HTTPException: With a 404 status code if the configuration file is not found.
		HTTPException: With a 400 status code if the configuration file is invalid.

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
