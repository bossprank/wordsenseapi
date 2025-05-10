# Lessons Learned: Async Server Setup (Flask + ASGI) - 2025-05-08

> **NOTE (2025-05-10):** The project is being migrated from Flask to FastAPI.
> Much of the specific Flask + `a2wsgi` + Uvicorn/Hypercorn setup described below
> is superseded by the native ASGI capabilities of FastAPI.
> The general problem of needing an ASGI server for async operations remains relevant,
> but the implementation details will change with FastAPI.
> See `.cline/lessons_learned_fastapi_migration_20250510.md` for the new direction.

## Context

The application uses Flask with routes that need to perform asynchronous operations, specifically calling async libraries for Google Generative AI (LLM) and Google Cloud Firestore (database). The initial setup used Flask's default WSGI server (Werkzeug) or Gunicorn (also WSGI).

## Problem Encountered

Running async operations directly within standard Flask routes under a WSGI server led to `RuntimeError: Event loop is closed` exceptions. This occurs because WSGI servers are typically synchronous and don't manage the asyncio event loop required by the async libraries.

## Solution: Transition to ASGI (Flask Context - Now Superseded by FastAPI Migration)

<!--
The solution was to switch the application from running on a WSGI server to an ASGI server, which is designed to handle asynchronous operations.

**Key Components:**

1.  **ASGI Server:** `uvicorn` was chosen as the ASGI server. It's a popular choice for running async Python web applications.
2.  **WSGI-to-ASGI Middleware:** Since Flask is natively a WSGI application, a middleware is needed to adapt it to the ASGI interface. `a2wsgi` was used for this purpose.
3.  **Application Wrapping:** In `app.py`, the Flask app instance (`app`) needs to be wrapped by the middleware:
    ```python
    from a2wsgi import WSGIMiddleware
    # ... Flask app initialization ...
    app = Flask(__name__)
    asgi_app = WSGIMiddleware(app) # Wrap the app
    ```
4.  **Server Invocation:** The server must be started using `uvicorn` and pointed to the *wrapped* ASGI application object (`asgi_app`), not the original Flask `app` object.
    ```bash
    uvicorn app:asgi_app --host 0.0.0.0 --port 5000 --reload
    ```
    *(Note: `app` refers to the filename `app.py`, and `asgi_app` refers to the variable within that file).*

**Dependencies:**

*   Ensure `uvicorn` and `a2wsgi` are added to `requirements.txt` with specific versions.
-->

## Related Issues & Learnings (Some still relevant, some Flask-specific)

*   **Port Conflicts (`Address already in use`):** When using `--reload`, the server process might not release the port immediately upon restart, causing `[Errno 98] Address already in use`.
    *   **Solution:** Development server scripts (`devserver.sh`) should include robust logic to kill existing processes on the target port before starting the new server. Using `lsof -t -i:<port>` to find the PID and `kill -9 <PID>` is more forceful than a simple `kill`. Adding a short `sleep 1` after killing can also help give the OS time to release the port.
*   **Environment Dependencies:** System tools used in scripts (like `lsof`) should ideally be included in the environment definition (e.g., `.idx/dev.nix`) to ensure they are available.
*   **Debugging:** Clear logging within the Flask app (`app.py`), async clients (`llm_client.py`, `firestore_client.py`), and the server itself (Uvicorn logs) is crucial for diagnosing issues during the transition.
*   **Client Initialization:** Ensure async clients (like Firestore's `AsyncClient`) are initialized correctly and awaited properly within `async def` routes.
