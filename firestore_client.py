# firestore_client.py v1.1 - Use model_dump(mode='json') for Firestore
# Handles interactions with the Google Cloud Firestore database using AsyncClient.
# Uses model_dump(mode='json') to ensure Firestore compatibility.

import sys
import asyncio
from google.cloud import firestore # Import firestore
from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, ValidationError, HttpUrl # Import HttpUrl for type checking if needed
from pydantic_core import Url # Import the core Url type
from typing import Optional, List, Dict, Any
from uuid import UUID # Import UUID for type checking and conversion
from loguru import logger # Use Loguru logger
from datetime import datetime # Import datetime

# logger = logging.getLogger(__name__) # No longer needed

try:
    from config import GCLOUD_PROJECT, FIRESTORE_DATABASE_ID
except ImportError:
    print("Error: Could not import configuration from config.py.")
    sys.exit(1)

try:
    from models import (
        Word, WordBase, Sense, LinkChain, # Existing
        GeneratedWordList, GeneratedWordListSummary, VocabularyCategory, LanguagePairConfiguration # New models
    )
except ImportError:
    print("Error: Could not import Pydantic models from models.py.")
    sys.exit(1)

# --- Firestore Client Management ---
# The get_db_client() function is removed.
# AsyncClient instances will be passed into functions that need them.

WORDS_COLLECTION = 'words'
GENERATED_WORD_LISTS_COLLECTION = 'GeneratedWordLists'
MASTER_CATEGORIES_COLLECTION = 'master_categories'


# --- Helper Function to Convert Complex Types (Primarily UUIDs for now) ---
def _convert_complex_types_to_firestore(data: Any) -> Any:
    """Recursively converts specific complex types in nested dicts/lists to Firestore-compatible formats."""
    if isinstance(data, dict):
        return {k: _convert_complex_types_to_firestore(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_complex_types_to_firestore(item) for item in data]
    elif isinstance(data, UUID):
        return str(data)
    else:
        return data

# --- Test Function ---
async def test_firestore_connection(db: AsyncClient): # db instance is now passed
    """Attempts a simple read operation to verify the connection."""
    try:
        logger.info("Testing Firestore connection...")
        doc_ref = db.collection(WORDS_COLLECTION).document('__test_connection__'); _ = await doc_ref.get()
        logger.info("Firestore connection test successful."); print("Firestore connection test successful.")
        return True
    except google_exceptions.PermissionDenied: logger.error("Firestore connection test failed: Permission Denied."); print("Firestore connection test failed: Permission Denied."); return False
    except Exception as e: logger.error(f"Firestore connection test failed: {e}"); print(f"Firestore connection test failed: {e}"); return False

# --- CRUD Operations (Now using AsyncClient) ---

async def get_word_by_id(db: AsyncClient, word_id: str) -> Optional[Word]: # db instance is now passed
    """Fetches a single Word document from Firestore by its ID."""
    try:
        logger.info(f"Attempting to fetch word with ID: {word_id}")
        doc_ref = db.collection(WORDS_COLLECTION).document(word_id); doc_snapshot = await doc_ref.get()
        if doc_snapshot.exists:
            # logger.debug(f"Document found for ID: {word_id}")
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

async def save_word(db: AsyncClient, word: Word) -> Optional[Word]: # Added db param
    """Saves (creates or updates) a Word document in Firestore."""
    word_id_str = ""
    try:
        # db instance is now passed
        word_id_str = str(word.word_id)
        logger.info(f"Attempting to save word with ID: {word_id_str}")
        data_to_save_dict = word.model_dump(
            mode='json',
            exclude={'created_at', 'updated_at'},
            exclude_none=True
        )
        data_to_save_firestore = data_to_save_dict
        if 'word_id' in data_to_save_firestore:
            del data_to_save_firestore['word_id']
        doc_ref = db.collection(WORDS_COLLECTION).document(word_id_str)
        doc_snapshot = await doc_ref.get()
        server_timestamp = SERVER_TIMESTAMP
        if doc_snapshot.exists:
            # logger.debug(f"Document {word_id_str} exists, updating...")
            data_to_save_firestore['updated_at'] = server_timestamp
            if 'created_at' in data_to_save_firestore: del data_to_save_firestore['created_at'] # Should not happen if exclude is working
            await doc_ref.update(data_to_save_firestore)
            logger.info(f"Word document {word_id_str} updated successfully.")
        else:
            # logger.debug(f"Document {word_id_str} does not exist, creating...")
            data_to_save_firestore['created_at'] = server_timestamp
            data_to_save_firestore['updated_at'] = server_timestamp
            await doc_ref.set(data_to_save_firestore)
            logger.info(f"Word document {word_id_str} created successfully.")
        # logger.debug(f"Fetching word {word_id_str} back after save...") # Can be verbose, implies another DB call
        saved_word_data = await get_word_by_id(db, word_id_str) # Pass db, This re-fetches, consider if necessary or return constructed
        return saved_word_data
    except ValidationError as e:
         logger.error(f"Pydantic validation error during save preparation (ID: {word_id_str}): {e}")
         return None
    except TypeError as te:
         logger.error(f"TypeError during Firestore save operation (ID: {word_id_str}): {te}")
         logger.error("This often means a data type wasn't converted correctly (e.g., Pydantic URL to string).")
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

async def search_words(db: AsyncClient, query: str, language: str, limit: int = 50) -> List[Word]:
    """Searches for words based on headword prefix and language."""
    words: List[Word] = []
    try:
        # db instance is now passed
        logger.info(f"Searching words: q='{query}', lang='{language}', limit={limit}")
        end_query = query + '\uf8ff'; query_ref = db.collection(WORDS_COLLECTION).where(filter=FieldFilter('language', '==', language)).where(filter=FieldFilter('headword', '>=', query)).where(filter=FieldFilter('headword', '<', end_query)).limit(limit)
        async for doc_snapshot in query_ref.stream():
            try:
                word_data = doc_snapshot.to_dict()
                if word_data is None: logger.warning(f"Skipping doc {doc_snapshot.id} in search results: no data."); continue
                word_data['word_id'] = doc_snapshot.id; word = Word.model_validate(word_data)
                words.append(word) # logger.debug(f"Validated word {doc_snapshot.id} from search.") # Verbose per item
            except ValidationError as e: logger.warning(f"Skipping word {doc_snapshot.id} during search (validation error): {e}")
            except Exception as e: logger.error(f"Error processing doc {doc_snapshot.id} during search: {e}")
        logger.info(f"Found {len(words)} words matching search.")
        return words
    except google_exceptions.PermissionDenied: logger.error(f"Permission denied searching words (q='{query}', lang='{language}')."); return []
    except Exception as e: logger.exception(f"Error searching words (q='{query}', lang='{language}'):"); return []

# --- Example Usage ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    async def run_tests():
        # This test will require a db client instance to be created and passed
        # For standalone testing, one might do:
        # test_db_client = AsyncClient(project=GCLOUD_PROJECT, database=FIRESTORE_DATABASE_ID or '(default)')
        # print("\n--- Running Firestore Client Tests ---"); connected = await test_firestore_connection(test_db_client)
        # if connected:
        #     print("\nAttempting search..."); search_results = await search_words(test_db_client, query="test", language="en", limit=5); print(f"Search returned {len(search_results)} words.")
        # if hasattr(test_db_client, 'close'): await test_db_client.close()
        print("Standalone tests need refactoring to create and pass an AsyncClient instance.")
        print("\n--- Firestore Client Tests Complete ---")
    try: asyncio.run(run_tests())
    except RuntimeError as e:
       if "cannot run nested event loops" in str(e): print("Warning: Could not run async main directly.")
       else: raise e

# --- CRUD Operations for GeneratedWordLists ---

async def save_generated_list(db: AsyncClient, list_data: GeneratedWordList) -> Optional[GeneratedWordList]: # Added db param
    """Saves (creates or updates) a GeneratedWordList document in Firestore.
    If list_data.list_firestore_id is None, a new document is created.
    Otherwise, the existing document with that ID is overwritten/updated.
    """
    try:
        # db instance is now passed
        
        doc_id = list_data.list_firestore_id
        is_new_document = not doc_id

        data_to_save = list_data.model_dump(
            mode='json',
            exclude={'list_firestore_id'}, # list_firestore_id is path, not field
            exclude_none=True
        )
        
        # Ensure timestamps are handled correctly for new vs. update
        if is_new_document:
            data_to_save['generation_parameters']['generation_timestamp'] = SERVER_TIMESTAMP
            data_to_save['generation_parameters']['last_status_update_timestamp'] = SERVER_TIMESTAMP
            logger.info(f"Attempting to create new generated word list with readable_id: {list_data.generation_parameters.list_readable_id}")
            doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document() # New ID
        else:
            # For updates, we only update last_status_update_timestamp.
            # generation_timestamp should remain from the original creation.
            # We also need to ensure we don't overwrite existing generation_timestamp if it's not in data_to_save.
            # model_dump by default includes all fields, so generation_timestamp from the loaded current_list will be there.
            data_to_save['generation_parameters']['last_status_update_timestamp'] = SERVER_TIMESTAMP
            if 'generation_timestamp' not in data_to_save['generation_parameters'] and current_list: # Should not happen if current_list is loaded
                 data_to_save['generation_parameters']['generation_timestamp'] = current_list.generation_parameters.generation_timestamp

            logger.info(f"Attempting to update generated word list with Firestore ID: {doc_id}")
            doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document(doc_id)

        await doc_ref.set(data_to_save, merge=not is_new_document) # Use merge=True for updates to not overwrite everything if only partial data is sent
                                                              # However, we are sending the full list_data model, so merge=False (overwrite) for new,
                                                              # and set (which overwrites) for existing is fine.
                                                              # Using .set with merge=True for updates is safer if we ever send partial updates.
                                                              # For now, assuming full object overwrite on update.
        
        logger.info(f"Generated word list '{doc_ref.id}' (readable: {list_data.generation_parameters.list_readable_id}) saved successfully.")
        
        # Fetch the document back to ensure it's correctly saved and to get server-generated timestamps
        saved_doc_snapshot = await doc_ref.get()
        if saved_doc_snapshot.exists:
            saved_data_dict = saved_doc_snapshot.to_dict()
            if saved_data_dict:
                saved_data_dict['list_firestore_id'] = doc_ref.id # Ensure ID is part of the model data
                validated_saved_list = GeneratedWordList.model_validate(saved_data_dict)
                return validated_saved_list
        
        logger.error(f"Failed to retrieve or validate list {doc_ref.id} immediately after saving.")
        return None

    except ValidationError as e:
         logger.error(f"Pydantic validation error during save preparation for generated list ({list_data.generation_parameters.list_readable_id if list_data and list_data.generation_parameters else 'Unknown'}): {e}")
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

async def get_generated_list_by_id(db: AsyncClient, list_firestore_id: str) -> Optional[GeneratedWordList]: # Added db param
    """Fetches a single GeneratedWordList document from Firestore by its ID."""
    try:
        # db instance is now passed
        logger.info(f"Attempting to fetch generated list with Firestore ID: {list_firestore_id}")
        doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document(list_firestore_id) # db already used
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

async def get_all_generated_lists( # Added db param
    db: AsyncClient,
    filters: Optional[Dict[str, Any]] = None,
    sort_by: Optional[str] = "generation_parameters.generation_timestamp",
    sort_direction: str = "DESCENDING",
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[GeneratedWordListSummary]:
    """Fetches a paginated and filtered list of generated word list summaries."""
    summaries: List[GeneratedWordListSummary] = []
    try:
        # db instance is now passed
        all_categories = await get_master_categories(db) # Pass db to nested call
        category_lookup = {cat.category_id: cat.display_name.get('en', cat.category_id) for cat in all_categories}
        # logger.debug(f"Category lookup created with {len(category_lookup)} entries.")
        query = db.collection(GENERATED_WORD_LISTS_COLLECTION)
        if filters:
            logger.info(f"Applying filters to generated lists: {filters}")
            filter_map = {
                "language": "generation_parameters.language",
                "cefr_level": "generation_parameters.cefr_level",
                "status": "generation_parameters.status",
                "list_category_id": "generation_parameters.list_category_id"
            }
            for key, value in filters.items():
                if key in filter_map and value:
                    firestore_field = filter_map[key]
                    query = query.where(filter=FieldFilter(firestore_field, "==", value))
                    # logger.debug(f"Applied filter: {firestore_field} == {value}")
        if sort_by:
            direction = sort_direction
            # logger.debug(f"Applying sort: {sort_by} {direction}")
            query = query.order_by(sort_by, direction=direction)
        else: # Default sort
             query = query.order_by("generation_parameters.generation_timestamp", direction="DESCENDING")
        if offset is not None and offset > 0:
            # logger.debug(f"Applying offset: {offset}")
            query = query.offset(offset)
        if limit is not None and limit > 0:
            # logger.debug(f"Applying limit: {limit}")
            query = query.limit(limit)
        # logger.info("Executing query to fetch generated list summaries...") # Covered by the Fetched X summaries log
        stream = query.stream()
        async for doc_snapshot in stream:
            try:
                list_data = doc_snapshot.to_dict()
                if list_data and 'generation_parameters' in list_data:
                    params = list_data['generation_parameters']
                    category_id = params.get('list_category_id')
                    display_name = category_lookup.get(category_id, category_id or "N/A")
                    gen_timestamp = params.get('generation_timestamp')
                    # Pydantic will attempt to parse gen_timestamp to datetime for GeneratedWordListSummary
                    # If it fails, the ValidationError below will catch it for this specific summary.
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

async def update_generated_list_metadata(db: AsyncClient, list_firestore_id: str, metadata_updates: Dict[str, Any]) -> bool: # Added db param
    """Updates specific metadata fields of an existing GeneratedWordList document."""
    try:
        # db instance is now passed
        doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document(list_firestore_id) # db already used
        doc_snapshot = await doc_ref.get()
        if not doc_snapshot.exists:
            logger.warning(f"GeneratedWordList with ID '{list_firestore_id}' not found for update.")
            return False
        updates_for_firestore = {}
        for key, value in metadata_updates.items():
            if key in ['status', 'list_category_id', 'admin_notes', 'reviewed_by']:
                updates_for_firestore[f'generation_parameters.{key}'] = value
        if not updates_for_firestore:
            logger.warning("No valid metadata fields provided for update.")
            return False
        updates_for_firestore['generation_parameters.last_status_update_timestamp'] = SERVER_TIMESTAMP
        logger.info(f"Attempting to update metadata for list ID: {list_firestore_id} with updates: {updates_for_firestore}")
        await doc_ref.update(updates_for_firestore)
        logger.info(f"Successfully updated metadata for list ID: {list_firestore_id}")
        return True
    except google_exceptions.NotFound:
        logger.warning(f"[update_generated_list_metadata] GeneratedWordList with ID '{list_firestore_id}' not found during update operation (NotFound exception).")
        return False
    except google_exceptions.PermissionDenied:
        logger.error(f"[update_generated_list_metadata] Permission denied updating metadata for list ID {list_firestore_id}.")
        return False
    except Exception as e:
        logger.exception(f"[update_generated_list_metadata] Unexpected error updating metadata for list ID {list_firestore_id}:")
        return False

async def delete_generated_list(db: AsyncClient, list_firestore_id: str) -> bool: # Added db param
    """Deletes a GeneratedWordList document from Firestore."""
    try:
        # db instance is now passed
        doc_ref = db.collection(GENERATED_WORD_LISTS_COLLECTION).document(list_firestore_id) # db already used
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

async def get_master_categories(db: AsyncClient) -> List[VocabularyCategory]:
    """Fetches all documents from the master_categories collection."""
    categories: List[VocabularyCategory] = []
    try:
        # db instance is now passed
        logger.info(f"Attempting to fetch all master categories from '{MASTER_CATEGORIES_COLLECTION}' using provided db client.")
        query_stream = db.collection(MASTER_CATEGORIES_COLLECTION).stream() # db already used
        async for doc_snapshot in query_stream:
            try:
                category_data = doc_snapshot.to_dict()
                if category_data:
                    category_data['category_id'] = doc_snapshot.id
                    category = VocabularyCategory.model_validate(category_data)
                    categories.append(category)
                else:
                    logger.warning(f"Master category document {doc_snapshot.id} contains no data.")
            except ValidationError as e:
                logger.warning(f"Skipping master category {doc_snapshot.id} due to validation error: {e}")
            except Exception as e:
                logger.error(f"Error processing master category document {doc_snapshot.id}: {e}")
        logger.info(f"Fetched {len(categories)} master categories.")
        return categories
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied fetching master categories.")
        return []
    except Exception as e:
        logger.exception("Error fetching master categories from Firestore:")
        return []

async def add_master_category(db: AsyncClient, category_data: VocabularyCategory) -> Optional[VocabularyCategory]:
    """Saves a new VocabularyCategory document in Firestore.
    The category_id from the input model is used as the document ID.
    """
    try:
        # db instance is now passed
        category_id = category_data.category_id
        logger.info(f"Attempting to add master category with ID: {category_id}")
        data_to_save = category_data.model_dump(
            mode='json',
            exclude={'category_id', 'created_at', 'updated_at'},
            exclude_none=True
        )
        data_to_save['created_at'] = SERVER_TIMESTAMP
        data_to_save['updated_at'] = SERVER_TIMESTAMP
        doc_ref = db.collection(MASTER_CATEGORIES_COLLECTION).document(category_id)
        await doc_ref.set(data_to_save)
        logger.info(f"Master category '{category_id}' saved successfully.")
        saved_doc_snapshot = await doc_ref.get()
        if saved_doc_snapshot.exists:
            saved_data_dict = saved_doc_snapshot.to_dict()
            if saved_data_dict:
                saved_data_dict['category_id'] = doc_ref.id
                validated_saved_category = VocabularyCategory.model_validate(saved_data_dict)
                return validated_saved_category
            else:
                logger.error(f"Failed to retrieve data for category {doc_ref.id} immediately after saving (to_dict was None).")
                return None
        else:
            logger.error(f"Failed to fetch category {doc_ref.id} immediately after saving.")
            return None
    except ValidationError as e:
         logger.error(f"Pydantic validation error during save preparation for category '{category_data.category_id if category_data else 'UNKNOWN'}': {e}")
         return None
    except TypeError as te:
         logger.error(f"TypeError during Firestore save operation for category '{category_data.category_id if category_data else 'UNKNOWN'}': {te}")
         return None
    except google_exceptions.PermissionDenied:
         logger.error(f"Permission denied saving category '{category_data.category_id if category_data else 'UNKNOWN'}'.")
         return None
    except Exception as e:
        logger.exception(f"Error saving category document '{category_data.category_id if category_data else 'UNKNOWN'}' to Firestore:")
        return None

async def update_master_category(db: AsyncClient, category_id: str, updates: Dict[str, Any]) -> Optional[VocabularyCategory]:
    """Updates an existing VocabularyCategory document in Firestore.
    Only fields present in the 'updates' dict will be modified.
    """
    try:
        # db instance is now passed
        doc_ref = db.collection(MASTER_CATEGORIES_COLLECTION).document(category_id)
        doc_snapshot = await doc_ref.get()
        if not doc_snapshot.exists:
            logger.warning(f"Master category with ID '{category_id}' not found for update.")
            return None
        updates_for_firestore = {}
        for key, value in updates.items():
            if isinstance(value, BaseModel):
                updates_for_firestore[key] = value.model_dump(mode='json', exclude_none=True)
            else:
                updates_for_firestore[key] = value
        if not updates_for_firestore:
            logger.warning(f"No valid update fields provided for category '{category_id}'.")
            return None
        updates_for_firestore['updated_at'] = SERVER_TIMESTAMP
        logger.info(f"Attempting to update master category ID: {category_id} with updates: {updates_for_firestore}")
        await doc_ref.update(updates_for_firestore)
        logger.info(f"Successfully updated master category ID: {category_id}")
        updated_doc_snapshot = await doc_ref.get()
        if updated_doc_snapshot.exists:
            updated_data_dict = updated_doc_snapshot.to_dict()
            if updated_data_dict:
                updated_data_dict['category_id'] = updated_doc_snapshot.id
                validated_category = VocabularyCategory.model_validate(updated_data_dict)
                return validated_category
        logger.error(f"Failed to fetch category {category_id} after update.")
        return None
    except google_exceptions.NotFound:
        logger.warning(f"Master category with ID '{category_id}' not found during update operation (NotFound exception).")
        return None
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied updating master category ID {category_id}.")
        return None
    except ValidationError as e:
        logger.error(f"Pydantic validation error during update for category '{category_id}': {e}")
        return None
    except Exception as e:
        logger.exception(f"Error updating master category ID {category_id}:")
        return None

async def delete_master_category(db: AsyncClient, category_id: str) -> bool:
    """Deletes a VocabularyCategory document from Firestore by its ID."""
    try:
        # db instance is now passed
        doc_ref = db.collection(MASTER_CATEGORIES_COLLECTION).document(category_id)
        logger.info(f"Attempting to delete master category ID: {category_id}")
        await doc_ref.delete()
        logger.info(f"Successfully deleted master category ID: {category_id}")
        return True
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied deleting master category ID {category_id}.")
        return False
    except Exception as e:
        logger.exception(f"Error deleting master category ID {category_id}:")
        return False

# --- CRUD Operations for LanguagePairConfigurations ---

async def add_language_pair_configuration(db: AsyncClient, config_data: LanguagePairConfiguration) -> Optional[LanguagePairConfiguration]:
    """Saves a new LanguagePairConfiguration document in Firestore.
    A new Firestore document ID will be auto-generated.
    """
    try:
        # db instance is now passed
        logger.info(f"Attempting to add new language pair configuration for: {config_data.language_pair} - {config_data.config_key}")
        data_to_save = config_data.model_dump(
            mode='json',
            exclude={'id', 'created_at', 'updated_at'},
            exclude_none=True
        )
        data_to_save['created_at'] = SERVER_TIMESTAMP
        data_to_save['updated_at'] = SERVER_TIMESTAMP
        doc_ref = db.collection('LanguagePairConfigurations').document()
        await doc_ref.set(data_to_save)
        logger.info(f"New language pair configuration created successfully with Firestore ID: {doc_ref.id}")
        saved_doc_snapshot = await doc_ref.get()
        if saved_doc_snapshot.exists:
            saved_data_dict = saved_doc_snapshot.to_dict()
            if saved_data_dict:
                saved_data_dict['id'] = doc_ref.id
                validated_config = LanguagePairConfiguration.model_validate(saved_data_dict)
                return validated_config
            else:
                logger.error(f"Failed to retrieve data for new config {doc_ref.id} (to_dict was None).")
                return None
        else:
            logger.error(f"Failed to fetch new config {doc_ref.id} immediately after creation.")
            return None
    except ValidationError as e:
         logger.error(f"Pydantic validation error for language pair config: {e}")
         return None
    except google_exceptions.PermissionDenied:
         logger.error(f"Permission denied saving language pair configuration.")
         return None
    except Exception as e:
        logger.exception(f"Error saving language pair configuration to Firestore:")
        return None

async def get_language_pair_configurations(db: AsyncClient, language_pair_filter: Optional[str] = None) -> List[LanguagePairConfiguration]:
    """Fetches LanguagePairConfiguration documents from Firestore.
    Optionally filters by the 'language_pair' field if language_pair_filter is provided.
    """
    configs: List[LanguagePairConfiguration] = []
    collection_name = 'LanguagePairConfigurations'
    try:
        # db instance is now passed
        query = db.collection(collection_name)
        if language_pair_filter:
            logger.info(f"Fetching language pair configurations for '{language_pair_filter}' from '{collection_name}'")
            query = query.where(filter=FieldFilter('language_pair', '==', language_pair_filter))
        else:
            logger.info(f"Attempting to fetch all language pair configurations from '{collection_name}'")
        query_stream = query.stream()
        async for doc_snapshot in query_stream:
            try:
                config_data = doc_snapshot.to_dict()
                if config_data:
                    config_data['id'] = doc_snapshot.id
                    config = LanguagePairConfiguration.model_validate(config_data)
                    configs.append(config)
                else:
                    logger.warning(f"Language pair config document {doc_snapshot.id} contains no data.")
            except ValidationError as e:
                logger.warning(f"Skipping language pair config {doc_snapshot.id} due to validation error: {e}")
            except Exception as e:
                logger.error(f"Error processing language pair config document {doc_snapshot.id}: {e}")
        logger.info(f"Fetched {len(configs)} language pair configurations"
                    f"{f' for {language_pair_filter}' if language_pair_filter else ''}.")
        return configs
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied fetching language pair configurations.")
        return []
    except Exception as e:
        logger.exception("Error fetching language pair configurations from Firestore:")
        return []

async def update_language_pair_configuration(db: AsyncClient, config_id: str, updates: Dict[str, Any]) -> Optional[LanguagePairConfiguration]:
    """Updates an existing LanguagePairConfiguration document in Firestore by its ID."""
    collection_name = 'LanguagePairConfigurations'
    try:
        # db instance is now passed
        doc_ref = db.collection(collection_name).document(config_id)
        doc_snapshot = await doc_ref.get()
        if not doc_snapshot.exists:
            logger.warning(f"LanguagePairConfiguration with ID '{config_id}' not found for update.")
            return None
        updates_for_firestore = {}
        for key, value in updates.items():
            if isinstance(value, BaseModel):
                updates_for_firestore[key] = value.model_dump(mode='json', exclude_none=True)
            else:
                updates_for_firestore[key] = value
        if not updates_for_firestore:
            logger.warning(f"No valid update fields provided for config ID '{config_id}'.")
            return None
        updates_for_firestore['updated_at'] = SERVER_TIMESTAMP
        logger.info(f"Attempting to update LanguagePairConfiguration ID: {config_id} with: {updates_for_firestore}")
        await doc_ref.update(updates_for_firestore)
        logger.info(f"Successfully updated LanguagePairConfiguration ID: {config_id}")
        updated_doc_snapshot = await doc_ref.get()
        if updated_doc_snapshot.exists:
            updated_data_dict = updated_doc_snapshot.to_dict()
            if updated_data_dict:
                updated_data_dict['id'] = updated_doc_snapshot.id
                validated_config = LanguagePairConfiguration.model_validate(updated_data_dict)
                return validated_config
        logger.error(f"Failed to fetch LanguagePairConfiguration {config_id} after update.")
        return None
    except google_exceptions.NotFound:
        logger.warning(f"LanguagePairConfiguration ID '{config_id}' not found (NotFound exception).")
        return None
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied updating LanguagePairConfiguration ID {config_id}.")
        return None
    except ValidationError as e:
        logger.error(f"Pydantic validation error during update for LanguagePairConfiguration '{config_id}': {e}")
        return None
    except Exception as e:
        logger.exception(f"Error updating LanguagePairConfiguration ID {config_id}:")
        return None

async def delete_language_pair_configuration(db: AsyncClient, config_id: str) -> bool:
    """Deletes a LanguagePairConfiguration document from Firestore by its ID."""
    collection_name = 'LanguagePairConfigurations'
    try:
        # db instance is now passed
        doc_ref = db.collection(collection_name).document(config_id)
        logger.info(f"Attempting to delete LanguagePairConfiguration ID: {config_id}")
        await doc_ref.delete()
        logger.info(f"Successfully deleted LanguagePairConfiguration ID: {config_id}")
        return True
    except google_exceptions.PermissionDenied:
        logger.error(f"Permission denied deleting LanguagePairConfiguration ID {config_id}.")
        return False
    except Exception as e:
        logger.exception(f"Error deleting LanguagePairConfiguration ID {config_id}:")
        return False

async def save_word_list(db: AsyncClient, word_list: GeneratedWordList):
    # Implementation to save a word list to Firestore
    # This function seems to be a duplicate or older version of save_generated_list.
    # Consider removing or consolidating if save_generated_list is the primary one.
    logger.warning("save_word_list function called, may be deprecated. Consider using save_generated_list.")
    # For now, let's delegate to save_generated_list if it's compatible
    return await save_generated_list(db, word_list)

async def get_word_list(db: AsyncClient, list_id: str) -> Optional[GeneratedWordList]:
    # Implementation to get a word list from Firestore by ID
    # This function seems to be a duplicate or older version of get_generated_list_by_id.
    # Consider removing or consolidating.
    logger.warning("get_word_list function called, may be deprecated. Consider using get_generated_list_by_id.")
    return await get_generated_list_by_id(db, list_id)
