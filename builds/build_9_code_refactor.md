# Build 9: Python Code Refactoring Plan (Flask Blueprints)

**Goal:** Improve maintainability, readability, and reduce context window usage by refactoring the large, monolithic `app.py` file into smaller, focused modules using Flask Blueprints.

**Proposed Structure:**

Create a new `routes` directory (or similar name like `views` or `controllers`) and potentially helper directories:

*   `routes/html.py`: Blueprint for basic HTML page routes (`/`, `/generate-new-list`, `/view-generated-lists`, `/list-details`, `/edit-list-metadata`, etc.).
*   `routes/api_categories.py`: Blueprint for API routes related to categories (`/api/categories/...`).
*   `routes/api_language_pairs.py`: Blueprint for API routes related to language pair configurations (`/api/language-pair-configurations/...`).
*   `routes/api_list_generation.py`: Blueprint for API routes related to generated lists (`/api/v1/generated-lists/...`).
*   `app_factory.py` (or `app_setup.py`): Function to create and configure the Flask app instance (including loading config, initializing extensions like Firestore client (if applicable), registering blueprints, setting up context processors, error handlers).
*   `helpers/` (Optional): Directory for helper functions currently in `app.py` (like `get_db`, `read_instruction_file`, `generate_readable_id`, `parse_word_items`) if they aren't tied to a specific blueprint.
*   `errors.py` (Optional): Centralized error handlers (`@app.errorhandler`).

**Refactoring Steps:**

1.  [ ] Create the `routes` directory (and potentially `helpers`, `errors`).
2.  [ ] Create `app_factory.py` (or similar). Define a `create_app()` function. Move Flask app instantiation (`app = Flask(__name__)`), config loading, context processor (`inject_global_vars`), and potentially Firestore client initialization (or pass client instance) into this function.
3.  [ ] Move error handlers (`@app.errorhandler`) from `app.py` into `app_factory.py` (registered on the app instance) or a separate `errors.py` (registered via a blueprint or directly).
4.  [ ] Create Blueprint files (`routes/html.py`, `routes/api_categories.py`, etc.).
5.  [ ] Define a `Flask.Blueprint` instance in each new route file.
6.  [ ] Move the relevant route functions (`@app.route(...)` or `@blueprint.route(...)`) from `app.py` into the corresponding Blueprint file. Change `@app.route` decorators to `@blueprint_name.route`.
7.  [ ] Move necessary imports and helper functions specific to those routes into the respective Blueprint files or into shared `helpers/` modules.
8.  [ ] In `app_factory.py`, import the Blueprints and register them with the app instance using `app.register_blueprint()`.
9.  [ ] Update the main entry point (e.g., potentially `app.py` becomes very minimal, just calling `create_app()`, or modify how Uvicorn/Gunicorn target the app) to use the `create_app` factory. Ensure `asgi_app = WSGIMiddleware(app)` uses the app returned by the factory.
10. [ ] Update imports across all modified files (`app_factory.py`, blueprint files, helper files) to reflect the new structure.
11. [ ] Test thoroughly: Run the server, access all pages and API endpoints, test all functionalities (CRUD operations, list generation) to ensure everything works as before.

**Benefits:**

*   Smaller, more focused files are easier to read, understand, and modify.
*   Reduced context window size needed when working on a specific feature area (e.g., category API).
*   Improved code organization and separation of concerns.
*   Easier testing of individual components (Blueprints).
