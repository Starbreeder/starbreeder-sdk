"""Evaluation endpoint `/evaluate` for batch genotype evaluation."""

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from starbreeder_sdk.api.routes.utils import (
	download_and_unpack_genotypes,
	get_config_from_request,
	manage_tmp_dir,
	upload_phenotypes,
)
from starbreeder_sdk.core.config import settings
from starbreeder_sdk.schemas import (
	EvaluateIndividualOutput,
	EvaluateRequest,
	EvaluateResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
	"",
	response_model=EvaluateResponse,
	status_code=status.HTTP_200_OK,
	summary="Evaluate individuals",
)
async def handle_evaluate(
	request: Request, evaluate_request: EvaluateRequest
) -> EvaluateResponse:
	"""Evaluate individuals.

	This endpoint:
		1. Loads the requested configuration.
		2. Downloads and unpacks each individual's genotype archive.
		3. Invokes the module's `evaluate` on all valid individuals.
		4. Uploads phenotype artifacts for evaluated individuals.
		5. Returns a per-individual status.

		Individuals that fail to download/unpack are marked with `status="error"`
		and do not block other evaluations.

	Args:
		request: The incoming FastAPI request object.
		evaluate_request: The request payload describing the config and individuals to
			evaluate.

	Returns:
		EvaluateResponse: A response with a result for each requested individual.

	Notes:
		Exceptions during processing are caught and translated into per-individual error
		statuses. The endpoint itself does not raise HTTP errors for per-individual
		failures.

	"""
	logger.info(f"Received evaluate request for config: {evaluate_request.config_name}")

	# 1. Load config
	try:
		config = await get_config_from_request(request, evaluate_request.config_name)
	except HTTPException as e:
		logger.error(f"Config error for '{evaluate_request.config_name}': {e.detail}")
		responses = [
			EvaluateIndividualOutput(
				id=individual.id,
				status="error",
				message=f"Configuration error: {e.detail}",
			)
			for individual in evaluate_request.individuals
		]
		return EvaluateResponse(individuals=responses)

	async with manage_tmp_dir() as tmp_dir:
		try:
			# 2. Download and unpack all genotypes concurrently
			async with httpx.AsyncClient(timeout=settings.HTTPX_TIMEOUT) as client:
				source_destination_pairs = []
				for individual in evaluate_request.individuals:
					individual_tmp_dir = os.path.join(tmp_dir, individual.id)
					await asyncio.to_thread(os.makedirs, individual_tmp_dir)
					source_destination_pairs.append(
						(individual.genotype_get_url, individual_tmp_dir)
					)
				download_results = await download_and_unpack_genotypes(
					source_destination_pairs, client
				)

			# 3. Prepare individuals for evaluation
			individuals_to_eval = []
			valid_genotype_dirs = []
			valid_phenotype_dirs = []
			eval_statuses: dict[str, EvaluateIndividualOutput] = {}

			for individual, result in zip(
				evaluate_request.individuals, download_results
			):
				if isinstance(result, Exception):
					logger.error(
						f"Failed to download/unpack for individual "
						f"{individual.id}: {result}"
					)
					eval_statuses[individual.id] = EvaluateIndividualOutput(
						id=individual.id,
						status="error",
						message="Failed during download/unpack phase",
					)
				else:
					genotype_dir = result
					phenotype_dir = os.path.join(
						os.path.dirname(genotype_dir), "phenotype"
					)
					await asyncio.to_thread(os.makedirs, phenotype_dir, exist_ok=True)

					individuals_to_eval.append(individual)
					valid_genotype_dirs.append(genotype_dir)
					valid_phenotype_dirs.append(phenotype_dir)

			# 4. Run batch evaluation if there are any valid individuals
			if individuals_to_eval:
				# Delegate to the module plugin's evaluate
				await asyncio.to_thread(
					request.app.state.module.evaluate,
					valid_genotype_dirs,
					valid_phenotype_dirs,
					config,
					evaluate_request.params,
				)

				# 5. Upload all phenotypes concurrently
				async with httpx.AsyncClient(timeout=settings.HTTPX_TIMEOUT) as client:
					phenotypes_to_upload = [
						(phenotype_dir, individual.phenotype_put_urls)
						for phenotype_dir, individual in zip(
							valid_phenotype_dirs, individuals_to_eval
						)
					]
					await upload_phenotypes(phenotypes_to_upload, config, client)

				# Mark successfully processed individuals
				for individual in individuals_to_eval:
					eval_statuses[individual.id] = EvaluateIndividualOutput(
						id=individual.id, status="success"
					)

			# 6. Compile final responses
			final_responses = [
				eval_statuses[individual.id]
				for individual in evaluate_request.individuals
			]
			return EvaluateResponse(individuals=final_responses)

		except Exception as e:
			logger.error(
				f"An unexpected error occurred during the eval process: {e}",
				exc_info=True,
			)
			# Create a generic error response for all individuals
			error_responses = [
				EvaluateIndividualOutput(
					id=individual.id, status="error", message=str(e)
				)
				for individual in evaluate_request.individuals
			]
			return EvaluateResponse(individuals=error_responses)
