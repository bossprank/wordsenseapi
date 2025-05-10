# Lessons Learned: Debugging Async Flask App (2025-05-08)

> **NOTE (2025-05-10):** The project is being migrated from Flask to FastAPI.
> Many lessons here regarding LLM interaction, prompting, schema handling, and general debugging remain valuable.
> However, specific discussions and solutions related to managing async operations and event loops
> within the Flask + `a2wsgi` + Uvicorn/Hypercorn environment (particularly in Point 2 and 3)
> are superseded by FastAPI's native async capabilities.
> See `.cline/lessons_learned_fastapi_migration_20250510.md` for the new direction.

**Context:** Debugging 500 errors related to Firestore database writes and LLM calls within a Flask application that uses asynchronous operations (`async def` routes, `google-generativeai`, `google-cloud-firestore` async client).

**Initial Problem:**
*   500 errors when saving categories (`/manage-categories`).
*   Errors reported as "cannot write to database" when generating new word lists (`/generate-new-list`).
*   Initial logs checked (`mylogs/main_app_*.log`) did not contain clear tracebacks for the 500 errors.

**Debugging Steps & Findings:**

1.  **Logging Configuration:**
    *   **Issue:** The application's `logging.basicConfig` calls in `app.py` and `config.py` were configured to log to `stderr` by default, not to the expected `mylogs/main_app.log` file (despite an old log message suggesting otherwise). This prevented viewing error tracebacks in log files.
    *   **Lesson:** Verify logging configuration early. Ensure handlers (like `FileHandler`) are explicitly added if file logging is desired, rather than relying solely on `basicConfig` defaults. Check where different loggers (`root`, `__main__`, module-specific) are actually writing.

2.  **Async/Sync Firestore Client Mix:**
    *   **Observation:** `app.py` initialized and used a *synchronous* `firestore.Client` for category CRUD, while `firestore_client.py` initialized and used an *asynchronous* `firestore_v1.async_client.AsyncClient` for list generation/fetching.
    *   **Hypothesis:** Mixing sync/async clients and operations within Flask's default WSGI server environment (Werkzeug) can lead to event loop conflicts.
    *   **Lesson:** While Flask supports `async def` views, carefully manage interactions between sync and async code, especially I/O bound operations like database clients. Standardizing on async operations and running under a proper ASGI server is generally more robust.

3.  **`RuntimeError: Event loop is closed` (Firestore & LLM):**
    *   **Issue:** This error occurred first during Firestore writes (`await doc_ref.set()`) and later during LLM calls (`await model.generate_content_async()`).
    *   **Cause:** Using Flask's default Werkzeug server, `async def` views are often run in a temporary event loop via `asyncio.run()`. Global/shared async client instances (like the Firestore `AsyncClient` or potentially underlying clients used by `google-generativeai`) initialized in one request's loop become invalid when that loop closes, causing errors in subsequent requests trying to reuse the client.
    *   **Fix Attempt 1 (Flask Context):** Modify `firestore_client.py` to create a *new* `AsyncClient` instance per request (`get_db_client`). This fixed the Firestore write error but the LLM call still failed with the same error.
    *   **Fix Attempt 2 (Recommended for Flask Context - Now Superseded by FastAPI Migration):**
        <!--
        Switch from Werkzeug/`python app.py` to running the application under a proper ASGI server setup that manages the event loop correctly across the application lifetime.
        *   Added `uvicorn` and `a2wsgi` dependencies.
        *   Wrapped the Flask `app` using `asgi_app = WSGIMiddleware(app)` in `app.py`.
        *   Changed run command to `uvicorn app:asgi_app --host 0.0.0.0 --port 5000 --reload`. (Initially tried `gunicorn -k uvicorn.workers.UvicornWorker` which still failed with `TypeError`).
        -->
        _The solution at the time for Flask involved transitioning to an ASGI server with `a2wsgi`. FastAPI, being natively ASGI, will not require this specific bridging setup._
    *   **Lesson (General):** For applications heavily using `async`/`await` and async libraries, running under an ASGI server (like Uvicorn/Hypercorn) is crucial for stable event loop management. _(With FastAPI, this is the default way of running the application)._ Avoid sharing async client instances incorrectly across requests/tasks, especially with simpler WSGI servers.

4.  **LLM JSON Output Issues:**
    *   **Issue:** LLM (Gemini 1.5 Flash) returned plain text instead of JSON, despite `response_mime_type="application/json"` and `response_schema` being provided. This caused `parse_word_items` to fail.
    *   **Cause 1:** Incorrect JSON schema format (used uppercase type names like "OBJECT", "STRING" instead of lowercase "object", "string").
    *   **Fix 1:** Corrected schema types to lowercase in `llm_prompts/llm_json_format.txt`.
    *   **Cause 2:** Prompts were not sufficiently explicit about the JSON-only requirement. `llm_client.py` only added reinforcement if a Pydantic `response_model` was passed, not just a `response_schema` dict.
    *   **Fix 2:** Strengthened JSON instructions in `llm_prompts/base.txt`. Modified `llm_client.py` to add JSON reinforcement if `response_schema` is provided.
    *   **Cause 3:** `app.py`'s `parse_word_items` expected a pre-parsed dict/list when `mime_type` was JSON, but `llm_client` returned the raw JSON string.
    *   **Fix 3:** Updated `parse_word_items` to explicitly check for a string and use `json.loads()` when `mime_type` is JSON.
    *   **Lesson:** Ensure JSON schemas are correctly formatted (case-sensitive types). Be very explicit in prompts when requiring strict JSON output. Ensure parsing logic correctly handles the type returned by the LLM client (raw string vs. pre-parsed object). Enable DEBUG logging to see raw LLM prompts/responses when debugging format issues.

5.  **LLM Language Output Issues:**
    *   **Issue:** LLM generated English words instead of the requested target language (Indonesian).
    *   **Cause:** The final prompt constructed in `app.py` did not include the target language/level parameters selected by the user.
    *   **Fix:** Modified `app.py` to prepend `Target Language: ...` and `CEFR Level: ...` to the `final_prompt_text`.
    *   **Lesson:** Dynamically insert all relevant parameters (language, level, topic constraints) into the final prompt sent to the LLM. Don't rely on the LLM inferring context solely from surrounding code or metadata.

6.  **Minor Bugs:**
    *   `NameError: name 'datetime' is not defined` in `firestore_client.py`: Missing import. Fixed by adding `from datetime import datetime`.
    *   `UnboundLocalError` in `llm_client.py`: Variable used before assignment after a code modification. Fixed by reordering assignment.
    *   "Regenerate" button didn't pre-populate form: Fixed by passing list ID as query param and adding JS logic to fetch details and populate form on the generate page.

**Overall:** Debugging involved iterative refinement of logging, async handling, prompt engineering, schema validation, and parsing logic. Switching to an ASGI server setup (Uvicorn + a2wsgi) is the recommended approach for robust async handling in Flask.
