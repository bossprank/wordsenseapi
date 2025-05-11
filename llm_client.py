# llm_client.py v6 - Removed ResponseBlockedError Import
# Handles interactions with different LLM APIs (Gemini, DeepSeek).
# Maps DeepSeek 500/503 status codes in logs.

import google.generativeai as genai
# Check if the types needed are directly available or under types
try:
    # Attempt primary import path
    from google.generativeai.types import GenerationConfig as GoogleGenerationConfig
    from google.generativeai.types import HarmCategory, HarmBlockThreshold, StopCandidateException
except ImportError:
    # Fallback if structure changed slightly (adapt as needed based on library version)
    logger.warning("Using fallback import path for google.generativeai.types")
    from google.generativeai import types as genai_types
    GoogleGenerationConfig = genai_types.GenerationConfig
    HarmCategory = genai_types.HarmCategory
    HarmBlockThreshold = genai_types.HarmBlockThreshold
    StopCandidateException = genai_types.StopCandidateException
    # NOTE: ResponseBlockedError is not consistently available - removed explicit import


# Use AsyncOpenAI for DeepSeek
from openai import AsyncOpenAI, RateLimitError, APIError, OpenAIError # Include base error
import httpx # For async client configuration
import json
import sys
import time
import asyncio
from loguru import logger # Use Loguru logger
import re # Import regex for cleaning
from typing import Type, TypeVar, Optional, Union, List, Dict, Any
from pydantic import BaseModel, ValidationError

# Import necessary models
from models import GenerateListInput, WordItem, LlmWordListResponse, LlmSimpleWordList, SimpleWordEntry # Added LlmSimpleWordList, SimpleWordEntry

# --- Get Logger ---
# logger = logging.getLogger(__name__) # No longer needed, Loguru's logger is imported directly

# Import the config module, but defer accessing its attributes
try:
    import config
    config_loaded = True
except ImportError:
    logger.error("Error: Could not import configuration from config.py. LLM clients will likely fail.")
    config_loaded = False
    # Define a dummy config object with None values to prevent AttributeError later
    config = type('obj', (object,), {
        'get_google_api_key': lambda: None,
        'DEEPSEEK_API_KEY': None,
        'DEFAULT_LLM_PROVIDER': 'googleai',
        'DEFAULT_GOOGLE_MODEL': 'gemini-1.5-flash-latest',
        'DEFAULT_DEEPSEEK_MODEL': 'deepseek-chat'
    })()


# --- Configure Clients ---
# We configure clients lazily now, especially Google, to avoid import-time issues.
# DeepSeek client configuration is also moved into a lazy function.
google_configured = False
deepseek_client: Optional[AsyncOpenAI] = None # Initialize as None

def configure_google_client():
    """Configures the Google client if not already done."""
    global google_configured
    if google_configured:
        return True

    if not config_loaded:
         logger.error("Cannot configure Google client: config.py failed to import.")
         return False

    # Access the lazy getter from the imported config module
    google_api_key = config.get_google_api_key()

    if google_api_key:
        try:
            logger.info("Configuring Google Generative AI client...")
            genai.configure(api_key=google_api_key)
            google_configured = True
            logger.info("Google Generative AI client configured successfully.")
            return True
        except Exception as e:
            logger.warning(f"Failed to configure Google Generative AI client: {e}. Google AI calls will fail.")
            google_configured = False
            return False
    else:
        logger.warning("Google API Key not available from Secret Manager. Google AI provider will be unavailable.")
        google_configured = False
        return False

def configure_deepseek_client():
    """Configures the DeepSeek client if not already done."""
    global deepseek_client
    if deepseek_client is not None:
        return True

    if not config_loaded:
         logger.error("Cannot configure DeepSeek client: config.py failed to import.")
         return False

    # Access the API key from the imported config module
    deepseek_api_key = config.DEEPSEEK_API_KEY

    if deepseek_api_key:
        try:
            logger.info("Configuring DeepSeek client (via OpenAI SDK)...")
            http_client = httpx.AsyncClient(trust_env=False) # Simpler default

            deepseek_client = AsyncOpenAI(
                api_key=deepseek_api_key,
                base_url="https://api.deepseek.com/v1", # Ensure correct base URL
                http_client=http_client,
                timeout=60.0, # Set a reasonable timeout
                max_retries=0 # Handle retries manually in our code
            )
            logger.info("DeepSeek client configured successfully.")
            return True
        except Exception as e:
            logger.warning(f"Failed to configure DeepSeek client: {e}. DeepSeek calls will fail.")
            deepseek_client = None # Ensure client is None on failure
            return False
    else:
        logger.warning("DeepSeek API Key not found in config. DeepSeek provider will be unavailable.")
        deepseek_client = None
        return False

# Clients are now configured within the generate_structured_content function
# or explicitly called via configure_google_client/configure_deepseek_client if needed elsewhere.


# --- Define Safety Settings (Google AI specific) ---
# Adjust these thresholds based on your application's tolerance
GOOGLE_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}
logger.info(f"Using Google AI safety settings: {GOOGLE_SAFETY_SETTINGS}")

# --- Generic Pydantic Model Type ---
T = TypeVar('T', bound=BaseModel) # Type variable constrained to Pydantic BaseModel subclasses

# --- Unified Generation Function ---

async def generate_structured_content(
    prompt: str,
    response_model: Optional[Type[T]] = None,
    provider: str = config.DEFAULT_LLM_PROVIDER,
    model_name: Optional[str] = None,
    temperature: float = 0.5,
    # --- New Gemini Specific Params ---
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    stop_sequences: Optional[List[str]] = None,
    response_mime_type: Optional[str] = None, # e.g., "application/json"
    response_schema: Optional[Union[Dict, Type[BaseModel]]] = None, # Pydantic model or dict schema
    # --- End New Gemini Specific Params ---
    max_retries: int = 2,
    initial_delay: float = 1.5, # Slightly increased delay
    system_prompt: Optional[str] = "You are a helpful assistant designed to output JSON." # More specific default
) -> Optional[Union[T, str, Dict[str, Any]]]: # Return Dict for raw on failure
    """
    Generates content using the specified LLM provider and model.
    Attempts to parse and validate against response_model if provided.
    Logs raw prompt and response at DEBUG level.
    Returns validated model, raw string (if no model requested), or dict with error and raw text on failure.
    """
    start_time = time.time()
    logger.info(f"Initiating structured content generation. Provider: {provider}, Model Requested: {model_name or 'default'}")

    # Ensure configuration was loaded - if not, fail early
    if not config_loaded:
         logger.error("LLM Client Error: Configuration failed to load. Cannot generate content.")
         return {"error": "LLM configuration failed to load", "raw_text": None}

    # Select provider and check/configure client
    if provider == 'googleai':
        # Ensure Google client is configured before proceeding
        if not configure_google_client(): # Call the lazy configuration function
             logger.error("LLM Error: Google AI client could not be configured.")
             return {"error": "Google AI client could not be configured", "raw_text": None}
             
        # Use specific model if provided, otherwise use default from config
        model_to_use = model_name or config.DEFAULT_GOOGLE_MODEL
        # logger.debug(f"Using Google AI model: {model_to_use}") # Reduced verbosity
        result = await _generate_googleai(
            prompt=prompt,
            response_model=response_model,
            model_name=model_to_use,
            temperature=temperature,
            top_p=top_p, # Pass down
            top_k=top_k, # Pass down
            max_output_tokens=max_output_tokens, # Pass down
            stop_sequences=stop_sequences, # Pass down
            response_mime_type=response_mime_type, # Pass down
            response_schema=response_schema, # Pass down
            max_retries=max_retries,
            initial_delay=initial_delay,
            system_prompt=system_prompt
        )

    elif provider == 'deepseek':
        # Note: DeepSeek part does not use the new Gemini-specific params yet
        if not deepseek_client:
            logger.error("LLM Error: DeepSeek client not configured or API key missing.")
            return {"error": "DeepSeek client not configured", "raw_text": None}
        # Use specific model if provided, otherwise use default from config
        model_to_use = model_name or config.DEFAULT_DEEPSEEK_MODEL
        # logger.debug(f"Using DeepSeek model: {model_to_use}") # Reduced verbosity
        result = await _generate_deepseek(prompt, response_model, model_to_use, temperature, max_retries, initial_delay, system_prompt)

    else:
        logger.error(f"LLM Error: Unsupported provider '{provider}'. Supported: 'googleai', 'deepseek'.")
        return {"error": f"Unsupported provider '{provider}'", "raw_text": None}

    end_time = time.time()
    logger.info(f"Content generation request completed in {end_time - start_time:.2f} seconds.")
    return result


# --- Helper to Clean LLM Output ---
def _clean_llm_json_output(raw_text: str, expected_model_name: str) -> str:
    """Attempts to extract valid JSON from raw LLM text output."""
    # logger.debug(f"Attempting to clean raw text (length {len(raw_text)}): {raw_text[:200]}...") # Can be verbose
    cleaned_text = raw_text.strip()

    # Basic Markdown code block removal
    if cleaned_text.startswith("```json") and cleaned_text.endswith("```"):
        # logger.debug("Removing ```json markdown.") # Minor detail
        cleaned_text = cleaned_text[7:-3].strip()
    elif cleaned_text.startswith("```") and cleaned_text.endswith("```"):
        # logger.debug("Removing ``` markdown.") # Minor detail
        cleaned_text = cleaned_text[3:-3].strip()

    # Sometimes models add introductory text before the JSON. Try to find the first '{' or '['
    first_brace = cleaned_text.find('{')
    first_bracket = cleaned_text.find('[')

    start_index = -1
    if first_brace != -1 and first_bracket != -1:
        start_index = min(first_brace, first_bracket)
    elif first_brace != -1:
        start_index = first_brace
    elif first_bracket != -1:
        start_index = first_bracket

    if start_index > 0:
        logger.warning(f"Potential non-JSON prefix detected. Stripping {start_index} characters.")
        cleaned_text = cleaned_text[start_index:]

    # Sometimes models add trailing text. Try to find the last '}' or ']'
    # This is harder and more error-prone. We rely more on the json.loads() failure later.
    # last_brace = cleaned_text.rfind('}')
    # last_bracket = cleaned_text.rfind(']')
    # end_index = -1
    # ... complex logic to find matching bracket/brace ...

    # logger.debug(f"Cleaned text (first 200 chars): {cleaned_text[:200]}...") # Can be verbose
    return cleaned_text

# --- Provider Specific Functions ---

async def _generate_googleai(
    prompt: str,
    response_model: Optional[Type[T]],
    model_name: str,
    temperature: float,
    top_p: Optional[float],
    top_k: Optional[int],
    max_output_tokens: Optional[int],
    stop_sequences: Optional[List[str]],
    response_mime_type: Optional[str],
    response_schema: Optional[Union[Dict, Type[BaseModel]]],
    max_retries: int,
    initial_delay: float,
    system_prompt: Optional[str]
) -> Optional[Union[T, str, Dict[str, Any]]]:
    """Handles generation using the google-generativeai library."""
    logger.info(f"--- Calling Google AI ({model_name}) ---")
    # logger.debug(f"Params: temp={temperature}, top_p={top_p}, top_k={top_k}, max_tokens={max_output_tokens}, stop={stop_sequences}, mime={response_mime_type}, schema_provided={response_schema is not None}") # Verbose

    contents = []
    # Add system prompt if provided (as the first part of the first 'user' turn)
    full_user_prompt = (system_prompt + "\n\n" + prompt) if system_prompt else prompt
    contents.append({"role": "user", "parts": [full_user_prompt]})

    # Determine the effective mime type *before* checking if JSON is expected
    effective_response_mime_type = response_mime_type
    if response_schema and not effective_response_mime_type:
        effective_response_mime_type = "application/json" # Default to JSON if schema is provided
        logger.info("Defaulting response_mime_type to 'application/json' because response_schema was provided.")

    # Append JSON instruction if JSON output is expected (via response_model or response_schema)
    json_instruction = ""
    # Determine if JSON output is intended
    expect_json = response_model or (response_schema and effective_response_mime_type == "application/json")

    if expect_json:
        model_name_for_log = response_model.__name__ if response_model else "the provided schema"
        logger.info(f"Expecting structured JSON output matching: {model_name_for_log}")
        json_instruction = (
            f"\n\nCRITICAL: Your entire response MUST be a single, valid JSON object that conforms "
            f"exactly to the structure defined ({model_name_for_log}). "
            f"Do not include any text, comments, explanations, apologies, or markdown formatting "
            f"(like ```json) outside the main JSON object itself.\n"
        )
        contents[-1]["parts"][-1] += json_instruction

    # Log full prompt being sent (mask API keys if they were accidentally included)
    # log_prompt = re.sub(r'key=[A-Za-z0-9_-]+', 'key=***MASKED***', contents[-1]["parts"][-1]) # Keep this if prompt structure is complex
    # logger.debug(f"Google AI Request Prompt (User Turn):\n---PROMPT START---\n{log_prompt}\n---PROMPT END---") # Very verbose, consider removing for cleaner logs


    try:
        model = genai.GenerativeModel(model_name)

        # --- Construct GenerationConfig ---
        config_params = {"temperature": temperature}
        if top_p is not None: config_params["top_p"] = top_p
        if top_k is not None: config_params["top_k"] = top_k
        if max_output_tokens is not None: config_params["max_output_tokens"] = max_output_tokens
        
        # Add stop_sequences to config_params
        if stop_sequences is not None:
            config_params["stop_sequences"] = stop_sequences
            # logger.debug(f"Added stop_sequences to config_params: {stop_sequences}") # Minor detail

        # Handle response format and schema (effective_response_mime_type calculated earlier)
        if effective_response_mime_type:
            config_params["response_mime_type"] = effective_response_mime_type
        if response_schema and effective_response_mime_type == "application/json":
            # Pass schema only if mime type is JSON
            config_params["response_schema"] = response_schema
            # logger.info(f"Using response_schema (type: {type(response_schema).__name__}) for Google AI model.") # Good info, but can be verbose
        elif response_schema:
             logger.warning(f"response_schema provided but response_mime_type is '{effective_response_mime_type}', schema will be ignored by the API.")

        generation_config = GoogleGenerationConfig(**config_params)
        # logger.debug(f"Constructed GoogleGenerationConfig: {generation_config}") # Verbose
        # --- End Construct GenerationConfig ---


        current_delay = initial_delay
        last_error = None

        for attempt in range(max_retries + 1):
            logger.info(f"Google AI Generation. Attempt {attempt + 1}/{max_retries + 1}...")
            raw_text = None
            try:
                response = await model.generate_content_async(
                    contents,
                    generation_config=generation_config,
                    safety_settings=GOOGLE_SAFETY_SETTINGS,
                    # Removed stop_sequences=stop_sequences from here
                    request_options={'timeout': 120} # Consider making timeout configurable
                )

                # --- Extract Raw Text ---
                # Check for blocked prompt first
                if response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason.name
                     block_message = response.prompt_feedback.block_reason_message or "No specific message."
                     logger.error(f"Google AI Error: Prompt blocked. Reason: {block_reason}. Message: {block_message}")
                     last_error = {"error": f"Prompt blocked by safety filter: {block_reason}", "raw_text": None}
                     return last_error # No retry

                # Check for blocked response candidates
                is_blocked = False
                if hasattr(response, 'candidates') and response.candidates:
                    if response.candidates[0].finish_reason.name == 'SAFETY':
                        is_blocked = True
                        logger.warning(f"Google AI Warning: Response candidate blocked due to safety filters.")
                        if response.candidates[0].safety_ratings:
                            for rating in response.candidates[0].safety_ratings:
                                logger.warning(f"  - {rating.category.name}: {rating.probability.name}")
                # Try to get text, catching ValueError which often indicates blocking
                try:
                    raw_text = response.text
                    if is_blocked and not raw_text: # Double check if candidate blocked but text is empty
                         logger.warning("Response candidate blocked and response.text is empty/None.")
                    # elif raw_text: # This debug log is very verbose if successful
                        # logger.debug(f"Google AI Raw Response Text (Attempt {attempt + 1}) obtained via .text")

                except ValueError as e_text_blocked:
                    # This exception is often raised when .text is accessed on a blocked response
                    logger.warning(f"Google AI Warning: ValueError accessing response.text (often indicates blocked content): {e_text_blocked}")
                    is_blocked = True # Mark as blocked if this error occurs
                    # Try extracting from parts as a fallback
                    try:
                        raw_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                        # logger.debug(f"Google AI Raw Response Text (Attempt {attempt + 1}) obtained via parts fallback.") # Verbose
                    except Exception as e_parts:
                        logger.warning(f"Google AI Warning: Could not extract text from parts either. Error: {e_parts}.")
                        raw_text = None

                except Exception as e_other_text:
                    logger.warning(f"Google AI Warning: Unexpected error extracting text: {e_other_text}")
                    raw_text = None

                # Handle blocking decision
                if is_blocked:
                    last_error = {"error": "Response blocked by safety filter", "raw_text": raw_text}
                    if attempt < max_retries:
                         logger.warning(f"Retrying after safety block (attempt {attempt + 1})...")
                         await asyncio.sleep(current_delay); current_delay *= 1.5; continue
                    else:
                         logger.error("Max retries reached after safety block.")
                         return last_error


                # <<< Log raw response at DEBUG level >>> # This is very verbose, only enable if deep debugging LLM output
                # logger.debug(f"Google AI Raw Response Content (Attempt {attempt + 1}):\n---RESPONSE START---\n{raw_text}\n---RESPONSE END---")

                if raw_text is None or not raw_text.strip():
                    logger.warning(f"Google AI returned empty or None response text on attempt {attempt+1}.")
                    last_error = {"error": "Empty response received", "raw_text": raw_text}
                    if attempt < max_retries: await asyncio.sleep(current_delay); current_delay *= 1.5; continue
                    else: return last_error


                # --- Process Response ---
                if not response_model:
                    logger.info("No response model specified, returning raw text.")
                    return raw_text

                # Clean and Parse JSON
                json_data = None # Initialize for logging in except block
                cleaned_text = "" # Initialize for logging in except block
                try:
                    cleaned_text = _clean_llm_json_output(raw_text, response_model.__name__)
                    if not cleaned_text:
                         raise json.JSONDecodeError("Cleaned text is empty", "", 0) # Error will be caught below

                    json_data = json.loads(cleaned_text)
                    validated_data = response_model.model_validate(json_data)
                    logger.info(f"Successfully validated Google AI response against {response_model.__name__}.")
                    return validated_data # Success!

                except json.JSONDecodeError as e:
                    logger.error(f"Google AI Error: Failed JSON parsing: {e}. Raw text snippet: {raw_text[:200] if raw_text else 'None'}")
                    # logger.debug(f"Raw Text Before Parsing:\n{raw_text}\n---END RAW---") # Redundant if snippet logged
                    last_error = {"error": f"Failed JSON parsing: {e}", "raw_text": raw_text}

                except ValidationError as e:
                    logger.error(f"Google AI Error: Failed Pydantic validation ({response_model.__name__}): {e}")
                    # logger.debug(f"Raw Text Before Validation:\n{raw_text}\n---END RAW---") # Redundant
                    # if cleaned_text: logger.debug(f"Cleaned Text Before Validation:\n{cleaned_text}\n---END CLEANED---") # Verbose
                    # if json_data: logger.debug(f"Parsed JSON Data:\n{json.dumps(json_data, indent=2)}\n---END JSON---") # Verbose
                    last_error = {"error": f"Failed Pydantic validation: {e}", "raw_text": raw_text}

                # Fall through to retry logic if JSON/Validation failed

            except StopCandidateException as e:
                logger.warning(f"Google AI StopCandidateException (attempt {attempt + 1}): {e}")
                last_error = {"error": f"StopCandidateException: {e}", "raw_text": raw_text}
                # Retry these
            except Exception as e:
                error_message = f"Google AI Error during generation: {type(e).__name__}: {e}"
                logger.error(error_message)
                if "API key not valid" in str(e):
                     logger.critical("Google AI API Key is invalid!")
                     return {"error": "Invalid Google API Key", "raw_text": None}
                if "permission" in str(e).lower() or "denied" in str(e).lower():
                     logger.error("Google AI Permission Denied.")
                if "quota" in str(e).lower():
                    logger.warning("Google AI Quota Exceeded.")
                last_error = {"error": error_message, "raw_text": raw_text}
                # Retry generic errors

            # --- Retry Logic ---
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt + 1} failed. Retrying in {current_delay:.1f}s...")
                await asyncio.sleep(current_delay)
                current_delay *= 1.5
            else:
                logger.error(f"Google AI Error: Max retries ({max_retries}) reached. Last error: {last_error.get('error') if last_error else 'Unknown'}")
                return last_error if last_error else {"error": "Max retries reached with unknown final error", "raw_text": raw_text}


        # Should not be reached
        logger.error("Google AI Error: Exited retry loop unexpectedly.")
        return {"error": "Exited retry loop unexpectedly", "raw_text": None}

    except Exception as e:
        logger.exception(f"Google AI Error: Failed setup or unexpected issue before generation loop:")
        return {"error": f"LLM client setup failed: {e}", "raw_text": None}


async def _generate_deepseek(
    prompt: str, response_model: Optional[Type[T]], model_name: str,
    temperature: float, max_retries: int, initial_delay: float, system_prompt: Optional[str]
) -> Optional[Union[T, str, Dict[str, Any]]]:
    """Handles generation using the DeepSeek API via OpenAI SDK."""
    if not deepseek_client: return {"error": "DeepSeek client not initialized", "raw_text": None}

    logger.info(f"--- Calling DeepSeek ({model_name}) ---")
    # No extensive debug logging for DeepSeek params for now, similar to Google AI

    messages: List[Dict[str, str]] = []
    effective_system_prompt = system_prompt or "You are a helpful assistant designed to output JSON."

    # Append JSON instruction if a response model is expected
    if response_model:
        # model_schema = response_model.model_json_schema() # Schema can be large
        logger.info(f"Expecting structured JSON output matching: {response_model.__name__}")
        json_instruction = (
            f"\n\nCRITICAL: Your entire response MUST be a single, valid JSON object that conforms "
            f"exactly to the Pydantic schema for '{response_model.__name__}'. "
            f"Ensure all required fields are present. Do not include any text, comments, explanations, "
            f"apologies, or markdown formatting (like ```json) outside the JSON object itself."
        )
        effective_system_prompt += json_instruction

    messages.append({"role": "system", "content": effective_system_prompt})
    messages.append({"role": "user", "content": prompt})

    # logger.debug(f"DeepSeek Request Messages:\n---MESSAGES START---\n{json.dumps(messages, indent=2)}\n---MESSAGES END---") # Verbose

    current_delay = initial_delay
    last_error = None

    for attempt in range(max_retries + 1):
        logger.info(f"DeepSeek Generation. Attempt {attempt + 1}/{max_retries + 1}...")
        raw_text = None
        try:
            extra_args = {}
            if response_model and ("deepseek-chat" in model_name):
                 extra_args["response_format"] = {"type": "json_object"}
                 logger.info("Set response_format=json_object for DeepSeek.")

            response = await deepseek_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                stream=False,
                **extra_args
            ) # type: ignore

            # --- Extract Raw Text ---
            if not response.choices or not response.choices[0].message or response.choices[0].message.content is None:
                logger.warning(f"DeepSeek returned empty or None content on attempt {attempt+1}.")
                raw_text = None
            else:
                raw_text = response.choices[0].message.content
                # logger.debug(f"DeepSeek Raw Response Text (Attempt {attempt + 1}) obtained.") # Verbose


            # logger.debug(f"DeepSeek Raw Response Content (Attempt {attempt + 1}):\n---RESPONSE START---\n{raw_text}\n---RESPONSE END---") # Verbose

            if raw_text is None or not raw_text.strip():
                logger.warning(f"DeepSeek returned empty or None response text on attempt {attempt+1}.")
                last_error = {"error": "Empty response received", "raw_text": raw_text}
                if attempt < max_retries: await asyncio.sleep(current_delay); current_delay *= 1.5; continue
                else: return last_error

            # --- Process Response ---
            if not response_model:
                logger.info("No response model specified, returning raw text.")
                return raw_text

            # Clean and Parse JSON
            json_data = None # Initialize for logging in except block
            cleaned_text = "" # Initialize for logging in except block
            try:
                cleaned_text = _clean_llm_json_output(raw_text, response_model.__name__)
                if not cleaned_text:
                    raise json.JSONDecodeError("Cleaned text is empty", "", 0) # Error will be caught below

                json_data = json.loads(cleaned_text)
                validated_data = response_model.model_validate(json_data)
                logger.info(f"Successfully validated DeepSeek response against {response_model.__name__}.")
                return validated_data # Success!

            except json.JSONDecodeError as e:
                logger.error(f"DeepSeek Error: Failed JSON parsing: {e}. Raw text snippet: {raw_text[:200] if raw_text else 'None'}")
                last_error = {"error": f"Failed JSON parsing: {e}", "raw_text": raw_text}

            except ValidationError as e:
                logger.error(f"DeepSeek Error: Failed Pydantic validation ({response_model.__name__}): {e}")
                last_error = {"error": f"Failed Pydantic validation: {e}", "raw_text": raw_text}

            # Fall through to retry logic if JSON/Validation failed (if last_error is set)

        # --- Handle OpenAI SDK / API Errors ---
        except RateLimitError as e:
            log_msg = f"DeepSeek Rate Limit Reached (429). Check usage plans/limits. Error: {e}"
            logger.warning(log_msg)
            last_error = {"error": "DeepSeek Rate Limit Reached (429)", "raw_text": raw_text}
            current_delay *= 2
        except APIError as e:
            status_code = e.status_code
            error_desc = f"API Error ({status_code})" # Default description
            log_level = logging.WARNING # Default log level
            should_retry = False # Default retry status
            should_return = False # Default immediate return status

            if status_code == 401:
                error_desc = "Authentication Fails (401)"
                log_level = logging.CRITICAL
                should_return = True # No retry for auth fail
            elif status_code == 402:
                error_desc = "Insufficient Balance (402)"
                log_level = logging.ERROR
                should_return = True # No retry for balance fail
            elif status_code == 500:
                error_desc = "Server Error (500)"
                should_retry = True # Retry server errors
            elif status_code == 503:
                error_desc = "Server Overloaded (503)"
                should_retry = True # Retry overloaded errors
            elif status_code >= 400 and status_code < 500:
                 # Other 4xx client errors (400, 422, etc.)
                 log_level = logging.ERROR
                 should_return = True # Generally don't retry other client errors

            log_msg = f"DeepSeek Error: {error_desc}. Error: {e}"
            logger.log(log_level, log_msg) # Log with appropriate level
            last_error = {"error": f"DeepSeek {error_desc}", "raw_text": raw_text}

            if should_return: return last_error
            if not should_retry: # If retry wasn't explicitly set, default to retry for >=500
                 should_retry = status_code >= 500

        except OpenAIError as e:
             log_msg = f"DeepSeek SDK Error (attempt {attempt + 1}): {type(e).__name__}: {e}"
             logger.warning(log_msg)
             last_error = {"error": f"DeepSeek SDK Error: {e}", "raw_text": raw_text}
             should_retry = True # Retry SDK errors
        except Exception as e:
            logger.exception(f"DeepSeek Unexpected Error (attempt {attempt + 1}):")
            last_error = {"error": f"Unexpected Error: {type(e).__name__}: {e}", "raw_text": raw_text}
            should_retry = True # Retry unexpected errors

        # --- Retry Logic ---
        # Use the should_retry flag determined in the exception blocks
        if should_retry and attempt < max_retries:
            logger.warning(f"Attempt {attempt + 1} failed. Retrying in {current_delay:.1f}s...")
            await asyncio.sleep(current_delay)
            current_delay *= 1.5
        elif not should_retry:
             # If we decided not to retry (e.g., 4xx error), exit loop and return error
             logger.error(f"DeepSeek Error: Not retrying. Last error: {last_error.get('error') if last_error else 'Unknown'}")
             return last_error if last_error else {"error": "Non-retried error", "raw_text": raw_text}
        else: # Max retries reached
            logger.error(f"DeepSeek Error: Max retries ({max_retries}) reached. Last error: {last_error.get('error') if last_error else 'Unknown'}")
            return last_error if last_error else {"error": "Max retries reached with unknown final error", "raw_text": raw_text}

    # Should not be reached if loop logic is correct
    logger.error("DeepSeek Error: Exited retry loop unexpectedly.")
    return {"error": "Exited retry loop unexpectedly", "raw_text": None}


# --- Example Usage (can be run directly for testing) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)])
    logger.info("Running llm_client.py standalone tests...")
    import asyncio

    class TestResponse(BaseModel):
        greeting: str
        subject: str
        number: int

    async def main():
        logger.info("\n--- Running LLM Client Tests ---")
        test_prompt = "Generate a simple JSON object containing a greeting message to 'World', a subject line 'Test JSON', and the number 42."

        # Test Google AI
        if google_configured:
            logger.info("\n--- Testing Google AI (gemini-1.5-flash-latest) ---")
            google_result = await generate_structured_content(
                prompt=test_prompt, response_model=TestResponse, provider='googleai', model_name='gemini-1.5-flash-latest', temperature=0.7
            )
            logger.info(f"--- Google AI Test Result ---")
            if isinstance(google_result, TestResponse): logger.info(f"Success!:\n{google_result.model_dump_json(indent=2)}")
            elif isinstance(google_result, dict): logger.error(f"Failed! Error: {google_result.get('error')}\nRaw Text: {google_result.get('raw_text')}")
            else: logger.warning(f"Unexpected result type: {type(google_result)}\n{google_result}")

            # Test specific model name override (e.g., preview model)
            logger.info("\n--- Testing Google AI (gemini-1.5-flash-preview-0514) ---") # Use a current preview or desired model name
            google_preview_result = await generate_structured_content(
                prompt=test_prompt, response_model=TestResponse, provider='googleai', model_name='models/gemini-1.5-flash-preview-0514', temperature=0.7
            )
            logger.info(f"--- Google AI Preview Model Test Result ---")
            if isinstance(google_preview_result, TestResponse): logger.info(f"Success!:\n{google_preview_result.model_dump_json(indent=2)}")
            elif isinstance(google_preview_result, dict): logger.error(f"Failed! Error: {google_preview_result.get('error')}\nRaw Text: {google_preview_result.get('raw_text')}")
            else: logger.warning(f"Unexpected result type: {type(google_preview_result)}\n{google_preview_result}")

        else: logger.info("\nSkipping Google AI test (not configured).")

        # Test DeepSeek
        if deepseek_client:
            logger.info("\n--- Testing DeepSeek ---")
            deepseek_result = await generate_structured_content(
                prompt=test_prompt, response_model=TestResponse, provider='deepseek', temperature=0.7
            )
            logger.info(f"--- DeepSeek Test Result ---")
            if isinstance(deepseek_result, TestResponse): logger.info(f"Success!:\n{deepseek_result.model_dump_json(indent=2)}")
            elif isinstance(deepseek_result, dict): logger.error(f"Failed! Error: {deepseek_result.get('error')}\nRaw Text: {deepseek_result.get('raw_text')}")
            else: logger.warning(f"Unexpected result type: {type(deepseek_result)}\n{deepseek_result}")
        else: logger.info("\nSkipping DeepSeek test (not configured).")

        logger.info("\n--- LLM Client Tests Complete ---")

    try:
       asyncio.run(main())
    except RuntimeError as e:
       if "cannot run nested event loops" in str(e): logger.warning("Could not run async main directly (likely due to existing event loop).")
       else: logger.exception("RuntimeError during standalone test execution:"); raise e
    except Exception as e: logger.exception("Unexpected error during standalone test execution:")

async def generate_word_list(input_data: GenerateListInput, final_prompt_text: str) -> Union[List[WordItem], Dict[str, Any]]:
    """
    Generates a word list using the LLM based on GenerateListInput.
    Returns a list of WordItem objects on success, or an error dictionary on failure.
    """
    logger.info(f"Initiating JSON-based word list generation for language: {input_data.language}, level: {input_data.cefr_level}")
    # logger.debug(f"[generate_word_list] input_data: {input_data.model_dump_json(indent=2)}") # Can be verbose
    # logger.debug(f"[generate_word_list] final_prompt_text (first 500 chars): {final_prompt_text[:500]}") # Verbose, prompt structure is logged by generate_structured_content

    # Define the response schema based on LlmSimpleWordList
    # This schema will be passed to generate_structured_content
    # Prioritize schema from input_data if provided and valid JSON.
    json_schema_for_llm = None
    if input_data.gemini_response_schema_used:
        if isinstance(input_data.gemini_response_schema_used, str):
            try:
                json_schema_for_llm = json.loads(input_data.gemini_response_schema_used)
                logger.info("Using JSON schema provided in input_data (parsed from string).")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON schema string from input_data: {e}. Falling back to LlmSimpleWordList schema.")
                json_schema_for_llm = LlmSimpleWordList.model_json_schema()
        elif isinstance(input_data.gemini_response_schema_used, dict):
            json_schema_for_llm = input_data.gemini_response_schema_used
            logger.info("Using JSON schema provided in input_data (as dict).")
        else:
            logger.warning(f"Unexpected type for gemini_response_schema_used: {type(input_data.gemini_response_schema_used)}. Falling back.")
            json_schema_for_llm = LlmSimpleWordList.model_json_schema()
    else:
        logger.info("No response schema in input_data, using LlmSimpleWordList.model_json_schema().")
        json_schema_for_llm = LlmSimpleWordList.model_json_schema()


    llm_structured_result = await generate_structured_content(
        prompt=final_prompt_text,
        response_model=LlmSimpleWordList, # Expecting the simple list structure
        provider=input_data.provider or config.DEFAULT_LLM_PROVIDER,
        model_name=input_data.source_model,
        temperature=input_data.gemini_temperature,
        top_p=input_data.gemini_top_p,
        top_k=input_data.gemini_top_k,
        max_output_tokens=input_data.gemini_max_output_tokens,
        stop_sequences=input_data.gemini_stop_sequences,
        response_mime_type="application/json", # Explicitly request JSON
        response_schema=json_schema_for_llm
    )

    if isinstance(llm_structured_result, LlmSimpleWordList):
        logger.info(f"LLM successfully returned and validated LlmSimpleWordList with {len(llm_structured_result.words)} entries.")
        word_items: List[WordItem] = []
        for simple_entry in llm_structured_result.words:
            try:
                # Create the more complex WordItem, mapping fields from SimpleWordEntry
                # and setting others to None or defaults.
                item_data = {
                    "word": simple_entry.headword, # Map 'headword' from SimpleWordEntry to 'word' in WordItem
                    "part_of_speech": None,
                    "definition": None,
                    "example_sentence": None,
                    "difficulty_level": None,
                    "cefr_level": input_data.cefr_level, # Can populate from input if desired
                    "translations": None
                }
                if simple_entry.translation_en:
                    # Ensure WordItem.translations.en is populated
                    item_data["translations"] = WordItem.WordItemTranslations(en=simple_entry.translation_en)

                word_item_obj = WordItem.model_validate(item_data)
                word_items.append(word_item_obj)
            except ValidationError as e:
                logger.warning(f"Failed to validate WordItem for simple entry '{simple_entry.headword}': {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing simple entry '{simple_entry.headword}': {e}")
        
        logger.info(f"Successfully converted {len(word_items)} SimpleWordEntry items to full WordItem objects.")
        return word_items

    elif isinstance(llm_structured_result, dict) and 'error' in llm_structured_result:
        logger.error(f"LLM generation failed: {llm_structured_result.get('error')}. Raw text (if any): {llm_structured_result.get('raw_text')}")
        return llm_structured_result # Propagate the error dictionary
    else:
        error_detail = "LLM did not return a LlmSimpleWordList object as expected."
        if llm_structured_result is None:
            error_detail = "LLM returned None when expecting LlmSimpleWordList."
        
        logger.error(f"LLM generation failed: {error_detail}. Full LLM result: {llm_structured_result}")
        return {"error": error_detail, "raw_text": str(llm_structured_result) if llm_structured_result is not None else None}
