"""API router aggregation."""

from fastapi import APIRouter

from starbreeder_sdk.api.routes import (
	config,
	evaluate,
	generate,
	health,
	initialize,
)

api_router = APIRouter()
api_router.include_router(
	config.router, prefix="/config", tags=["Configuration"]
)
api_router.include_router(
	initialize.router, prefix="/initialize", tags=["Initialize"]
)
api_router.include_router(
	evaluate.router, prefix="/evaluate", tags=["Evaluate"]
)
api_router.include_router(
	generate.router, prefix="/generate", tags=["Generate"]
)
api_router.include_router(health.router, prefix="/health", tags=["Health"])
