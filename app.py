# app.py - Minimal entry point for the Flask application using an application factory

import sys
import os

# Add the project root to the Python path if necessary (can be removed if handled by env)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import logging # Keep basic logging for early errors
from a2wsgi import WSGIMiddleware # Keep import for wrapping

# Basic logging setup (will likely be overridden by config loaded in factory)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.info("--- app.py: Minimal entry point started ---")

# Import the application factory function
try:
    from app_factory import create_app
    logger.info("Successfully imported create_app from app_factory.")
except ImportError as e:
    logger.critical(f"CRITICAL ERROR: Could not import create_app from app_factory: {e}")
    sys.exit(1) # Exit if factory cannot be imported

# Create the Flask application instance using the factory
# The factory returns the WSGI/ASGI wrapped app
try:
    asgi_app = create_app()
    logger.info("Application instance created successfully via create_app factory.")
except Exception as e:
    logger.critical(f"CRITICAL ERROR: Failed to create application instance via factory: {e}")
    sys.exit(1) # Exit if factory fails

# asgi_app is now the target for Uvicorn/ASGI servers (e.g., devserver.sh)

# Remove the __main__ block for running with a separate ASGI server
# if __name__ == '__main__':
#    ...
