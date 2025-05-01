# test_model.py
# Tests a single Gemini model API call.
# Takes the model name as a command-line argument.

import google.generativeai as genai
import sys
import os
from dotenv import load_dotenv, find_dotenv

def run_test(model_name: str):
    """Attempts a simple generation task with the specified model."""
    print(f"--- Testing Model: {model_name} ---")

    # --- Load API Key ---
    print("Loading environment variables...")
    dotenv_path = find_dotenv()
    if not dotenv_path:
        print("Warning: .env file not found.")
    else:
        print(f"Loading .env from: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path)

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("FAILURE: GOOGLE_API_KEY not found in environment.")
        return False

    # --- Configure SDK ---
    try:
        genai.configure(api_key=api_key)
        print("SDK Configured.")
    except Exception as e:
        print(f"FAILURE: Error configuring SDK: {e}")
        return False

    # --- Generate Content ---
    try:
        print("Initializing model...")
        model = genai.GenerativeModel(model_name)
        print("Attempting to generate content...")
        # Use a simple, non-controversial prompt
        response = model.generate_content("Explain what an API key is in one sentence.")

        # Check if response has text (basic success indicator)
        _ = response.text # Accessing .text will raise an error if generation failed badly
        print(f"SUCCESS: Model '{model_name}' generated a response.")
        # print(f"Response Snippet: {response.text[:100]}...") # Optional: print snippet
        return True

    except Exception as e:
        print(f"FAILURE: Error during generation with model '{model_name}': {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_model.py <model_name>")
        sys.exit(1)

    model_to_test = sys.argv[1]
    success = run_test(model_to_test)

    # Exit with status 0 on success, 1 on failure
    sys.exit(0 if success else 1)
