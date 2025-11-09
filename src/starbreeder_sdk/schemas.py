"""Pydantic schemas for API requests and responses."""

from typing import Any

from pydantic import BaseModel, Field


# === /initialize ===
class RootIndividualInitialize(BaseModel):
	"""Schema for a root individual in the /initialize request."""

	id: str
	key: str
	genotype_put_url: str


class InitializeRequest(BaseModel):
	"""Request body for /initialize endpoint."""

	config_name: str
	root_individuals: list[RootIndividualInitialize]


class RootIndividualInitializeResponse(BaseModel):
	"""Schema for a created root individual in the /initialize response."""

	id: str
	parent_ids: list[str] = Field(default_factory=list)


class InitializeResponse(BaseModel):
	"""Response body for /initialize endpoint."""

	root_individuals: list[RootIndividualInitializeResponse]


# === /evaluate ===
class IndividualEvaluate(BaseModel):
	"""Schema for an individual to be evaluated in the /evaluate request."""

	id: str
	genotype_get_url: str
	phenotype_put_urls: dict[str, str]


class EvaluateRequest(BaseModel):
	"""Request body for /evaluate endpoint."""

	config_name: str
	individuals: list[IndividualEvaluate]
	params: dict[str, Any] | None = None


class IndividualEvaluateResponse(BaseModel):
	"""Schema for an evaluated individual in the /evaluate response."""

	id: str
	status: str
	message: str | None = None


class EvaluateResponse(BaseModel):
	"""Response body for /evaluate endpoint."""

	individuals: list[IndividualEvaluateResponse]


# === /generate ===
class ParentIndividualGenerate(BaseModel):
	"""Schema for a parent individual in the /generate request."""

	id: str
	genotype_get_url: str


class ChildIndividualGenerate(BaseModel):
	"""Schema for a child individual to be created in the /generate request."""

	id: str
	genotype_put_url: str


class GenerateRequest(BaseModel):
	"""Request body for /generate endpoint."""

	config_name: str
	parent_individuals: list[ParentIndividualGenerate]
	child_individuals: list[ChildIndividualGenerate]
	params: dict[str, Any] | None = None


class ChildIndividualGenerateResponse(BaseModel):
	"""Schema for a created child individual in the /generate response."""

	id: str
	parent_ids: list[str]


class GenerateResponse(BaseModel):
	"""Response body for /generate endpoint."""

	child_individuals: list[ChildIndividualGenerateResponse]
