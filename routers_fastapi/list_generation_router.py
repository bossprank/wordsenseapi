from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import ValidationError # Added import
from typing import List, Optional, Dict, Any
from uuid import uuid4
import os
import asyncio
from datetime import datetime, timezone # Added datetime import
from zoneinfo import ZoneInfo # Added ZoneInfo import
from loguru import logger

# Models from the project's models.py
from models import (
    GenerateListInput,
    GeneratedWordList,
    GeneratedWordListSummary,
    UpdateListMetadataInput,
    GeneratedWordListParameters,
    WordItem, # For the type hint of llm_response
    VocabularyCategory # For fetching category display name
)

# Client-specific functions (will need to be adapted to use passed client instances)
import llm_client # Assuming generate_word_list is here
import firestore_client # Assuming all firestore functions are here

router = APIRouter(
    prefix="/api/v1/generated-lists",
    tags=["Generated Lists Management"]
)

# Helper function to read instruction files (can be kept similar)
async def read_instruction_file(file_ref: str) -> Optional[str]:
    file_path = os.path.join('llm_prompts', file_ref)
    if not os.path.exists(file_path):
        logger.error(f"Instruction file not found: {file_path}")
        return None
    try:
        # Using async file read if available, otherwise standard sync read in thread
        # For simplicity, keeping sync read as it's usually fast for small local files
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading instruction file {file_path}: {e}")
        return None

# Updated helper function to generate a readable ID in the new format
async def generate_readable_id(language: str, cefr_level: str, timestamp: datetime) -> str:
    # Ensure the input timestamp (assumed UTC from utcnow()) is made aware
    utc_timestamp_aware = timestamp.replace(tzinfo=timezone.utc)
    
    sg_timezone = ZoneInfo("Asia/Singapore")
    timestamp_sg = utc_timestamp_aware.astimezone(sg_timezone)
    # Format: Lang-CEFR-DDMMYY-HHMM
    timestamp_str = timestamp_sg.strftime("%d%m%y-%H%M")
    return f"{language.upper()}-{cefr_level.upper()}-{timestamp_str}"


async def run_llm_and_update_db(
    list_firestore_id: str,
    prompt_text: str,
    input_params_dict: Dict[str, Any], # Pass validated input_data as dict
    db_client: Any # Firestore AsyncClient passed from app.state
):
    logger.info(f"Background task started for list ID: {list_firestore_id}")
    # Re-create GenerateListInput from dict for type safety if llm_client.generate_word_list expects it
    input_params = GenerateListInput(**input_params_dict)
    try:
        logger.info(f"[run_llm_and_update_db] Task {list_firestore_id}: Attempting to update status to 'generating'.")
        status_update_successful = await firestore_client.update_generated_list_metadata(
            db_client, list_firestore_id, {"status": "generating"}
        )
        logger.info(f"[run_llm_and_update_db] Task {list_firestore_id}: update_generated_list_metadata call to set 'generating' status returned: {status_update_successful}")

        if not status_update_successful:
            logger.error(f"[run_llm_and_update_db] Task {list_firestore_id}: Failed to update status to 'generating'. Aborting task.")
            await firestore_client.update_generated_list_metadata(
                db_client, list_firestore_id, {"status": "error", "admin_notes": "Failed to set status to 'generating' at task start."}
            )
            return

        logger.info(f"[run_llm_and_update_db] Task {list_firestore_id}: About to call llm_client.generate_word_list.")
        
        llm_response: Union[List[WordItem], Dict[str, Any]] = await llm_client.generate_word_list(input_params, prompt_text)
        
        if isinstance(llm_response, dict) and 'error' in llm_response:
            logger.error(f"LLM generation failed for list {list_firestore_id}: {llm_response.get('error')}")
            await firestore_client.update_generated_list_metadata(
                db_client, list_firestore_id, {"status": "error", "admin_notes": f"LLM Error: {llm_response.get('error')}"}
            )
            return

        word_items = llm_response if isinstance(llm_response, list) else []

        current_list = await firestore_client.get_generated_list_by_id(db_client, list_firestore_id)
        if current_list is None:
            logger.error(f"Background task failed: Could not fetch list {list_firestore_id} for update after LLM generation.")
            # Attempt to set error status even if list fetch failed, though doc might be gone
            await firestore_client.update_generated_list_metadata(
                db_client, list_firestore_id, {"status": "error", "admin_notes": "Background update failed: Could not fetch list after generation."}
            )
            return

        current_list.word_items = word_items
        current_list.generation_parameters.generated_word_count = len(word_items)
        current_list.generation_parameters.status = "review"

        await firestore_client.save_generated_list(db_client, current_list) # save_generated_list needs to handle updates too
        logger.info(f"Successfully generated and updated list {list_firestore_id} with {len(word_items)} words. Status set to 'review'.")

    except Exception as e:
        logger.exception(f"Error in background LLM & DB update task for list ID {list_firestore_id}:")
        try:
            await firestore_client.update_generated_list_metadata(
                db_client, list_firestore_id, {"status": "error", "admin_notes": f"Background generation task failed: {str(e)}"}
            )
        except Exception as update_e:
            logger.error(f"Failed to update list status to error for {list_firestore_id} after task exception: {update_e}")

@router.post("/generate", response_model=GeneratedWordList, status_code=201)
async def generate_list_api(
    input_data: GenerateListInput,
    request: Request,
    background_tasks: BackgroundTasks
):
    db_client = request.app.state.firestore_client
    try:
        base_instructions = await read_instruction_file(input_data.base_instruction_file_ref)
        if base_instructions is None:
            raise HTTPException(status_code=400, detail=f"Base instruction file not found: {input_data.base_instruction_file_ref}")

        custom_instructions = ""
        if input_data.custom_instruction_file_ref:
            custom_instructions = await read_instruction_file(input_data.custom_instruction_file_ref)
            if custom_instructions is None:
                 raise HTTPException(status_code=400, detail=f"Custom instruction file not found: {input_data.custom_instruction_file_ref}")

        category_display_name = input_data.list_category_id
        try:
            categories_list = await firestore_client.get_master_categories(db_client)
            category_lookup = {cat.category_id: cat.display_name.get('en', cat.category_id) for cat in categories_list}
            category_display_name = category_lookup.get(input_data.list_category_id, input_data.list_category_id)
        except Exception as cat_e:
            logger.warning(f"Could not fetch or resolve category display name for {input_data.list_category_id}: {cat_e}. Using ID as fallback.")
        
        filled_base_instructions = base_instructions.replace(
            "[This will be filled in by the system, e.g., \"Indonesian\"]", input_data.language
        ).replace(
            "[This will be filled in by the system, e.g., \"A1\"]", input_data.cefr_level
        ).replace(
            "[This will be filled in by the system, e.g., \"Food and Drink\" or \"Housing\"]", category_display_name
        ).replace(
            "[This will be filled in by the system, e.g., \"50\"]", str(input_data.requested_word_count)
        )
        final_prompt_text_sent = f"{filled_base_instructions}\n\n{custom_instructions or ''}\n\n{input_data.ui_text_refinements or ''}".strip()
        # logger.debug(f"Final prompt text sent to LLM (first 500 chars): {final_prompt_text_sent[:500]}")

        current_timestamp = datetime.utcnow()
        readable_id = await generate_readable_id(input_data.language, input_data.cefr_level, current_timestamp)
        gen_params_dict = input_data.model_dump()
        gen_params_dict['list_readable_id'] = readable_id
        gen_params_dict['generation_timestamp'] = current_timestamp
        gen_params_dict['status'] = "pending"
        gen_params_dict['final_llm_prompt_text_sent'] = final_prompt_text_sent
        gen_params_dict['gemini_response_mime_type'] = input_data.gemini_response_mime_type # Use from input
        gen_params_dict['gemini_response_schema_used'] = input_data.gemini_response_schema_used # Use from input
        
        generation_params_obj = GeneratedWordListParameters(**gen_params_dict)
        
        initial_list_data = GeneratedWordList(
            generation_parameters=generation_params_obj,
            word_items=[]
        )
        
        # save_generated_list in firestore_client needs to handle new vs update.
        # For a new list, it should create and return the object with list_firestore_id.
        saved_list_header = await firestore_client.save_generated_list(db_client, initial_list_data)
        if not saved_list_header or not saved_list_header.list_firestore_id:
            raise HTTPException(status_code=500, detail="Failed to save initial word list to Firestore or retrieve its ID.")

        background_tasks.add_task(
            run_llm_and_update_db,
            list_firestore_id=saved_list_header.list_firestore_id,
            prompt_text=final_prompt_text_sent,
            input_params_dict=input_data.model_dump(), # Pass serializable dict
            db_client=db_client
        )
        
        return saved_list_header
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except ValidationError as e: # Pydantic validation error for input_data
        logger.error(f"Validation error in generate_list input: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.exception("Error in generate_list_api endpoint:")
        raise HTTPException(status_code=500, detail="Failed to initiate word list generation.")

# Moved /filter-options before /{list_id} to ensure correct route matching
@router.get("/filter-options", response_model=Dict[str, List[Dict[str, str]]])
async def get_filter_options_api(request: Request):
    db_client = request.app.state.firestore_client
    try:
        categories = await firestore_client.get_master_categories(db_client)
        category_options = [{"id": cat.category_id, "name": cat.display_name.get('en', cat.category_id)} for cat in categories]
        
        language_options = [
            {"id": "id", "name": "Indonesian"}, {"id": "en", "name": "English"},
            {"id": "es", "name": "Spanish"}, # Add others as needed
        ]
        cefr_options = [
            {"id": "A1", "name": "A1"}, {"id": "A2", "name": "A2"},
            {"id": "B1", "name": "B1"}, {"id": "B2", "name": "B2"},
            {"id": "C1", "name": "C1"}, {"id": "C2", "name": "C2"},
        ]
        status_options = [
            {"id": "pending", "name": "Pending"}, {"id": "generating", "name": "Generating"},
            {"id": "review", "name": "Ready for Review"}, {"id": "approved", "name": "Approved"},
            {"id": "rejected", "name": "Rejected"}, {"id": "error", "name": "Error"},
        ]
        return {
            "categories": category_options, "languages": language_options,
            "cefr_levels": cefr_options, "statuses": status_options,
        }
    except Exception as e:
        logger.exception("Error fetching filter options (API):")
        raise HTTPException(status_code=500, detail="Failed to fetch filter options.")

@router.get("/", response_model=List[GeneratedWordListSummary])
async def get_all_lists_summary_api(
    request: Request,
    language: Optional[str] = None,
    cefr_level: Optional[str] = None,
    status: Optional[str] = None,
    list_category_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    sort_by: Optional[str] = "generation_parameters.generation_timestamp",
    sort_direction: str = "DESCENDING"
):
    db_client = request.app.state.firestore_client
    try:
        filters = {
            "language": language,
            "cefr_level": cefr_level,
            "status": status,
            "list_category_id": list_category_id
        }
        filters = {k: v for k, v in filters.items() if v is not None}
        
        summaries = await firestore_client.get_all_generated_lists(
            db_client,
            filters=filters,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset
        )
        return summaries
    except Exception as e:
        logger.exception("Error fetching all generated lists summaries (API):")
        raise HTTPException(status_code=500, detail="Failed to fetch generated word list summaries.")

@router.get("/{list_id}", response_model=GeneratedWordList) # Assuming full detail for now
async def get_list_details_api(list_id: str, request: Request):
    db_client = request.app.state.firestore_client
    try:
        list_data = await firestore_client.get_generated_list_by_id(db_client, list_id)
        if list_data is None:
            raise HTTPException(status_code=404, detail=f"Word list with ID '{list_id}' not found.")
        return list_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching generated list details for ID {list_id} (API):")
        raise HTTPException(status_code=500, detail="Failed to fetch word list details.")

@router.patch("/{list_id}/metadata", status_code=200)
async def update_list_metadata_api(
    list_id: str,
    update_data: UpdateListMetadataInput,
    request: Request
):
    db_client = request.app.state.firestore_client
    try:
        metadata_updates = update_data.model_dump(exclude_none=True)
        if not metadata_updates:
            raise HTTPException(status_code=400, detail="No valid metadata fields provided for update.")

        success = await firestore_client.update_generated_list_metadata(db_client, list_id, metadata_updates)
        if success:
            return {"message": "Metadata updated successfully"}
        else:
            # This could be due to not found or other update failure in client
            # Check firestore_client logic for how it returns False
            existing_list = await firestore_client.get_generated_list_by_id(db_client, list_id)
            if not existing_list:
                 raise HTTPException(status_code=404, detail=f"Word list with ID '{list_id}' not found.")
            else: # Update failed for other reason
                 raise HTTPException(status_code=500, detail=f"Failed to update metadata for word list ID '{list_id}'.")
    except HTTPException:
        raise
    except ValidationError as e: # Pydantic validation error for update_data
        logger.error(f"Validation error in update_list_metadata input for list ID {list_id}: {e.errors()}")
        raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        logger.exception(f"Error updating metadata for list ID {list_id} (API):")
        raise HTTPException(status_code=500, detail="Failed to update word list metadata.")

@router.delete("/{list_id}", status_code=200)
async def delete_list_api(list_id: str, request: Request):
    db_client = request.app.state.firestore_client
    try:
        success = await firestore_client.delete_generated_list(db_client, list_id)
        if success:
            return {"message": f"Word list with ID '{list_id}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Word list with ID '{list_id}' not found or delete failed.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting list ID {list_id} (API):")
        raise HTTPException(status_code=500, detail="Failed to delete word list.")
