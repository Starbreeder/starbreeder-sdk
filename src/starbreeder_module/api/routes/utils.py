"""Utility functions for FastAPI routers."""

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

from starbreeder_module.core.module_config import Config


async def get_config_from_request(request: Request, config_name: str) -> Config:
	"""Load and validate the specified configuration file.

	This helper function centralizes the logic for fetching the configs directory,
	loading a config file in a non-blocking way, and handling common errors
	(e.g., file not found, validation errors) by raising appropriate HTTPErrors.

	Args:
		request: The incoming FastAPI request object, used to access application state.
		config_name: The name of the configuration file to load.

	Returns:
		A validated Pydantic Config object.

	Raises:
		HTTPException: With a 500 status code if the service is misconfigured.
		HTTPException: With a 404 status code if the config file is not found.
		HTTPException: With a 400 status code for validation or other load errors.

	"""
	try:
		configs_dir = request.app.state.configs_dir
	except AttributeError:
		raise HTTPException(
			status_code=500,
			detail="Module is not properly configured. Missing app.state.configs_dir.",
		)

	config_path = os.path.join(configs_dir, config_name)

	try:
		config = await asyncio.to_thread(request.app.state.module.config, config_path)
		return config
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail=f"Config file '{config_name}' not found.")
	except Exception as e:
		raise HTTPException(status_code=400, detail=f"Failed to load or validate config file: {e}")


async def download_file_buffered(url: str, client: httpx.AsyncClient) -> bytes:
	"""Download a file into an in-memory bytes object."""
	response = await client.get(url)
	response.raise_for_status()
	return response.content


async def upload_file_buffered(
	url: str, data: bytes, client: httpx.AsyncClient, content_type: str
) -> None:
	"""Upload an in-memory bytes object to a URL."""
	headers = {"Content-Type": content_type}
	response = await client.put(url, content=data, headers=headers)
	response.raise_for_status()


async def download_file_streamed(url: str, target_path: str, client: httpx.AsyncClient) -> None:
	"""Download a file and stream it directly to disk."""
	async with client.stream("GET", url) as response:
		response.raise_for_status()
		async with aiofiles.open(target_path, "wb") as f:
			async for chunk in response.aiter_bytes():
				await f.write(chunk)


async def upload_file_streamed(
	url: str, source_path: str, client: httpx.AsyncClient, content_type: str
) -> None:
	"""Read a file from disk and stream it to a URL."""
	file_size = (await aiofiles.os.stat(source_path)).st_size
	headers = {"Content-Type": content_type, "Content-Length": str(file_size)}

	async with aiofiles.open(source_path, "rb") as f:
		response = await client.put(url, content=f, headers=headers)
		response.raise_for_status()


@asynccontextmanager
async def manage_tmp_dir() -> AsyncGenerator[str, None]:
	"""Create and manage a temporary directory in a context block.

	Yields:
		The path to the created temporary directory.

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
		source_dir: The parent directory containing the genotype folder to pack.
		put_url: The pre-signed URL to upload the archive to.
		client: The httpx client to use for the upload.

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
	"""Download and unpack a genotype archive from a URL.

	This function streams the download to a temporary file on disk, unpacks it
	to the specified directory, and ensures the temporary archive is cleaned up.

	Args:
		get_url: The URL from which to download the genotype archive.
		target_dir: The directory to unpack the archive into.
		client: The httpx client to use for the download.

	Returns:
		The path to the extracted 'genotype/' subdirectory.

	Raises:
		FileNotFoundError: If the archive does not contain a 'genotype/' directory.

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
	"""Pack and upload multiple genotype directories in parallel."""
	tasks = [
		pack_and_upload_genotype(source_dir, put_url, client)
		for source_dir, put_url in source_destination_pairs
	]
	await asyncio.gather(*tasks)


async def download_and_unpack_genotypes(
	source_destination_pairs: list[tuple[str, str]], client: httpx.AsyncClient
) -> list[str | Exception]:
	"""Download and unpack multiple genotype archives in parallel."""
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
	"""Upload phenotype to URLs."""
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
	"""Upload multiple phenotypes in parallel."""
	tasks = [
		upload_phenotype(phenotype_dir, put_urls, config, client)
		for phenotype_dir, put_urls in source_destination_pairs
	]
	if tasks:
		await asyncio.gather(*tasks)
