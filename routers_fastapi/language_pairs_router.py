from fastapi import APIRouter, Request, HTTPException
from typing import List, Optional, Dict, Any
from loguru import logger

from models import LanguagePairConfiguration # Pydantic model
import firestore_client

router = APIRouter(
    prefix="/api/language-pairs", # Matches Flask blueprint url_prefix
    tags=["Language Pair Configurations"]
)

@router.get("/", response_model=List[LanguagePairConfiguration])
async def get_language_pairs_api(
    request: Request,
    language_pair_filter: Optional[str] = None # Query parameter
):
    """Fetches all language pair configurations, optionally filtered by language_pair."""
    db_client = request.app.state.firestore_client
    try:
        configs = await firestore_client.get_language_pair_configurations(db_client, language_pair_filter)
        return configs
    except Exception as e:
        logger.exception("Error fetching language pair configurations (API):")
        raise HTTPException(status_code=500, detail="Failed to fetch language pair configurations.")

@router.post("/", response_model=LanguagePairConfiguration, status_code=201)
async def create_language_pair_api(
    config_data: LanguagePairConfiguration, # Request body
    request: Request
):
    """Creates a new language pair configuration."""
    db_client = request.app.state.firestore_client
    try:
        # Ensure ID is not set by client for creation, Firestore will generate it.
        if config_data.id is not None:
            logger.warning(f"Client attempted to provide ID '{config_data.id}' for new language pair config. ID will be auto-generated.")
            config_data.id = None # Ensure ID is None for new document creation

        new_config = await firestore_client.add_language_pair_configuration(db_client, config_data)
        if new_config:
            return new_config
        else:
            raise HTTPException(status_code=500, detail="Failed to create language pair configuration.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error creating language pair configuration (API):")
        raise HTTPException(status_code=500, detail="Failed to create language pair configuration.")

@router.put("/{config_id}", response_model=LanguagePairConfiguration)
async def update_language_pair_api(
    config_id: str,
    update_payload: Dict[str, Any], # Request body
    request: Request
):
    """Updates an existing language pair configuration by its Firestore ID."""
    db_client = request.app.state.firestore_client
    if not update_payload:
        raise HTTPException(status_code=400, detail="Request body cannot be empty for update.")
    try:
        updated_config = await firestore_client.update_language_pair_configuration(db_client, config_id, update_payload)
        if updated_config:
            return updated_config
        else:
            raise HTTPException(status_code=404, detail=f"Language pair configuration with ID '{config_id}' not found or update failed.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating language pair configuration ID {config_id} (API):")
        raise HTTPException(status_code=500, detail="Failed to update language pair configuration.")

@router.delete("/{config_id}", status_code=200)
async def delete_language_pair_api(config_id: str, request: Request):
    """Deletes a language pair configuration by its Firestore ID."""
    db_client = request.app.state.firestore_client
    try:
        success = await firestore_client.delete_language_pair_configuration(db_client, config_id)
        if success:
            return {"message": f"Language pair configuration with ID '{config_id}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Language pair configuration with ID '{config_id}' not found or delete failed.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting language pair configuration ID {config_id} (API):")
        raise HTTPException(status_code=500, detail="Failed to delete language pair configuration.")
