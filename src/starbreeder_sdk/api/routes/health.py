"""Health-check endpoint `/health` for modules."""

from fastapi import APIRouter, Request, status

router = APIRouter()


@router.get(
	"",
	status_code=status.HTTP_200_OK,
	summary="Health",
)
def handle_health(request: Request):
	"""Health.

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
