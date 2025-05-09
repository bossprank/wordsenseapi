# Lessons Learned: Vocabulary List Generation - 2025-05-08

## Context

The application features a core function to generate vocabulary lists using an LLM (Google Gemini) based on user inputs (language, CEFR level, category, word count) and save the results to Firestore.

## Challenges & Solutions

1.  **LLM Output Formatting:**
    *   **Problem:** The LLM initially returned plain strings or improperly formatted JSON instead of the expected structured JSON object containing a list of words with translations.
    *   **Solution:**
        *   **Prompt Engineering:** Significantly strengthened the instructions in the base prompt (`llm_prompts/base.txt`) to explicitly demand JSON output matching a specific schema. Added examples and constraints.
        *   **Schema Definition:** Provided a clear JSON schema definition (`llm_prompts/llm_json_format.txt`) and ensured it was correctly passed to the LLM client (`llm_client.py`) when `response_mime_type` was `application/json`. Corrected schema types (e.g., using lowercase `string`, `object`, `array`).
        *   **Backend Parsing:** Implemented robust parsing logic in `app.py` (`parse_word_items` function) to handle potential variations in LLM output, including stripping markdown code fences (```json ... ```) before attempting `json.loads()`. Added error handling for `JSONDecodeError`.

2.  **Incorrect Language/Content:**
    *   **Problem:** The LLM sometimes generated words in the wrong language or for a different CEFR level than requested.
    *   **Solution:** Modified the prompt construction logic in `app.py` to explicitly include the target language (full name and code) and CEFR level at the beginning of the final prompt sent to the LLM.

3.  **Backend Errors:**
    *   **Problem:** Encountered Python errors like `UnboundLocalError` in `llm_client.py` (variable accessed before assignment in an exception path) and `NameError` (missing imports like `datetime` in `firestore_client.py`).
    *   **Solution:** Standard debugging - corrected variable scopes, added missing imports.

4.  **Frontend "Regenerate" Flow:**
    *   **Problem:** The "Regenerate" button on the "View Generated Lists" page initially didn't correctly link to the generation page or pre-populate the form with the parameters of the list being regenerated.
    *   **Solution:**
        *   Modified the link generation in `static/view_generated_word_lists.js` to correctly construct the URL for the `/generate-new-list` page, including the `regenerate_id` query parameter.
        *   Added logic to `static/generate_new_word_list.js` to detect the `regenerate_id` parameter on page load, fetch the details of the corresponding list via the API, and use that data to pre-fill the form fields.

5.  **Saving to Firestore (Async Context):**
    *   **Problem:** Initial attempts to save the generated list using the async Firestore client (`firestore_client.save_generated_list`) failed within the Flask/WSGI context due to event loop issues (See `lessons_learned_async_server_20250508.md`).
    *   **Solution:** Transitioned the application server to ASGI (Uvicorn + `a2wsgi`), allowing the `async def` route (`generate_list` in `app.py`) to correctly `await` the `save_generated_list` function.

## Key Takeaways

*   LLM interaction requires precise prompting, clear schema definition, and robust backend parsing/validation.
*   Always include all necessary context (language, level, topic) explicitly in LLM prompts.
*   Frontend logic must correctly handle data flow between different views (e.g., list view -> regeneration form).
*   Asynchronous operations in Python web frameworks require careful consideration of the server type (WSGI vs. ASGI) and event loop management.
