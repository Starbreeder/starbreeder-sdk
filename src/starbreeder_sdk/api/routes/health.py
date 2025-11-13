"""Health-check endpoint `/health` for modules."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
def handle_health(request: Request):
	"""Return lightweight runtime status.

	Args:
		request: The incoming FastAPI request object.

	Returns:
		dict[str, str | None]: A minimal health payload including the module name (if
			initialized) and a static status value.

	"""
	return {
		"module_name": getattr(request.app.state, "module_name", None),
		"status": "running",
	}
