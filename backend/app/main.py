import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from app.core.config import settings
from app.db.base import init_db, close_db
from app.api.v1.api import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_observe_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _observe_client
    logger.info("Starting up Yuno Chat Backend...")
    await init_db()
    logger.info("Database initialized successfully")

    observe_endpoint = os.environ.get("OBSERVE_ME_ENDPOINT", "")
    if observe_endpoint:
        try:
            import observe_me
            _observe_client = observe_me.configure(endpoint=observe_endpoint, enabled=True)
            await _observe_client.start()
            logger.info("observe-me SDK started → %s", observe_endpoint)
        except ImportError:
            logger.warning("observe_me SDK not installed — telemetry disabled")

    # Start Slack Socket Mode handler in the background if tokens are configured.
    # No separate process or terminal needed — it runs alongside the API.
    slack_task: asyncio.Task | None = None
    try:
        from app.worker.slack_worker import start_socket_handler
        slack_task = asyncio.create_task(start_socket_handler())
    except Exception as e:
        logger.warning("Could not start Slack handler: %s", e)

    yield

    logger.info("Shutting down Yuno Chat Backend...")
    if slack_task and not slack_task.done():
        try:
            from app.worker.slack_worker import stop_socket_handler
            await stop_socket_handler()  # close the WS cleanly first
        except Exception as e:
            logger.warning("Slack handler close failed: %s", e)
        slack_task.cancel()
        try:
            await slack_task
        except asyncio.CancelledError:
            pass
    if _observe_client is not None:
        await _observe_client.stop()
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Yuno Chat Backend API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.3f}s"
    )
    return response


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return JSONResponse(
        content={
            "status": "ok",
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
        }
    )


@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok", "version": settings.VERSION})
