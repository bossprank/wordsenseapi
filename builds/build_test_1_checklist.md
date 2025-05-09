# Build Test 1 Checklist: Initial Test Suite

**Objective:** Define a set of initial tests to verify core functionality and prevent regressions after code changes, based on issues encountered during recent debugging sessions.

**Testing Framework:** (To be decided - e.g., `pytest`, Python's `unittest`)

**Test Categories:**

**1. Configuration & Initialization:**
    *   `test_config_loading`: Verify `config.py` loads environment variables (`.env`) correctly (check `GCLOUD_PROJECT`, `FIRESTORE_DATABASE_ID`, API key presence).
    *   `test_firestore_sync_client_init`: Verify the synchronous Firestore client (`db` in `app.py`) initializes without errors.
    *   `test_firestore_async_client_init`: Verify the asynchronous Firestore client (`_db_client` via `get_db_client()` in `firestore_client.py`) initializes without errors.
    *   `test_llm_client_init`: Verify `llm_client.py` can configure Google and DeepSeek clients (check for API keys, handle missing keys gracefully).
    *   `test_logging_setup`: Verify logging is configured as expected (e.g., level, handler - potentially mock handlers/check stream output).

**2. API Endpoint Tests (using Flask test client or `requests`):**

    *   **Category API (`/api/categories`):**
        *   `test_get_categories_empty`: Test GET when no categories exist.
        *   `test_create_category_success`: Test POST with valid data. Verify 201 status and returned data. Check Firestore directly.
        *   `test_create_category_duplicate`: Test POST with an existing ID. Verify 409 status.
        *   `test_create_category_invalid_data`: Test POST with invalid data (missing fields, wrong types). Verify 400 status.
        *   `test_get_category_exists`: Test GET with a valid ID. Verify 200 status and correct data.
        *   `test_get_category_not_found`: Test GET with an invalid ID. Verify 404 status.
        *   `test_update_category_success`: Test PUT with valid data on an existing category. Verify 200 status and updated data. Check Firestore.
        *   `test_update_category_not_found`: Test PUT with an invalid ID. Verify 404 status.
        *   `test_update_category_invalid_data`: Test PUT with invalid data. Verify 400 status.
        *   `test_delete_category_success`: Test DELETE on an existing category. Verify 200 status. Check Firestore.
        *   `test_delete_category_not_found`: Test DELETE with an invalid ID. Verify 404 status.
        *   `test_get_categories_filtered`: Test GET with `?lang=` filter. Verify correct filtering.

    *   **Language Pair API (`/api/language-pair-configurations`):**
        *   (Similar tests as Category API: GET all, POST valid/invalid, GET one, PUT valid/invalid, DELETE)

    *   **Generated List API (`/api/v1/generated-lists`):**
        *   `test_generate_list_success`: Test POST with valid parameters (including schema). Mock the LLM call to return valid JSON. Verify 201 status, correct Firestore document structure (header + word items), and correct `generated_word_count`.
        *   `test_generate_list_llm_json_error`: Test POST. Mock LLM call to return invalid JSON/string. Verify 500 status (or specific error handling if added) and that Firestore document is *not* created or has 0 words.
        *   `test_generate_list_llm_language_error`: Test POST for a specific language. Mock LLM call to return English words. Verify saved `word_items` contain English (demonstrates need for prompt fix). *Note: This test might become obsolete once the prompt fix is verified.*
        *   `test_generate_list_firestore_error`: Test POST. Mock `firestore_client.save_generated_list` to raise an exception. Verify 500 status.
        *   `test_generate_list_invalid_input`: Test POST with invalid input data (missing fields, bad schema). Verify 400 status.
        *   `test_get_lists_empty`: Test GET when no lists exist.
        *   `test_get_lists_with_data`: Test GET after creating lists. Verify summaries are returned correctly.
        *   `test_get_lists_filtering`: Test GET with various filters (`language`, `cefr_level`, `status`, `list_category_id`). Verify correct filtering.
        *   `test_get_lists_sorting`: Test GET with `sort_by` and `sort_dir`. Verify correct sorting.
        *   `test_get_lists_pagination`: Test GET with `limit` and `offset`. Verify correct pagination. *(Requires API support for total count)*.
        *   `test_get_list_detail_success`: Test GET `/<id>` for an existing list. Verify full data is returned.
        *   `test_get_list_detail_not_found`: Test GET `/<id>` for non-existent list. Verify 404.
        *   `test_update_metadata_success`: Test PATCH `/<id>/metadata` with valid updates. Verify 200 status and check Firestore for changes.
        *   `test_update_metadata_not_found`: Test PATCH `/<id>/metadata` for non-existent list. Verify 404.
        *   `test_delete_list_success`: Test DELETE `/<id>` for existing list. Verify 200 status and check Firestore.
        *   `test_delete_list_not_found`: Test DELETE `/<id>` for non-existent list. Verify 404.
        *   `test_get_filter_options`: Test GET `/filter-options`. Verify expected structure and data types.

**3. Frontend Interaction Tests (Optional - using Selenium/Puppeteer):**

    *   `test_regenerate_button_flow`:
        *   Load `/view-generated-lists`.
        *   Click a "Regen" button.
        *   Verify URL changes to `/generate-new-list?regenerate_id=...`.
        *   Verify the form on the generate page is pre-populated with data fetched from the API for that ID.

**4. Async Handling Tests (Requires ASGI server setup):**

    *   `test_concurrent_generation_requests`: Simulate multiple concurrent POST requests to `/api/v1/generated-lists`. Verify all complete successfully without event loop errors (requires running tests against the ASGI server).
    *   `test_mixed_sync_async_requests`: Simulate concurrent requests to sync endpoints (e.g., `/api/categories`) and async endpoints (e.g., `/api/v1/generated-lists`). Verify correct operation without errors.

**Notes:**
*   LLM and Firestore interactions should be mocked during unit/integration tests to avoid external dependencies and costs.
*   Focus initially on API tests as they cover backend logic directly.
*   These tests cover issues encountered during debugging (logging, async, LLM format, prompt data, CRUD operations). Expand as new features are added.
