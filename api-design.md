# Word Enrichment API Design Document

## 1. Introduction

This document describes the design and structure of the Word Enrichment API. The API is built using Flask and provides endpoints for enriching words with additional information.

## 2. Project Structure

The project follows a standard structure for a Python Flask application:

```
.
├── .gitignore
├── app.py                  # Empty file, likely placeholder or not used
├── config.py               # Configuration settings (e.g., GCLOUD_PROJECT)
├── devserver.sh            # Script for running the development server
├── firestore_client.py     # Client for interacting with Firestore (likely for data storage)
├── llm_client.py           # Client for interacting with a Language Model (likely for enrichment logic)
├── main_enrichment.py      # Core logic for the word enrichment process
├── main.py                 # Main Flask application entry point and API endpoint definitions
├── models.py               # Pydantic models for data validation and serialization
├── README.md               # Project README
├── requirements.txt        # Python dependencies
├── run_model_tests.sh      # Script for running model tests
├── setup_flask_app.sh      # Script for setting up the Flask app
├── setup_flask_project.sh  # Script for setting up the Flask project
├── test_model.py           # Tests for the data models
├── mylogs/                 # Directory for application logs
│   └── main_app.log        # Main application log file
├── static/                 # Static files (CSS, JS)
│   ├── app.js
│   └── style.css
└── templates/              # HTML templates
    └── index.html
```

## 3. Purpose

The primary purpose of this API is to receive a word and associated parameters (like language and categories) and return an "enriched" version of that word, likely containing definitions, synonyms, translations, or other relevant linguistic information. It acts as a backend service for a potential frontend application (indicated by the `static` and `templates` directories).

## 4. Code Connections and Dependencies

The core `main.py` file orchestrates the API by importing and utilizing functionality from other modules:

*   **`models.py`**: Defines the data structures used for input validation (`EnrichmentInput`) and output serialization (`Word`, `EnrichmentInfo`). This ensures data consistency and type safety.
*   **`main_enrichment.py`**: Contains the main business logic for performing the word enrichment. The `run_enrichment_for_word` function is the key entry point called by the API handler.
*   **`config.py`**: Provides configuration settings, such as the Google Cloud project ID (`GCLOUD_PROJECT`).
*   **`firestore_client.py`**: Likely handles interactions with a Firestore database, potentially for storing enriched words or fetching existing data.
*   **`llm_client.py`**: Likely handles communication with a Language Model, which is probably used to generate the enrichment data.

The API also uses standard libraries like `flask` for the web framework, `pydantic` for data validation, `asyncio` for asynchronous operations, `logging` for application logging, and `uuid` for generating unique request IDs.

## 5. Basic Functions (API Endpoints)

The API exposes the following endpoints:

*   **`POST /api/v1/enrich`**:
    *   **Purpose**: Triggers the word enrichment process.
    *   **Input**: Expects a JSON payload validated against the `EnrichmentInput` model (defined in `models.py`). This payload includes the `headword`, `language`, `target_language`, and optional `categories`, `provider`, and `force_reenrich` flags.
    *   **Process**: Validates the input, generates a request ID and batch information, calls the `run_enrichment_for_word` function from `main_enrichment.py`, and serializes the result using `model_dump()` from the `Word` model.
    *   **Output**: Returns a JSON response containing the enriched word data (based on the `Word` model) on success (200 OK). Returns appropriate JSON error responses for missing body (400 Bad Request), JSON parsing errors (400 Bad Request), validation errors (422 Unprocessable Entity), internal enrichment failures (503 Service Unavailable), or unexpected server errors (500 Internal Server Error).
*   **`GET /health`**:
    *   **Purpose**: Provides a basic health check for the API.
    *   **Output**: Returns a JSON response with status "ok" and the configured project name (200 OK).
*   **`GET /`**:
    *   **Purpose**: A simple welcome endpoint.
    *   **Output**: Returns a plain text greeting message including the project name (200 OK).

## 6. Logging

The application is configured to use Python's built-in `logging` module with a `RotatingFileHandler` to write logs to `mylogs/main_app.log`. Logs include timestamps, logger names, log levels, and messages, with unique request IDs (`RID-`) added to logs within the `/api/v1/enrich` handler for traceability.