# Build 7 Checklist: Resolve ASGI Server Compatibility Issues

**Objective:** Ensure the Flask application runs correctly using an ASGI server (Uvicorn) to properly handle asynchronous operations, resolving the `TypeError: Flask.__call__() missing 1 required positional argument: 'start_response'` error encountered when running with Uvicorn/Gunicorn directly or via the standard Gunicorn Uvicorn worker.

**Context/Problem:**
The Flask application uses `async def` views (e.g., for `/api/v1/generated-lists`) which interact with asynchronous libraries (`google-generativeai`, `google-cloud-firestore` async client). Running this application under Flask's default WSGI server (Werkzeug) or standard ASGI server configurations (like `uvicorn app:app` or `gunicorn -k uvicorn.workers.UvicornWorker app:app`) leads to errors related to event loop management (`RuntimeError: Event loop is closed`) or WSGI/ASGI interface mismatches (`TypeError: Flask.__call__() missing 1 required positional argument: 'start_response'`).

**Relevant Files:**
*   `app.py`: Contains Flask app definition and routes (including async ones).
*   `llm_client.py`: Handles async calls to Google Generative AI.
*   `firestore_client.py`: Handles async calls to Firestore.
*   `requirements.txt`: Lists project dependencies.

**Proposed Solution:**
Run the Flask application using the Uvicorn ASGI server, but explicitly wrap the Flask WSGI application object using the `a2wsgi` library to provide the necessary ASGI interface compatibility.

**Steps Completed:**
1.  Added `uvicorn[standard]==0.29.0` to `requirements.txt`.
2.  Added `a2wsgi==1.8.0` to `requirements.txt`.
3.  Installed updated requirements (`source .venv/bin/activate && python -m pip install -r requirements.txt`).

**Remaining Steps:**

1.  **Modify `app.py`:**
    *   Add the import: `from a2wsgi import WSGIMiddleware` near the top.
    *   After the `app = Flask(__name__)` line, add the wrapping line: `asgi_app = WSGIMiddleware(app)`.
2.  **Modify Run Command:**
    *   Stop any currently running server process (Werkzeug, Gunicorn, or previous Uvicorn attempts). Use `fuser -k 5000/tcp` or `kill $(lsof -t -i:5000)` if needed.
    *   Start the server using Uvicorn, pointing it to the wrapped `asgi_app` object:
        ```bash
        source .venv/bin/activate && uvicorn app:asgi_app --host 0.0.0.0 --port 5000 --reload
        ```
3.  **Test Application:**
    *   Access the root URL (`/`) via the forwarded port URL (e.g., `https://5000-idx-wordsense-api-fe-...cloudworkstations.dev/`). Verify it loads without the `TypeError`.
    *   Test the "Generate New List" functionality again (e.g., Indonesian A1).
        *   Verify it completes without errors (no `Event loop is closed` or `TypeError`).
        *   Verify the generated words are in the target language (Indonesian).
        *   Verify the word list is saved correctly to Firestore.
    *   Test the "Regenerate" button functionality from the "View Generated Lists" page. Verify it pre-populates the form correctly.

**Previous Fixes Applied (Context for next LLM):**
*   Resolved initial 500 errors during Firestore writes by addressing event loop conflicts (initially by creating new async clients per request, though the ASGI server approach is preferred).
*   Corrected JSON schema format (lowercase types) in `llm_prompts/llm_json_format.txt`.
*   Strengthened JSON output instructions in `llm_prompts/base.txt` and `llm_client.py`.
*   Fixed `UnboundLocalError` in `llm_client.py`.
*   Fixed JSON string parsing logic in `app.py` (`parse_word_items`).
*   Fixed LLM generating English words by adding target language/level to the prompt in `app.py`.
*   Fixed `NameError: name 'datetime' is not defined` in `firestore_client.py`.
*   Implemented "Regenerate" button pre-population logic in frontend JavaScript.
