# Build 9: Python Code Refactoring Plan (Flask Blueprints for app.py)

**Goal:** Improve maintainability, readability, and reduce context window usage by refactoring the `app.py` file (excluding `main.py`'s word enrichment routes) into smaller, focused modules using Flask Blueprints and an application factory pattern.

**Scope:** This refactor targets `app.py` and its routes related to the Admin Panel (HTML pages, Categories API, Language Pairs API, new Vocabulary List Generation Admin API). The existing `main.py` (with the `/api/v1/enrich` endpoint) and `main_enrichment.py` will **not** be modified in this build.

**Proposed New Files/Directories:**
*   `project_root/app_factory.py`: Will contain the `create_app()` function.
*   `project_root/routes/`: Directory to hold blueprint modules.
    *   `routes/html_routes.py`
    *   `routes/api_list_generation_routes.py`
    *   `routes/api_categories_routes.py`
    *   `routes/api_language_pairs_routes.py`

**Detailed Plan (Phased Approach - Complex First):**

**Phase 1: Implement App Factory and Core Structure (`app_factory.py`)**
1.  **Create `app_factory.py`:**
    *   Define a function `create_app()`.
    *   **Move Core App Initialization from `app.py` into `create_app()`:**
        *   Flask app instantiation: `app = Flask(__name__)`.
        *   Import `config` from `config.py`; make `APP_VERSION`, `BUILD_NUMBER`, `GCLOUD_PROJECT` available (e.g., by attaching to `app` or via context processor).
        *   **Firestore Client:** Initialize `db = firestore.Client(...)` and attach to the app: `app.db = db`.
        *   **`get_db()` Helper:** Move `get_db()` from `app.py` here. Modify it to use `current_app.db` (requires `from flask import current_app`). This function will be imported by blueprints.
        *   **Log Rotation:** Move the `rotate_log_file()` function and its initial call from `app.py` to the start of `create_app()`.
        *   **Context Processor:** Move `inject_global_vars()` from `app.py` and register it with `app`.
        *   **Error Handlers:** Move all `@app.errorhandler` functions from `app.py` and register them with `app`.
    *   **Blueprint Registration:** This function will import and register all the blueprints created in subsequent phases.
    *   **ASGI Wrapping:** Add `from a2wsgi import WSGIMiddleware` and `asgi_app = WSGIMiddleware(app)`. The `create_app()` function will return this `asgi_app`.
2.  **Modify `app.py` (to become a minimal entry point):**
    *   Remove all routes, most helper functions, error handlers, context processors, and app configuration logic that has been moved to `app_factory.py` or will be moved to blueprints.
    *   `app.py` will primarily:
        *   Handle `sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))` (if still needed).
        *   Import `create_app` from `app_factory`.
        *   Call `asgi_app = create_app()`. This `asgi_app` is what Uvicorn in `devserver.sh` will target.
    *   The `if __name__ == '__main__':` block will be removed from `app.py`.

**Phase 2: Vocabulary List Generation API Blueprint (`routes/api_list_generation_routes.py`)**
1.  Create `routes/api_list_generation_routes.py`.
2.  Define `list_gen_api_bp = Blueprint('list_gen_api', __name__, url_prefix='/api/v1/generated-lists')`.
3.  Move all `async def` routes from `app.py` that handle `/api/v1/generated-lists/...`.
4.  Change route decorators from `@app.route` to `@list_gen_api_bp.route`.
5.  Move helper functions from `app.py` specific to these routes (e.g., `read_instruction_file`, `generate_readable_id`, `parse_word_items`) into this file.
6.  Update imports: `Blueprint`, `jsonify`, `request`, `abort`, `current_app`, `asyncio`, Pydantic models from `models.py`, `firestore_client`, `llm_client`, and `get_db` from `app_factory`.
7.  In `app_factory.py` (within `create_app()`): Import and register `list_gen_api_bp`.

**Phase 3: Categories API Blueprint (`routes/api_categories_routes.py`)**
1.  Create `routes/api_categories_routes.py`.
2.  Define `categories_api_bp = Blueprint('categories_api', __name__, url_prefix='/api/categories')`.
3.  Move all routes from `app.py` for `/api/categories/...`.
4.  Update decorators and imports (using `get_db` from `app_factory`).
5.  Register `categories_api_bp` in `app_factory.py`.

**Phase 4: Language Pairs API Blueprint (`routes/api_language_pairs_routes.py`)**
1.  Create `routes/api_language_pairs_routes.py`.
2.  Define `lang_pairs_api_bp = Blueprint('lang_pairs_api', __name__, url_prefix='/api/language-pair-configurations')`.
3.  Move all routes from `app.py` for `/api/language-pair-configurations/...`.
4.  Update decorators and imports.
5.  Register `lang_pairs_api_bp` in `app_factory.py`.

**Phase 5: HTML Serving Routes Blueprint (`routes/html_routes.py`)**
1.  Create `routes/html_routes.py`.
2.  Define `html_bp = Blueprint('html', __name__)`.
3.  Move all remaining HTML page-serving routes from `app.py`.
4.  Update decorators and imports (mainly `render_template`, `logger`).
5.  Register `html_bp` in `app_factory.py`.

**Phase 6: Final Review and Import Adjustments**
1.  Meticulously review `app.py`, `app_factory.py`, and all `routes/*.py` files for correct import statements, removal of unused imports, and ensuring `app.py` is minimal.
2.  Confirm `devserver.sh` correctly targets `asgi_app` from the updated `app.py`.

**Testing Strategy (Post-Refactor):**
*   Start server with `devserver.sh`.
*   Test all Admin Panel HTML pages.
*   Test all Admin Panel API functionalities (CRUD for categories, language pairs; all operations for vocabulary list generation).
*   Check application logs (`mylogs/main_app.log`) for errors.
