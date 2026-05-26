from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter()


@router.get("")
@router.get("/")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "ok",
            "version": settings.VERSION,
            "name": settings.PROJECT_NAME,
        }
    )
