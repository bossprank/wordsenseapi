# Build Guide 10: Flask to FastAPI Migration - Detailed Steps

**Date:** 2025-05-10

---
**Handoff Document: WordSense Admin Panel - FastAPI Migration**

**To:** New Senior FastAPI Development Engineer
**From:** [Project Lead/Previous Developer]
**Date:** May 10, 2025
**Project:** WordSense Admin Panel Backend (Migrating from Flask to FastAPI)
**Current GitHub Checkpoint:** "Version 3 - Pre-FastAPI Refactor" (Commit `49c12d0` on `master` branch of `bossprank/wordsenseapi`)

Welcome to the WordSense Admin Panel project! We're currently in the process of migrating the Python backend from Flask to FastAPI to address some persistent issues with asynchronous operations and to build a more robust, modern foundation. Your expertise in FastAPI will be invaluable.

**1. Reviewing the Environment & Project Setup:**

*   **Primary Goal:** The admin panel is designed for 1-2 administrative users to manage linguistic data, primarily generating vocabulary lists using Google's Generative AI (Gemini models) and storing/managing this data in Google Cloud Firestore. The ultimate aim is for a Flutter frontend (mobile/web app) to consume data managed by this admin panel.
*   **Current State:** The application was initially built with Flask. We've encountered significant challenges with asynchronous operations (LLM calls, Firestore async client interactions) within the Flask/`a2wsgi`/Hypercorn stack, leading to "Event loop is closed" errors and `CancelledError` in background tasks.
*   **Key Files & Directories to Review:**
    *   `requirements.txt`: Note the dependencies. We've just added `fastapi` and `uvicorn`. `a2wsgi` is now commented out.
    *   `config.py`: Handles configuration, including API keys (via Google Secret Manager) and project IDs. **Preference: All configurable variables should be clearly defined here or in environment variables loaded by `python-dotenv`.**
    *   `models.py`: Contains all Pydantic models for data validation and structuring. This is a critical file and should be the single source of truth for data shapes.
    *   `llm_client.py`: Handles interaction with the Google Generative AI SDK.
    *   `firestore_client.py`: Handles interaction with Google Cloud Firestore using the `AsyncClient`.
    *   `routes/` (old Flask blueprints): Understand the existing API structure and HTML routes. These will be migrated to FastAPI routers.
    *   `templates/` & `static/`: Contain the Jinja2 templates and static assets for the admin UI.
    *   `.cline/` directory: **Crucial for understanding project history and decisions.**
        *   `lessons_learned_fastapi_migration_20250510.md`: Outlines the rationale and high-level plan for this FastAPI migration.
        *   Other `lessons_learned_*.md` files: Provide context on past challenges and solutions. Note that some sections related to Flask-specific async workarounds have been recently annotated as superseded.
    *   `builds/` directory:
        *   `build_10_fastapi_migration_steps.md` (this document): This is the detailed, step-by-step guide for the FastAPI migration you will be undertaking. Please familiarize yourself with it thoroughly.
        *   Other build checklists provide historical context on feature development.
    *   `.clinerules/`: Contains project-specific guidelines (e.g., `python-startup-error-debugging.md`).
*   **Development Environment:**
    *   The project uses a Python virtual environment (`.venv`).
    *   The server was run using `run_server_asgi.sh` (previously with Hypercorn, will be updated for Uvicorn with FastAPI).
    *   Logging is managed by Loguru, configured in `app_factory.py` (this will move to the new FastAPI main application file, e.g., `main_fastapi.py`).

**2. Project Working Style & Preferences:**

*   **Documentation is Key:** We strive to document important decisions, architectural choices, and lessons learned in the `.cline/` and `builds/` directories. Please continue this practice. If you make a significant change or solve a tricky problem, a brief markdown note is highly appreciated.
*   **Explicit Variable Definition:** As much as possible, variables, configurations, and constants should be explicitly defined, typically in `config.py` or at the top of relevant modules. Avoid magic numbers or hardcoded strings where configurations are more appropriate.
*   **Pydantic for Data Integrity:** We rely heavily on Pydantic models (`models.py`) for defining clear data structures and for validating data at API boundaries and when interacting with external services (LLM, Firestore).
*   **Clear Commit Messages:** When committing to GitHub, please use descriptive commit messages.
*   **Problem Solving Approach:** We've been working iteratively. If you hit a roadblock, documenting the problem, what's been tried, and any error logs is very helpful for collaborative debugging.

**3. Migration Focus Area (Initial Priority):**

The immediate and most critical task is to successfully migrate the **vocabulary list generation functionality** to FastAPI. This is detailed further in this document (`builds/build_10_fastapi_migration_steps.md`). Key aspects include:

*   **Setting up the core FastAPI application** (`main_fastapi.py`) with proper lifecycle management for shared `AsyncFirestoreClient` and `genai.Client` (or its configuration). This is paramount to solving the event loop issues.
*   **Refactoring `firestore_client.py` and `llm_client.py`** to use these shared, correctly initialized clients.
*   **Converting the Flask blueprint in `routes/api_list_generation_routes.py`** to a FastAPI router. This includes:
    *   The `POST /api/v1/generated-lists/generate` endpoint.
    *   The background task logic (previously `_generate_and_update_list`, to be adapted for FastAPI's `BackgroundTasks`) which handles:
        1.  Updating list status to "generating" in Firestore.
        2.  Calling the LLM via `llm_client.py`.
        3.  Processing the LLM's JSON response.
        4.  Saving the generated word items and updating the list status to "review" in Firestore.
*   **Ensuring the supporting API endpoints** for fetching list summaries (`GET /api/v1/generated-lists/`) and list details (`GET /api/v1/generated-lists/{list_id}`) are also migrated and functional.

**Success for this initial phase means:**
*   The admin user can trigger a new vocabulary list generation via the UI (or API directly).
*   The background task completes without `CancelledError` or "Event loop is closed" issues.
*   The generated words are correctly parsed and saved to Firestore.
*   The list status is updated appropriately (pending -> generating -> review).

Once this core functionality is stable on FastAPI, we can proceed to migrate the remaining API endpoints (categories, language pairs) and the HTML-serving routes.

Please review the detailed steps in this document carefully.
---

**Objective:** Migrate the Python backend for the WordSense Admin Panel from Flask to FastAPI to improve asynchronous operation stability, leverage modern tooling, and establish a more robust foundation. This guide follows the "big bang" approach outlined in `.cline/lessons_learned_fastapi_migration_20250510.md`.

**Pre-requisites:**
*   Current codebase (Version 3 - Pre-FastAPI Refactor) committed to GitHub.
*   Necessary Python packages (`fastapi`, `uvicorn[standard]`) added to `requirements.txt` and installed in the virtual environment.
*   `a2wsgi` commented out or removed from `requirements.txt`.

---

## Phase 1: Core Application Setup & Resource Management

**Step 1.1: Modify `requirements.txt` (Completed)**
*   **Action:** Add `fastapi>=0.100.0` (or latest stable). Ensure `uvicorn[standard]` is present. Comment out `a2wsgi`.
*   **Status:** Done.

**Step 1.2: Create/Refactor Main Application File (e.g., `main_fastapi.py`)**
*   **Action:**
    *   Create a new file, `main_fastapi.py` at the project root. This will be the entry point for the FastAPI application.
    *   Alternatively, significantly refactor the existing `app.py` if it's preferred to keep that filename (though `main_fastapi.py` might be clearer during transition). For this guide, we'll assume `main_fastapi.py`.
*   **Content for `main_fastapi.py` (Initial):**
    ```python
    import asyncio
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from contextlib import asynccontextmanager
    from loguru import logger

    # Import configurations and client modules
    import config
    from config import APP_VERSION, BUILD_NUMBER # Ensure these are accessible
    # We will refactor firestore_client and llm_client to not self-initialize globals
    # but rather accept client instances or configure them via app state.

    # Placeholder for client initialization functions (to be defined/imported)
    async def initialize_firestore_client():
        from google.cloud.firestore_v1.async_client import AsyncClient as AsyncFirestoreClient
        logger.info(f"Initializing shared Firestore AsyncClient for project '{config.GCLOUD_PROJECT}'...")
        client = AsyncFirestoreClient(project=config.GCLOUD_PROJECT, database=config.FIRESTORE_DATABASE_ID or '(default)')
        logger.info("Shared Firestore AsyncClient initialized.")
        return client

    async def initialize_llm_client_config():
        from google.generativeai import configure as genai_configure
        logger.info("Configuring shared Google Generative AI (genai)...")
        api_key = config.get_google_api_key()
        if not api_key:
            logger.warning("Google API Key for GenAI not found. LLM features may fail.")
        else:
            genai_configure(api_key=api_key)
            logger.info("Shared Google Generative AI configured.")
        # Note: The actual genai.Client or GenerativeModel instances might be created per-request or as needed,
        # but the API key configuration can be global.
        # For simplicity, we might store a configured genai module or a base client on app.state if useful.

    async def close_firestore_client(client):
        if hasattr(client, 'close') and callable(client.close):
            logger.info("Closing shared Firestore AsyncClient...")
            await client.close() # Assuming google-cloud-firestore >= 2.15.0 for async close
            logger.info("Shared Firestore AsyncClient closed.")
        else:
            logger.info("Firestore client does not have an async close method or is None.")


    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: Initialize resources
        logger.info("FastAPI application startup...")
        app.state.firestore_client = await initialize_firestore_client()
        await initialize_llm_client_config() # Configure genai globally
        # If llm_client.py needs a shared genai.Client instance, initialize it here too.
        # app.state.llm_client_instance = SomeLLMClient()

        # Loguru setup (can be moved from app_factory.py here)
        # from app_factory import setup_logging # Assuming setup_logging is refactored
        # setup_logging() # Call your existing Loguru setup function

        logger.info("Resources initialized and logging configured.")
        yield
        # Shutdown: Cleanup resources
        logger.info("FastAPI application shutdown...")
        if hasattr(app.state, 'firestore_client'):
            await close_firestore_client(app.state.firestore_client)
        logger.info("Resources cleaned up.")

    app = FastAPI(lifespan=lifespan, title="WordSense Admin API", version=APP_VERSION)

    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Setup Jinja2 templates
    templates = Jinja2Templates(directory="templates")

    # TODO: Add global exception handlers (e.g., for RequestValidationError)
    # TODO: Include routers from the refactored routes files

    @app.get("/")
    async def read_root(request: Request):
        # Example: Render index.html (adapt from html_routes.py)
        return templates.TemplateResponse("index.html", {"request": request, "app_version": APP_VERSION, "build_number": BUILD_NUMBER})

    # Placeholder for where routers will be included
    # from routes_fastapi.html_routes_fastapi import router as html_router
    # app.include_router(html_router)
    # ... include other routers ...
    ```

**Step 1.3: Update Server Start Script (`run_server_asgi.sh` or `devserver.sh`)**
*   **Action:** Modify the script to use `uvicorn` to run the FastAPI application.
*   **Example for `run_server_asgi.sh`:**
    ```bash
    #!/bin/bash
    # run_server_asgi.sh - Runs the FastAPI application with Uvicorn

    PORT=${PORT:-8080} # Default to 8080 if PORT not set

    echo "Attempting to start FastAPI server on port $PORT..."

    # Find and kill any existing process on the port
    PID=$(lsof -t -i:$PORT)
    if [ -n "$PID" ]; then
        echo "Process $PID found on port $PORT. Killing it..."
        kill -9 $PID
        sleep 1 # Give OS time to release port
    fi

    echo "Starting Uvicorn server for main_fastapi:app..."
    uvicorn main_fastapi:app --host 0.0.0.0 --port $PORT --reload
    ```
*   Ensure `devserver.sh` is similarly updated or points to `run_server_asgi.sh`.

**Step 1.4: Refactor Logging Setup**
*   **Action:** Move Loguru configuration from `app_factory.py` into `main_fastapi.py` (or a dedicated `logging_config.py` imported by `main_fastapi.py`). Call the Loguru setup function early in `main_fastapi.py` or within the `lifespan` startup event.
*   Remove the old `app_factory.py` or significantly strip it down if it's no longer the entry point. The `get_db()` function will be obsolete.

---

## General Principles for Migration & Code Structure:

*   **Modularity:** Where appropriate, aim for smaller, focused files. For example, if `llm_client.py` grows too large with multiple LLM provider implementations, consider splitting it (e.g., `llm_google_client.py`, `llm_deepseek_client.py` under an `llm_providers` sub-package).
*   **Clarity over Premature Optimization:** Ensure the code is clear and easy to understand. Performance optimizations can be addressed later if specific bottlenecks are identified.
*   **Conciseness:** Remove redundant comments or overly verbose logging that doesn't add significant debugging value for typical operations. Essential error logging and key informational logs should be retained.

---

## General Principles for Migration & Code Structure:

*   **Modularity:** Where appropriate, aim for smaller, focused files. For example, if `llm_client.py` grows too large with multiple LLM provider implementations, consider splitting it (e.g., `llm_google_client.py`, `llm_deepseek_client.py` under an `llm_providers` sub-package).
*   **Clarity over Premature Optimization:** Ensure the code is clear and easy to understand. Performance optimizations can be addressed later if specific bottlenecks are identified.
*   **Conciseness:** Remove redundant comments or overly verbose logging that doesn't add significant debugging value for typical operations. Essential error logging and key informational logs should be retained. (This cleanup was partially done before this build guide was finalized).

---

## Phase 2: Client Module Refactoring

**Step 2.1: Refactor `firestore_client.py`**
*   **Action:**
    *   Remove the `get_db_client()` function.
    *   Modify all CRUD functions (e.g., `save_generated_list`, `get_master_categories`) to accept an `AsyncFirestoreClient` instance as a parameter (e.g., `async def get_master_categories(db: AsyncFirestoreClient) -> ...`).
    *   Alternatively, for functions that will only be called from within FastAPI route handlers or dependencies, they could import a shared client or use a dependency injection mechanism if we set one up. For now, passing the client as a parameter is explicit.
*   **Example Change:**
    ```python
    # In firestore_client.py
    # async def get_master_categories() -> List[VocabularyCategory]:
    # becomes:
    async def get_master_categories(db: AsyncFirestoreClient) -> List[VocabularyCategory]:
        # categories: List[VocabularyCategory] = [] # No longer need to initialize here
        # try:
        #     # db = await get_db_client() # REMOVE THIS
        # ... rest of the function uses the passed 'db' client ...
    ```

**Step 2.2: Refactor `llm_client.py`**
*   **Action:**
    *   The `configure_google_client()` function (which calls `genai.configure`) can remain, as it configures the `google.generativeai` module globally. This should be called once at app startup (done in `main_fastapi.py` lifespan).
    *   Functions like `generate_structured_content` and `_generate_googleai` use `genai.GenerativeModel()`. This part is fine as it creates model instances on the fly after global configuration.
    *   If a shared `GenAIClient` instance is preferred for other operations (e.g., listing models, managing tunings - though not currently used heavily), it could be initialized in `main_fastapi.py`'s lifespan and passed similarly to the Firestore client. For now, the existing per-call `GenerativeModel` instantiation after global `genai.configure` is likely sufficient.

---

## Phase 3: Route Conversion (Iterative, starting with List Generation)

**Step 3.1: Create FastAPI Router Structure**
*   **Action:** Create a new directory, e.g., `routers_fastapi/`.
*   For each file in `routes/` (e.g., `api_list_generation_routes.py`), create a corresponding file in `routers_fastapi/` (e.g., `list_generation_router.py`).

**Step 3.2: Convert `api_list_generation_routes.py` to FastAPI**
*   **File:** `routers_fastapi/list_generation_router.py`
*   **Actions:**
    *   Import `APIRouter` from `fastapi`.
    *   Create `router = APIRouter(prefix="/api/v1/generated-lists", tags=["Generated Lists"])`.
    *   Convert each Flask route (`@list_gen_api_bp.route(...) async def ...`) to a FastAPI route (`@router.post("/generate") async def ...`).
    *   **Request Handling:**
        *   Use Pydantic models directly in function signatures for request body validation (e.g., `input_data: GenerateListInput`).
        *   Use `Request` type hint to access `request.app.state.firestore_client`.
        *   Use `BackgroundTasks` for the background task.
    *   **Response Handling:** Return Pydantic models or dictionaries directly. FastAPI handles JSON conversion.
    *   Replace Flask's `abort()` with `raise HTTPException(...)`.
    *   Adapt helper functions like `read_instruction_file` and `generate_readable_id` (they can likely remain as is if they don't depend on Flask's `request` context).
    *   The background task function (`_generate_and_update_list`) will be refactored into `run_llm_and_update_db` and will need to accept the Firestore client and LLM client (or access them from `app.state` if passed the `Request` object or app instance).

**Step 3.3: Convert `api_categories_routes.py` to FastAPI**
*   **File:** `routers_fastapi/categories_router.py`
*   **Actions:** Similar to above. Convert routes, adapt request/response handling, use shared `AsyncFirestoreClient` passed via dependency or `request.app.state`.

**Step 3.4: Convert `api_language_pairs_routes.py` to FastAPI**
*   **File:** `routers_fastapi/language_pairs_router.py`
*   **Actions:** Similar conversion.

**Step 3.5: Convert `html_routes.py` to FastAPI**
*   **File:** `routers_fastapi/html_router.py`
*   **Actions:**
    *   Convert routes.
    *   Use `fastapi.templating.Jinja2Templates` instance (initialized in `main_fastapi.py`) to render HTML.
    *   Pass `{"request": request, ...}` as context to templates.

**Step 3.6: Include Routers in `main_fastapi.py`**
*   **Action:** In `main_fastapi.py`, import and include each new FastAPI router:
    ```python
    # from routers_fastapi.list_generation_router import router as list_gen_router
    # app.include_router(list_gen_router)
    # ... etc. for other routers
    ```

---

## Phase 4: Static Files and Templates

**Step 4.1: Static File Configuration (Completed in Step 1.2)**
*   **Action:** Ensure `app.mount("/static", StaticFiles(directory="static"), name="static")` is in `main_fastapi.py`.

**Step 4.2: Template Configuration (Completed in Step 1.2)**
*   **Action:** Ensure `templates = Jinja2Templates(directory="templates")` is in `main_fastapi.py`. Route handlers rendering HTML will use this `templates` object.

**Step 4.3: Update HTML Templates (If Necessary)**
*   **Action:** Review templates for any Flask-specific constructs (e.g., `url_for`) that might need equivalents in FastAPI (e.g., `request.url_for`). For simple URL paths, direct links might be fine. Context variables (`app_version`, `build_number`) will need to be passed from FastAPI route handlers.

---

## Phase 5: Testing and Refinement

**Step 5.1: Initial Run & Basic Testing**
*   **Action:** Start the FastAPI app using Uvicorn: `uvicorn main_fastapi:app --reload --port 8080`.
*   Test basic HTML page rendering and simple API endpoints.

**Step 5.2: Test Core Functionality (List Generation)**
*   **Action:** Thoroughly test the "Generate Vocabulary List" feature.
*   Monitor logs closely for any errors, especially related to async operations, client usage, or background tasks.
*   Verify data is correctly saved to Firestore.

**Step 5.3: Test Other API Endpoints and UI Interactions**
*   **Action:** Test category management, language pair management, etc.

**Step 5.4: Iterative Debugging and Refinement**
*   **Action:** Address any issues found during testing. This may involve further adjustments to client management, background task handling, or route logic.

---

This detailed build guide provides a roadmap for the "big bang" migration. Each step will require careful implementation and testing.
