from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates # For type hinting if needed
from loguru import logger

# Assuming APP_VERSION and BUILD_NUMBER will be available via app.state or config
# For now, let's assume they might be passed via request.app.state if set up in main_fastapi.py
# Or, import directly from config if that's preferred.
from config import APP_VERSION, BUILD_NUMBER

router = APIRouter(
    tags=["HTML Pages"],
    default_response_class=HTMLResponse # Default for this router
)

# This router will need access to the Jinja2Templates instance.
# It's typically initialized in the main app file and can be accessed via request.app.state.templates
# or passed via dependency injection. In main_fastapi.py, it's named 'templates'.

@router.get("/")
async def route_index(request: Request):
    # templates object should be on app.state if initialized in lifespan, or globally in main_fastapi.py
    # For this example, assuming it's accessible via request.app.state.templates if set up that way,
    # or directly if main_fastapi.py makes 'templates' instance importable.
    # Let's assume it's on app.state for consistency with client access.
    # If main_fastapi.py defines `templates = Jinja2Templates(directory="templates")` globally,
    # then this router file could potentially import it: `from main_fastapi import templates`
    # However, using request.app.state is cleaner for shared resources.
    # We need to ensure `app.state.templates` is set in `main_fastapi.py`'s lifespan.
    
    # Correct access assuming 'templates' is stored on app.state:
    # templates_obj = request.app.state.templates 
    # For now, let's assume main_fastapi.py will make 'templates' available globally for routers to import
    from main_fastapi import templates # This requires 'templates' to be defined globally in main_fastapi.py

    return templates.TemplateResponse(request, "index.html", {
        "request": request,
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": True # Explicitly set for index page
    })

import os # Add os import for path joining
import json # Add json import for loading schema

# Helper to load default schema
def load_default_schema():
    schema_path = os.path.join('llm_prompts', 'default_word_list_schema.json')
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.dumps(json.load(f)) # Return as a JSON string
    except Exception as e:
        logger.error(f"Error loading default schema from {schema_path}: {e}")
        return "{}" # Return empty JSON object string on error

@router.get("/generate-new-word-list") # Corrected path
async def route_generate_new_list_page(request: Request): # Function name can remain for url_for
    # logger.info(f"Accessed /generate-new-word-list route. Query params: {request.query_params}") # Removing debug log
    from main_fastapi import templates
    default_schema_str = load_default_schema()
    return templates.TemplateResponse(request, "generate_new_word_list.html", {
        "request": request,
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": False,
        "default_schema": default_schema_str
    })

@router.get("/view-generated-word-lists")
async def route_view_generated_lists_page(request: Request):
    from main_fastapi import templates
    return templates.TemplateResponse(request, "view_generated_word_lists.html", {
        "request": request,
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": False
    })

@router.get("/generated-list-details/{list_id}")
async def route_generated_list_details_page(request: Request, list_id: str):
    from main_fastapi import templates
    return templates.TemplateResponse(request, "generated_list_details.html", {
        "request": request,
        "list_id": list_id, 
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": False
    })

@router.get("/edit-list-metadata/{list_id}")
async def route_edit_list_metadata_page(request: Request, list_id: str):
    from main_fastapi import templates
    return templates.TemplateResponse(request, "edit_list_metadata.html", {
        "request": request,
        "list_id": list_id,
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": False
    })

@router.get("/manage-categories")
async def route_manage_categories_page(request: Request):
    from main_fastapi import templates
    return templates.TemplateResponse(request, "manage_categories.html", {
        "request": request,
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": False
    })

@router.get("/manage-language-pairs")
async def route_manage_language_pairs_page(request: Request):
    from main_fastapi import templates
    return templates.TemplateResponse(request, "manage_language_pairs.html", {
        "request": request,
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": False
    })

@router.get("/language-pair-config-detail/{config_id}")
async def route_language_pair_config_detail_page(request: Request, config_id: str):
    from main_fastapi import templates
    return templates.TemplateResponse(request, "language_pair_config_detail.html", {
        "request": request,
        "config_id": config_id,
        "app_version": APP_VERSION,
        "build_number": BUILD_NUMBER,
        "is_index_page": False
    })
