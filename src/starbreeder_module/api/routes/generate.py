"""API endpoint for /generate."""

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request

from starbreeder_module.api.routes.utils import (
	download_and_unpack_genotypes,
	get_config_from_request,
	manage_tmp_dir,
	pack_and_upload_genotypes,
)
from starbreeder_module.core.config import settings
from starbreeder_module.schemas import (
	ChildIndividualGenerateResponse,
	GenerateRequest,
	GenerateResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=GenerateResponse)
async def handle_generate(request: Request, generate_request: GenerateRequest) -> GenerateResponse:
	"""Handle the /generate request."""
	logger.info(f"Received generate request for config: {generate_request.config_name}")

	# 1. Load config
	try:
		config = await get_config_from_request(request, generate_request.config_name)
	except HTTPException as e:
		logger.error(f"Config error for '{generate_request.config_name}': {e.detail}")
		raise HTTPException(status_code=500, detail=f"Configuration error: {e.detail}")

	async with manage_tmp_dir() as tmp_dir:
		try:
			# 2. Download and unpack parent genotypes concurrently
			parent_ids = [
				parent_individual.id for parent_individual in generate_request.parent_individuals
			]
			parent_dirs: dict[str, str] = {}
			async with httpx.AsyncClient(timeout=settings.HTTPX_TIMEOUT) as client:
				source_destination_pairs = []
				for child_individual in generate_request.parent_individuals:
					individual_tmp_dir = os.path.join(tmp_dir, "parents", child_individual.id)
					await asyncio.to_thread(os.makedirs, individual_tmp_dir)
					source_destination_pairs.append(
						(child_individual.genotype_get_url, individual_tmp_dir)
					)
				download_results = await download_and_unpack_genotypes(
					source_destination_pairs, client
				)

			# Filter out download failures
			valid_parent_dirs = []
			for i, result in enumerate(download_results):
				if isinstance(result, Exception):
					parent_id = generate_request.parent_individuals[i].id
					logger.error(f"Failed to download/unpack for parent {parent_id}: {result}")
					raise HTTPException(
						status_code=500,
						detail=f"Failed to download genotype for parent {parent_id}",
					)
				parent_dirs[parent_ids[i]] = result
				valid_parent_dirs.append(result)

			# 3. Create directories for each child genotype
			child_genotype_dirs_map: dict[str, str] = {}
			for child_individual in generate_request.child_individuals:
				# The final archive will be created from the contents of this dir
				child_dir = os.path.join(tmp_dir, "children", child_individual.id)
				# The core logic saves the genotype files inside this nested dir
				genotype_dir = os.path.join(child_dir, "genotype")
				await asyncio.to_thread(os.makedirs, genotype_dir)
				child_genotype_dirs_map[child_individual.id] = genotype_dir

			# 4. Call core logic to generate child genotypes
			child_dirs = list(child_genotype_dirs_map.values())
			parentage_indices = await asyncio.to_thread(
				request.app.state.module.generate,
				valid_parent_dirs,
				child_dirs,
				config,
				generate_request.params,
			)

			# 5. Archive and upload all child genotypes concurrently
			source_destination_pairs = [
				(
					os.path.join(tmp_dir, "children", individual.id),
					individual.genotype_put_url,
				)
				for individual in generate_request.child_individuals
			]
			async with httpx.AsyncClient(timeout=settings.HTTPX_TIMEOUT) as client:
				await pack_and_upload_genotypes(source_destination_pairs, client)

		except Exception as e:
			logger.error(f"Error during breeding process: {e}", exc_info=True)
			detail = f"Failed to create new population: {e}"
			raise HTTPException(status_code=500, detail=detail)

	# 6. Return the success response
	response_individuals = []
	for i, child_individual in enumerate(generate_request.child_individuals):
		parent_ids_for_child = [parent_ids[p_idx] for p_idx in parentage_indices[i]]
		response_individuals.append(
			ChildIndividualGenerateResponse(id=child_individual.id, parent_ids=parent_ids_for_child)
		)

	return GenerateResponse(child_individuals=response_individuals)
