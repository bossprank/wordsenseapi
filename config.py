# config.py
# Loads environment variables from the .env file and makes them available.

import os
from dotenv import load_dotenv, find_dotenv
import sys

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
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    # Allow running without Google key if DeepSeek key is present
    print("Warning: GOOGLE_API_KEY not found. Google AI models will not be available.")
else:
    print(f"GOOGLE_API_KEY found (starts with: {GOOGLE_API_KEY[:4]}...).")

# *** Add DeepSeek API Key ***
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
if not DEEPSEEK_API_KEY:
    # Allow running without DeepSeek key if Google key is present
    print("Warning: DEEPSEEK_API_KEY not found. DeepSeek models will not be available.")
else:
     print(f"DEEPSEEK_API_KEY found (starts with: {DEEPSEEK_API_KEY[:4]}...).")

# Ensure at least one key is present
if not GOOGLE_API_KEY and not DEEPSEEK_API_KEY:
     print("CRITICAL ERROR: Neither GOOGLE_API_KEY nor DEEPSEEK_API_KEY is set.")
     sys.exit("Exiting: At least one LLM API key is required.")


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


print("Configuration loading complete.")
