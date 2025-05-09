# config.py
# Loads environment variables from the .env file and makes them available.
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s') # Basic config
logging.info("--- config.py: STARTING EXECUTION ---")

import os
from dotenv import load_dotenv, find_dotenv
import sys
from gcp_utils import fetch_secret # Import the new utility
from typing import Optional # Import Optional
# import pytz # Import pytz # Temporarily remove pytz import

# --- Load .env file ---
print("Searching for .env file...")
dotenv_path = find_dotenv()
if not dotenv_path:
    print("Warning: .env file not found. Relying on system environment variables.")
else:
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path, verbose=True)

# --- Retrieve required configuration ---

# Google Generative AI (Gemini) API Key
# Fetched from Google Cloud Secret Manager as per user specification
GEMINI_API_KEY_PROJECT_ID: str = "652524238030"
GEMINI_API_KEY_SECRET_ID: str = "Vocabulary-List-Gemini-ID-May-8"
GEMINI_API_KEY_VERSION_ID: str = "1"

# Define a function to fetch the key lazily
_google_api_key_cache: Optional[str] = None

def get_google_api_key() -> Optional[str]:
    """Fetches the Google API Key from Secret Manager, caching the result."""
    global _google_api_key_cache
    if _google_api_key_cache is None:
        print(f"Attempting to fetch Gemini API Key from Secret Manager: projects/{GEMINI_API_KEY_PROJECT_ID}/secrets/{GEMINI_API_KEY_SECRET_ID}/versions/{GEMINI_API_KEY_VERSION_ID}")
        _google_api_key_cache = fetch_secret(
            project_id=GEMINI_API_KEY_PROJECT_ID,
            secret_id=GEMINI_API_KEY_SECRET_ID,
            version_id=GEMINI_API_KEY_VERSION_ID
        )
        if not _google_api_key_cache:
             print("CRITICAL: GOOGLE_API_KEY not fetched from Secret Manager. Google AI models will likely be unavailable. This might be due to authentication issues (e.g., missing GOOGLE_APPLICATION_CREDENTIALS or ADC setup).")
             # Potentially raise an exception or handle more gracefully depending on desired app behavior
             # For now, returning None and letting the app decide.
        else:
             print(f"GOOGLE_API_KEY fetched from Secret Manager and cached (starts with: {_google_api_key_cache[:4]}...).")
    return _google_api_key_cache

# GOOGLE_API_KEY is now primarily accessed via get_google_api_key().
# The environment variable is a fallback if direct access is attempted, but this is discouraged.
_raw_google_api_key_env = os.environ.get('GOOGLE_API_KEY')
if _raw_google_api_key_env:
     print(f"INFO: GOOGLE_API_KEY found directly in environment (starts with: {_raw_google_api_key_env[:4]}...). This will be overridden by Secret Manager fetch if get_google_api_key() is called.")

# *** Add DeepSeek API Key ***
# This remains as an environment variable as per current structure, can be refactored later if needed
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
if not DEEPSEEK_API_KEY:
    # Allow running without DeepSeek key if Google key is present
    print("Warning: DEEPSEEK_API_KEY not found. DeepSeek models will not be available.")
else:
     print(f"DEEPSEEK_API_KEY found (starts with: {DEEPSEEK_API_KEY[:4]}...).")

# Defer the critical check until the key is actually needed and fetched by get_google_api_key()
# The check within llm_client.py configure block is now more relevant.
# if not get_google_api_key() and not DEEPSEEK_API_KEY:
#      print("CRITICAL ERROR: Neither GOOGLE_API_KEY (from Secret Manager) nor DEEPSEEK_API_KEY is available.")
#      # Avoid sys.exit here, let the application handle the lack of keys gracefully if possible.


# Google Cloud Project ID (for Firestore)
GCLOUD_PROJECT = os.environ.get('GCLOUD_PROJECT')
if not GCLOUD_PROJECT:
    print("Warning: GCLOUD_PROJECT not set in environment. Firestore client will attempt to infer it.")
else:
    print(f"GCLOUD_PROJECT: {GCLOUD_PROJECT}")


# Optional: Firestore Database ID (defaults to '(default)' if not set)
FIRESTORE_DATABASE_ID = os.environ.get('FIRESTORE_DATABASE_ID')
if FIRESTORE_DATABASE_ID:
    print(f"FIRESTORE_DATABASE_ID: {FIRESTORE_DATABASE_ID}")
else:
    print("FIRESTORE_DATABASE_ID not set, using default Firestore database.")


# --- Default LLM Provider and Model ---
# Choose which provider/model to use by default if not specified elsewhere
# Can be overridden by setting these in the .env file
DEFAULT_LLM_PROVIDER = os.environ.get('DEFAULT_LLM_PROVIDER', 'googleai') # 'googleai' or 'deepseek'
DEFAULT_GOOGLE_MODEL = os.environ.get('DEFAULT_GOOGLE_MODEL', 'gemini-1.5-flash-latest')
DEFAULT_DEEPSEEK_MODEL = os.environ.get('DEFAULT_DEEPSEEK_MODEL', 'deepseek-chat') # Or 'deepseek-coder'

print(f"Default LLM Provider: {DEFAULT_LLM_PROVIDER}")
if DEFAULT_LLM_PROVIDER == 'googleai':
    print(f"Default Google Model: {DEFAULT_GOOGLE_MODEL}")
elif DEFAULT_LLM_PROVIDER == 'deepseek':
    print(f"Default DeepSeek Model: {DEFAULT_DEEPSEEK_MODEL}")

# --- Application Version and Build Number ---
# from datetime import datetime, utcnow # Import utcnow specifically # Temporarily remove datetime import
APP_VERSION: str = "1.0.0"

# Use UTC time directly for the build number to avoid timezone issues during import
# BUILD_NUMBER: str = utcnow().strftime("%Y%m%d%H%M%SUTC") # Temporarily remove calculation
BUILD_NUMBER: str = "TEMP_BUILD_ID" # Hardcode temporarily

print(f"Application Version: {APP_VERSION}")
print(f"Build Number: {BUILD_NUMBER}")

logging.info("--- config.py: FINISHED EXECUTION ---")
print("Configuration loading complete.")
