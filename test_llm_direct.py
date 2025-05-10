import asyncio
import sys
import os
import json # Added import for json.dumps
from loguru import logger

# --- Minimal Loguru Setup ---
LOGURU_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
logger.remove()
logger.add(sys.stderr, level="DEBUG", format=LOGURU_FORMAT, colorize=True)
logger.info("Loguru configured for test_llm_direct.py")

# --- Imports from project ---
try:
    import config
    from llm_client import generate_structured_content, configure_google_client, _clean_llm_json_output
    from models import LlmWordListResponse # Using existing model for a more relevant test
    from pydantic import BaseModel, ValidationError
    from typing import List, Dict, Any
except ImportError as e:
    logger.critical(f"Failed to import necessary modules: {e}")
    logger.critical("Ensure your PYTHONPATH is set correctly or run from the project root.")
    sys.exit(1)

# --- Test Pydantic Model (using LlmWordListResponse from models.py) ---
# We will use the existing LlmWordListResponse for a more direct test of the actual use case.

async def main():
    logger.info("--- Starting Direct LLM Test ---")

    # 1. Configure Google Client (which includes fetching API key)
    logger.info("Attempting to configure Google client (fetches API key)...")
    if not configure_google_client():
        logger.error("Failed to configure Google client. API key might be missing or invalid.")
        return
    logger.info("Google client configured (API key should be loaded).")

    # 2. Define a test prompt and parameters
    # This prompt is simplified but aims for the LlmWordListResponse structure.
    test_prompt = """
    Generate a list of 2 common English words related to "technology".
    For each word, provide:
    - word (string, the word itself)
    - part_of_speech (string, e.g., "noun", "verb")
    - definition (string, a concise definition)
    - example_sentence (string, an example sentence using the word)
    - difficulty_level (integer, 1-5, 5 being most difficult)
    - cefr_level (string, e.g., "A1", "B2")
    - translations (object, with a key "es" for Spanish translation string)

    Your entire response MUST be a single, valid JSON object conforming to the schema for LlmWordListResponse,
    which expects a root key "words" containing a list of these word objects.
    Do not include any text, comments, explanations, apologies, or markdown formatting (like ```json)
    outside the main JSON object itself.
    """
    
    logger.info(f"Test prompt:\n{test_prompt}")

    # --- Print the generated schema for debugging ---
    try:
        schema_json = LlmWordListResponse.model_json_schema()
        logger.debug(f"Generated JSON Schema for LlmWordListResponse:\n{json.dumps(schema_json, indent=2)}")
    except Exception as e_schema:
        logger.error(f"Could not generate/print JSON schema: {e_schema}")
    # --- End schema printing ---

    # Parameters for generate_structured_content
    # Using LlmWordListResponse as the response_model
    # The schema for LlmWordListResponse will be automatically used by generate_structured_content
    # if response_mime_type is "application/json" (which it defaults to if response_schema is a Pydantic model)

    try:
        logger.info("Calling generate_structured_content...")
        result = await generate_structured_content(
            prompt=test_prompt,
            response_model=LlmWordListResponse, # Expecting this Pydantic model
            provider='googleai',
            model_name='gemini-1.5-flash-latest', # Using a known fast model
            temperature=0.5,
            # Ensure response_mime_type is set if not automatically inferred for JSON output
            response_mime_type="application/json", 
            # response_schema can be explicitly LlmWordListResponse.model_json_schema() or the model itself
            response_schema=LlmWordListResponse 
        )

        logger.info("--- LLM Call Complete ---")

        if result:
            if isinstance(result, LlmWordListResponse):
                logger.success("Successfully received and validated LlmWordListResponse!")
                logger.info(f"Number of words generated: {len(result.words)}")
                for i, word_item in enumerate(result.words):
                    logger.info(f"Word {i+1}: {word_item.word} ({word_item.part_of_speech}) - CEFR: {word_item.cefr_level}")
                    logger.debug(f"Full item {i+1}: {word_item.model_dump_json(indent=2)}")
            elif isinstance(result, dict) and 'error' in result:
                logger.error(f"LLM call failed with error: {result.get('error')}")
                raw_text = result.get('raw_text')
                if raw_text:
                    logger.error(f"Raw text received:\n{raw_text}")
                    logger.info("Attempting to clean the raw text for inspection...")
                    cleaned = _clean_llm_json_output(raw_text, "LlmWordListResponse")
                    logger.info(f"Cleaned text attempt:\n{cleaned}")
            else:
                logger.warning(f"Received unexpected result type: {type(result)}")
                logger.info(f"Raw result: {result}")
        else:
            logger.error("LLM call returned None or empty result.")

    except Exception as e:
        logger.exception("An exception occurred during the LLM test:")

if __name__ == "__main__":
    # Ensure the script can find project modules if run from project root
    # For example, by ensuring current dir is in path if not installed as package
    sys.path.insert(0, os.getcwd())
    
    asyncio.run(main())
