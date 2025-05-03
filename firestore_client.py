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

logger = logging.getLogger(__name__)

try:
    from config import GCLOUD_PROJECT, FIRESTORE_DATABASE_ID
except ImportError:
    print("Error: Could not import configuration from config.py.")
    sys.exit(1)

try:
    from models import Word, WordBase, Sense, LinkChain
except ImportError:
    print("Error: Could not import Pydantic models from models.py.")
    sys.exit(1)

_db_client: Optional[AsyncClient] = None

async def get_db_client() -> AsyncClient:
    """Initializes and returns the Firestore AsyncClient instance."""
    global _db_client
    if _db_client is None:
        if not GCLOUD_PROJECT:
             logger.critical("CRITICAL ERROR: GCLOUD_PROJECT not set. Cannot initialize Firestore client.")
             print("CRITICAL ERROR: GCLOUD_PROJECT not set. Cannot initialize Firestore client.")
             sys.exit(1)
        try:
            logger.info(f"Initializing Firestore AsyncClient for project '{GCLOUD_PROJECT}'"
                  f"{f' and database {FIRESTORE_DATABASE_ID}' if FIRESTORE_DATABASE_ID else ''}...")
            _db_client = AsyncClient(project=GCLOUD_PROJECT, database=FIRESTORE_DATABASE_ID or '(default)')
            logger.info("Firestore AsyncClient initialized successfully.")
        except google_exceptions.PermissionDenied:
            logger.critical("CRITICAL ERROR: Permission denied connecting to Firestore."); logger.critical("Ensure ADC/Service Account have Firestore roles.")
            print("CRITICAL ERROR: Permission denied connecting to Firestore."); print("Ensure ADC/Service Account have Firestore roles.")
            sys.exit(1)
        except Exception as e:
            logger.critical(f"CRITICAL ERROR: Failed to initialize Firestore AsyncClient: {e}"); print(f"CRITICAL ERROR: Failed to initialize Firestore AsyncClient: {e}")
            sys.exit(1)
    assert _db_client is not None
    return _db_client

WORDS_COLLECTION = 'words'

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