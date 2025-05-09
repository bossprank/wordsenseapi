# Build Checklist: Admin Panel for Vocabulary List Generation & Management (Build 6)

**Version:** 1.0
**Date:** May 8, 2025
**Main Specification:** `Admin Panel for Vocabulary List Generation & Management.md.txt`

This checklist outlines the tasks required to implement the Admin Panel for Vocabulary List Generation and Management.

## Phase 1: Project Setup & Core Configuration

*   [ ] **Task 1.1: Update `config.py` for Version and Build Numbers**
    *   [ ] Add `APP_VERSION = "1.0.0"` to `config.py`.
    *   [ ] Add `BUILD_NUMBER = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")` (or similar dynamic build identifier) to `config.py`.
    *   [ ] Ensure `app.py` makes `APP_VERSION` and `BUILD_NUMBER` available to Flask templates (e.g., via `app.context_processor`).
*   [ ] **Task 1.2: Implement Google Cloud Secret Fetching for Gemini API Key**
    *   [ ] Add `google-cloud-secret-manager` to `requirements.txt`.
    *   [ ] Create a new utility function (e.g., in `gcp_utils.py` or `llm_client.py`) to fetch a secret from Google Cloud Secret Manager.
        *   Function signature: `fetch_secret(project_id: str, secret_id: str, version_id: str = "latest") -> Optional[str]`.
    *   [ ] Update `config.py`: Modify `GOOGLE_API_KEY` to be populated by calling `fetch_secret` with `projects/652524238030/secrets/Vocabulary-List-Gemini-ID-May-8/versions/1`.
    *   [ ] Ensure `llm_client.py` correctly uses the fetched `GOOGLE_API_KEY`.
*   [ ] **Task 1.3: Create `llm_prompts/` Directory**
    *   [ ] Create an empty directory named `llm_prompts` in the project root.
    *   [ ] Add a `.gitkeep` file if it's initially empty to ensure the directory is committed.
*   [ ] **Task 1.4: Logging Setup Review**
    *   [ ] Confirm all new Python modules use `logger = logging.getLogger(__name__)`.
    *   [ ] Ensure logs from new API routes and services are captured in `mylogs/main_app.log` following existing patterns in `app.py`.

## Phase 2: Pydantic Models (`models.py`)

*   [ ] **Task 2.1: Define `GeneratedWordListParameters` Model** (Corresponds to `generation_parameters` in Firestore)
    *   [ ] `list_readable_id: str`
    *   [ ] `status: str` (Consider Enum later if statuses are fixed)
    *   [ ] `language: str`
    *   [ ] `cefr_level: str`
    *   [ ] `list_category_id: str`
    *   [ ] `admin_notes: Optional[str] = None`
    *   [ ] `requested_word_count: int`
    *   [ ] `generated_word_count: Optional[int] = None`
    *   [ ] `base_instruction_file_ref: str`
    *   [ ] `custom_instruction_file_ref: Optional[str] = None`
    *   [ ] `ui_text_refinements: Optional[str] = None`
    *   [ ] `final_llm_prompt_text_sent: Optional[str] = None`
    *   [ ] `source_model: str`
    *   [ ] `gemini_temperature: float`
    *   [ ] `gemini_top_p: float`
    *   [ ] `gemini_top_k: int`
    *   [ ] `gemini_max_output_tokens: int`
    *   [ ] `gemini_stop_sequences: Optional[List[str]] = None`
    *   [ ] `gemini_response_mime_type: str`
    *   [ ] `gemini_response_schema_used: Optional[Union[Dict[str, Any], str]] = None`
    *   [ ] `include_english_translation: bool`
    *   [ ] `generation_timestamp: Optional[datetime] = None` (Handled by Firestore server timestamp on save)
    *   [ ] `last_status_update_timestamp: Optional[datetime] = None` (Handled by Firestore server timestamp on save/update)
    *   [ ] `generated_by: str`
    *   [ ] `reviewed_by: Optional[str] = None`
*   [ ] **Task 2.2: Define `WordItem` Model** (Flexible for `word_items` array)
    *   [ ] `headword: str`
    *   [ ] `translation_en: Optional[str] = None`
    *   [ ] Allow other dynamic fields: `class Config: extra = 'allow'` or use `Dict[str, Any]`.
*   [ ] **Task 2.3: Define `GeneratedWordList` Model** (Main Firestore document model)
    *   [ ] `list_firestore_id: Optional[str] = None` (Represents Firestore document ID, not stored in document fields)
    *   [ ] `generation_parameters: GeneratedWordListParameters`
    *   [ ] `word_items: List[WordItem]`
*   [ ] **Task 2.4: Define `GeneratedWordListSummary` Model** (For table views)
    *   [ ] `list_firestore_id: str`
    *   [ ] `list_readable_id: str`
    *   [ ] `language: str`
    *   [ ] `cefr_level: str`
    *   [ ] `list_category_display_name: str` (Resolved from `list_category_id`)
    *   [ ] `status: str`
    *   [ ] `generated_word_count: Optional[int] = None`
    *   [ ] `generation_timestamp: datetime`
*   [ ] **Task 2.5: Define `MasterCategory` Model** (If not already present, for `master_categories` collection)
    *   [ ] `category_id: str`
    *   [ ] `display_name: Dict[str, str]` (e.g., `{"en": "Name", "id": "Nama"}`)
    *   [ ] `description: Optional[Dict[str, str]] = None`
    *   [ ] `parent_category_id: Optional[str] = None`
    *   [ ] `created_at: Optional[datetime] = None`
    *   [ ] `updated_at: Optional[datetime] = None`

## Phase 3: Firestore Client Updates

*   [ ] **Task 3.1: Create `GeneratedWordLists` Client Functions** (in `firestore_client.py` or a new dedicated file)
    *   [ ] `COLLECTION_NAME = "GeneratedWordLists"`
    *   [ ] `async def save_generated_list(list_data: GeneratedWordList) -> Optional[GeneratedWordList]:`
        *   Handles create/update logic.
        *   Uses `SERVER_TIMESTAMP` for `generation_timestamp` (on create) and `last_status_update_timestamp`.
        *   Firestore document ID should be `list_data.generation_parameters.list_readable_id` if we want to use the human-readable ID as the Firestore doc ID, OR auto-generate Firestore ID and store `list_readable_id` as a field. Specification implies auto-generated Firestore ID.
    *   [ ] `async def get_generated_list_by_id(list_firestore_id: str) -> Optional[GeneratedWordList]:`
    *   [ ] `async def get_all_generated_lists(filters: Optional[Dict] = None, sort_by: Optional[str] = "generation_parameters.generation_timestamp", sort_direction: str = "DESCENDING", limit: Optional[int] = None, offset: Optional[int] = None) -> List[GeneratedWordListSummary]:`
        *   Handles filtering by language, CEFR, category, status.
        *   Resolves `list_category_id` to `display_name` for the summary.
        *   Implements pagination.
    *   [ ] `async def update_generated_list_metadata(list_firestore_id: str, metadata_updates: Dict) -> bool:`
        *   Updates `status`, `list_category_id`, `admin_notes`, `reviewed_by`.
        *   Updates `last_status_update_timestamp` with `SERVER_TIMESTAMP`.
    *   [ ] `async def delete_generated_list(list_firestore_id: str) -> bool:`
*   [ ] **Task 3.2: Create `master_categories` Fetch Function**
    *   [ ] `async def get_master_categories() -> List[MasterCategory]:` (Fetches all categories for dropdowns)
*   [ ] **Task 3.3: Firestore Rules (Informational - Manual Step)**
    *   [ ] Review and update Firestore security rules for `GeneratedWordLists` and `master_categories` to ensure appropriate access control for admin users.

## Phase 4: LLM Client Updates (`llm_client.py`)

*   [ ] **Task 4.1: Enhance `_generate_googleai` Function**
    *   [ ] Add parameters: `top_p: Optional[float]`, `top_k: Optional[int]`, `max_output_tokens: Optional[int]`, `stop_sequences: Optional[List[str]]`, `response_mime_type: Optional[str]`, `response_schema: Optional[Union[Dict, Type[BaseModel]]]` to the function signature.
    *   [ ] Update `GoogleGenerationConfig` (or `types.GenerateContentConfig`) instantiation to include `top_p`, `top_k`, `max_output_tokens`.
    *   [ ] Pass `stop_sequences` directly to `model.generate_content_async`.
    *   [ ] Pass `response_mime_type` and `response_schema` to `GoogleGenerationConfig` (or `types.GenerateContentConfig`).
*   [ ] **Task 4.2: Update `generate_structured_content` Function**
    *   [ ] Add the new parameters from Task 4.1 to its signature and pass them down to `_generate_googleai`.

## Phase 5: Flask Application (`app.py`) & API Endpoints

*   [ ] **Task 5.1: Implement API Endpoint - Generate New List**
    *   [ ] Route: `POST /api/v1/generated-lists`
    *   [ ] Logic:
        *   Validate input payload.
        *   Generate unique `list_readable_id`.
        *   Read content from local instruction files (`base_instruction_file_ref`, `custom_instruction_file_ref` from `llm_prompts/`).
        *   Concatenate instructions.
        *   Call `llm_client.generate_structured_content` with all parameters.
        *   Process response, create `GeneratedWordList` object.
        *   Save to Firestore using `firestore_client.save_generated_list`.
        *   Return success/failure JSON.
*   [ ] **Task 5.2: Implement API Endpoint - View Generated Lists**
    *   [ ] Route: `GET /api/v1/generated-lists`
    *   [ ] Logic:
        *   Accept query parameters for filtering, sorting, pagination.
        *   Call `firestore_client.get_all_generated_lists`.
        *   Return JSON list of `GeneratedWordListSummary`.
*   [ ] **Task 5.3: Implement API Endpoint - Get Filter Options**
    *   [ ] Route: `GET /api/v1/generated-lists/filter-options`
    *   [ ] Logic:
        *   Fetch distinct values for language, CEFR, status from `GeneratedWordLists`.
        *   Fetch all `master_categories` using `firestore_client.get_master_categories`.
        *   Return JSON for populating filter dropdowns.
*   [ ] **Task 5.4: Implement API Endpoint - View Single List Details**
    *   [ ] Route: `GET /api/v1/generated-lists/{list_firestore_id}`
    *   [ ] Logic:
        *   Call `firestore_client.get_generated_list_by_id`.
        *   Resolve category display name.
        *   Return full `GeneratedWordList` JSON.
*   [ ] **Task 5.5: Implement API Endpoint - Update List Metadata**
    *   [ ] Route: `PATCH /api/v1/generated-lists/{list_firestore_id}/metadata`
    *   [ ] Logic:
        *   Validate input payload (`status`, `list_category_id`, `admin_notes`, `reviewed_by`).
        *   Call `firestore_client.update_generated_list_metadata`.
        *   Return success/failure JSON.
*   [ ] **Task 5.6: Implement API Endpoint - Delete List**
    *   [ ] Route: `DELETE /api/v1/generated-lists/{list_firestore_id}`
    *   [ ] Logic:
        *   Call `firestore_client.delete_generated_list`.
        *   Return success/failure JSON.
*   [ ] **Task 5.7: Implement API Endpoint - Get Master Categories** (If not covered by filter options)
    *   [ ] Route: `GET /api/v1/master-categories`
    *   [ ] Logic: Call `firestore_client.get_master_categories`.

## Phase 6: HTML Templates & Frontend JavaScript

*   [ ] **Task 6.1: Update `base_adminlte.html` Footer**
    *   [ ] Modify footer to use `{{ app_version }}` and `{{ build_number }}`.
*   [ ] **Task 6.2: Create Navigation Links in Sidebar**
    *   [ ] Add a new section/item in `base_adminlte.html` sidebar for "Vocabulary Generation" linking to the main "View Generated Word Lists" screen.
*   [ ] **Task 6.3: Screen 1: Generate New Word List**
    *   [ ] HTML: `templates/generate_new_word_list.html` (extends `base_adminlte.html`).
        *   Implement form elements as per Wireframe 1.
        *   Populate Language, CEFR, Model dropdowns (static or from config).
        *   Dynamically populate List Category dropdown from `/api/v1/master-categories` or `/api/v1/generated-lists/filter-options`.
        *   Show/hide JSON Schema textarea based on Response Format.
    *   [ ] JS: `static/generate_new_word_list.js`
        *   Handle form submission.
        *   Client-side validation.
        *   AJAX call to `POST /api/v1/generated-lists`.
        *   Display success/error messages.
        *   Redirect on success (e.g., to View Lists screen).
*   [ ] **Task 6.4: Screen 2: View Generated Word Lists**
    *   [ ] HTML: `templates/view_generated_word_lists.html`
        *   Implement filter controls and table structure as per Wireframe 2.
        *   `[+ Add New Generation Task]` button links to Screen 1.
    *   [ ] JS: `static/view_generated_word_lists.js`
        *   Fetch filter options from `/api/v1/generated-lists/filter-options` to populate dropdowns.
        *   Fetch and display lists from `GET /api/v1/generated-lists` in the table.
        *   Implement client-side filtering/sorting or trigger API calls on filter changes.
        *   Handle pagination.
        *   Handle "Details", "Edit Meta", "Regen", "Delete" button actions (navigation or AJAX calls).
        *   "Regen": Navigate to Screen 1, passing parameters of the selected list.
        *   "Delete": Confirmation dialog, then AJAX call to `DELETE /api/v1/generated-lists/{id}`.
*   [ ] **Task 6.5: Screen 3: Generated Word List Details**
    *   [ ] HTML: `templates/generated_list_details.html`
        *   Display all fields from `generation_parameters` and `word_items` as per Wireframe 3.
        *   Read-only view.
    *   [ ] JS: `static/generated_list_details.js`
        *   Fetch data from `GET /api/v1/generated-lists/{list_firestore_id}` based on URL parameter.
        *   Populate the page with the fetched data.
*   [ ] **Task 6.6: Screen 4: Edit Generated List Metadata**
    *   [ ] HTML: `templates/edit_list_metadata.html`
        *   Implement form for editable fields (`Status`, `List Category`, `Administrator Notes`, `Reviewed By`) as per Wireframe 4.
        *   Display non-editable reference parameters.
    *   [ ] JS: `static/edit_list_metadata.js`
        *   Fetch current list data from `GET /api/v1/generated-lists/{list_firestore_id}` to pre-fill form.
        *   Populate Status and List Category dropdowns.
        *   Handle form submission: AJAX call to `PATCH /api/v1/generated-lists/{id}/metadata`.
        *   Display success/error messages.
        *   Redirect on success.

## Phase 7: Testing & Refinement

*   [ ] **Task 7.1: Unit Tests (Optional but Recommended)**
    *   [ ] Write unit tests for critical utility functions (e.g., secret fetching, complex logic in API handlers).
*   [ ] **Task 7.2: API Endpoint Testing**
    *   [ ] Test all API endpoints using a tool like Postman or curl with various valid and invalid inputs.
*   [ ] **Task 7.3: Frontend UI/UX Testing**
    *   [ ] Test all four screens across different browsers (if applicable).
    *   [ ] Verify form validations, data display, button actions, and overall workflow.
    *   [ ] Test responsiveness if required.
*   [ ] **Task 7.4: End-to-End Flow Testing**
    *   [ ] Test the complete flow: Generate a list -> View it -> View Details -> Edit Metadata -> Re-generate (as new) -> Delete.
*   [ ] **Task 7.5: Logging Verification**
    *   [ ] Check `mylogs/main_app.log` to ensure all actions are being logged appropriately.
*   [ ] **Task 7.6: Code Review & Refactoring**
    *   [ ] Review code for clarity, efficiency, and adherence to best practices.
    *   [ ] Refactor as needed.

This checklist provides a detailed breakdown. Each major task can be further divided into sub-tasks as development progresses.
