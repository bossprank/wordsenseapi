# llm_client.py
# Handles interactions with different LLM APIs (Gemini, DeepSeek).

import google.generativeai as genai
from google.generativeai.types import GenerationConfig as GoogleGenerationConfig
from google.generativeai.types import HarmCategory, HarmBlockThreshold, StopCandidateException
from openai import OpenAI, AsyncOpenAI, RateLimitError, APIError
import httpx # *** Import httpx ***
import json
import sys
import time
import asyncio
from typing import Type, TypeVar, Optional, Union, List, Dict, Any
from pydantic import BaseModel, ValidationError

# Import configuration variables
try:
    from config import (
        GOOGLE_API_KEY, DEEPSEEK_API_KEY,
        DEFAULT_LLM_PROVIDER, DEFAULT_GOOGLE_MODEL, DEFAULT_DEEPSEEK_MODEL
    )
except ImportError:
    print("Error: Could not import configuration from config.py.")
    sys.exit(1)

# --- Configure Clients (only if keys exist) ---

google_configured = False
if GOOGLE_API_KEY:
    try:
        print("Configuring Google Generative AI client...")
        genai.configure(api_key=GOOGLE_API_KEY)
        google_configured = True
        print("Google Generative AI client configured successfully.")
    except Exception as e:
        print(f"Warning: Failed to configure Google Generative AI client: {e}")

# DeepSeek uses OpenAI compatible API
deepseek_client: Optional[AsyncOpenAI] = None
if DEEPSEEK_API_KEY:
    try:
        print("Configuring DeepSeek client (via OpenAI SDK)...")
        # *** Explicitly create an httpx client without default proxy handling ***
        # trust_env=False prevents httpx from automatically picking up proxy env vars
        http_client = httpx.AsyncClient(trust_env=False)

        deepseek_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
            http_client=http_client # *** Pass the explicit client ***
        )
        print("DeepSeek client configured successfully.")
    except Exception as e:
        print(f"Warning: Failed to configure DeepSeek client: {e}")
        deepseek_client = None


# --- Define Safety Settings (Google AI specific) ---
GOOGLE_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

# --- Generic Pydantic Model Type ---
T = TypeVar('T', bound=BaseModel)

# --- Unified Generation Function ---

async def generate_structured_content(
    prompt: str,
    response_model: Optional[Type[T]] = None,
    provider: str = DEFAULT_LLM_PROVIDER,
    model_name: Optional[str] = None, # If None, use default for provider
    temperature: float = 0.5,
    max_retries: int = 2,
    initial_delay: float = 1.0,
    system_prompt: Optional[str] = "You are a helpful assistant." # Default system prompt
) -> Optional[Union[T, str]]:
    """
    Generates content using the specified LLM provider and model.
    (Rest of the function remains the same as previous version)
    """
    if provider == 'googleai':
        if not google_configured:
            print("LLM Error: Google AI client not configured (check API key).")
            return None
        model_to_use = model_name or DEFAULT_GOOGLE_MODEL
        return await _generate_googleai(prompt, response_model, model_to_use, temperature, max_retries, initial_delay, system_prompt)
    elif provider == 'deepseek':
        if not deepseek_client:
            print("LLM Error: DeepSeek client not configured (check API key).")
            return None
        model_to_use = model_name or DEFAULT_DEEPSEEK_MODEL
        return await _generate_deepseek(prompt, response_model, model_to_use, temperature, max_retries, initial_delay, system_prompt)
    else:
        print(f"LLM Error: Unsupported provider '{provider}'.")
        return None

# --- Provider Specific Functions ---

async def _generate_googleai(
    prompt: str, response_model: Optional[Type[T]], model_name: str,
    temperature: float, max_retries: int, initial_delay: float, system_prompt: Optional[str]
) -> Optional[Union[T, str]]:
    """Handles generation using the google-generativeai library."""
    # (Code for _generate_googleai remains the same as previous version)
    print(f"\n--- Calling Google AI ({model_name}) ---")
    print(f"Prompt (first 100 chars): {prompt[:100]}...")
    contents = []
    if system_prompt: contents.append(f"{system_prompt}\n\n{prompt}")
    else: contents.append(prompt)
    if response_model:
        print(f"Expecting structured output matching: {response_model.__name__}")
        contents[-1] += f"\n\nPlease format your entire response as a single, valid JSON object that strictly adheres to the structure defined by the Pydantic model '{response_model.__name__}', including all required fields. Do not include any text outside of the JSON object itself."
    try:
        model = genai.GenerativeModel(model_name)
        generation_config = GoogleGenerationConfig(temperature=temperature)
        current_delay = initial_delay
        for attempt in range(max_retries + 1):
            try:
                print(f"Attempt {attempt + 1}/{max_retries + 1}...")
                response = await model.generate_content_async(contents, generation_config=generation_config, safety_settings=GOOGLE_SAFETY_SETTINGS)
                if not response.candidates:
                     print(f"Google AI Warning: No candidates returned.");
                     if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason: print(f"Google AI Block Reason: {response.prompt_feedback.block_reason_message}")
                     if attempt < max_retries: print(f"Retrying after {current_delay:.1f}s..."); await asyncio.sleep(current_delay); current_delay *= 2; continue
                     else: print("Google AI Error: No candidates after retries."); return None
                raw_text = None
                try: raw_text = response.text
                except ValueError: print(f"Google AI Warning: Could not extract text directly.")
                except Exception as e_text: print(f"Google AI Warning: Unexpected error extracting text: {e_text}")
                if not raw_text:
                    try: raw_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                    except (AttributeError, ValueError, TypeError) as e_parts: print(f"Google AI Warning: Could not extract text from parts. Error: {e_parts}.")
                if not raw_text:
                    if attempt < max_retries: print(f"Retrying after {current_delay:.1f}s..."); await asyncio.sleep(current_delay); current_delay *= 2; continue
                    else: print("Google AI Error: Empty response after retries."); return None
                print(f"Google AI Raw Response (first 100 chars): {raw_text[:100]}...")
                if not response_model: return raw_text
                try:
                    cleaned_text = raw_text.strip()
                    if cleaned_text.startswith("```json"): cleaned_text = cleaned_text[7:-3].strip()
                    elif cleaned_text.startswith("```"): cleaned_text = cleaned_text[3:-3].strip()
                    json_data = json.loads(cleaned_text)
                    validated_data = response_model.model_validate(json_data)
                    print(f"Successfully validated response against {response_model.__name__}.")
                    return validated_data
                except json.JSONDecodeError as e: print(f"Google AI Error: Failed JSON parsing: {e}\nText: {raw_text[:500]}"); return None
                except ValidationError as e: print(f"Google AI Error: Failed Pydantic validation ({response_model.__name__}): {e}\nText: {raw_text[:500]}"); return None
            except StopCandidateException as e:
                print(f"Google AI StopCandidateException (attempt {attempt + 1}/{max_retries + 1}): {e}")
                if attempt < max_retries: print(f"Retrying after {current_delay:.1f}s..."); await asyncio.sleep(current_delay); current_delay *= 2
                else: print("Google AI Error: StopCandidateException after retries."); return None
            except Exception as e:
                error_message = str(e); print(f"Google AI Error during generation (attempt {attempt + 1}/{max_retries + 1}): {error_message}")
                if "API key not valid" in error_message: print("Google AI Error: Invalid API Key."); return None
                if attempt < max_retries: print(f"Retrying after {current_delay:.1f}s..."); await asyncio.sleep(current_delay); current_delay *= 2
                else: print("Google AI Error: Max retries reached."); return None
    except Exception as e: print(f"Google AI Error: Failed setup: {e}"); return None
    print("Google AI Error: Reached end unexpectedly."); return None


async def _generate_deepseek(
    prompt: str, response_model: Optional[Type[T]], model_name: str,
    temperature: float, max_retries: int, initial_delay: float, system_prompt: Optional[str]
) -> Optional[Union[T, str]]:
    """Handles generation using the DeepSeek API via OpenAI SDK."""
    # (Code for _generate_deepseek remains the same as previous version)
    if not deepseek_client: return None
    print(f"\n--- Calling DeepSeek ({model_name}) ---"); print(f"Prompt (first 100 chars): {prompt[:100]}...")
    messages: List[Dict[str, str]] = []
    if system_prompt: messages.append({"role": "system", "content": system_prompt})
    if response_model:
        print(f"Expecting structured output matching: {response_model.__name__}")
        json_instruction = f"You are a helpful assistant designed to output JSON conforming to the Pydantic model: {response_model.__name__}. Respond ONLY with the valid JSON object, without any introductory text or markdown formatting."
        if messages and messages[0]["role"] == "system": messages[0]["content"] += "\n" + json_instruction
        else: messages.insert(0, {"role": "system", "content": json_instruction})
    messages.append({"role": "user", "content": prompt})
    current_delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            print(f"Attempt {attempt + 1}/{max_retries + 1}...")
            response = await deepseek_client.chat.completions.create(model=model_name, messages=messages, temperature=temperature, stream=False) # type: ignore
            if not response.choices: print("DeepSeek Warning: No choices returned.");
            elif response.choices[0].message.content is None: print("DeepSeek Error: Response message content is None.")
            else:
                raw_text = response.choices[0].message.content
                print(f"DeepSeek Raw Response (first 100 chars): {raw_text[:100]}...")
                if not response_model: return raw_text
                try:
                    cleaned_text = raw_text.strip();
                    if cleaned_text.startswith("```json"): cleaned_text = cleaned_text[7:-3].strip()
                    elif cleaned_text.startswith("```"): cleaned_text = cleaned_text[3:-3].strip()
                    json_data = json.loads(cleaned_text)
                    validated_data = response_model.model_validate(json_data)
                    print(f"Successfully validated response against {response_model.__name__}.")
                    return validated_data
                except json.JSONDecodeError as e: print(f"DeepSeek Error: Failed JSON parsing: {e}\nText: {raw_text[:500]}"); return None
                except ValidationError as e: print(f"DeepSeek Error: Failed Pydantic validation ({response_model.__name__}): {e}\nText: {raw_text[:500]}"); return None
            # If we fall through (no choices or None content) and can retry:
            if attempt < max_retries: print(f"Retrying after {current_delay:.1f}s..."); await asyncio.sleep(current_delay); current_delay *= 2; continue
            else: print("DeepSeek Error: Failed after retries."); return None
        except RateLimitError as e: print(f"DeepSeek Rate Limit Error (attempt {attempt + 1}/{max_retries + 1}): {e}");
        except APIError as e: print(f"DeepSeek API Error (attempt {attempt + 1}/{max_retries + 1}): {e}");
        except Exception as e: print(f"DeepSeek Unexpected Error (attempt {attempt + 1}/{max_retries + 1}): {e}");
        if attempt < max_retries: print(f"Retrying after {current_delay:.1f}s..."); await asyncio.sleep(current_delay); current_delay *= 2
        else: print("DeepSeek Error: Max retries reached."); return None
    print("DeepSeek Error: Reached end unexpectedly."); return None


# --- Example Usage (can be run directly for testing) ---
if __name__ == '__main__':
    import asyncio

    class TestResponse(BaseModel):
        greeting: str
        subject: str
        number: int

    async def main():
        print("\n--- Running LLM Client Tests ---")

        # Test Google AI (if configured)
        if google_configured:
            print("\nTesting Google AI...")
            google_result = await generate_structured_content(
                prompt="Generate a JSON object with keys 'greeting', 'subject', and 'number'.",
                response_model=TestResponse,
                provider='googleai'
            )
            print(f"Google AI Result: {google_result}")
        else:
            print("\nSkipping Google AI test (not configured).")

        # Test DeepSeek (if configured)
        if deepseek_client:
            print("\nTesting DeepSeek...")
            deepseek_result = await generate_structured_content(
                prompt="Generate a JSON object with keys 'greeting', 'subject', and 'number'.",
                response_model=TestResponse,
                provider='deepseek'
            )
            print(f"DeepSeek Result: {deepseek_result}")
        else:
             print("\nSkipping DeepSeek test (not configured).")

        print("\n--- LLM Client Tests Complete ---")

    try:
       asyncio.run(main())
    except RuntimeError as e:
       if "cannot run nested event loops" in str(e):
           print("Warning: Could not run async main directly.")
       else:
           raise e

