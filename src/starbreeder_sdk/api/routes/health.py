"""API endpoint for health checks."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
def handle_health(request: Request):
	"""Lightweight health endpoint."""
	return {
		"module_name": getattr(request.app.state, "module_name", None),
		"status": "running",
	}
