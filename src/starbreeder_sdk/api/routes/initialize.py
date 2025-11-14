"""Initialization endpoint `/initialize` for creating root genotypes."""

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from starbreeder_sdk.api.routes.utils import (
	get_config_from_request,
	manage_tmp_dir,
	pack_and_upload_genotypes,
)
from starbreeder_sdk.core.config import settings
from starbreeder_sdk.schemas import (
	InitializeRequest,
	InitializeResponse,
	InitializeRootIndividualOutput,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
	"",
	response_model=InitializeResponse,
	status_code=status.HTTP_200_OK,
	summary="Initialize root individuals",
)
async def handle_initialize(
	request: Request, initialize_request: InitializeRequest
) -> InitializeResponse:
	"""Initialize root individuals.

	This endpoint:
		1. Loads the requested configuration.
		2. Validates that requested root keys match the configuration.
		3. Creates genotype output directories for each root key.
		4. Invokes the module's `initialize` to write root genotypes.
		5. Archives and uploads each root's genotype.

	Args:
		request: The incoming FastAPI request object. Used to access application state.
		initialize_request: The request body containing the configuration file and root
			individuals.

	Returns:
		InitializeResponse: A response containing the created root individuals.

	Raises:
		HTTPException: 400 if the set of root keys does not match the config.
		HTTPException: 500 on generation or upload failures.

	"""
	# 1. Load config
	config = await get_config_from_request(request, initialize_request.config_name)

	# 2. Validate request against config
	config_root_keys = set(config.initialize.root_individuals)
	request_root_keys = set(
		individual.key for individual in initialize_request.root_individuals
	)
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
			logger.exception("Error during root genotypes init")
			detail = f"Failed to initialize root population: {e}"
			raise HTTPException(status_code=500, detail=detail)

	# 6. Return the success response
	response_individuals = [
		InitializeRootIndividualOutput(id=individual.id, parent_ids=[])
		for individual in initialize_request.root_individuals
	]
	return InitializeResponse(root_individuals=response_individuals)
