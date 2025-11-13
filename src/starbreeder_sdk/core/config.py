"""Application settings management."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	"""Manages application-level settings.

	Pydantic's `BaseSettings` automatically reads from environment variables. For example,
	the value for `httpx_timeout` will be sourced from the `HTTPX_TIMEOUT` environment
	variable.
	"""

	model_config = SettingsConfigDict(
		env_file=".env", env_file_encoding="utf-8", extra="ignore"
	)

	# Default timeout for HTTP requests made by the service
	HTTPX_TIMEOUT: int = 60


settings = Settings()
