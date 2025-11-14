"""Pydantic schemas for API requests and responses."""

from typing import Any

from pydantic import BaseModel, Field


# --- Initialize ---
class InitializeRootIndividualInput(BaseModel):
	"""Input schema for a root individual in the `/initialize` request."""

	id: str
	key: str
	genotype_put_url: str


class InitializeRequest(BaseModel):
	"""Request body for `/initialize` endpoint."""

	config_name: str
	root_individuals: list[InitializeRootIndividualInput]


class InitializeRootIndividualOutput(BaseModel):
	"""Output schema for a created root individual in the `/initialize` response."""

	id: str
	parent_ids: list[str] = Field(default_factory=list)


class InitializeResponse(BaseModel):
	"""Response body for `/initialize` endpoint."""

	root_individuals: list[InitializeRootIndividualOutput]


# --- Evaluate ---
class EvaluateIndividualInput(BaseModel):
	"""Input schema for an individual to be evaluated in the `/evaluate` request."""

	id: str
	genotype_get_url: str
	phenotype_put_urls: dict[str, str]


class EvaluateRequest(BaseModel):
	"""Request body for `/evaluate` endpoint."""

	config_name: str
	individuals: list[EvaluateIndividualInput]
	params: dict[str, Any] | None = None


class EvaluateIndividualOutput(BaseModel):
	"""Output schema for an evaluated individual in the `/evaluate` response."""

	id: str
	status: str
	message: str | None = None


class EvaluateResponse(BaseModel):
	"""Response body for `/evaluate` endpoint."""

	individuals: list[EvaluateIndividualOutput]


# --- Generate ---
class GenerateParentIndividualInput(BaseModel):
	"""Input schema for a parent individual in the `/generate` request."""

	id: str
	genotype_get_url: str


class GenerateChildIndividualInput(BaseModel):
	"""Input schema for a child individual to be created in the `/generate` request."""

	id: str
	genotype_put_url: str


class GenerateRequest(BaseModel):
	"""Request body for `/generate` endpoint."""

	config_name: str
	parent_individuals: list[GenerateParentIndividualInput]
	child_individuals: list[GenerateChildIndividualInput]
	params: dict[str, Any] | None = None


class GenerateChildIndividualOutput(BaseModel):
	"""Output schema for a created child individual in the `/generate` response."""

	id: str
	parent_ids: list[str]


class GenerateResponse(BaseModel):
	"""Response body for `/generate` endpoint."""

	child_individuals: list[GenerateChildIndividualOutput]
