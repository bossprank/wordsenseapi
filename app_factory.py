import os
import sys
from loguru import logger as loguru_logger
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.cloud.firestore_v1.async_client import AsyncClient as AsyncFirestoreClient
from google.generativeai import Client as GenAIClient
from google.generativeai import configure as genai_configure
from google.api_core import exceptions as google_exceptions
from typing import Dict, Any

# Attempt to import config and models
try:
    import config
    from config import APP_VERSION, BUILD_NUMBER, GCLOUD_PROJECT, FIRESTORE_DATABASE_ID, get_google_api_key
except ImportError:
    loguru_logger.critical("CRITICAL: config.py not found or key variables missing. App factory cannot proceed.")
    APP_VERSION = "Unknown"
    BUILD_NUMBER = "Unknown"
    GCLOUD_PROJECT = os.environ.get('GCLOUD_PROJECT')
    FIRESTORE_DATABASE_ID = os.environ.get('FIRESTORE_DATABASE_ID')
    def get_google_api_key(): return os.environ.get('GOOGLE_API_KEY') # Fallback

# --- Loguru Configuration (remains largely the same) ---
LOGURU_LOG_DIR = 'mylogs'
LOGURU_LOG_FILE_PATH = os.path.join(LOGURU_LOG_DIR, 'main_app_loguru.log')
LOGURU_ROTATION = "10 minutes"
LOGURU_RETENTION = "5 days"
LOGURU_COMPRESSION = "zip"
logger = logging.getLogger(__name__) # This logger for app_factory.py messages

# --- Loguru Configuration ---
LOGURU_LOG_DIR = 'mylogs'
LOGURU_LOG_FILE_PATH = os.path.join(LOGURU_LOG_DIR, 'main_app_loguru.log') # New name to avoid conflict
LOGURU_ROTATION = "10 minutes" # Changed from "10 MB"
LOGURU_RETENTION = "5 days" # Retention can remain time-based
LOGURU_COMPRESSION = "zip"
LOGURU_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOGURU_CONSOLE_LEVEL = "INFO"
LOGURU_FILE_LEVEL = "DEBUG"

# --- Firestore Helper ---
def get_db() -> firestore.Client:
    """Returns the Firestore client instance from the current app context."""
    # Note: If switching other modules to Loguru, their logger.error calls will use Loguru.
    # This logger.error here will use the standard logger for app_factory.
    if not hasattr(current_app, 'db') or current_app.db is None:
        loguru_logger.error("Firestore client (current_app.db) is not available (called from get_db).") # Use Loguru here for consistency in app logic
        raise RuntimeError("Database client not initialized on app context.")
    return current_app.db

# --- App Factory Function ---
def create_app():
    # --- Loguru Setup ---
    # Ensure LOGURU_LOG_DIR exists
    if not os.path.exists(LOGURU_LOG_DIR):
        try:
            os.makedirs(LOGURU_LOG_DIR)
            print(f"Loguru log directory '{LOGURU_LOG_DIR}' created.")
        except Exception as e:
            print(f"Warning: Could not create Loguru log directory '{LOGURU_LOG_DIR}': {e}")

    loguru_logger.remove() # Remove default handler

    # Console sink
    loguru_logger.add(
        sys.stderr,
        level=LOGURU_CONSOLE_LEVEL,
        format=LOGURU_FORMAT,
        colorize=True # Auto-detects if terminal supports colors
    )
    print(f"Loguru: Console logging configured at level {LOGURU_CONSOLE_LEVEL}.")

    # File sink
    try:
        loguru_logger.add(
            LOGURU_LOG_FILE_PATH,
            level=LOGURU_FILE_LEVEL,
            rotation=LOGURU_ROTATION,
            retention=LOGURU_RETENTION,
            compression=LOGURU_COMPRESSION,
            enqueue=True,  # For async/multiprocess safety
            format=LOGURU_FORMAT,
            encoding="utf-8" # Explicitly set encoding
        )
        print(f"Loguru: File logging configured at '{LOGURU_LOG_FILE_PATH}', level {LOGURU_FILE_LEVEL}.")
    except Exception as e:
        print(f"Warning: Could not set up Loguru file sink for '{LOGURU_LOG_FILE_PATH}': {e}")
        # Loguru might still work with console if file setup fails

    # Intercept standard logging (optional, but can be useful for libraries)
    # This part needs careful consideration if other parts of the app or dependencies
    # rely heavily on standard logging configuration that might conflict.
    # For now, let's keep it simple and assume our app modules will switch to Loguru.
    # If needed, Loguru's InterceptHandler can be added.

    loguru_logger.info("--- create_app(): Application factory started (Loguru configured) ---")

    app = Flask(__name__)
    loguru_logger.info("Flask app instance created.")

    # Load configuration (example: attaching to app.config or directly using imported config)
    # For GCLOUD_PROJECT, APP_VERSION, BUILD_NUMBER, we'll use the imported config module directly
    # or the fallbacks defined at the top of this file.
    app.config['GCLOUD_PROJECT'] = config.GCLOUD_PROJECT
    app.config['FIRESTORE_DATABASE_ID'] = getattr(config, 'FIRESTORE_DATABASE_ID', None)
    app.config['APP_VERSION'] = APP_VERSION
    app.config['BUILD_NUMBER'] = BUILD_NUMBER
    logger.info(f"App configured with GCLOUD_PROJECT: {app.config['GCLOUD_PROJECT']}")

    # Initialize Firestore Client and attach to app context
    try:
        if not app.config['GCLOUD_PROJECT']:
            logger.critical("CRITICAL ERROR: GCLOUD_PROJECT not set in app.config. Cannot initialize Firestore client.")
            # Decide handling: raise error, or let it fail when get_db() is called
            app.db = None # Explicitly set to None
        else:
            logger.info(f"Initializing Firestore Client for project '{app.config['GCLOUD_PROJECT']}'...")
            app.db = firestore.Client(
                project=app.config['GCLOUD_PROJECT'],
                database=app.config['FIRESTORE_DATABASE_ID'] or '(default)'
            )
            logger.info("Firestore Client initialized and attached to app.db.")
    except google_exceptions.PermissionDenied:
        logger.critical("CRITICAL ERROR: Permission denied connecting to Firestore. Check ADC/SA roles.")
        app.db = None
    except Exception as e:
        logger.critical(f"CRITICAL ERROR: Failed to initialize Firestore Client: {e}")
        app.db = None

    # Register Context Processors
    @app.context_processor
    def inject_global_vars() -> Dict[str, str]:
        return dict(
            app_version=app.config['APP_VERSION'],
            build_number=app.config['BUILD_NUMBER']
        )
    logger.info("Global template variables context processor registered.")

    # Register Error Handlers
    @app.errorhandler(400)
    def bad_request(error) -> WerkzeugResponse:
        response = jsonify({'error': 'Bad Request', 'message': error.description})
        response.status_code = 400
        return response

    @app.errorhandler(404)
    def not_found(error) -> WerkzeugResponse:
        response = jsonify({'error': 'Not Found', 'message': error.description})
        response.status_code = 404
        return response

    @app.errorhandler(409)
    def conflict(error) -> WerkzeugResponse:
        response = jsonify({'error': 'Conflict', 'message': error.description})
        response.status_code = 409
        return response

    @app.errorhandler(500)
    def internal_server_error(error) -> WerkzeugResponse:
        logger.exception(f"Internal Server Error: {getattr(error, 'description', str(error))}")
        response = jsonify({'error': 'Internal Server Error', 'message': getattr(error, 'description', 'An internal error occurred.')})
        response.status_code = 500
        return response
    logger.info("Custom error handlers registered.")

    # --- Register Blueprints ---
    from routes.html_routes import html_bp
    from routes.api_list_generation_routes import list_gen_api_bp
    from routes.api_categories_routes import categories_api_bp
    from routes.api_language_pairs_routes import lang_pairs_api_bp

    app.register_blueprint(html_bp)
    app.register_blueprint(list_gen_api_bp)
    app.register_blueprint(categories_api_bp)
    app.register_blueprint(lang_pairs_api_bp)

    # Wrap with WSGIMiddleware for ASGI compatibility
    asgi_app = WSGIMiddleware(app)
    logger.info("Flask app wrapped with WSGIMiddleware for ASGI.")
    logger.info("--- create_app(): Application factory finished ---")
    return asgi_app
