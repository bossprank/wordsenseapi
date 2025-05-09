# firestore_client.py v1.1 - Use model_dump(mode='json') for Firestore
# Handles interactions with the Google Cloud Firestore database using AsyncClient.
# Uses model_dump(mode='json') to ensure Firestore compatibility.

import sys
import asyncio
from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, ValidationError, HttpUrl # Import HttpUrl for type checking if needed
from pydantic_core import Url # Import the core Url type
from typing import Optional, List, Dict, Any
from uuid import UUID # Import UUID for type checking and conversion
import logging
from datetime import datetime # Import datetime

logger = logging.getLogger(__name__)

try:
    from config import GCLOUD_PROJECT, FIRESTORE_DATABASE_ID
except ImportError:
    print("Error: Could not import configuration from config.py.")
    sys.exit(1)

try:
    from models import (
        Word, WordBase, Sense, LinkChain, # Existing
        GeneratedWordList, GeneratedWordListSummary, VocabularyCategory # New models
    )
except ImportError:
    print("Error: Could not import Pydantic models from models.py.")
    sys.exit(1)

_db_client: Optional[AsyncClient] = None

async def get_db_client() -> AsyncClient:
    """Initializes and returns the Firestore AsyncClient instance."""
    # global _db_client # No longer using a long-lived global singleton for async contexts
    # if _db_client is None: # Always create a new one for async contexts managed by Flask's asyncio.run()

    # Create a new client instance for each call in an async context
    # This helps avoid "Event loop is closed" errors when Flask runs async views
    # with its default WSGI server, as each request might get its own event loop.
    if not GCLOUD_PROJECT:
            logger.critical("CRITICAL ERROR: GCLOUD_PROJECT not set. Cannot initialize Firestore client.")
            print("CRITICAL ERROR: GCLOUD_PROJECT not set. Cannot initialize Firestore client.")
            # Raising an exception might be better than sys.exit in a library module
            raise EnvironmentError("GCLOUD_PROJECT not set, cannot create Firestore client.")
    try:
        logger.info(f"Creating new Firestore AsyncClient instance for project '{GCLOUD_PROJECT}'"
              f"{f' and database {FIRESTORE_DATABASE_ID}' if FIRESTORE_DATABASE_ID else ''}...")
        local_db_client = AsyncClient(project=GCLOUD_PROJECT, database=FIRESTORE_DATABASE_ID or '(default)')
        logger.info("New Firestore AsyncClient instance created successfully.")
        return local_db_client
    except google_exceptions.PermissionDenied:
        logger.critical("CRITICAL ERROR: Permission denied connecting to Firestore."); logger.critical("Ensure ADC/Service Account have Firestore roles.")
        print("CRITICAL ERROR: Permission denied connecting to Firestore."); print("Ensure ADC/Service Account have Firestore roles.")
        raise # Re-raise to be handled by the caller
    except Exception as e:
        logger.critical(f"CRITICAL ERROR: Failed to initialize Firestore AsyncClient: {e}"); print(f"CRITICAL ERROR: Failed to initialize Firestore AsyncClient: {e}")
        raise # Re-raise

WORDS_COLLECTION = 'words'
GENERATED_WORD_LISTS_COLLECTION = 'GeneratedWordLists'
MASTER_CATEGORIES_COLLECTION = 'master_categories'


# --- Helper Function to Convert Complex Types (Primarily UUIDs for now) ---
# Note: model_dump(mode='json') should handle most types, but keeping this
# for UUIDs specifically might still be relevant depending on exact Pydantic/Firestore interaction.
# It won't hurt to leave it.
def _convert_complex_types_to_firestore(data: Any) -> Any:
    """Recursively converts specific complex types in nested dicts/lists to Firestore-compatible formats."""
    if isinstance(data, dict):
        return {k: _convert_complex_types_to_firestore(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_complex_types_to_firestore(item) for item in data]
    elif isinstance(data, UUID):
        return str(data)
    # Example: If Firestore didn't handle datetime automatically with mode='json'
    # elif isinstance(data, datetime):
    #    return data # Firestore client usually handles datetime objects directly
    # Pydantic Url types should be handled by mode='json' now.
    # elif isinstance(data, Url):
    #     return str(data)
    else:
        return data

# --- Test Function ---
# [Remains Unchanged]
async def test_firestore_connection():
    """Attempts a simple read operation to verify the connection."""
    try:
        db = await get_db_client(); logger.info("Testing Firestore connection...")
        doc_ref = db.collection(WORDS_COLLECTION).document('__test_connection__'); _ = await doc_ref.get()
        logger.info("Firestore connection test successful."); print("Firestore connection test successful.")
        return True
    except google_exceptions.PermissionDenied: logger.error("Firestore connection test failed: Permission Denied."); print("Firestore connection test failed: Permission Denied."); return False
    except Exception as e: logger.error(f"Firestore connection test failed: {e}"); print(f"Firestore connection test failed: {e}"); return False

# --- CRUD Operations (Now using AsyncClient) ---

async def get_word_by_id(word_id: str) -> Optional[Word]:
    """Fetches a single Word document from Firestore by its ID."""
    # [Remains Unchanged]
    try:
        db = await get_db_client(); logger.info(f"Attempting to fetch word with ID: {word_id}")
        doc_ref = db.collection(WORDS_COLLECTION).document(word_id); doc_snapshot = await doc_ref.get()
        if doc_snapshot.exists:
            logger.debug(f"Document found for ID: {word_id}")
            try:
                word_data = doc_snapshot.to_dict()
                if word_data is None: logger.warning(f"Document {word_id} exists but contains no data."); return None
                word_data['word_id'] = doc_snapshot.id # Add doc ID back
                word = Word.model_validate(word_data); logger.info(f"Data validation successful for word ID: {word_id}")
                return word
            except ValidationError as e: logger.error(f"Pydantic validation failed for Firestore data (ID: {word_id}): {e}"); return None
            except Exception as e: logger.error(f"Error processing document data (ID: {word_id}): {e}"); return None
        else: logger.info(f"No document found for word ID: {word_id}"); return None
    except google_exceptions.PermissionDenied: logger.error(f"Permission denied fetching word ID {word_id}."); return None
    except Exception as e: logger.exception(f"Error fetching word ID {word_id} from Firestore:"); return None

# *** MODIFIED Function v1.1 ***
async def save_word(word: Word) -> Optional[Word]:
    """Saves (creates or updates) a Word document in Firestore."""
    word_id_str = ""
    try:
        db = await get_db_client()
        word_id_str = str(word.word_id)
        logger.info(f"Attempting to save word with ID: {word_id_str}")

        # 1. *** Use model_dump(mode='json') to serialize complex types ***
        # This converts HttpUrl to str, datetime to str, UUID to str, etc.
        data_to_save_dict = word.model_dump(
            mode='json',
            exclude={'created_at', 'updated_at'}, # Exclude timestamps set by server
            exclude_none=True # Exclude fields that are None
        )
        logger.debug(f"Data after model_dump(mode='json'): {data_to_save_dict}")

        # 2. Optional: Recursively ensure UUIDs are strings if mode='json' didn't cover them (shouldn't be needed but safe)
        # data_to_save_firestore = _convert_complex_types_to_firestore(data_to_save_dict)
        # If using the helper above, uncomment the previous line and comment out the next line
        data_to_save_firestore = data_to_save_dict # Use the dict directly if relying solely on mode='json'

        # 3. Remove the top-level word_id (it's the doc key, not field data)
        if 'word_id' in data_to_save_firestore:
            del data_to_save_firestore['word_id']

        # 4. Prepare doc ref and check existence
        doc_ref = db.collection(WORDS_COLLECTION).document(word_id_str)
        doc_snapshot = await doc_ref.get()

        server_timestamp = SERVER_TIMESTAMP

        # 5. Set/Update data in Firestore
        if doc_snapshot.exists:
            logger.debug(f"Document {word_id_str} exists, updating...")
            data_to_save_firestore['updated_at'] = server_timestamp
            # Ensure created_at is not accidentally overwritten on update
            if 'created_at' in data_to_save_firestore: del data_to_save_firestore['created_at']
            await doc_ref.update(data_to_save_firestore)
            logger.info(f"Word document {word_id_str} updated successfully.")
        else:
            logger.debug(f"Document {word_id_str} does not exist, creating...")
            data_to_save_firestore['created_at'] = server_timestamp
            data_to_save_firestore['updated_at'] = server_timestamp
            await doc_ref.set(data_to_save_firestore)
            logger.info(f"Word document {word_id_str} created successfully.")

        # 6. Fetch back the saved data to confirm and return
        logger.debug(f"Fetching word {word_id_str} back after save...")
        saved_word_data = await get_word_by_id(word_id_str)
        return saved_word_data

    except ValidationError as e:
         logger.error(f"Pydantic validation error during save preparation (ID: {word_id_str}): {e}")
         return None
    except TypeError as te: # Catch the specific TypeError we saw
         logger.error(f"TypeError during Firestore save operation (ID: {word_id_str}): {te}")
         logger.error("This often means a data type wasn't converted correctly (e.g., Pydantic URL to string).")
         # Log the data that was attempted to be saved for debugging
         try:
             logger.error(f"Data attempted to save: {json.dumps(data_to_save_firestore, default=str)}")
         except Exception as dump_err:
             logger.error(f"Could not dump data causing TypeError: {dump_err}")
         return None
    except google_exceptions.PermissionDenied:
         logger.error(f"Permission denied saving word ID {word_id_str}.")
         return None
    except Exception as e:
        logger.exception(f"Error saving word document {word_id_str} to Firestore:")
        return None


async def search_words(query: str, language: str, limit: int = 50) -> List[Word]:
    """Searches for words based on headword prefix and language."""
    # [Remains Unchanged]
    words: List[Word] = []
    try:
        db = await get_db_client(); logger.info(f"Searching words: q='{query}', lang='{language}', limit={limit}")
        end_query = query + '\uf8ff'; query_ref = db.collection(WORDS_COLLECTION).where(filter=FieldFilter('language', '==', language)).where(filter=FieldFilter('headword', '>=', query)).where(filter=FieldFilter('headword', '<', end_query)).limit(limit)
        async for doc_snapshot in query_ref.stream():
            try:
                word_data = doc_snapshot.to_dict()
                if word_data is None: logger.warning(f"Skipping doc {doc_snapshot.id}: no data."); continue
                word_data['word_id'] = doc_snapshot.id; word = Word.model_validate(word_data)
                words.append(word); logger.debug(f"Validated word {doc_snapshot.id} from search.")
            except ValidationError as e: logger.warning(f"Skipping word {doc_snapshot.id} during search (validation error): {e}")
            except Exception as e: logger.error(f"Error processing doc {doc_snapshot.id} during search: {e}")
        logger.info(f"Found {len(words)} words matching search.")
        return words
    except google_exceptions.PermissionDenied: logger.error(f"Permission denied searching words (q='{query}', lang='{language}')."); return []
    except Exception as e: logger.exception(f"Error searching words (q='{query}', lang='{language}'):"); return []

# --- Example Usage ---
# [Remains Unchanged]
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    async def run_tests():
        print("\n--- Running Firestore Client Tests ---"); connected = await test_firestore_connection()
        if connected:
            print("\nAttempting search..."); search_results = await search_words(query="test", language="en", limit=5); print(f"Search returned {len(search_results)} words.")
        print("\n--- Firestore Client Tests Complete ---")
    try: asyncio.run(run_tests())
    except RuntimeError as e:
       if "cannot run nested event loops" in str(e): print("Warning: Could not run async main directly.")
       else: raise e

# --- CRUD Operations for GeneratedWordLists ---

async def save_generated_list(list_data: GeneratedWordList) -> Optional[GeneratedWordList]:
    """Saves a new GeneratedWordList document in Firestore.
    Assumes list_firestore_id is None for new documents and will be auto-generated.
    """
    try:
        db = await get_db_client()
        
        # Prepare data using model_dump, similar to save_word
        # Exclude list_firestore_id as it's the doc key, not field data
        # Timestamps are handled by SERVER_TIMESTAMP
        data_to_save = list_data.model_dump(
            mode='json',
            exclude={'list_firestore_id', 'generation_parameters.generation_timestamp', 'generation_parameters.last_status_update_timestamp'},
            exclude_none=True
        )

        # Set server timestamps
        data_to_save['generation_parameters']['generation_timestamp'] = SERVER_TIMESTAMP
        data_to_save['generation_parameters']['last_status_update_timestamp'] = SERVER_TIMESTAMP
        
        logger.info(f"Attempting to create new generated word list with readable_id: {list_data.generation_parameters.list_readable_id}")
        
        # Create a new document with an auto-generated ID
        doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document()
        await doc_ref.set(data_to_save)
        
        logger.info(f"New generated word list created successfully with Firestore ID: {doc_ref.id}")

        # Fetch back the saved data to confirm and return with the Firestore ID
        saved_doc_snapshot = await doc_ref.get()
        if saved_doc_snapshot.exists:
            saved_data_dict = saved_doc_snapshot.to_dict()
            if saved_data_dict: # Ensure to_dict() didn't return None
                # Add the auto-generated Firestore ID to the model instance
                saved_data_dict['list_firestore_id'] = doc_ref.id
                # Re-validate to get a complete GeneratedWordList object including timestamps
                # Need to handle nested timestamps correctly for validation if they are already datetime objects
                # Pydantic should handle this if Firestore returns them as datetime
                validated_saved_list = GeneratedWordList.model_validate(saved_data_dict)
                return validated_saved_list
            else:
                logger.error(f"Failed to retrieve data for new list {doc_ref.id} immediately after creation (to_dict was None).")
                return None
        else:
            logger.error(f"Failed to fetch new list {doc_ref.id} immediately after creation.")
            return None

    except ValidationError as e:
         logger.error(f"Pydantic validation error during save preparation for generated list: {e}")
         return None
    except TypeError as te:
         logger.error(f"TypeError during Firestore save operation for generated list: {te}")
         return None
    except google_exceptions.PermissionDenied:
         logger.error(f"Permission denied saving generated list.")
         return None
    except Exception as e:
        logger.exception(f"Error saving generated list document to Firestore:")
        return None

async def get_generated_list_by_id(list_firestore_id: str) -> Optional[GeneratedWordList]:
    """Fetches a single GeneratedWordList document from Firestore by its ID."""
    try:
        db = await get_db_client()
        logger.info(f"Attempting to fetch generated list with Firestore ID: {list_firestore_id}")
        doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document(list_firestore_id)
        doc_snapshot = await doc_ref.get()

        if doc_snapshot.exists:
            list_data_dict = doc_snapshot.to_dict()
            if list_data_dict:
                list_data_dict['list_firestore_id'] = doc_snapshot.id
                validated_list = GeneratedWordList.model_validate(list_data_dict)
                logger.info(f"Successfully fetched and validated generated list: {list_firestore_id}")
                return validated_list
            else:
                logger.warning(f"Document {list_firestore_id} exists but contains no data.")
                return None
        else:
            logger.info(f"No document found for generated list ID: {list_firestore_id}")
            return None
    except ValidationError as e:
        logger.error(f"Pydantic validation failed for Firestore data (ID: {list_firestore_id}): {e}")
        return None
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied fetching generated list ID {list_firestore_id}.")
        return None
    except Exception as e:
        logger.exception(f"Error fetching generated list ID {list_firestore_id} from Firestore:")
        return None

async def get_all_generated_lists(
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = "generation_parameters.generation_timestamp", # Default sort field path
    sort_direction: str = "DESCENDING", # Firestore direction constant
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[GeneratedWordListSummary]:
    """Fetches a paginated and filtered list of generated word list summaries."""
    summaries: List[GeneratedWordListSummary] = []
    try:
        db = await get_db_client()
        
        # 1. Fetch categories for display name lookup (assuming 'en' for now)
        all_categories = await get_master_categories()
        category_lookup = {cat.category_id: cat.display_name.get('en', cat.category_id) for cat in all_categories}
        logger.debug(f"Category lookup created with {len(category_lookup)} entries.")

        # 2. Build base query
        query = db.collection(GENERATED_WORD_LISTS_COLLECTION)

        # 3. Apply filters
        if filters:
            logger.info(f"Applying filters: {filters}")
            filter_map = {
                "language": "generation_parameters.language",
                "cefr_level": "generation_parameters.cefr_level",
                "status": "generation_parameters.status",
                "list_category_id": "generation_parameters.list_category_id"
            }
            for key, value in filters.items():
                if key in filter_map and value: # Ensure value is not empty/None
                    firestore_field = filter_map[key]
                    query = query.where(filter=FieldFilter(firestore_field, "==", value))
                    logger.debug(f"Applied filter: {firestore_field} == {value}")

        # 4. Apply sorting
        if sort_by:
            direction = sort_direction # Firestore uses string constants
            logger.debug(f"Applying sort: {sort_by} {direction}")
            query = query.order_by(sort_by, direction=direction)
        else:
             # Default sort if none provided, required for cursor/offset usage with inequality filters if any
             query = query.order_by("generation_parameters.generation_timestamp", direction="DESCENDING")


        # 5. Apply offset (Note: Firestore offset requires order_by)
        if offset is not None and offset > 0:
            logger.debug(f"Applying offset: {offset}")
            query = query.offset(offset)

        # 6. Apply limit
        if limit is not None and limit > 0:
            logger.debug(f"Applying limit: {limit}")
            query = query.limit(limit)

        # 7. Execute query and process results
        logger.info("Executing query to fetch generated list summaries...")
        stream = query.stream()
        async for doc_snapshot in stream:
            try:
                list_data = doc_snapshot.to_dict()
                if list_data and 'generation_parameters' in list_data:
                    params = list_data['generation_parameters']
                    category_id = params.get('list_category_id')
                    display_name = category_lookup.get(category_id, category_id or "N/A") # Fallback to ID or N/A

                    # Ensure timestamp is datetime object
                    gen_timestamp = params.get('generation_timestamp')
                    # Firestore SDK usually returns datetime, but handle potential string if needed
                    # if isinstance(gen_timestamp, str):
                    #     gen_timestamp = datetime.fromisoformat(gen_timestamp.replace("Z", "+00:00"))

                    if not isinstance(gen_timestamp, datetime):
                         logger.warning(f"Skipping doc {doc_snapshot.id}: Invalid generation_timestamp type ({type(gen_timestamp)}).")
                         continue


                    summary = GeneratedWordListSummary(
                        list_firestore_id=doc_snapshot.id,
                        list_readable_id=params.get('list_readable_id', 'N/A'),
                        language=params.get('language', 'N/A'),
                        cefr_level=params.get('cefr_level', 'N/A'),
                        list_category_display_name=display_name,
                        status=params.get('status', 'N/A'),
                        generated_word_count=params.get('generated_word_count'),
                        generation_timestamp=gen_timestamp
                    )
                    summaries.append(summary)
                else:
                    logger.warning(f"Skipping document {doc_snapshot.id}: Missing data or generation_parameters.")
            except ValidationError as e:
                logger.warning(f"Skipping document {doc_snapshot.id} due to validation error during summary creation: {e}")
            except Exception as e:
                logger.error(f"Error processing document {doc_snapshot.id} into summary: {e}")

        logger.info(f"Fetched {len(summaries)} generated list summaries.")
        return summaries

    except google_exceptions.PermissionDenied:
        logger.error("Permission denied fetching generated list summaries.")
        return []
    except Exception as e:
        logger.exception("Error fetching generated list summaries from Firestore:")
        return []


async def update_generated_list_metadata(list_firestore_id: str, metadata_updates: Dict[str, Any]) -> bool:
    """Updates specific metadata fields of an existing GeneratedWordList document."""
    try:
        db = await get_db_client()
        doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document(list_firestore_id)

        # Ensure the document exists before attempting to update
        doc_snapshot = await doc_ref.get()
        if not doc_snapshot.exists:
            logger.warning(f"GeneratedWordList with ID '{list_firestore_id}' not found for update.")
            return False

        # Prepare updates, ensuring to use dot notation for nested fields in generation_parameters
        updates_for_firestore = {}
        for key, value in metadata_updates.items():
            if key in ['status', 'list_category_id', 'admin_notes', 'reviewed_by']: # Fields directly in generation_parameters
                updates_for_firestore[f'generation_parameters.{key}'] = value
            # Add other direct top-level fields if any in future, though spec focuses on metadata in generation_parameters
        
        if not updates_for_firestore:
            logger.warning("No valid metadata fields provided for update.")
            return False

        updates_for_firestore['generation_parameters.last_status_update_timestamp'] = SERVER_TIMESTAMP
        
        logger.info(f"Attempting to update metadata for list ID: {list_firestore_id} with updates: {updates_for_firestore}")
        await doc_ref.update(updates_for_firestore)
        logger.info(f"Successfully updated metadata for list ID: {list_firestore_id}")
        return True

    except google_exceptions.NotFound: # Should be caught by pre-check, but defensive
        logger.warning(f"GeneratedWordList with ID '{list_firestore_id}' not found during update operation (NotFound exception).")
        return False
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied updating metadata for list ID {list_firestore_id}.")
        return False
    except Exception as e:
        logger.exception(f"Error updating metadata for list ID {list_firestore_id}:")
        return False

async def delete_generated_list(list_firestore_id: str) -> bool:
    """Deletes a GeneratedWordList document from Firestore."""
    try:
        db = await get_db_client()
        doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document(list_firestore_id)
        
        # Optionally, check if document exists before deleting, though delete is idempotent
        # doc_snapshot = await doc_ref.get()
        # if not doc_snapshot.exists:
        #     logger.warning(f"GeneratedWordList with ID '{list_firestore_id}' not found for deletion.")
        #     return False # Or True if idempotent behavior is desired

        logger.info(f"Attempting to delete generated list ID: {list_firestore_id}")
        await doc_ref.delete()
        logger.info(f"Successfully deleted generated list ID: {list_firestore_id}")
        return True
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied deleting list ID {list_firestore_id}.")
        return False
    except Exception as e:
        logger.exception(f"Error deleting list ID {list_firestore_id}:")
        return False

# --- CRUD Operations for MasterCategories ---

async def get_master_categories() -> List[VocabularyCategory]:
    """Fetches all documents from the master_categories collection."""
    categories: List[VocabularyCategory] = []
    try:
        db = await get_db_client()
        logger.info(f"Attempting to fetch all master categories from '{MASTER_CATEGORIES_COLLECTION}'")
        
        query_stream = db.collection(MASTER_CATEGORIES_COLLECTION).stream()
        async for doc_snapshot in query_stream:
            try:
                category_data = doc_snapshot.to_dict()
                if category_data:
                    category_data['category_id'] = doc_snapshot.id # Ensure ID is part of the model data
                    category = VocabularyCategory.model_validate(category_data)
                    categories.append(category)
                else:
                    logger.warning(f"Master category document {doc_snapshot.id} contains no data.")
            except ValidationError as e:
                logger.warning(f"Skipping master category {doc_snapshot.id} due to validation error: {e}")
            except Exception as e: # Catch any other error during individual doc processing
                logger.error(f"Error processing master category document {doc_snapshot.id}: {e}")
        
        logger.info(f"Fetched {len(categories)} master categories.")
        return categories
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied fetching master categories.")
        return [] # Return empty list on permission error
    except Exception as e:
        logger.exception("Error fetching master categories from Firestore:")
        return [] # Return empty list on other errors
