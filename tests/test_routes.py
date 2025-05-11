import pytest
from fastapi.testclient import TestClient
from main_fastapi import app # Import your FastAPI app instance

# Create a single TestClient instance for all tests
client = TestClient(app)

# --- HTML Page Tests ---

def test_read_main_root_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_generate_new_list_page_html():
    response = client.get("/generate-new-word-list") # Corrected path
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_view_generated_word_lists_page_html():
    response = client.get("/view-generated-word-lists")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_manage_categories_page_html():
    response = client.get("/manage-categories")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_manage_language_pairs_page_html():
    response = client.get("/manage-language-pairs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_generated_list_details_page_html():
    # This tests if the page route itself loads, not if the data for the ID is valid.
    # The JavaScript on the page would handle fetching actual data.
    response = client.get("/generated-list-details/dummy_list_id")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_edit_list_metadata_page_html():
    # Similar to above, tests the route loading.
    response = client.get("/edit-list-metadata/dummy_list_id")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

# --- API Endpoint Tests ---

# Categories API
def test_get_all_categories_api():
    response = client.get("/api/categories/")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    # Optionally, assert the structure of the response if known
    # assert isinstance(response.json(), list)

# Language Pairs API
def test_get_all_language_pairs_api():
    response = client.get("/api/language-pairs/")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    # assert isinstance(response.json(), list)

# Generated Lists API
def test_get_list_filter_options_api():
    response = client.get("/api/v1/generated-lists/filter-options")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    # Example: Check for expected keys in the response
    # data = response.json()
    # assert "categories" in data
    # assert "languages" in data

def test_get_all_generated_lists_summary_api():
    response = client.get("/api/v1/generated-lists/")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    # assert isinstance(response.json(), list)

# Example of testing a non-existent resource (parameterized route)
def test_get_generated_list_details_api_not_found():
    response = client.get("/api/v1/generated-lists/non_existent_id_123abc")
    assert response.status_code == 404 # Assuming 404 for not found
    assert "application/json" in response.headers["content-type"]
    # data = response.json()
    # assert "detail" in data

# Note: Tests for POST, PUT, PATCH, DELETE endpoints would require
# more setup, like providing request bodies and potentially mocking
# database interactions or ensuring a clean test database state.
# These examples focus on GET requests for route existence and basic responses.

# To run these tests:
# 1. Ensure pytest and httpx are installed: pip install pytest httpx
# 2. Navigate to the project root directory in your terminal.
# 3. Run the command: pytest
# 4. Check `my_test_logs/pytest_run.log` for detailed log output.
