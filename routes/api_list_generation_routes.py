from flask import Blueprint, jsonify, request, abort
from models import InstructionFile, WordItem, GenerateListInput, GeneratedWordList, GeneratedWordListSummary, UpdateListMetadataInput, GeneratedWordListParameters
from llm_client import generate_word_list
from firestore_client import save_generated_list, get_generated_list_by_id, get_all_generated_lists, update_generated_list_metadata, delete_generated_list, get_master_categories
from app_factory import get_db
import asyncio
import json
from loguru import logger # Use Loguru logger
import os # Added import
from typing import Optional # Added import
from uuid import uuid4 # Import uuid4 for generating readable IDs
from pydantic import ValidationError # Added import
import functools # Moved import to top

# logger = logging.getLogger(__name__) # No longer needed

list_gen_api_bp = Blueprint('list_gen_api', __name__, url_prefix='/api/v1/generated-lists')

# Helper function to read instruction files (assuming they are in llm_prompts/)
async def read_instruction_file(file_ref: str) -> Optional[str]:
    """Reads the content of an instruction file from the llm_prompts directory."""
    file_path = os.path.join('llm_prompts', file_ref)
    if not os.path.exists(file_path):
        logger.error(f"Instruction file not found: {file_path}")
        return None
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading instruction file {file_path}: {e}")
        return None

# Helper function to generate a readable ID
async def generate_readable_id() -> str:
    """Generates a simple readable ID (e.g., using UUID and taking a part)."""
    # This is a placeholder; a more robust implementation might check for collisions
    return str(uuid4()).split('-')[0] # Use the first part of a UUID

@list_gen_api_bp.route('/', methods=['GET'])
async def get_all_lists_summary():
    """Fetches a summarized list of all generated word lists with optional filters."""
    try:
        # Get filters from query parameters
        filters = {
            "language": request.args.get('language'),
            "cefr_level": request.args.get('cefr_level'),
            "status": request.args.get('status'),
            "list_category_id": request.args.get('list_category_id')
        }
        # Remove None values from filters
        filters = {k: v for k, v in filters.items() if v is not None}

        # Get pagination/sorting parameters
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        sort_by = request.args.get('sort_by')
        sort_direction = request.args.get('sort_direction', 'DESCENDING') # Default to DESCENDING

        summaries = await get_all_generated_lists(
            filters=filters,
            sort_by=sort_by,
            sort_direction=sort_direction,
            limit=limit,
            offset=offset
        )
        return jsonify([summary.model_dump(mode='json') for summary in summaries])
    except Exception as e:
        logger.exception("Error fetching all generated lists:")
        abort(500, description="Failed to fetch generated word lists.")

@list_gen_api_bp.route('/filter-options', methods=['GET'])
async def get_filter_options():
    """Provides options for filtering generated word lists (e.g., categories, languages)."""
    try:
        # Fetch categories to provide category filter options
        categories = await get_master_categories()
        category_options = [{"id": cat.category_id, "name": cat.display_name.get('en', cat.category_id)} for cat in categories]

        # TODO: Fetch available languages and CEFR levels from a more central source if needed
        language_options = [
            {"id": "id", "name": "Indonesian"},
            {"id": "en", "name": "English"},
            {"id": "es", "name": "Spanish"},
            # Add other supported languages
        ]
        cefr_options = [
            {"id": "A1", "name": "A1"},
            {"id": "A2", "name": "A2"},
            {"id": "B1", "name": "B1"},
            {"id": "B2", "name": "B2"},
            {"id": "C1", "name": "C1"},
            {"id": "C2", "name": "C2"},
        ]
        status_options = [
            {"id": "pending", "name": "Pending"},
            {"id": "generating", "name": "Generating"},
            {"id": "review", "name": "Ready for Review"},
            {"id": "approved", "name": "Approved"},
            {"id": "rejected", "name": "Rejected"},
            {"id": "error", "name": "Error"},
        ]


        return jsonify({
            "categories": category_options,
            "languages": language_options,
            "cefr_levels": cefr_options,
            "statuses": status_options,
        })
    except Exception as e:
        logger.exception("Error fetching filter options:")
        abort(500, description="Failed to fetch filter options.")


@list_gen_api_bp.route('/generate', methods=['POST'])
async def generate_list():
    """Initiates the generation of a new word list."""
    try:
        # Parse request data into Pydantic model
        input_data = GenerateListInput.model_validate(request.json)

        # Read instruction files
        base_instructions = await read_instruction_file(input_data.base_instruction_file_ref)
        if base_instructions is None:
            abort(400, description=f"Base instruction file not found: {input_data.base_instruction_file_ref}")

        custom_instructions = ""
        if input_data.custom_instruction_file_ref:
            custom_instructions = await read_instruction_file(input_data.custom_instruction_file_ref)
            if custom_instructions is None:
                 abort(400, description=f"Custom instruction file not found: {input_data.custom_instruction_file_ref}")

        # Fetch category display name for the prompt
        # This assumes get_master_categories returns a list of VocabularyCategory Pydantic models
        # and that input_data.list_category_id is a valid ID.
        category_display_name = input_data.list_category_id # Default to ID if not found
        try:
            categories = await get_master_categories()
            category_lookup = {cat.category_id: cat.display_name.get('en', cat.category_id) for cat in categories}
            category_display_name = category_lookup.get(input_data.list_category_id, input_data.list_category_id)
        except Exception as cat_e:
            logger.warning(f"Could not fetch or resolve category display name for {input_data.list_category_id}: {cat_e}. Using ID as fallback.")

        # Fill in placeholders in the base_instructions template
        # Placeholders are:
        # - Target Language: [This will be filled in by the system, e.g., "Indonesian"]
        # - CEFR Level: [This will be filled in by the system, e.g., "A1"]
        # - Topic/Category: [This will be filled in by the system, e.g., "Food and Drink" or "Housing"]
        # - Approximate Number of Words: [This will be filled in by the system, e.g., "50"]
        
        filled_base_instructions = base_instructions.replace(
            "[This will be filled in by the system, e.g., \"Indonesian\"]", input_data.language
        ).replace(
            "[This will be filled in by the system, e.g., \"A1\"]", input_data.cefr_level
        ).replace(
            "[This will be filled in by the system, e.g., \"Food and Drink\" or \"Housing\"]", category_display_name
        ).replace(
            "[This will be filled in by the system, e.g., \"50\"]", str(input_data.requested_word_count)
        )

        # Combine instructions and refinements
        final_prompt_text_sent = f"{filled_base_instructions}\n\n{custom_instructions or ''}\n\n{input_data.ui_text_refinements or ''}".strip()
        logger.debug(f"Final prompt text sent to LLM (first 500 chars): {final_prompt_text_sent[:500]}")

        # Generate readable ID
        readable_id = await generate_readable_id()

        # Create GeneratedWordListParameters instance
        gen_params_dict = input_data.model_dump()
        gen_params_dict['list_readable_id'] = readable_id
        gen_params_dict['status'] = "pending"  # Initial status
        gen_params_dict['final_llm_prompt_text_sent'] = final_prompt_text_sent # Log the fully constructed prompt
        # Update Gemini response settings for JSON generation
        gen_params_dict['gemini_response_mime_type'] = "application/json"
        gen_params_dict['gemini_response_schema_used'] = "llm_prompts/default_word_list_schema.json" # Reference to the schema file
        # generated_word_count will be None initially
        # reviewed_by will be None initially
        # timestamps (generation_timestamp, last_status_update_timestamp) are handled by Firestore or later updates

        try:
            generation_params_obj = GeneratedWordListParameters.model_validate(gen_params_dict)
        except ValidationError as ve:
            logger.error(f"Validation error creating GeneratedWordListParameters: {ve.errors()}")
            # Provide more specific error to client if possible, or a generic one
            abort(400, description=f"Invalid data for generation parameters: {ve.errors()}")

        # Create initial GeneratedWordList object
        initial_list_data = GeneratedWordList(
            generation_parameters=generation_params_obj,
            word_items=[], # Start empty
        )
        # Timestamps (created_at, updated_at for the list itself) are handled by Firestore save_generated_list

        # Save initial list data to Firestore (status: pending)
        saved_list = await save_generated_list(initial_list_data)
        if saved_list is None:
            abort(500, description="Failed to save initial word list to Firestore.")

        # --- Asynchronously call LLM and update list ---
        # We don't await the LLM call here to return a quick response.
        # The LLM generation and subsequent Firestore update will happen in the background.
        
        # Define a done callback to handle task exceptions
        def _handle_task_result(task: asyncio.Task, list_id_for_callback: str) -> None:
            try:
                task.result()  # Raises an exception if the task failed
                logger.info(f"Background task for list ID {list_id_for_callback} completed successfully (as reported by done callback).")
            except asyncio.CancelledError:
                logger.warning(f"Background task for list ID {list_id_for_callback} was cancelled.")
            except Exception:
                # Log the exception from the task
                logger.exception(f"EXCEPTION in background task for list ID {list_id_for_callback} (reported by done callback):")
                # Try to update Firestore status to 'error' from this synchronous callback
                # Note: This is a synchronous context. Calling async firestore update directly is problematic.
                # For robust error reporting from background task to DB, the task itself should handle it.
                # This callback is more for logging the fact that an unhandled exception occurred.
                # Consider a more robust mechanism if this becomes common.
                # For now, just log it. The task's own try/except should handle DB updates.
        
        # Try getting current loop and creating task from it
        try:
            loop = asyncio.get_running_loop()
            logger.info(f"Event loop obtained: {loop}. Creating task on this loop.")
            bg_task = loop.create_task(_generate_and_update_list(saved_list.list_firestore_id, final_prompt_text_sent, input_data))
        except RuntimeError as e_no_loop:
            logger.error(f"Could not get running event loop: {e_no_loop}. Falling back to asyncio.create_task.")
            bg_task = asyncio.create_task(_generate_and_update_list(saved_list.list_firestore_id, final_prompt_text_sent, input_data))
            
        # Pass the list_id to the callback using a lambda or functools.partial if needed,
        # but here we can define the callback inside generate_list to capture saved_list.list_firestore_id
        # However, to avoid issues with closures and loop variables if this were in a loop,
        # it's safer to pass it explicitly. Let's refine the callback.

        # Simplified done callback for diagnostics
        def _simple_task_done_callback(task: asyncio.Task, firestore_id_for_log: str):
            logger.info(f"SIMPLE DONE CALLBACK: Task for list {firestore_id_for_log} has finished.")
            if task.cancelled():
                # Try to get more info about the cancellation
                logger.warning(f"SIMPLE DONE CALLBACK: Task for list {firestore_id_for_log} was cancelled. Details: {task}")
                # Attempt to log the cancellation exception object itself if possible
                try:
                    task.result() # This should re-raise CancelledError
                except asyncio.CancelledError as ce:
                    logger.error(f"SIMPLE DONE CALLBACK: CancelledError object for task {firestore_id_for_log}: {ce}", exc_info=True)
                except Exception as e_in_cancel_log: # Should not happen if only CancelledError
                    logger.error(f"SIMPLE DONE CALLBACK: Unexpected error trying to log CancelledError for task {firestore_id_for_log}: {e_in_cancel_log}", exc_info=True)

            elif task.exception() is not None:
                logger.error(f"SIMPLE DONE CALLBACK: Task for list {firestore_id_for_log} failed with exception: {task.exception()}", exc_info=task.exception())
            else:
                logger.info(f"SIMPLE DONE CALLBACK: Task for list {firestore_id_for_log} completed without apparent error in callback.")

        # Add the simplified callback
        # Use functools.partial to pass the firestore_id correctly
        # import functools # Moved to top of file
        
        callback_with_id = functools.partial(_simple_task_done_callback, firestore_id_for_log=saved_list.list_firestore_id)
        bg_task.add_done_callback(callback_with_id)

        # Return the initial saved list data (including Firestore ID)
        return jsonify(saved_list.model_dump(mode='json')), 201 # 201 Created

    except ValidationError as e:
        logger.error(f"Validation error in generate_list input: {e.errors()}")
        abort(400, description=f"Invalid input data: {e.errors()}")
    except Exception as e:
        logger.exception("Error in generate_list endpoint:")
        abort(500, description="Failed to initiate word list generation.")

async def _generate_and_update_list(list_firestore_id: str, prompt_text: str, input_params: GenerateListInput):
    """Background task to call LLM and update the generated list in Firestore."""
    logger.info(f"Background task started for list ID: {list_firestore_id}")
    try:
        logger.info(f"[_generate_and_update_list] Task {list_firestore_id}: Attempting to update status to 'generating'.")
        status_update_successful = False # Default to false
        try:
            status_update_successful = await update_generated_list_metadata(list_firestore_id, {"status": "generating"})
            logger.info(f"[_generate_and_update_list] Task {list_firestore_id}: update_generated_list_metadata call returned: {status_update_successful}")
        except Exception as e_update_meta:
            logger.exception(f"[_generate_and_update_list] Task {list_firestore_id}: EXCEPTION during 'update_generated_list_metadata' for status 'generating':")
            # Try to set status to error directly here if the call itself failed catastrophically
            try:
                await update_generated_list_metadata(list_firestore_id, {"status": "error", "admin_notes": f"EXCEPTION during initial status update: {str(e_update_meta)}"})
            except Exception as e_set_error_status:
                logger.error(f"[_generate_and_update_list] Task {list_firestore_id}: CRITICAL - Failed to set status to 'error' after initial update exception: {e_set_error_status}")
            return # Abort task

        if status_update_successful:
            logger.info(f"[_generate_and_update_list] Task {list_firestore_id}: Successfully updated status to 'generating'.")
        else:
            logger.error(f"[_generate_and_update_list] Task {list_firestore_id}: Failed to update status to 'generating' (update_generated_list_metadata returned False). Aborting task.")
            try:
                await update_generated_list_metadata(list_firestore_id, {"status": "error", "admin_notes": "Failed to set status to 'generating' at task start (returned False)."})
            except Exception as e_set_error_status_false:
                 logger.error(f"[_generate_and_update_list] Task {list_firestore_id}: Failed to set status to 'error' after initial update returned False: {e_set_error_status_false}")
            return # Stop further processing for this task

        logger.debug(f"[_generate_and_update_list] Task {list_firestore_id}: About to call generate_word_list.")
        logger.debug(f"[_generate_and_update_list] input_params: {input_params.model_dump_json(indent=2)}")
        logger.debug(f"[_generate_and_update_list] prompt_text (first 500 chars): {prompt_text[:500]}")

        # Call LLM
        # Pass the final_prompt_text_sent which is already available in this function's scope
        llm_response = await generate_word_list(input_params, prompt_text) 
        
        logger.debug(f"[_generate_and_update_list] llm_response from generate_word_list: {type(llm_response)}")
        if isinstance(llm_response, list):
            logger.debug(f"[_generate_and_update_list] llm_response item count: {len(llm_response)}")
        elif isinstance(llm_response, dict):
            logger.debug(f"[_generate_and_update_list] llm_response dict: {llm_response}")


        # Check if LLM call returned an error dict
        if isinstance(llm_response, dict) and 'error' in llm_response:
             logger.error(f"LLM generation failed for list {list_firestore_id}: {llm_response.get('error')}")
             await update_generated_list_metadata(list_firestore_id, {"status": "error", "admin_notes": f"LLM Error: {llm_response.get('error')}"})
             return # Exit task

        # Assuming llm_response is a list of WordItem models
        word_items = llm_response # Directly use the list of WordItem models

        # Fetch the current list data to update it
        current_list = await get_generated_list_by_id(list_firestore_id)
        if current_list is None:
            logger.error(f"Background task failed: Could not fetch list {list_firestore_id} for update after LLM generation.")
            await update_generated_list_metadata(list_firestore_id, {"status": "error", "admin_notes": "Background update failed: Could not fetch list after generation."})
            return

        # Update word items and generated count
        current_list.word_items = word_items
        current_list.generation_parameters.generated_word_count = len(word_items)
        current_list.generation_parameters.status = "review" # Ready for review

        # Save the updated list data
        await save_generated_list(current_list) # Use the imported function
        logger.info(f"Successfully generated and updated list {list_firestore_id} with {len(word_items)} words. Status set to 'review'.")

    except Exception as e:
        logger.exception(f"Error in background generation task for list ID {list_firestore_id}:")
        # Attempt to update status to error
        try:
            await update_generated_list_metadata(list_firestore_id, {"status": "error", "admin_notes": f"Background generation task failed: {str(e)}"})
        except Exception as update_e:
            logger.error(f"Failed to update list status to error for {list_firestore_id}: {update_e}")
    # finally: # No longer needed as we are not managing a db client instance in this function scope
        # if db:
            # try:
                # await db.close() # This was causing TypeError as db was sync client
                # logger.debug(f"Firestore client for task {list_firestore_id} closed.")
            # except Exception as close_e:
                # logger.error(f"Error closing Firestore client for task {list_firestore_id}: {close_e}")


@list_gen_api_bp.route('/<list_id>', methods=['GET'])
async def get_list_details(list_id: str):
    """Fetches details for a single generated word list by its Firestore ID."""
    try:
        list_data = await get_generated_list_by_id(list_id)
        if list_data is None:
            abort(404, description=f"Word list with ID '{list_id}' not found.")

        # Fetch category display name for the summary
        categories = await get_master_categories()
        category_lookup = {cat.category_id: cat.display_name.get('en', cat.category_id) for cat in categories}
        category_display_name = category_lookup.get(list_data.generation_parameters.list_category_id, list_data.generation_parameters.list_category_id or "N/A")

        # Create a summary object to include the display name
        summary = GeneratedWordListSummary(
            list_firestore_id=list_data.list_firestore_id,
            list_readable_id=list_data.generation_parameters.list_readable_id,
            language=list_data.generation_parameters.language,
            cefr_level=list_data.generation_parameters.cefr_level,
            list_category_display_name=category_display_name,
            status=list_data.generation_parameters.status,
            generated_word_count=list_data.generation_parameters.generated_word_count,
            generation_timestamp=list_data.generation_parameters.generation_timestamp
        )

        # Return both the full list data and the summary
        return jsonify({
            "details": list_data.model_dump(mode='json'),
            "summary": summary.model_dump(mode='json')
        })

    except Exception as e:
        logger.exception(f"Error fetching generated list details for ID {list_id}:")
        abort(500, description="Failed to fetch word list details.")


@list_gen_api_bp.route('/<list_id>/metadata', methods=['PATCH'])
async def update_list_metadata(list_id: str):
    """Updates metadata fields for a generated word list by its Firestore ID."""
    try:
        # Parse request data into Pydantic model
        update_data = UpdateListMetadataInput.model_validate(request.json)

        # Convert Pydantic model to dictionary, excluding None values
        metadata_updates = update_data.model_dump(exclude_none=True)

        if not metadata_updates:
            abort(400, description="No valid metadata fields provided for update.")

        success = await update_generated_list_metadata(list_id, metadata_updates)

        if success:
            return jsonify({"message": "Metadata updated successfully"}), 200
        else:
            abort(404, description=f"Word list with ID '{list_id}' not found or no valid fields to update.")

    except ValidationError as e:
        logger.error(f"Validation error in update_list_metadata input for list ID {list_id}: {e.errors()}")
        abort(400, description=f"Invalid input data: {e.errors()}")
    except Exception as e:
        logger.exception(f"Error updating metadata for list ID {list_id}:")
        abort(500, description="Failed to update word list metadata.")


@list_gen_api_bp.route('/<list_id>', methods=['DELETE'])
async def delete_list(list_id: str):
    """Deletes a generated word list by its Firestore ID."""
    try:
        success = await delete_generated_list(list_id)
        if success:
            return jsonify({"message": f"Word list with ID '{list_id}' deleted successfully"}), 200
        else:
            abort(404, description=f"Word list with ID '{list_id}' not found.")
    except Exception as e:
        logger.exception(f"Error deleting list ID {list_id}:")
        abort(500, description="Failed to delete word list.")
