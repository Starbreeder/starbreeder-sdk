"""API endpoint for /initialize."""

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request

from starbreeder_module.api.routes.utils import (
	get_config_from_request,
	manage_tmp_dir,
	pack_and_upload_genotypes,
)
from starbreeder_module.core.config import settings
from starbreeder_module.schemas import (
	InitializeRequest,
	InitializeResponse,
	RootIndividualInitializeResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=InitializeResponse)
async def handle_initialize(request: Request, initialize_request: InitializeRequest):
	"""Handle the `/initialize` endpoint.

	Get root genotypes and upload them to the object store.

	Args:
		request: The incoming FastAPI request object, used to access application state.
		initialize_request: The request body containing the configuration file and root individuals.

	Returns:
		An InitResponse object containing the root individuals.

	Raises:
		HTTPException: With a 400 status code if the request is invalid.
		HTTPException: With a 500 status code if the request fails.

	"""
	# 1. Load config
	config = await get_config_from_request(request, initialize_request.config_name)

	# 2. Validate request against config
	config_root_keys = set(config.initialize.roots)
	request_root_keys = set(individual.key for individual in initialize_request.root_individuals)
	if config_root_keys != request_root_keys:
		error_msg = (
			"Mismatch between root keys in config and request. "
			f"Config: {sorted(list(config_root_keys))}, "
			f"Request: {sorted(list(request_root_keys))}."
		)
		raise HTTPException(status_code=400, detail=error_msg)

	async with manage_tmp_dir() as tmp_dir:
		try:
			# 3. Create directories for each root genotype
			genotype_dirs_map: dict[str, str] = {}
			for individual in initialize_request.root_individuals:
				genotype_dir = os.path.join(tmp_dir, individual.key, "genotype")
				await asyncio.to_thread(os.makedirs, genotype_dir)
				genotype_dirs_map[individual.key] = genotype_dir

			# 4. Call core logic to generate root genotypes
			await asyncio.to_thread(
				request.app.state.module.initialize,
				genotype_dirs_map,
				config,
				None,
			)

			# 5. Archive and upload all root genotypes concurrently
			source_destination_pairs = [
				(
					os.path.join(tmp_dir, individual.key),
					individual.genotype_put_url,
				)
				for individual in initialize_request.root_individuals
			]
			async with httpx.AsyncClient(timeout=settings.HTTPX_TIMEOUT) as client:
				await pack_and_upload_genotypes(source_destination_pairs, client)

		except Exception as e:
			logger.error(f"Error during root genotypes init: {e}", exc_info=True)
			detail = f"Failed to initialize root population: {e}"
			raise HTTPException(status_code=500, detail=detail)

	# 6. Return the success response
	response_individuals = [
		RootIndividualInitializeResponse(id=individual.id, parent_ids=[])
		for individual in initialize_request.root_individuals
	]
	return InitializeResponse(root_individuals=response_individuals)
