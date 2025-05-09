# app.py - Flask application for WordSense API and Category Management

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import logging
from flask import Flask, request, jsonify, render_template, abort, Response
from google.cloud import firestore
from google.api_core import exceptions as google_exceptions
from pydantic import ValidationError, BaseModel # Added BaseModel
from datetime import datetime # Needed for log rotation timestamp
import shutil # Needed for log rotation (rename)
import uuid # For generating readable IDs
import json # For parsing JSON schema input
import asyncio # For running async functions
from typing import Optional, List, Dict, Any, Tuple # Added Tuple
from werkzeug.wrappers import Response as WerkzeugResponse # Added Response alias
from a2wsgi import WSGIMiddleware

# --- Log Rotation ---
LOG_DIR = 'mylogs'
LOG_FILE = os.path.join(LOG_DIR, 'main_app.log')

def rotate_log_file():
    """Archives the existing log file with a timestamp if it exists."""
    try:
        # Ensure log directory exists
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
        # Check if the file exists before attempting to move
        if os.path.exists(LOG_FILE):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_file = os.path.join(LOG_DIR, f'main_app_{timestamp}.log')
            print(f"Archiving existing log file to: {archive_file}")
            shutil.move(LOG_FILE, archive_file)
    except Exception as e:
        print(f"Warning: Could not archive log file '{LOG_FILE}': {e}")

# Rotate log before setting up logging
rotate_log_file()

# Set up basic logging before attempting to import config
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Changed to DEBUG
logger = logging.getLogger(__name__)
logger.info("--- app.py: Logging level set to DEBUG ---") # Added log message

# --- Configuration and Initialization ---
try:
    # Assuming config.py sets up logging and loads environment variables
    import config
    from config import APP_VERSION, BUILD_NUMBER # Import new vars
    # config.py is expected to configure logging, but basic config is already set up.
    # If config.py has its own logging setup, it might override this.
except ImportError:
    print("Warning: config.py not found or import failed. Using basic config and environment variables.")
    # Attempt to load GCLOUD_PROJECT directly if config fails
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
    config = type('obj', (object,), {'GCLOUD_PROJECT': os.environ.get('GCLOUD_PROJECT'), 'FIRESTORE_DATABASE_ID': os.environ.get('FIRESTORE_DATABASE_ID')})()
    # Define fallback values for APP_VERSION and BUILD_NUMBER if config import fails
    APP_VERSION = "Unknown"
    BUILD_NUMBER = "Unknown"


try:
    from models import VocabularyCategory, LanguagePairConfiguration
except ImportError:
    logger.critical("CRITICAL ERROR: Could not import models from models.py.")
    sys.exit(1)

# Import new models and clients in separate blocks to isolate import errors
try:
    from models import GenerateListInput, GeneratedWordList, GeneratedWordListParameters, WordItem, UpdateListMetadataInput # Added UpdateListMetadataInput
except ImportError as e:
     logger.critical(f"CRITICAL ERROR: Could not import models for list generation: {e}")
     sys.exit(1)

try:
    import llm_client
except ImportError as e:
     logger.critical(f"CRITICAL ERROR: Could not import llm_client: {e}")
     sys.exit(1)

try:
    import firestore_client # Assuming this now contains the async functions
except ImportError as e:
     logger.critical(f"CRITICAL ERROR: Could not import firestore_client: {e}")
     sys.exit(1)

# --- Test Config Import After Client Imports ---
try:
    import config as test_config_import
    logger.info("Test: Successfully imported config after client imports.")
except ImportError as e:
    logger.critical(f"Test: Failed to import config after client imports: {e}")
# --- End Test ---


app = Flask(__name__)
asgi_app = WSGIMiddleware(app)

# --- Inject Global Template Variables ---
@app.context_processor
def inject_global_vars() -> Dict[str, str]: # Added return type hint
    return dict(
        app_version=APP_VERSION,
        build_number=BUILD_NUMBER
    )

# --- Firestore Client Initialization ---
# Using synchronous client for simplicity in Flask routes for now
# TODO: Refactor to use async client from firestore_client.py if possible
db = None
try:
    if not config.GCLOUD_PROJECT:
        logger.critical("CRITICAL ERROR: GCLOUD_PROJECT not set. Cannot initialize Firestore client.")
        sys.exit(1)
    logger.info(f"Initializing Firestore Client for project '{config.GCLOUD_PROJECT}'...")
    db = firestore.Client(project=config.GCLOUD_PROJECT, database=config.FIRESTORE_DATABASE_ID or '(default)')
    # Removed problematic test connection: db.collection('__test__').document('__test__').get()
    logger.info("Firestore Client initialized successfully.")
except google_exceptions.PermissionDenied:
    logger.critical("CRITICAL ERROR: Permission denied connecting to Firestore. Check ADC/SA roles.")
    # Don't exit here, let app run but endpoints will fail
except Exception as e:
    logger.critical(f"CRITICAL ERROR: Failed to initialize Firestore Client: {e}")
    # Don't exit here, let app run but endpoints will fail

CATEGORIES_COLLECTION = 'master_categories'
LANGUAGE_PAIR_CONFIGS_COLLECTION = 'language_pair_configurations'

# --- Helper Functions ---
def get_db() -> firestore.Client: # Added return type hint
    """Returns the Firestore client instance, raising an error if unavailable."""
    if db is None:
        logger.error("Firestore client is not available.")
        abort(500, description="Database connection is not available.")
    # Type checker might complain db can be None, but abort prevents that path.
    # Add assert or cast if needed: assert db is not None
    return db # type: ignore

# --- Custom Error Handlers for API ---
@app.errorhandler(400)
def bad_request(error) -> WerkzeugResponse: # Added return type hint
    response = jsonify({'error': 'Bad Request', 'message': error.description})
    response.status_code = 400
    return response

@app.errorhandler(404)
def not_found(error) -> WerkzeugResponse: # Added return type hint
    response = jsonify({'error': 'Not Found', 'message': error.description})
    response.status_code = 404
    return response

@app.errorhandler(409)
def conflict(error) -> WerkzeugResponse: # Added return type hint
    response = jsonify({'error': 'Conflict', 'message': error.description})
    response.status_code = 409
    return response

@app.errorhandler(500)
def internal_server_error(error) -> WerkzeugResponse: # Added return type hint
    # Log the error with traceback
    logger.exception(f"Internal Server Error: {error.description}")
    response = jsonify({'error': 'Internal Server Error', 'message': error.description})
    response.status_code = 500
    return response

# --- HTML Routes ---

@app.route('/')
def index() -> str: # Added return type hint
    """Serves the main index page (assuming it exists)."""
    # Pass a variable to the template to indicate it's the index page
    return render_template('index.html', is_index_page=True)

@app.route('/manage-categories')
@app.route('/manage-categories')
def manage_categories_page() -> str: # Added return type hint
    """Serves the HTML page for managing categories."""
    logger.info("Serving category management page.")
    return render_template('manage_categories.html', is_index_page=False)

@app.route('/manage-language-pairs')
@app.route('/manage-language-pairs')
def manage_language_pairs_page() -> str: # Added return type hint
    """Serves the HTML page for managing language pair configurations."""
    logger.info("Serving language pair management page.")
    return render_template('manage_language_pairs.html', is_index_page=False)

@app.route('/language-pair-config-detail/<string:config_id>')
def language_pair_config_detail_page(config_id: str) -> str: # Added type hint
    """Serves the HTML page for adding/editing a single language pair configuration."""
    logger.info(f"Serving language pair config detail page for ID: {config_id}")
    # Pass config_id and hide_navigation flag to the template
    hide_nav = config_id == 'new'
    return render_template('language_pair_config_detail.html', config_id=config_id, hide_navigation=hide_nav, is_index_page=False)

@app.route('/generate-new-list')
def generate_new_word_list_page() -> str: # Added return type hint
    """Serves the HTML page for generating a new word list."""
    logger.info("Serving generate new word list page.")
    # Need to decide if sidebar should be shown. Assuming yes for now.
    return render_template('generate_new_word_list.html', is_index_page=False) 

@app.route('/view-generated-lists')
def view_generated_lists_page() -> str: # Added return type hint
    """Serves the HTML page for viewing generated word lists."""
    logger.info("Serving view generated lists page.")
    # Assuming sidebar should be shown
    return render_template('view_generated_word_lists.html', is_index_page=False)

@app.route('/list-details/<string:list_firestore_id>')
def generated_list_details_page(list_firestore_id: str) -> str: # Added type hint
    """Serves the HTML page for viewing details of a specific generated list."""
    logger.info(f"Serving generated list details page for ID: {list_firestore_id}")
    # Assuming sidebar should be shown
    return render_template('generated_list_details.html', list_firestore_id=list_firestore_id, is_index_page=False)

@app.route('/edit-list-metadata/<string:list_firestore_id>')
def edit_list_metadata_page(list_firestore_id: str) -> str: # Added type hint
    """Serves the HTML page for editing metadata of a specific generated list."""
    logger.info(f"Serving edit list metadata page for ID: {list_firestore_id}")
    # Assuming sidebar should be shown
    return render_template('edit_list_metadata.html', list_firestore_id=list_firestore_id, is_index_page=False)

# --- API Routes for Vocabulary Categories ---

@app.route('/api/categories', methods=['GET'])
def get_categories() -> WerkzeugResponse: # Added return type hint
    """API endpoint to get categories, optionally filtered by language."""
    language_filter = request.args.get('lang')
    logger.info(f"GET /api/categories called. Language filter: {language_filter}")
    categories = []
    try:
        fs_db = get_db()
        query = fs_db.collection(CATEGORIES_COLLECTION).stream() # Basic stream for now

        for doc in query:
            category_data = doc.to_dict()
            if category_data: # Check if data is not None
                 category_data['category_id'] = doc.id # Add ID back

                 # Apply language filter (basic check on display_name)
                 if language_filter:
                     if language_filter in category_data.get('display_name', {}):
                         categories.append(category_data)
                 else:
                     # No filter, add all
                     categories.append(category_data)

        logger.info(f"Returning {len(categories)} categories.")
        return jsonify(categories)
    except Exception as e:
        logger.exception(f"Error fetching categories: {e}")
        abort(500, description="Failed to retrieve categories.")


@app.route('/api/categories', methods=['POST'])
def create_category() -> Tuple[WerkzeugResponse, int]: # Added return type hint
    """API endpoint to create a new category."""
    logger.info("POST /api/categories called.")
    if not request.is_json:
        logger.warning("Request is not JSON.")
        abort(400, description="Request must be JSON.")

    data = request.get_json()
    if not data or 'category_id' not in data:
         logger.warning("Missing category_id in request data.")
         abort(400, description="Missing 'category_id' in request data.")

    doc_id = data['category_id']

    try:
        # Validate incoming data using the Pydantic model
        # Note: Pydantic expects the data *without* the ID field usually,
        # but our model includes it. Let's validate the whole thing.
        # Exclude timestamp fields from validation as they are server-set
        category = VocabularyCategory.model_validate(data, exclude={'created_at', 'updated_at'})
        data_to_save = category.model_dump(exclude={'category_id', 'created_at', 'updated_at'}, exclude_none=True) # Exclude ID & timestamps

        fs_db = get_db()
        doc_ref = fs_db.collection(CATEGORIES_COLLECTION).document(doc_id)

        # Check if document already exists
        if doc_ref.get().exists:
            logger.warning(f"Category with ID '{doc_id}' already exists.")
            abort(409, description=f"Category with ID '{doc_id}' already exists.")

        # Add server timestamps for create and update times
        data_to_save['created_at'] = firestore.SERVER_TIMESTAMP
        data_to_save['updated_at'] = firestore.SERVER_TIMESTAMP

        doc_ref.set(data_to_save)
        logger.info(f"Successfully created category: {doc_id}")

        # Fetch the created data to return it (timestamps will be populated)
        created_doc = doc_ref.get()
        if created_doc.exists:
             response_data = created_doc.to_dict()
             if response_data: # Check if data is not None
                 response_data['category_id'] = created_doc.id
                 return jsonify(response_data), 201 # 201 Created
             else:
                 logger.error(f"Category {doc_id} created but to_dict() returned None.")
                 abort(500, description="Category created but could not be retrieved.")
        else:
             # Should not happen if set() succeeded, but handle defensively
             logger.error(f"Failed to fetch category {doc_id} immediately after creation.")
             abort(500, description="Category created but could not be retrieved.")

    except ValidationError as e:
        logger.warning(f"Validation error creating category: {e}")
        abort(400, description=f"Invalid category data: {e}")
    except Exception as e:
        logger.exception(f"Error creating category {doc_id}: {e}")
        abort(500, description="Failed to create category.")


@app.route('/api/categories/<string:category_id>', methods=['GET'])
def get_category(category_id: str) -> WerkzeugResponse: # Added type hint
    """API endpoint to get a single category by ID."""
    logger.info(f"GET /api/categories/{category_id} called.")
    try:
        fs_db = get_db()
        doc_ref = fs_db.collection(CATEGORIES_COLLECTION).document(category_id)
        doc_snapshot = doc_ref.get()

        if doc_snapshot.exists:
            category_data = doc_snapshot.to_dict()
            if category_data: # Check if data is not None
                category_data['category_id'] = doc_snapshot.id
                logger.info(f"Found category: {category_id}")
                return jsonify(category_data)
            else:
                logger.warning(f"Category document {category_id} exists but has no data.")
                abort(404, description=f"Category with ID '{category_id}' found but contains no data.")
        else:
            logger.warning(f"Category not found: {category_id}")
            abort(404, description=f"Category with ID '{category_id}' not found.")
    except Exception as e:
        logger.exception(f"Error fetching category {category_id}: {e}")
        abort(500, description="Failed to retrieve category.")


@app.route('/api/categories/<string:category_id>', methods=['PUT'])
def update_category(category_id: str) -> WerkzeugResponse: # Added type hint
    """API endpoint to update an existing category."""
    logger.info(f"PUT /api/categories/{category_id} called.")
    if not request.is_json:
        logger.warning("Request is not JSON.")
        abort(400, description="Request must be JSON.")

    data = request.get_json()
    # Ensure the ID in the payload matches the URL, if provided
    if 'category_id' in data and data['category_id'] != category_id:
         logger.warning(f"Mismatch between category_id in URL ({category_id}) and payload ({data['category_id']}).")
         abort(400, description="Category ID in payload must match URL.")
    # Add category_id from URL to data for validation if not present
    if 'category_id' not in data:
        data['category_id'] = category_id

    try:
        # Validate incoming data (Timestamps are handled by Firestore, not excluded here)
        category = VocabularyCategory.model_validate(data)
        # Exclude timestamps here before saving, as they are server-managed
        data_to_save = category.model_dump(exclude={'category_id', 'created_at', 'updated_at'}, exclude_none=True)

        # Add server timestamp only for update time
        data_to_save['updated_at'] = firestore.SERVER_TIMESTAMP

        fs_db = get_db()
        doc_ref = fs_db.collection(CATEGORIES_COLLECTION).document(category_id)

        # Use update for partial updates, or set with merge=True
        # Using set() here to match the original population script's behavior (overwrite)
        # Check existence before setting to provide 404 if not found
        if not doc_ref.get().exists:
             logger.warning(f"Category not found for update: {category_id}")
             abort(404, description=f"Category with ID '{category_id}' not found for update.")

        doc_ref.set(data_to_save) # Overwrites the document
        logger.info(f"Successfully updated category: {category_id}")

        # Fetch the updated data to return it
        updated_doc = doc_ref.get()
        if updated_doc.exists:
             response_data = updated_doc.to_dict()
             if response_data: # Check if data is not None
                 response_data['category_id'] = updated_doc.id
                 return jsonify(response_data)
             else:
                 logger.error(f"Category {category_id} updated but to_dict() returned None.")
                 abort(500, description="Category updated but could not be retrieved.")
        else:
             logger.error(f"Failed to fetch category {category_id} immediately after update.")
             abort(500, description="Category updated but could not be retrieved.")

    except ValidationError as e:
        logger.warning(f"Validation error updating category {category_id}: {e}")
        abort(400, description=f"Invalid category data: {e}")
    except google_exceptions.NotFound: # Should be caught by pre-check now
         logger.warning(f"Category not found for update (NotFound Exception): {category_id}")
         abort(404, description=f"Category with ID '{category_id}' not found for update.")
    except Exception as e:
        logger.exception(f"Error updating category {category_id}: {e}")
        abort(500, description="Failed to update category.")


@app.route('/api/categories/<string:category_id>', methods=['DELETE'])
def delete_category(category_id: str) -> Tuple[WerkzeugResponse, int]: # Added type hint
    """API endpoint to delete a category."""
    logger.info(f"DELETE /api/categories/{category_id} called.")
    try:
        fs_db = get_db()
        doc_ref = fs_db.collection(CATEGORIES_COLLECTION).document(category_id)

        # Check if document exists before deleting
        if not doc_ref.get().exists:
             logger.warning(f"Category not found for deletion: {category_id}")
             abort(404, description=f"Category with ID '{category_id}' not found.")

        doc_ref.delete()
        logger.info(f"Successfully deleted category: {category_id}")
        return jsonify({"message": f"Category '{category_id}' deleted successfully."}), 200
    except google_exceptions.NotFound: # Should be caught by the check above, but handle defensively
         logger.warning(f"Category not found for deletion (redundant check): {category_id}")
         abort(404, description=f"Category with ID '{category_id}' not found.")
    except Exception as e:
        logger.exception(f"Error deleting category {category_id}: {e}")
        abort(500, description="Failed to delete category.")

# ==== Language Pair Configuration Endpoints ====

@app.route('/api/language-pair-configurations', methods=['GET'])
def get_language_pair_configs() -> WerkzeugResponse: # Added return type hint
    """API endpoint to get configurations with optional filters."""
    language_pair_filter = request.args.get('language_pair')
    config_key_filter = request.args.get('config_key')
    logger.info(f"GET /api/language-pair-configurations called. Filters: pair={language_pair_filter}, key={config_key_filter}")
    
    try:
        fs_db = get_db()
        query = fs_db.collection(LANGUAGE_PAIR_CONFIGS_COLLECTION)
        
        # Apply filters
        if language_pair_filter:
            query = query.where('language_pair', '==', language_pair_filter)
        if config_key_filter:
            query = query.where('config_key', '==', config_key_filter)
            
        docs = query.stream()
        
        configs = []
        for doc in docs:
            config_data = doc.to_dict()
            if config_data: # Check if data is not None
                config_data['id'] = doc.id
                configs.append(config_data)
            
        logger.info(f"Returning {len(configs)} configurations")
        return jsonify(configs)
        
    except Exception as e:
        logger.exception(f"Error fetching configurations: {e}")
        abort(500, description="Failed to retrieve configurations")

@app.route('/api/language-pair-configurations', methods=['POST'])
def create_language_pair_config() -> Tuple[WerkzeugResponse, int]: # Added return type hint
    """API endpoint to create a new configuration."""
    logger.info("POST /api/language-pair-configurations called")
    if not request.is_json:
        abort(400, description="Request must be JSON")

    data = request.get_json()
    
    try:
        # Validate incoming data
        config_model = LanguagePairConfiguration.model_validate(data) # Renamed variable
        data_to_save = config_model.model_dump(exclude={'id', 'created_at', 'updated_at'}, exclude_none=True)
        
        # Add server timestamps
        data_to_save['created_at'] = firestore.SERVER_TIMESTAMP
        data_to_save['updated_at'] = firestore.SERVER_TIMESTAMP

        fs_db = get_db()
        # Let Firestore auto-generate ID
        doc_ref = fs_db.collection(LANGUAGE_PAIR_CONFIGS_COLLECTION).document()
        doc_ref.set(data_to_save)
        
        # Return created document
        created_doc = doc_ref.get()
        if created_doc.exists:
            created_data = created_doc.to_dict()
            if created_data: # Check if data is not None
                created_data['id'] = doc_ref.id
                return jsonify(created_data), 201
            else:
                 logger.error(f"Config {doc_ref.id} created but to_dict() returned None.")
                 abort(500, description="Config created but could not be retrieved.")
        else:
             logger.error(f"Failed to fetch config {doc_ref.id} immediately after creation.")
             abort(500, description="Config created but could not be retrieved.")


    except ValidationError as e:
        logger.warning(f"Validation error creating configuration: {e}")
        abort(400, description=f"Invalid configuration data: {e}")
    except Exception as e:
        logger.exception(f"Error creating configuration: {e}")
        abort(500, description="Failed to create configuration")

@app.route('/api/language-pair-configurations/<string:config_id>', methods=['GET'])
def get_language_pair_config(config_id: str) -> WerkzeugResponse: # Added type hint
    """API endpoint to get a single configuration by ID."""
    logger.info(f"GET /api/language-pair-configurations/{config_id} called")
    try:
        fs_db = get_db()
        doc_ref = fs_db.collection(LANGUAGE_PAIR_CONFIGS_COLLECTION).document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            abort(404, description=f"Configuration {config_id} not found")
            
        config_data = doc.to_dict()
        if config_data: # Check if data is not None
            config_data['id'] = doc.id
            return jsonify(config_data)
        else:
             logger.warning(f"Config document {config_id} exists but has no data.")
             abort(404, description=f"Configuration {config_id} found but contains no data.")

    except google_exceptions.NotFound:
        logger.warning(f"Configuration not found: {config_id}")
        abort(404, description=f"Configuration {config_id} not found")
    except Exception as e:
        logger.exception(f"Error fetching configuration {config_id}: {e}")
        abort(500, description="Failed to retrieve configuration")

@app.route('/api/language-pair-configurations/<string:config_id>', methods=['PUT'])
def update_language_pair_config(config_id: str) -> WerkzeugResponse: # Added type hint
    """API endpoint to update an existing configuration."""
    logger.info(f"PUT /api/language-pair-configurations/{config_id} called")
    if not request.is_json:
        abort(400, description="Request must be JSON")

    data = request.get_json()
    if 'id' in data and data['id'] != config_id:
        abort(400, description="Configuration ID in payload must match URL")

    try:
        fs_db = get_db()
        doc_ref = fs_db.collection(LANGUAGE_PAIR_CONFIGS_COLLECTION).document(config_id)
        
        if not doc_ref.get().exists:
            abort(404, description=f"Configuration {config_id} not found")

        # Validate and prepare update data
        data['id'] = config_id  # Ensure ID matches for validation
        config_model = LanguagePairConfiguration.model_validate(data) # Renamed variable
        update_data = config_model.model_dump(exclude={'id', 'created_at', 'updated_at'}, exclude_none=True)
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP

        doc_ref.update(update_data)
        
        # Return updated config
        updated_doc = doc_ref.get()
        if updated_doc.exists:
            updated_data_dict = updated_doc.to_dict() # Renamed variable
            if updated_data_dict: # Check if data is not None
                updated_data_dict['id'] = config_id
                return jsonify(updated_data_dict)
            else:
                 logger.error(f"Config {config_id} updated but to_dict() returned None.")
                 abort(500, description="Config updated but could not be retrieved.")
        else:
             logger.error(f"Failed to fetch config {config_id} immediately after update.")
             abort(500, description="Config updated but could not be retrieved.")


    except ValidationError as e:
        logger.warning(f"Validation error updating configuration {config_id}: {e}")
        abort(400, description=f"Invalid configuration data: {e}")
    except Exception as e:
        logger.exception(f"Error updating configuration {config_id}: {e}")
        abort(500, description="Failed to update configuration")

@app.route('/api/language-pair-configurations/<string:config_id>', methods=['DELETE'])
def delete_language_pair_config(config_id: str) -> Tuple[WerkzeugResponse, int]: # Added type hint
    """API endpoint to delete a configuration."""
    logger.info(f"DELETE /api/language-pair-configurations/{config_id} called")
    try:
        fs_db = get_db()
        doc_ref = fs_db.collection(LANGUAGE_PAIR_CONFIGS_COLLECTION).document(config_id)

        if not doc_ref.get().exists:
            abort(404, description=f"Configuration {config_id} not found")

        doc_ref.delete()
        return jsonify({"message": f"Configuration {config_id} deleted successfully"}), 200

    except Exception as e:
        logger.exception(f"Error deleting configuration {config_id}: {e}")
        abort(500, description="Failed to delete configuration")


# ==== Vocabulary List Generation Endpoints ====

# Helper function to read instruction files safely
def read_instruction_file(file_ref: str) -> Optional[str]:
    """Reads content from a file within the llm_prompts directory."""
    # Basic security: prevent path traversal
    if ".." in file_ref or file_ref.startswith("/"):
        logger.warning(f"Attempted to access potentially unsafe path: {file_ref}")
        return None
    
    file_path = os.path.join('llm_prompts', file_ref)
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            logger.warning(f"Instruction file not found: {file_path}")
            return None
    except Exception as e:
        logger.error(f"Error reading instruction file {file_path}: {e}")
        return None

# Helper function to generate readable ID
def generate_readable_id(language: str, cefr: str) -> str:
    """Generates a unique readable ID for a new list."""
    timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")
    # Use first 4 chars of uuid4 hex for uniqueness component
    unique_part = uuid.uuid4().hex[:4].upper()
    return f"{language.upper()}-{cefr.upper()}-{timestamp}-{unique_part}"

# Helper to parse word items from LLM response
def parse_word_items(llm_output: Any, mime_type: str) -> List[WordItem]:
    """Parses the LLM output into a list of WordItem objects."""
    word_items = []
    parsed_data: Optional[Union[Dict, List]] = None # Variable to hold parsed JSON

    if mime_type == "application/json":
        if isinstance(llm_output, str): # Check if it's a string first
            try:
                # Attempt to parse the JSON string
                # Optional: Use _clean_llm_json_output from llm_client if needed
                # Note: _clean_llm_json_output is internal, better to handle potential markdown here if necessary
                cleaned_text = llm_output.strip()
                if cleaned_text.startswith("```json") and cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[7:-3].strip()
                elif cleaned_text.startswith("```") and cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[3:-3].strip()
                
                parsed_data = json.loads(cleaned_text)
                logger.info("Successfully parsed JSON string from LLM output.")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON string from LLM output: {e}")
                logger.debug(f"Raw string received: {llm_output}")
                # Keep parsed_data as None
            except Exception as e: # Catch other potential errors during parsing
                 logger.error(f"Unexpected error parsing JSON string: {e}")
                 logger.debug(f"Raw string received: {llm_output}")

        elif isinstance(llm_output, (dict, list)): # Handle if it was already parsed (e.g., by llm_client if response_model was used)
            logger.debug("LLM output was already a dict or list.")
            parsed_data = llm_output
        else:
             logger.error(f"LLM output type unexpected for JSON mime_type. Got: {type(llm_output)}")


        # Now process the parsed_data (which should be a dict or list, or None if parsing failed)
        if isinstance(parsed_data, dict) and 'words' in parsed_data and isinstance(parsed_data['words'], list):
            logger.info(f"Found 'words' list in parsed JSON dict. Processing {len(parsed_data['words'])} items.")
            for item in parsed_data['words']:
                 if isinstance(item, dict):
                     try:
                         # Validate against WordItem, allowing extra fields
                         word_item = WordItem.model_validate(item)
                         word_items.append(word_item)
                     except ValidationError as e:
                         logger.warning(f"Skipping word item due to validation error: {e}. Item: {item}")
                 else:
                      logger.warning(f"Skipping non-dict item in 'words' list: {item}")
        elif isinstance(parsed_data, list):
             # Maybe the LLM returned a list directly? Less ideal but handle it.
             logger.warning("Parsed JSON was a list directly instead of a dict with 'words'. Attempting to parse list items.")
             for item in parsed_data:
                 if isinstance(item, dict):
                     try:
                         word_item = WordItem.model_validate(item)
                         word_items.append(word_item)
                     except ValidationError as e:
                         logger.warning(f"Skipping word item due to validation error: {e}. Item: {item}")
                 else:
                     logger.warning(f"Skipping non-dict item in list: {item}")
        elif parsed_data is not None: # Parsed but not the expected format
             logger.error(f"Parsed JSON structure unexpected. Expected dict with 'words' list or list. Got: {type(parsed_data)}")
        # else: parsing failed or input was wrong type, already logged

    elif mime_type == "text/plain":
        # Basic parsing: split by newline, assume each line is a headword
        if isinstance(llm_output, str):
            lines = llm_output.strip().split('\n')
            word_items = [WordItem(headword=line.strip()) for line in lines if line.strip()]
        else:
             logger.error(f"LLM Text response was not a string. Got: {type(llm_output)}")
    else:
        logger.error(f"Unsupported response mime type for parsing word items: {mime_type}")

    return word_items


@app.route('/api/v1/generated-lists', methods=['POST'])
async def generate_list() -> Tuple[WerkzeugResponse, int]: # Added return type hint
    """API endpoint to generate a new vocabulary list."""
    logger.info("POST /api/v1/generated-lists called.")
    if not request.is_json:
        logger.warning("Request is not JSON.")
        abort(400, description="Request must be JSON.")

    request_data = request.get_json()

    try:
        # 1. Validate input payload
        input_params = GenerateListInput.model_validate(request_data)
        logger.info(f"Validated input parameters for language: {input_params.language}, level: {input_params.cefr_level}")
    except ValidationError as e:
        logger.warning(f"Input validation failed: {e}")
        abort(400, description=f"Invalid input data: {e}")

    # 2. Generate unique readable ID
    readable_id = generate_readable_id(input_params.language, input_params.cefr_level)
    logger.info(f"Generated readable ID: {readable_id}")

    # 3. Read instruction files
    base_instruction = read_instruction_file(input_params.base_instruction_file_ref)
    if base_instruction is None:
        abort(400, description=f"Base instruction file not found or could not be read: {input_params.base_instruction_file_ref}")

    custom_instruction = ""
    if input_params.custom_instruction_file_ref:
        custom_content = read_instruction_file(input_params.custom_instruction_file_ref)
        if custom_content is None:
            abort(400, description=f"Custom instruction file not found or could not be read: {input_params.custom_instruction_file_ref}")
        custom_instruction = custom_content + "\n\n" # Add separator

    # 4. Concatenate instructions, adding language and level explicitly
    language_name_map = {"id": "Indonesian", "en": "English"} # Add more languages as needed
    language_name = language_name_map.get(input_params.language, input_params.language) # Get full name if possible

    prompt_prefix = f"Target Language: {language_name} ({input_params.language})\n" \
                    f"CEFR Level: {input_params.cefr_level}\n\n"

    final_prompt_text = prompt_prefix + base_instruction + "\n\n" + custom_instruction + (input_params.ui_text_refinements or "")
    logger.debug(f"Final prompt text generated (first 300 chars): {final_prompt_text[:300]}...") # Log more chars

    # 5. Prepare parameters for LLM call
    llm_response_schema = None
    if input_params.gemini_response_mime_type == "application/json" and input_params.gemini_response_schema_used:
        if isinstance(input_params.gemini_response_schema_used, str):
            try:
                llm_response_schema = json.loads(input_params.gemini_response_schema_used)
                logger.info("Parsed JSON schema string from input.")
            except json.JSONDecodeError as e:
                 logger.error(f"Failed to parse JSON schema string: {e}")
                 abort(400, description="Invalid JSON schema string provided.")
        elif isinstance(input_params.gemini_response_schema_used, dict):
             llm_response_schema = input_params.gemini_response_schema_used
             logger.info("Using dictionary schema from input.")
        # Note: Pydantic model schema support might require passing the model class itself,
        # which isn't directly feasible from JSON input. Using dict schema is more practical here.

    # 6. Call LLM client
    try:
        logger.info(f"Calling LLM ({input_params.source_model}) for generation...")
        llm_result = await llm_client.generate_structured_content(
            prompt=final_prompt_text,
            provider='googleai', # Hardcoded for now, could be dynamic later
            model_name=input_params.source_model,
            temperature=input_params.gemini_temperature,
            top_p=input_params.gemini_top_p,
            top_k=input_params.gemini_top_k,
            max_output_tokens=input_params.gemini_max_output_tokens,
            stop_sequences=input_params.gemini_stop_sequences,
            response_mime_type=input_params.gemini_response_mime_type,
            response_schema=llm_response_schema,
            # Using default retries/delay from llm_client
        )
    except Exception as e:
        logger.exception("LLM client call failed.")
        abort(500, description=f"LLM generation failed: {e}")

    # 7. Process LLM response
    if llm_result is None or (isinstance(llm_result, dict) and 'error' in llm_result):
        error_detail = llm_result.get('error', 'Unknown LLM error') if isinstance(llm_result, dict) else 'Unknown LLM error'
        raw_text = llm_result.get('raw_text', None) if isinstance(llm_result, dict) else None
        logger.error(f"LLM generation failed. Error: {error_detail}. Raw text (if any): {raw_text}")
        abort(500, description=f"LLM generation failed: {error_detail}")

    logger.info("LLM generation successful.")
    # llm_result contains the parsed Pydantic model if response_model was used,
    # or raw string/dict otherwise. We need to parse based on mime_type.
    word_items = parse_word_items(llm_result, input_params.gemini_response_mime_type)
    generated_count = len(word_items)
    logger.info(f"Parsed {generated_count} word items from LLM response.")

    # 8. Construct GeneratedWordList object
    try:
        list_params = GeneratedWordListParameters(
            list_readable_id=readable_id,
            status="New", # Initial status
            language=input_params.language,
            cefr_level=input_params.cefr_level,
            list_category_id=input_params.list_category_id,
            admin_notes=input_params.admin_notes,
            requested_word_count=input_params.requested_word_count,
            generated_word_count=generated_count,
            base_instruction_file_ref=input_params.base_instruction_file_ref,
            custom_instruction_file_ref=input_params.custom_instruction_file_ref,
            ui_text_refinements=input_params.ui_text_refinements,
            final_llm_prompt_text_sent=final_prompt_text, # Log the prompt sent
            source_model=input_params.source_model,
            gemini_temperature=input_params.gemini_temperature,
            gemini_top_p=input_params.gemini_top_p,
            gemini_top_k=input_params.gemini_top_k,
            gemini_max_output_tokens=input_params.gemini_max_output_tokens,
            gemini_stop_sequences=input_params.gemini_stop_sequences,
            gemini_response_mime_type=input_params.gemini_response_mime_type,
            gemini_response_schema_used=input_params.gemini_response_schema_used, # Log schema used
            include_english_translation=input_params.include_english_translation,
            generated_by=input_params.generated_by, # Need to get actual user ID later
            # Timestamps are set by Firestore
        )

        new_list_data = GeneratedWordList(
            generation_parameters=list_params,
            word_items=word_items
        )
    except ValidationError as e:
         logger.error(f"Failed to construct GeneratedWordList object: {e}")
         abort(500, description=f"Internal error constructing list data: {e}")


    # 9. Save to Firestore
    try:
        # Assuming firestore_client has the async save function
        saved_list = await firestore_client.save_generated_list(new_list_data)
        if saved_list and saved_list.list_firestore_id:
            logger.info(f"Successfully saved generated list with Firestore ID: {saved_list.list_firestore_id}")
            # Return the saved list data (or just ID and readable ID)
            return jsonify({
                "message": "Word list generated successfully.",
                "list_firestore_id": saved_list.list_firestore_id,
                "list_readable_id": saved_list.generation_parameters.list_readable_id
            }), 201
        else:
            logger.error("Failed to save generated list to Firestore (save function returned None or no ID).")
            abort(500, description="Failed to save generated list after generation.")
    except Exception as e:
        logger.exception("Error saving generated list to Firestore.")
        abort(500, description="Failed to save generated list to database.")

@app.route('/api/v1/generated-lists', methods=['GET'])
async def get_generated_lists() -> WerkzeugResponse: # Added return type hint
    """API endpoint to get generated word lists with filtering, sorting, and pagination."""
    logger.info("GET /api/v1/generated-lists called.")
    
    # Extract query parameters
    try:
        # Filters
        filters = {
            "language": request.args.get('language'),
            "cefr_level": request.args.get('cefr_level'),
            "status": request.args.get('status'),
            "list_category_id": request.args.get('list_category_id')
        }
        # Remove None values from filters
        filters = {k: v for k, v in filters.items() if v}

        # Sorting - map frontend keys to Firestore paths if needed
        sort_by_param = request.args.get('sort_by', 'generation_timestamp') # Default sort
        sort_direction_param = request.args.get('sort_dir', 'DESC').upper()
        
        # Basic mapping (can be expanded)
        sort_field_map = {
            "readable_id": "generation_parameters.list_readable_id",
            "language": "generation_parameters.language",
            "cefr": "generation_parameters.cefr_level",
            # "category": "generation_parameters.list_category_id", # Sorting by resolved name is hard
            "status": "generation_parameters.status",
            "words_gen": "generation_parameters.generated_word_count",
            "date_created": "generation_parameters.generation_timestamp"
        }
        sort_by_firestore = sort_field_map.get(sort_by_param, "generation_parameters.generation_timestamp")
        
        sort_direction = "DESCENDING" if sort_direction_param == "DESC" else "ASCENDING"

        # Pagination
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        
        logger.debug(f"Query Params: filters={filters}, sort_by={sort_by_firestore}, sort_dir={sort_direction}, limit={limit}, offset={offset}")

    except Exception as e:
        logger.error(f"Error parsing query parameters: {e}")
        abort(400, description="Invalid query parameters.")

    # Call Firestore client function
    try:
        summaries = await firestore_client.get_all_generated_lists(
            filters=filters,
            sort_by=sort_by_firestore,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset
        )
        
        # Convert Pydantic models to dicts for JSON response
        response_data = [summary.model_dump(mode='json') for summary in summaries]
        
        # TODO: Add pagination metadata to response (total count, current page, etc.)
        # This would require an additional count query in firestore_client or returning count from get_all_generated_lists
        
        return jsonify(response_data)

    except Exception as e:
        logger.exception("Error fetching generated lists.")
        abort(500, description="Failed to retrieve generated lists.")

@app.route('/api/v1/generated-lists/filter-options', methods=['GET'])
async def get_list_filter_options() -> WerkzeugResponse: # Added return type hint
    """API endpoint to get distinct values for filter dropdowns."""
    logger.info("GET /api/v1/generated-lists/filter-options called.")
    try:
        # 1. Fetch all master categories
        all_categories = await firestore_client.get_master_categories()
        category_options = [
            {"value": cat.category_id, "label": cat.display_name.get('en', cat.category_id)}
            for cat in all_categories
        ]
        
        # 2. Fetch recent lists to derive other distinct values (simplified approach)
        # Fetching e.g., last 200 lists ordered by creation date
        # Note: This might not capture *all* possible values if the dataset is large
        # A more robust solution might involve aggregation or separate tracking.
        # Need async client for this part if using firestore_client directly
        # Using synchronous client 'db' for now, assuming firestore_client.db points to it
        # TODO: Refactor to use async client consistently
        if db is None: abort(500, description="Database client not initialized")
        recent_lists_query = db.collection(firestore_client.GENERATED_WORD_LISTS_COLLECTION)\
            .order_by("generation_parameters.generation_timestamp", direction=firestore.Query.DESCENDING)\
            .limit(200) # Limit the number of docs scanned

        languages = set()
        cefr_levels = set()
        statuses = set()
        
        # Use synchronous stream with sync client
        for doc in recent_lists_query.stream():
            data = doc.to_dict()
            if data and 'generation_parameters' in data:
                params = data['generation_parameters']
                if params.get('language'): languages.add(params['language'])
                if params.get('cefr_level'): cefr_levels.add(params['cefr_level'])
                if params.get('status'): statuses.add(params['status'])

        # Define standard workflow statuses (can be moved to config)
        defined_statuses = ["New", "Pending Review", "Approved for Enrichment", "Enrichment in Progress", "Ready for Test", "Live in Production", "Archived", "Rejected"]
        all_possible_statuses = sorted(list(statuses.union(defined_statuses)))


        # Prepare response
        filter_options = {
            "languages": sorted(list(languages)),
            "cefr_levels": sorted(list(cefr_levels), key=lambda x: (x[0], int(x[1]))), # Sort A1, A2, B1 etc.
            "statuses": all_possible_statuses,
            "categories": sorted(category_options, key=lambda x: x['label'])
        }
        
        return jsonify(filter_options)

    except Exception as e:
        logger.exception("Error fetching filter options.")
        abort(500, description="Failed to retrieve filter options.")

@app.route('/api/v1/generated-lists/<string:list_firestore_id>', methods=['GET'])
async def get_generated_list_detail(list_firestore_id: str) -> WerkzeugResponse: # Added type hint
    """API endpoint to get full details for a single generated list."""
    logger.info(f"GET /api/v1/generated-lists/{list_firestore_id} called.")
    
    try:
        # Fetch the specific list
        list_data = await firestore_client.get_generated_list_by_id(list_firestore_id)
        
        if not list_data:
            logger.warning(f"Generated list not found: {list_firestore_id}")
            abort(404, description=f"Generated list with ID '{list_firestore_id}' not found.")
            
        # Fetch categories to resolve display name (could be cached)
        all_categories = await firestore_client.get_master_categories()
        category_lookup = {cat.category_id: cat.display_name.get('en', cat.category_id) for cat in all_categories}
        
        category_id = list_data.generation_parameters.list_category_id
        category_display_name = category_lookup.get(category_id, category_id) # Fallback to ID
        
        # Convert to dict and add resolved name (optional, could be done by frontend)
        response_data = list_data.model_dump(mode='json')
        response_data['generation_parameters']['list_category_display_name'] = category_display_name
        
        logger.info(f"Returning details for generated list: {list_firestore_id}")
        
        # Create response object and add cache-control headers to prevent caching
        response = app.response_class(
            response=json.dumps(response_data), # Use json.dumps for raw string
            status=200,
            mimetype='application/json'
        )
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response # Return the Response object with headers
        
    except Exception as e:
        logger.exception(f"Error fetching generated list detail for ID {list_firestore_id}.")
        abort(500, description="Failed to retrieve generated list details.")

@app.route('/api/v1/generated-lists/<string:list_firestore_id>/metadata', methods=['PATCH'])
async def update_list_metadata(list_firestore_id: str) -> WerkzeugResponse: # Added type hint
    """API endpoint to update metadata for a specific generated list."""
    logger.info(f"PATCH /api/v1/generated-lists/{list_firestore_id}/metadata called.")
    if not request.is_json:
        logger.warning("Request is not JSON.")
        abort(400, description="Request must be JSON.")

    request_data = request.get_json()

    # Import the specific input model here or at top of file
    from models import UpdateListMetadataInput

    try:
        # Validate input payload - ensures at least one field is present
        update_input = UpdateListMetadataInput.model_validate(request_data)
        # Get only the fields that were actually provided in the request
        updates_to_apply = update_input.model_dump(exclude_unset=True) 
        
        if not updates_to_apply:
             # Should be caught by model validator, but double-check
             logger.warning("PATCH request received with no fields to update.")
             abort(400, description="No fields provided for update.")

        logger.info(f"Attempting metadata update for {list_firestore_id} with data: {updates_to_apply}")

    except ValidationError as e:
        logger.warning(f"Input validation failed for metadata update: {e}")
        abort(400, description=f"Invalid input data: {e}")

    # Call Firestore client function
    try:
        success = await firestore_client.update_generated_list_metadata(list_firestore_id, updates_to_apply)
        
        if success:
            logger.info(f"Successfully updated metadata for list: {list_firestore_id}")
            # Optionally fetch and return the updated document summary or full doc
            return jsonify({"message": "Metadata updated successfully."})
        else:
            # update_generated_list_metadata logs specific errors (e.g., not found)
            # Assume 404 if not found, 500 otherwise based on client logs
            # Re-fetch to check if it exists for a more specific error
            list_exists = await firestore_client.get_generated_list_by_id(list_firestore_id)
            if not list_exists:
                 abort(404, description=f"Generated list with ID '{list_firestore_id}' not found.")
            else:
                 abort(500, description="Failed to update metadata.")

    except Exception as e:
        logger.exception(f"Error updating metadata for list {list_firestore_id}.")
        abort(500, description="Failed to update list metadata.")

@app.route('/api/v1/generated-lists/<string:list_firestore_id>', methods=['DELETE'])
async def delete_list(list_firestore_id: str) -> Tuple[WerkzeugResponse, int]: # Added type hint
    """API endpoint to delete a specific generated list."""
    logger.info(f"DELETE /api/v1/generated-lists/{list_firestore_id} called.")
    
    try:
        success = await firestore_client.delete_generated_list(list_firestore_id)
        
        if success:
            logger.info(f"Successfully deleted list: {list_firestore_id}")
            return jsonify({"message": "Generated list deleted successfully."}), 200 # OK
        else:
            # delete_generated_list logs errors, assume 404 if it failed likely due to not found
            # Re-fetch to confirm non-existence for 404
            list_exists = await firestore_client.get_generated_list_by_id(list_firestore_id)
            if not list_exists:
                 abort(404, description=f"Generated list with ID '{list_firestore_id}' not found.")
            else:
                 # If it still exists, deletion failed for another reason
                 abort(500, description="Failed to delete generated list.")

    except Exception as e:
        logger.exception(f"Error deleting list {list_firestore_id}.")
        abort(500, description="Failed to delete generated list.")


# --- Main Execution ---
if __name__ == '__main__':
    # Use environment variable for port or default to 5003 (changed from 5002)
    port = int(os.environ.get('PORT', 5000))
    # Run in debug mode based on environment variable or default to False
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    logger.info(f"Starting Flask app on port {port} with debug mode: {debug_mode}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
'''
</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.

<environment_details>
# VSCode Visible Files
app.py

# VSCode Open Tabs
.cline/Admin Panel UI Best Practices (Updated).md
captures/Capture.PNG
../.codeoss-cloudworkstations/data/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
Language Pair Configuration Specification.md
static/language_pair_config_detail.js
.cline/rules.yaml
builds/build_checklist.md
builds/build_2_checklist.md
static/categories_manager.js
builds/build_3_checklist.md
builds/build_4_checklist.md
templates/manage_language_pairs.html
templates/language_pair_config_detail.html
templates/manage_categories.html
templates/index.html
venv/data/id/a2_headwords.json
venv/data/id/id_full_list.json
Specification_Word_Data_Structure_v1.5.md
test_model.py
venv/data/id/a1_headwords.json
Admin Panel for Vocabulary List Generation & Management.md.txt
builds/build_6_checklist.md
config.py
app.py
requirements.txt
gcp_utils.py
llm_prompts/.gitkeep
llm_client.py
firestore_client.py
models.py
templates/base_adminlte.html
templates/generate_new_word_list.html
static/generate_new_word_list.js
templates/view_generated_word_lists.html
static/view_generated_word_lists.js
templates/generated_list_details.html
static/generated_list_details.js
templates/edit_list_metadata.html
static/edit_list_metadata.js
venv/data/id/b1_headwords.json
venv/data/id/b2_headwords.json
static/style.css
builds/build_5_checklist.md
static/language_pair_manager.js
screen_ids_and_versions.md

# Current Time
5/8/2025, 6:13:30 AM (UTC, UTC+0:00)

# Context Window Usage
411,910 / 1,048.576K tokens used (39%)

# Current Mode
ACT MODE
</environment_details>
'''
