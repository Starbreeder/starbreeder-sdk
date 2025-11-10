"""Utility helpers used across API routers.

These functions implement common I/O patterns (buffered/streamed HTTP file transfer,
temporary directory management, and parallel packing/unpacking) used by the generation,
evaluation, and initialization endpoints.
"""

import asyncio
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager

import aiofiles
import aiofiles.os
import httpx
from fastapi import HTTPException, Request

from starbreeder_sdk.core.module_config import Config


async def get_config_from_request(request: Request, config_name: str) -> Config:
	"""Load and validate a module configuration by name.

	This helper centralizes logic for:
	- Finding the configs directory
	- Loading the config file without blocking the event loop
	- Raising clear HTTP errors (validation, file not found)

	Args:
		request: The incoming FastAPI request object. Used to access application state.
		config_name: The name of the configuration file to load.

	Returns:
		Config: A validated configuration object.

	Raises:
		HTTPException: With a 500 status code if the service is misconfigured.
		HTTPException: With a 404 status code if the config file is not found.
		HTTPException: With a 400 status code for validation or load errors.

	"""
	try:
		configs_dir = request.app.state.configs_dir
	except AttributeError:
		raise HTTPException(
			status_code=500,
			detail=(
				"Module is not properly configured. Missing app.state.configs_dir."
			),
		)

	config_path = os.path.join(configs_dir, config_name)

	try:
		config = await asyncio.to_thread(request.app.state.module.config, config_path)
		return config
	except FileNotFoundError:
		raise HTTPException(
			status_code=404, detail=f"Config file '{config_name}' not found."
		)
	except Exception as e:
		raise HTTPException(
			status_code=400,
			detail=f"Failed to load or validate config file: {e}",
		)


async def download_file_buffered(url: str, client: httpx.AsyncClient) -> bytes:
	"""Download a file into an in-memory bytes object.

	Args:
		url: The HTTP(S) URL to download.
		client: An `httpx.AsyncClient` instance to use for the request.

	Returns:
		bytes: The downloaded file bytes.

	Raises:
		httpx.HTTPStatusError: If the server responds with an error status.

	"""
	response = await client.get(url)
	response.raise_for_status()
	return response.content


async def upload_file_buffered(
	url: str, data: bytes, client: httpx.AsyncClient, content_type: str
) -> None:
	"""Upload an in-memory bytes object to a URL.

	Args:
		url: The HTTP(S) URL to upload to.
		data: The in-memory bytes to send.
		client: An `httpx.AsyncClient` instance to use for the request.
		content_type: Value for the `Content-Type` header.

	Returns:
		None

	Raises:
		httpx.HTTPStatusError: If the server responds with an error status.

	"""
	headers = {"Content-Type": content_type}
	response = await client.put(url, content=data, headers=headers)
	response.raise_for_status()


async def download_file_streamed(
	url: str, target_path: str, client: httpx.AsyncClient
) -> None:
	"""Download a file and stream it directly to disk.

	Args:
		url: The HTTP(S) URL to download.
		target_path: Absolute file path to write to.
		client: An `httpx.AsyncClient` instance to use for the request.

	Raises:
		httpx.HTTPStatusError: If the server responds with an error status.

	"""
	async with client.stream("GET", url) as response:
		response.raise_for_status()
		async with aiofiles.open(target_path, "wb") as f:
			async for chunk in response.aiter_bytes():
				await f.write(chunk)


async def upload_file_streamed(
	url: str, source_path: str, client: httpx.AsyncClient, content_type: str
) -> None:
	"""Read a file from disk and stream it to a URL.

	Args:
		url: The HTTP(S) URL to upload to.
		source_path: Absolute path to the file to upload.
		client: An `httpx.AsyncClient` instance to use for the request.
		content_type: Value for the `Content-Type` header.

	Raises:
		httpx.HTTPStatusError: If the server responds with an error status.

	"""
	file_size = (await aiofiles.os.stat(source_path)).st_size
	headers = {"Content-Type": content_type, "Content-Length": str(file_size)}

	async with aiofiles.open(source_path, "rb") as f:
		response = await client.put(url, content=f, headers=headers)
		response.raise_for_status()


@asynccontextmanager
async def manage_tmp_dir() -> AsyncGenerator[str]:
	"""Create and manage a temporary directory in a context block.

	Yields:
		str: The absolute path to the temporary directory.

	"""
	tmp_dir = await asyncio.to_thread(tempfile.mkdtemp)
	try:
		yield tmp_dir
	finally:
		await asyncio.to_thread(shutil.rmtree, tmp_dir, ignore_errors=True)


async def pack_and_upload_genotype(
	source_dir: str, put_url: str, client: httpx.AsyncClient
) -> None:
	"""Pack a genotype directory and upload it to a URL.

	This function creates a .tar archive of the genotype directory inside the
	source directory, uploads it to the specified URL, and cleans up the
	temporary archive.

	Args:
		source_dir: The parent directory containing the genotype directory to
			pack and upload.
		put_url: The pre-signed URL to upload the archive to.
		client: The httpx client to use for the upload.

	Returns:
		None

	Raises:
		httpx.HTTPStatusError: If the upload fails.

	"""
	async with manage_tmp_dir() as tmp_dir:
		base_name = os.path.join(tmp_dir, "genotype")

		# 1. Create archive (this is a blocking, CPU-bound operation)
		archive_path = await asyncio.to_thread(
			shutil.make_archive,
			base_name=base_name,
			format="tar",
			root_dir=source_dir,
			base_dir="genotype",
		)

		# 2. Stream the created archive to the object store
		await upload_file_streamed(put_url, archive_path, client, "application/x-tar")


async def download_and_unpack_genotype(
	get_url: str, target_dir: str, client: httpx.AsyncClient
) -> str:
	"""Download a genotype archive from a URL and unpack it.

	This function streams the download to a temporary file on disk, unpacks it
	to the target directory, and ensures the temporary archive is cleaned up.

	Args:
		get_url: The URL from which to download the genotype archive.
		target_dir: The directory to unpack the archive into.
		client: The httpx client to use for the download.

	Returns:
		str: Absolute path to the extracted `genotype/` subdirectory.

	Raises:
		FileNotFoundError: If the archive does not contain a `genotype/`
			directory.

	"""
	tmp_file = os.path.join(target_dir, "genotype.tar.tmp")
	try:
		# 1. Stream the download directly to a temporary file on disk
		await download_file_streamed(get_url, tmp_file, client)

		# 2. Unpack the archive (this is a blocking, I/O-bound operation)
		await asyncio.to_thread(shutil.unpack_archive, tmp_file, target_dir, "tar")
	finally:
		# 3. Ensure the temporary archive file is always cleaned up
		if await aiofiles.os.path.exists(tmp_file):
			await aiofiles.os.remove(tmp_file)

	# 4. Verify that the expected genotype directory exists and return its path
	genotype_dir = os.path.join(target_dir, "genotype")
	if not os.path.isdir(genotype_dir):
		raise FileNotFoundError("'genotype/' directory not found in tar archive.")

	return genotype_dir


async def pack_and_upload_genotypes(
	source_destination_pairs: list[tuple[str, str]], client: httpx.AsyncClient
) -> None:
	"""Pack and upload multiple genotype directories in parallel.

	Args:
		source_destination_pairs: A list of `(source_dir, put_url)` tuples.
		client: Shared `httpx.AsyncClient` instance used for uploads.

	Returns:
		None

	"""
	tasks = [
		pack_and_upload_genotype(source_dir, put_url, client)
		for source_dir, put_url in source_destination_pairs
	]
	await asyncio.gather(*tasks)


async def download_and_unpack_genotypes(
	source_destination_pairs: list[tuple[str, str]], client: httpx.AsyncClient
) -> list[str | Exception]:
	"""Download and unpack multiple genotype archives in parallel.

	Args:
		source_destination_pairs: A list of `(get_url, target_dir)` tuples.
		client: Shared `httpx.AsyncClient` instance used for downloads.

	Returns:
		list[str | Exception]: For each pair, either the genotype directory
		path or an exception if the operation failed.

	"""
	tasks = [
		download_and_unpack_genotype(get_url, target_dir, client)
		for get_url, target_dir in source_destination_pairs
	]
	return await asyncio.gather(*tasks)


async def upload_phenotype(
	phenotype_dir: str,
	put_urls: dict[str, str],
	config: Config,
	client: httpx.AsyncClient,
) -> None:
	"""Upload phenotype artifacts for a single individual.

	Files to upload are derived from the configuration's
	`config.evaluate.phenotype` mapping. Only existing files with matching
	keys in `put_urls` are uploaded.

	Args:
		phenotype_dir: Absolute directory path containing phenotype files.
		put_urls: Mapping from phenotype keys to upload URLs.
		config: The validated configuration object.
		client: Shared `httpx.AsyncClient` used for uploads.

	Returns:
		None

	"""
	phenotype_config = config.evaluate.phenotype
	tasks: list[Coroutine] = []

	for key, phenotype_file_config in phenotype_config.items():
		file_path = os.path.join(phenotype_dir, phenotype_file_config.name)
		if key in put_urls and await aiofiles.os.path.exists(file_path):
			tasks.append(
				upload_file_streamed(
					put_urls[key],
					file_path,
					client,
					phenotype_file_config.content_type,
				)
			)

	if tasks:
		await asyncio.gather(*tasks)


async def upload_phenotypes(
	source_destination_pairs: list[tuple[str, dict[str, str]]],
	config: Config,
	client: httpx.AsyncClient,
) -> None:
	"""Upload multiple phenotypes in parallel.

	Args:
		source_destination_pairs: A list of `(phenotype_dir, put_urls)` tuples.
		config: The validated configuration object.
		client: Shared `httpx.AsyncClient` used for uploads.

	Returns:
		None

	"""
	tasks = [
		upload_phenotype(phenotype_dir, put_urls, config, client)
		for phenotype_dir, put_urls in source_destination_pairs
	]
	if tasks:
		await asyncio.gather(*tasks)
