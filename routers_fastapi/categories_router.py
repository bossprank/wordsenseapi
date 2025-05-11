from fastapi import APIRouter, Request, HTTPException
from typing import List, Dict, Any
from loguru import logger

from models import VocabularyCategory # Pydantic model for category data
import firestore_client # Assuming all firestore functions are here

router = APIRouter(
    prefix="/api/categories", # Matches Flask blueprint url_prefix
    tags=["Categories Management"]
)

@router.get("/", response_model=List[VocabularyCategory])
async def get_categories_api(request: Request):
    """Fetches all master categories."""
    db_client = request.app.state.firestore_client
    try:
        categories = await firestore_client.get_master_categories(db_client)
        return categories
    except Exception as e:
        logger.exception("Error fetching categories (API):")
        raise HTTPException(status_code=500, detail="Failed to fetch categories.")

@router.post("/", response_model=VocabularyCategory, status_code=201)
async def create_category_api(
    category_data: VocabularyCategory, # FastAPI uses Pydantic model for request body
    request: Request
):
    """Creates a new master category. Client must provide a unique category_id."""
    db_client = request.app.state.firestore_client
    try:
        # add_master_category in firestore_client now takes db client as first arg
        new_category = await firestore_client.add_master_category(db_client, category_data)
        if new_category:
            return new_category
        else:
            # Consider if add_master_category should raise specific exceptions
            # for clearer error handling here (e.g., if ID already exists and we don't want to overwrite)
            raise HTTPException(status_code=500, detail="Failed to create category. Check server logs.")
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e: # Catch other exceptions (like Pydantic validation if not handled by FastAPI)
        logger.exception("Error creating category (API):")
        # If it's a Pydantic validation error from manual validation (though FastAPI handles most)
        # from pydantic import ValidationError
        # if isinstance(e, ValidationError):
        #     raise HTTPException(status_code=422, detail=e.errors())
        raise HTTPException(status_code=500, detail="Failed to create category.")

@router.put("/{category_id}", response_model=VocabularyCategory)
async def update_category_api(
    category_id: str,
    update_payload: Dict[str, Any], # Request body is a dict of fields to update
    request: Request
):
    """Updates an existing master category by ID."""
    db_client = request.app.state.firestore_client
    if not update_payload:
        raise HTTPException(status_code=400, detail="Request body cannot be empty for update.")
    try:
        updated_category = await firestore_client.update_master_category(db_client, category_id, update_payload)
        if updated_category:
            return updated_category
        else:
            # update_master_category returns None if not found or on other error
            # Check if it was a "not found" case specifically if possible
            # For now, assume 404 if None is returned, but could be more specific
            raise HTTPException(status_code=404, detail=f"Category with ID '{category_id}' not found or update failed.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating category ID {category_id} (API):")
        raise HTTPException(status_code=500, detail="Failed to update category.")

@router.delete("/{category_id}", status_code=200)
async def delete_category_api(category_id: str, request: Request):
    """Deletes a master category by ID."""
    db_client = request.app.state.firestore_client
    try:
        success = await firestore_client.delete_master_category(db_client, category_id)
        if success:
            return {"message": f"Category with ID '{category_id}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Category with ID '{category_id}' not found or delete failed.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting category ID {category_id} (API):")
        raise HTTPException(status_code=500, detail="Failed to delete category.")
