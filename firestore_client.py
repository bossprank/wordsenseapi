# firestore_client.py
# Handles interactions with the Google Cloud Firestore database using AsyncClient.

import sys
import asyncio
from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, ValidationError
from typing import Optional, List, Dict, Any
from uuid import UUID # Import UUID for type checking and conversion

# Import configuration variables
try:
    from config import GCLOUD_PROJECT, FIRESTORE_DATABASE_ID
except ImportError:
    print("Error: Could not import configuration from config.py.")
    sys.exit(1)

# Import Pydantic models
try:
    # Assuming models.py is in the same directory
    from models import Word, WordBase, Sense, LinkChain
except ImportError:
    print("Error: Could not import Pydantic models from models.py.")
    sys.exit(1)

# Global variable for the client instance (initialized lazily)
_db_client: Optional[AsyncClient] = None

async def get_db_client() -> AsyncClient:
    """Initializes and returns the Firestore AsyncClient instance."""
    global _db_client
    if _db_client is None:
        if not GCLOUD_PROJECT:
             print("CRITICAL ERROR: GCLOUD_PROJECT is not set. Cannot initialize Firestore client.")
             sys.exit(1)
        try:
            print(f"Initializing Firestore AsyncClient for project '{GCLOUD_PROJECT}'"
                  f"{f' and database {FIRESTORE_DATABASE_ID}' if FIRESTORE_DATABASE_ID else ''}...")
            _db_client = AsyncClient(project=GCLOUD_PROJECT, database=FIRESTORE_DATABASE_ID or '(default)')
            print("Firestore AsyncClient initialized successfully.")
        except google_exceptions.PermissionDenied:
            print("CRITICAL ERROR: Permission denied connecting to Firestore.")
            print("Ensure the Application Default Credentials (ADC) or Service Account have the necessary Firestore roles.")
            sys.exit(1)
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to initialize Firestore AsyncClient: {e}")
            sys.exit(1)
    assert _db_client is not None
    return _db_client

# Define the main collection reference
WORDS_COLLECTION = 'words'

# --- Helper Function to Convert UUIDs in Dict ---
def _convert_uuids_to_str(data: Any) -> Any:
    """Recursively converts UUID objects in nested dicts/lists to strings."""
    if isinstance(data, dict):
        # Process dictionary items recursively
        return {k: _convert_uuids_to_str(v) for k, v in data.items()}
    elif isinstance(data, list):
        # Process list items recursively
        return [_convert_uuids_to_str(item) for item in data]
    elif isinstance(data, UUID):
        # Convert UUID to string
        return str(data)
    # Handle other types that might need conversion (like datetime, though Firestore handles it)
    # elif isinstance(data, datetime):
    #     return data.isoformat() # Example if needed
    else:
        # Return other types as is
        return data

# --- Test Function ---
async def test_firestore_connection():
    """Attempts a simple read operation to verify the connection."""
    try:
        db = await get_db_client()
        print("Testing Firestore connection by trying to get a dummy document...")
        doc_ref = db.collection(WORDS_COLLECTION).document('__test_connection__')
        _ = await doc_ref.get()
        print("Firestore connection test successful (API call completed).")
        return True
    except google_exceptions.PermissionDenied:
        print("Firestore connection test failed: Permission Denied.")
        return False
    except Exception as e:
        print(f"Firestore connection test failed: {e}")
        return False

# --- CRUD Operations (Now using AsyncClient) ---

async def get_word_by_id(word_id: str) -> Optional[Word]:
    """Fetches a single Word document from Firestore by its ID."""
    try:
        db = await get_db_client()
        print(f"Attempting to fetch word with ID: {word_id}")
        doc_ref = db.collection(WORDS_COLLECTION).document(word_id)
        doc_snapshot = await doc_ref.get()

        if doc_snapshot.exists:
            print(f"Document found for ID: {word_id}")
            try:
                word_data = doc_snapshot.to_dict()
                if word_data is None:
                     print(f"Warning: Document {word_id} exists but contains no data.")
                     return None
                word_data['word_id'] = doc_snapshot.id # Add doc ID back
                # Pydantic v2 automatically handles string -> UUID conversion if type hint is UUID
                word = Word.model_validate(word_data)
                print(f"Data validation successful for word ID: {word_id}")
                return word
            except ValidationError as e:
                print(f"Pydantic validation failed for Firestore data (ID: {word_id}): {e}")
                return None
            except Exception as e:
                 print(f"Error processing document data (ID: {word_id}): {e}")
                 return None
        else:
            print(f"No document found for word ID: {word_id}")
            return None
    except google_exceptions.PermissionDenied:
         print(f"Permission denied fetching word ID {word_id}.")
         return None
    except Exception as e:
        print(f"Error fetching word ID {word_id} from Firestore: {e}")
        return None

async def save_word(word: Word) -> Optional[Word]:
    """Saves (creates or updates) a Word document in Firestore."""
    try:
        db = await get_db_client()
        word_id_str = str(word.word_id) # Use string for Firestore doc ID
        print(f"Attempting to save word with ID: {word_id_str}")

        # 1. Dump the Pydantic model to a dictionary
        # Exclude timestamps as they will be set by the server
        data_to_save_raw = word.model_dump(exclude={'created_at', 'updated_at'}, exclude_none=True)

        # 2. ***Crucially, convert ALL UUIDs (top-level and nested) to strings***
        data_to_save_firestore = _convert_uuids_to_str(data_to_save_raw)

        # 3. Remove the top-level word_id as it's the document key, not data
        if 'word_id' in data_to_save_firestore:
            del data_to_save_firestore['word_id']

        # 4. Prepare document reference and check existence
        doc_ref = db.collection(WORDS_COLLECTION).document(word_id_str)
        doc_snapshot = await doc_ref.get()

        server_timestamp = SERVER_TIMESTAMP

        # 5. Set/Update data in Firestore
        if doc_snapshot.exists:
            data_to_save_firestore['updated_at'] = server_timestamp
            # Ensure created_at is not accidentally overwritten on update
            if 'created_at' in data_to_save_firestore:
                del data_to_save_firestore['created_at']
            await doc_ref.update(data_to_save_firestore)
            print(f"Word document {word_id_str} updated successfully.")
        else:
            data_to_save_firestore['created_at'] = server_timestamp
            data_to_save_firestore['updated_at'] = server_timestamp
            await doc_ref.set(data_to_save_firestore)
            print(f"Word document {word_id_str} created successfully.")

        # 6. Fetch back the saved data to confirm and return
        saved_word_data = await get_word_by_id(word_id_str)
        return saved_word_data

    except ValidationError as e:
         print(f"Pydantic validation error preparing data for save (ID: {word_id_str}): {e}")
         return None
    except google_exceptions.PermissionDenied:
         print(f"Permission denied saving word ID {word_id_str}.")
         return None
    except Exception as e:
        print(f"Error saving word document {word_id_str} to Firestore: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging save errors
        return None

async def search_words(query: str, language: str, limit: int = 50) -> List[Word]:
    """Searches for words based on headword prefix and language."""
    words: List[Word] = []
    try:
        db = await get_db_client()
        print(f"Searching for words with query='{query}', language='{language}', limit={limit}")
        end_query = query + '\uf8ff'
        query_ref = db.collection(WORDS_COLLECTION).where(
            filter=FieldFilter('language', '==', language)
        ).where(
            filter=FieldFilter('headword', '>=', query)
        ).where(
            filter=FieldFilter('headword', '<', end_query)
        ).limit(limit)

        async for doc_snapshot in query_ref.stream():
            try:
                word_data = doc_snapshot.to_dict()
                if word_data is None: continue
                word_data['word_id'] = doc_snapshot.id
                word = Word.model_validate(word_data)
                words.append(word)
            except ValidationError as e:
                print(f"Skipping word document {doc_snapshot.id} due to validation error: {e}")
            except Exception as e:
                 print(f"Error processing document data {doc_snapshot.id} during search: {e}")

        print(f"Found {len(words)} words matching search.")
        return words
    except google_exceptions.PermissionDenied:
         print(f"Permission denied searching words (query='{query}', lang='{language}').")
         return []
    except Exception as e:
        print(f"Error searching words in Firestore (query='{query}', lang='{language}'): {e}")
        return []

# --- Example Usage ---
if __name__ == '__main__':
    async def run_tests():
        print("\n--- Running Firestore Client Tests ---")
        connected = await test_firestore_connection()
        if connected:
            print("\nAttempting to search words starting with 'test' in 'en'")
            search_results = await search_words(query="test", language="en", limit=5)
            print(f"Search returned {len(search_results)} words.")
        print("\n--- Firestore Client Tests Complete ---")

    try:
       asyncio.run(run_tests())
    except RuntimeError as e:
       if "cannot run nested event loops" in str(e):
           print("Warning: Could not run async main directly (likely due to existing event loop).")
       else:
           raise e
