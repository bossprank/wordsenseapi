
# main.py v1.10 - Refined JSON response
# Flask application for the Word Enrichment API
# Using model_dump() for serialization with jsonify.

import os
import asyncio
import logging
import logging.handlers
import traceback
import json # Keep json for potential request parsing issues
from flask import Flask, request, jsonify
from pydantic import ValidationError
from pydantic_core import PydanticSerializationError # Keep for potential model_dump errors
from uuid import uuid4, UUID # Import UUID for type hint

# --- Force Root Logging Configuration ---
LOG_DIR = "mylogs"
LOG_FILENAME = os.path.join(LOG_DIR, "main_app.log")
os.makedirs(LOG_DIR, exist_ok=True) # Ensure log directory exists

# Configure root logger (will apply to Flask and others if not configured separately)
# Use rotating file handler for production
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=10*1024*1024, backupCount=5) # 10MB per file, 5 backups
log_handler.setFormatter(log_formatter)

# Get root logger and add handler
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO) # Set level for root logger
root_logger.addHandler(log_handler)
# Optional: Add console handler for easier debugging during development
# console_handler = logging.StreamHandler()
# console_handler.setFormatter(log_formatter)
# root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__) # Get logger for this module
logger.info("--- Root Logging Initialized (Level: INFO) -> %s ---", LOG_FILENAME)


# --- Initialize Flask App ---
app = Flask(__name__)
# Flask uses its own logger, but messages might propagate to root if not handled
app.logger.info("Flask app initialized. Logging should go to root logger config.")


# --- Import Application Modules ---
Word = None # Define placeholders
EnrichmentInput = None
EnrichmentInfo = None
run_enrichment_for_word = None

try:
    # Ensure models.py v1.3 or later is used
    from models import EnrichmentInput, Word, EnrichmentInfo
    logger.info("Models imported successfully.")
except ImportError as e:
    logger.critical(f"CRITICAL ERROR: Could not import Pydantic models from models.py: {e}")
    # Keep placeholders as None

try:
    # Ensure main_enrichment.py v1.16 or later is used
    from main_enrichment import run_enrichment_for_word
    logger.info("Enrichment logic imported successfully.")
except ImportError as e:
    logger.critical(f"CRITICAL ERROR: Could not import enrichment logic from main_enrichment.py: {e}")
    # Keep placeholder as None

try:
    from config import GCLOUD_PROJECT
    logger.info(f"Configuration loaded for project: {GCLOUD_PROJECT}")
except ImportError:
    logger.warning("Warning: Could not load configuration from config.py.")
    GCLOUD_PROJECT = "N/A" # Set default if config fails


# --- API Endpoints ---

@app.route("/api/v1/enrich", methods=['POST'])
async def handle_enrich_request():
    """Handles POST requests to trigger word enrichment."""
    request_id = str(uuid4()) # Generate unique ID for this request
    logger.info(f"RID-{request_id}: Received {request.method} request for {request.path}")

    # Check if critical components loaded
    if not EnrichmentInput or not run_enrichment_for_word or not Word:
         logger.error(f"RID-{request_id}: Missing critical dependencies (Models/Enrichment Logic). Endpoint disabled.")
         return jsonify({"error": "Server configuration error, enrichment unavailable."}), 500

    # 1. Get and Parse JSON Payload
    try:
        json_data = request.get_json()
        if not json_data:
            logger.warning(f"RID-{request_id}: Missing JSON body.")
            return jsonify({"error": "Missing JSON body."}), 400
        logger.debug(f"RID-{request_id}: Received JSON data: {json_data}")
    except json.JSONDecodeError as e: # More specific exception
        logger.error(f"RID-{request_id}: Error parsing JSON body: {e}")
        return jsonify({"error": f"Could not parse JSON: {e}"}), 400
    except Exception as e:
        logger.error(f"RID-{request_id}: Unexpected error getting JSON: {e}")
        return jsonify({"error": "Could not parse JSON."}), 400


    # 2. Validate Input Data
    try:
        input_data = EnrichmentInput.model_validate(json_data)
        logger.info(f"RID-{request_id}: Validated input for headword: '{input_data.headword}' ({input_data.language} -> {input_data.target_language})")
    except ValidationError as e:
        logger.warning(f"RID-{request_id}: Input validation Error: {e.errors()}")
        # Provide detailed validation errors back to the client
        return jsonify({"error": "Invalid input data.", "details": e.errors()}), 422 # Unprocessable Entity


    # 3. Prepare Batch Info
    batch_info = EnrichmentInfo(batch_id=f"api-enrich-{request_id}", tags=["api", "single-word"])
    logger.debug(f"RID-{request_id}: Batch info created: {batch_info.batch_id}")

    # 4. Call Core Enrichment Logic
    try:
        logger.info(f"RID-{request_id}: Calling enrichment logic for '{input_data.headword}'...")
        # Determine provider override (handle potential absence in older models if necessary)
        provider_override = input_data.provider if hasattr(input_data, 'provider') and input_data.provider else None
        force_reenrich_flag = input_data.force_reenrich if hasattr(input_data, 'force_reenrich') else False

        enriched_word: Optional[Word] = await run_enrichment_for_word(
            headword=input_data.headword,
            source_language=input_data.language,
            target_language=input_data.target_language,
            categories=input_data.categories,
            provider=provider_override,
            force_reenrich=force_reenrich_flag,
            batch_info=batch_info
        )
        logger.info(f"RID-{request_id}: Enrichment logic call completed for '{input_data.headword}'.")

        # 5. Handle Enrichment Result and Respond
        if enriched_word:
            logger.info(f"RID-{request_id}: Enrichment successful for '{input_data.headword}'. Preparing response...")
            try:
                # *** Use model_dump() which returns a dict, suitable for jsonify ***
                response_data = enriched_word.model_dump(mode='json', exclude_none=True) # mode='json' ensures types like UUID/datetime are JSON-serializable
                # logger.debug(f"RID-{request_id}: Prepared response data (dict): {response_data}") # Can be verbose
                return jsonify(response_data), 200
            except (PydanticSerializationError, TypeError, Exception) as resp_err:
                 # Catch potential errors during model_dump
                 logger.error(f"RID-{request_id}: Error serializing successful response for '{input_data.headword}': {resp_err}")
                 # Attempt to return a simplified success message if serialization fails
                 # Ensure word_id is converted to string for JSON
                 word_id_str = str(enriched_word.word_id) if enriched_word.word_id else "N/A"
                 return jsonify({"message": "Enrichment completed but response serialization failed.", "word_id": word_id_str}), 207 # Multi-Status
        else:
            # Enrichment logic itself failed (returned None)
            logger.error(f"RID-{request_id}: Enrichment process failed for '{input_data.headword}' (run_enrichment_for_word returned None).")
            # Return 503 Service Unavailable, as the service failed to fulfill the request
            return jsonify({"error": "Word enrichment process failed internally."}), 503 # Service Unavailable

    except Exception as e:
        # Catch unexpected errors during the process
        logger.exception(f"RID-{request_id}: ERROR: Unexpected error during enrichment processing for '{input_data.headword}':")
        # Return 500 Internal Server Error
        return jsonify({"error": "An unexpected server error occurred during enrichment."}), 500


# --- Other Endpoints (health, hello_world) ---
@app.route("/health")
def health_check():
    """Basic health check endpoint."""
    logger.info("Health check requested.")
    return jsonify({"status": "ok", "project": GCLOUD_PROJECT}), 200

@app.route("/")
def hello_world():
    """Simple welcome endpoint."""
    logger.info("Root path '/' accessed.")
    name = os.environ.get("NAME", "World")
    return f"Hello {name}! Welcome to the Word Enrichment API (Project: {GCLOUD_PROJECT})."

# --- Main Execution ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    # Use debug=False for production/staging environments
    # debug=True enables auto-reloading and more verbose error pages
    is_debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ['true', '1', 't']
    logger.info(f"Starting Flask server on host 0.0.0.0, port {port} (Debug Mode: {is_debug_mode})...")
    # Use app.run for development only. Use a production WSGI server (like gunicorn or uvicorn) for deployment.
    app.run(debug=is_debug_mode, host="0.0.0.0", port=port)
