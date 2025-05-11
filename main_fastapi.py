import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from loguru import logger as loguru_logger # Renamed to avoid conflict
import os
import sys

# Import configurations and client modules
import config
from config import APP_VERSION, BUILD_NUMBER # Ensure these are accessible

# --- Loguru Configuration ---
LOGURU_LOG_DIR = 'mylogs'
LOGURU_LOG_FILE_PATH = os.path.join(LOGURU_LOG_DIR, 'main_app_loguru.log') # Consistent
LOGURU_ROTATION = "10 minutes"
LOGURU_RETENTION = "5 days"
LOGURU_COMPRESSION = "zip"
LOGURU_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOGURU_CONSOLE_LEVEL = os.environ.get("LOGURU_CONSOLE_LEVEL", "INFO").upper()
LOGURU_FILE_LEVEL = os.environ.get("LOGURU_FILE_LEVEL", "DEBUG").upper()

def setup_logging():
    if not os.path.exists(LOGURU_LOG_DIR):
        try:
            os.makedirs(LOGURU_LOG_DIR)
            print(f"Loguru log directory '{LOGURU_LOG_DIR}' created.")
        except Exception as e:
            print(f"Warning: Could not create Loguru log directory '{LOGURU_LOG_DIR}': {e}")

    loguru_logger.remove() # Remove default handler

    loguru_logger.add(
        sys.stderr,
        level=LOGURU_CONSOLE_LEVEL,
        format=LOGURU_FORMAT,
        colorize=True
    )
    # print(f"Loguru: Console logging configured at level {LOGURU_CONSOLE_LEVEL}.")

    try:
        loguru_logger.add(
            LOGURU_LOG_FILE_PATH,
            level=LOGURU_FILE_LEVEL,
            rotation=LOGURU_ROTATION,
            retention=LOGURU_RETENTION,
            compression=LOGURU_COMPRESSION,
            enqueue=True,
            format=LOGURU_FORMAT,
            encoding="utf-8"
        )
        # print(f"Loguru: File logging configured at '{LOGURU_LOG_FILE_PATH}', level {LOGURU_FILE_LEVEL}.")
    except Exception as e:
        print(f"Warning: Could not set up Loguru file sink for '{LOGURU_LOG_FILE_PATH}': {e}")

# Call logging setup early
setup_logging()

# Client initialization functions
async def initialize_firestore_client_instance():
    from google.cloud.firestore_v1.async_client import AsyncClient as AsyncFirestoreClient
    loguru_logger.info(f"Initializing shared Firestore AsyncClient for project '{config.GCLOUD_PROJECT}'...")
    client = AsyncFirestoreClient(project=config.GCLOUD_PROJECT, database=config.FIRESTORE_DATABASE_ID or '(default)')
    loguru_logger.info("Shared Firestore AsyncClient initialized.")
    return client

async def configure_generative_ai_client():
    from google.generativeai import configure as genai_configure
    loguru_logger.info("Configuring Google Generative AI module...")
    api_key = config.get_google_api_key()
    if not api_key:
        loguru_logger.warning("Google API Key for GenAI not found. LLM features may fail.")
    else:
        genai_configure(api_key=api_key)
        loguru_logger.info("Google Generative AI module configured.")

async def close_firestore_client_instance(client):
    if client and hasattr(client, 'close') and callable(client.close):
        loguru_logger.info("Closing shared Firestore AsyncClient...")
        # Check if 'close' is a coroutine function
        if asyncio.iscoroutinefunction(client.close):
            await client.close()
        else:
            client.close() # Call synchronously if not a coroutine
        loguru_logger.info("Shared Firestore AsyncClient closed.")
    else:
        loguru_logger.info("Firestore client instance was None or does not have a close method.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    loguru_logger.info("FastAPI application startup sequence initiated...")
    app.state.firestore_client = await initialize_firestore_client_instance()
    await configure_generative_ai_client()
    # Example: if you had a specific llm_client class instance to create and store:
    # from llm_client import ActualLLMClientClass # Replace with your actual class if any
    # app.state.llm_service = ActualLLMClientClass(...) # Initialize with necessary config
    loguru_logger.info("Shared resources initialized and logging configured.")
    yield
    loguru_logger.info("FastAPI application shutdown sequence initiated...")
    if hasattr(app.state, 'firestore_client') and app.state.firestore_client:
        await close_firestore_client_instance(app.state.firestore_client)
    # If you initialized other clients on app.state that need closing, do it here.
    # if hasattr(app.state, 'llm_service') and hasattr(app.state.llm_service, 'close'):
    #     await app.state.llm_service.close() # Assuming it has an async close
    loguru_logger.info("Shared resources cleaned up.")

app = FastAPI(lifespan=lifespan, title="WordSense Admin API", version=APP_VERSION)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
# This needs to be accessible by routers_fastapi/html_router.py
# Defining it globally here makes it importable.
templates = Jinja2Templates(directory="templates")


# --- Global Exception Handlers (Example) ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    loguru_logger.error(f"Request validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    loguru_logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    loguru_logger.exception("Unhandled exception:") # This will log the full traceback
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )

# --- Include Routers ---
from routers_fastapi.html_router import router as html_router_fastapi
from routers_fastapi.list_generation_router import router as list_gen_router_fastapi
from routers_fastapi.categories_router import router as categories_router_fastapi
from routers_fastapi.language_pairs_router import router as lang_pairs_router_fastapi

app.include_router(html_router_fastapi)
app.include_router(list_gen_router_fastapi)
app.include_router(categories_router_fastapi)
app.include_router(lang_pairs_router_fastapi)

# The basic root endpoint "/" is now handled by html_router_fastapi,
# so the @app.get("/") here can be removed if html_router_fastapi defines it.
# For now, html_router_fastapi does define "/", so we can remove the one below.

# @app.get("/", response_class=HTMLResponse)
# async def read_root(request: Request):
#     # This will eventually be replaced by including the html_router
#     return templates.TemplateResponse("index.html", {
#         "request": request,
#         "app_version": APP_VERSION,
#         "build_number": BUILD_NUMBER
#     })

loguru_logger.info("FastAPI application instance created, configured, and routers included.")

# If you need to run this file directly with uvicorn for testing:
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8080)
