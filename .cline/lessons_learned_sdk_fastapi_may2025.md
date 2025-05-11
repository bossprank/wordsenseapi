# Lessons Learned: FastAPI Migration & SDK Integration (May 2025)

This document summarizes key challenges, solutions, and insights gained during the FastAPI migration and associated SDK integration efforts in May 2025.

## 1. FastAPI URL Generation (`url_for` equivalent)

*   **Challenge**: Flask's `url_for()` is not directly available in FastAPI. Jinja2 templates needed a new way to generate URLs for routes and static files.
*   **Solution**:
    *   Utilized `request.url_for('route_name')` for named routes defined in FastAPI routers.
    *   Used `request.url_for('static', path='filename.js')` for static files.
    *   This required ensuring the `Request` object was passed to the template context.
*   **Lesson**: FastAPI's URL generation is tied to the `Request` object and router setup. Consistent naming of routes and understanding of how `StaticFiles` is mounted are crucial.

## 2. Pydantic Model Validation and Error Handling

*   **Challenge**: Multiple `ValidationError` and `AttributeError` instances arose due to mismatches between data structures and Pydantic model definitions.
    *   `AttributeError: 'GenerateListInput' object has no attribute 'provider'`: The `provider` field was expected by `llm_client.py` but missing in the `GenerateListInput` model.
    *   `ValidationError: ... provider Extra inputs are not permitted`: The `provider` field was added to `GenerateListInput` but not to `GeneratedWordListParameters` where it was also needed.
    *   `NameError: name 'ValidationError' is not defined`: `ValidationError` was used in `try-except` blocks without being imported from `pydantic`.
*   **Solution**:
    *   Carefully added missing fields (`provider`) to the relevant Pydantic models (`GenerateListInput`, `GeneratedWordListParameters`).
    *   Ensured `model_config = ConfigDict(extra='forbid')` was used where appropriate to catch unexpected fields, but also understood that this requires all fields passed during model instantiation to be defined in the model.
    *   Imported `ValidationError` from `pydantic` in files where it was caught.
*   **Lesson**: Strict Pydantic models (`extra='forbid'`) are good for data integrity but require careful synchronization between data sources, data transformation steps, and all model definitions involved. Ensure all models that handle a piece of data (even if just passing it through) are aware of all its fields.

## 3. Google Generative AI SDK - JSON Schema Handling

*   **Challenge**: The Google AI SDK raised `ValueError: Unknown field for Schema: $defs` when using a Pydantic-generated JSON schema (`LlmSimpleWordList.model_json_schema()`).
*   **Solution**:
    *   The issue was that Pydantic's `model_json_schema()` can produce schemas with features (like `$defs`) not directly supported by the Google AI API's `response_schema` parameter.
    *   The fix involved prioritizing a user-provided schema string (from `llm_prompts/default_word_list_schema.json`, which is known to be compatible) in `llm_client.py`. The client now attempts to load and use this schema first, falling back to the Pydantic-generated one only if necessary.
*   **Lesson**: When an SDK expects a JSON schema, it might have specific constraints on the schema version or supported keywords. Directly using a Pydantic-generated schema might not always work. It's often safer to use a manually crafted, known-good schema string or dictionary that adheres to the SDK's specific requirements.

## 4. FastAPI Route Ordering

*   **Challenge**: A 404 error occurred for `/api/v1/generated-lists/filter-options` because it was being incorrectly matched by the parameterized route `GET /api/v1/generated-lists/{list_id}`.
*   **Solution**: Reordered routes in `routers_fastapi/list_generation_router.py` to define specific paths (like `/filter-options`) *before* more general parameterized paths (like `/{list_id}`).
*   **Lesson**: FastAPI matches routes in the order they are registered. Path parameters can be greedy, so more specific routes must always come before routes with similar base paths but trailing path parameters.

## 5. Frontend Data Access and Display

*   **Challenge**:
    *   UI showed "ID: undefined" because JavaScript was accessing `result.list_readable_id` while the API returned it nested as `result.generation_parameters.list_readable_id`.
    *   "Error Loading Details" on the list details page due to JavaScript expecting a `{ "details": ..., "summary": ... }` structure, but the API returned a flat `GeneratedWordList` object.
    *   Comment artifacts (`{# ... #}`) from template literals in JavaScript were rendering in the UI.
    *   Incorrect data path for English translations (`item.translation_en` instead of `item.translations.en`).
*   **Solution**:
    *   Corrected JavaScript data access paths to match the actual API response structures.
    *   Removed comment artifacts from JavaScript template literals.
    *   Added verbose `console.log` statements to help debug API response structures on the client-side.
*   **Lesson**: Frontend JavaScript must be kept in sync with backend API response models. Client-side logging of received data is invaluable for debugging discrepancies. Be careful with comments within template literals in JS.

## 6. Python Syntax Errors During Development

*   **Challenge**: Several `SyntaxError` instances occurred (e.g., `unmatched ')'`, `'(' was never closed`), often due to small mistakes during refactoring or applying diffs. These blocked server startup/reloads.
*   **Solution**: Careful review of the code around the line indicated by the traceback, paying attention to parentheses, indentation, and trailing characters. Using an IDE with good Python linting helps catch these early.
*   **Lesson**: Even minor syntax issues can halt development. Uvicorn's auto-reloader is helpful but will fail if the code has syntax errors. Iterative, small changes can sometimes be easier to debug than large refactors.

## 7. Readable ID Generation

*   **Challenge**: The `list_readable_id` was initially a UUID segment and needed to be changed to `LanguageCode-CEFRLevel-DDMMYYHHMM`.
*   **Solution**: Modified the `generate_readable_id` helper function in `routers_fastapi/list_generation_router.py` to accept language, CEFR level, and a timestamp, and to format the ID accordingly. This involved importing `datetime` and using `strftime`.
*   **Lesson**: Helper functions for specific formatting tasks should be designed to take necessary inputs. Generating timestamps (`datetime.utcnow()`) at the point of ID creation is a common pattern.
