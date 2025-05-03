# main_enrichment.py v1.21 - Handle Incomplete LLM Image Data
# Orchestrates the word enrichment process using Firestore and LLM clients.
# Defers Sense validation, handles incomplete image data from LLM.

import asyncio
import sys
import argparse
import traceback
import logging
from uuid import uuid4, UUID
from typing import Optional, List, Dict, Any, Union, Type, TypeVar
from pydantic import BaseModel, ValidationError

# --- Get Logger ---
logger = logging.getLogger(__name__)

# Import Pydantic models (ensure models.py is v1.4+)
try:
    from models import (
        Word, WordBase, Sense, SenseBase, LinkChain, LinkChainBase,
        EnrichmentInput, Language, LlmSenseInfo, EnrichmentInfo,
        LlmCoreDetailsOutput, LlmSenseDetailsOutput, LlmLinkChainsResponse,
        LlmCoreLangOutput, LlmLinkChainOutput, SenseDefinition, Example,
        TranslationDetail, Pronunciation, SemanticRelationDetail, ImageData # Import ImageData
    )
    logger.info("Models imported successfully in main_enrichment.")
except ImportError as e:
    logger.critical(f"CRITICAL Error: Could not import Pydantic models from models.py: {e}")
    print(f"Error: Could not import Pydantic models from models.py: {e}")
    sys.exit(1)

# Import client functions
try:
    # *** CORRECTED IMPORT LINE ***
    from firestore_client import get_word_by_id, save_word, search_words
    logger.info("Firestore client functions imported successfully.")
except ImportError as e:
    logger.critical(f"CRITICAL Error: Could not import required functions from firestore_client.py: {e}")
    print(f"Error: Could not import from firestore_client.py: {e}")
    sys.exit(1)

try:
    from llm_client import generate_structured_content
    from config import DEFAULT_LLM_PROVIDER
    logger.info("LLM client functions imported successfully.")
except ImportError as e:
    logger.critical(f"CRITICAL Error: Could not import from llm_client.py or config.py: {e}")
    print(f"Error: Could not import from llm_client.py or config.py: {e}")
    sys.exit(1)

# --- Placeholder Config / Prompts ---
# [Prompts definitions remain unchanged]
# --- Verbose Prompt for Step 1 ---
get_senses_prompt = """You are an expert linguist assisting in building a database for a language learning app.
Your task is to analyze the headword '{headword}' from the '{language}' language.
I need you to provide its essential linguistic details and identify its distinct meanings (senses).

Please structure your entire response as a single, valid JSON object that strictly adheres to the following Pydantic schema (LlmCoreDetailsOutput):
{{
  "headword": "{headword}", // REQUIRED: The exact headword provided.
  "language": "{language}", // REQUIRED: The exact language code provided.
  "pronunciation": {{ // Object or null. Provide if known.
    "ipa": "string or null", // International Phonetic Alphabet transcription.
    "audio_url": null, // Leave as null for now.
    "phonetic_spelling": "string or null" // Simplified spelling for learners, e.g., "mah-KAHN".
  }},
  "frequency_rank": "integer or null", // Estimated rank (lower is more frequent).
  "register": "string or null", // General formality (e.g., "formal", "informal", "neutral", "slang").
  "etymology": null, // Set explicitly to null. This will be requested separately.
  "collocations": null, // Set explicitly to null. This will be requested separately.
  "semantic_relations": null, // Set explicitly to null. This will be requested separately.
  "usage_notes": null, // Set explicitly to null. This will be requested separately.
  "senses": [ // REQUIRED: Array of identified senses. MUST NOT be empty if the word is valid.
    {{ // For EACH distinct sense:
      "part_of_speech": "string", // e.g., "VERB", "NOUN", "ADJECTIVE".
      "brief_description": "string" // A concise definition explaining this specific sense.
    }}
    // Add more sense objects as needed.
  ]
}}

CRITICAL INSTRUCTIONS:
1.  Respond ONLY with the valid JSON object described above.
2.  Do NOT include any introductory text, explanations, apologies, or markdown formatting (like ```json) outside the JSON structure.
3.  Ensure all REQUIRED fields ("headword", "language", "senses") are present.
4.  Ensure the "senses" array is not empty for valid words. If the word is nonsensical or hypothetical, indicate that in the brief_description of a single sense entry.
5.  Set the specified fields (etymology, collocations, etc.) explicitly to null as requested.
"""
# --- Verbose Prompt for Step 2 ---
get_core_details_lang_prompt = """You are an expert linguist assisting in building a database for a language learning app.
For the headword '{headword}' (language: {language}), I need specific details explained in {target_language} for a language learner.

Please provide the following information, structuring your response as a single, valid JSON object matching the LlmCoreLangOutput schema:
{{
  "etymology": "string or null", // A brief explanation of the word's origin, written clearly in {target_language}.
  "collocations": [ // List of common words used with '{headword}', presented in {target_language} (e.g., translations or explanations). Null if none.
    "string", ...
  ],
  "semantic_relations": {{ // Synonyms, antonyms, related concepts relevant to '{headword}', presented in {target_language}. Null if none.
    "synonyms": ["string", ...], // Synonyms in {target_language}.
    "antonyms": ["string", ...], // Antonyms in {target_language}.
    "related_concepts": ["string", ...] // Related concepts in {target_language}.
  }},
  "usage_notes": "string or null" // Any important usage notes (e.g., common mistakes, formality), written clearly in {target_language}.
}}

CRITICAL INSTRUCTIONS:
1.  Respond ONLY with the valid JSON object described above.
2.  Write all explanations and lists *in the target language: {target_language}*.
3.  Do NOT include any introductory text, explanations, or markdown formatting outside the JSON structure.
4.  If information for a field is not available or applicable, set its value to null.
"""
# --- Verbose Prompt for Step 3 ---
get_sense_details_prompt = """You are an expert linguist assisting in building a database for a language learning app.
Focus *only* on the specific sense of the word '{headword}' ({language}) identified as:
- Part of Speech: {pos}
- Brief Description: {sense_desc}

I need detailed information about *this specific sense* for someone learning {target_language}.

Please structure your response as a single, valid JSON object matching the LlmSenseDetailsOutput schema:
{{
  "definition": {{ // REQUIRED: Definition of *this specific sense* written in {target_language}.
    "language": "{target_language}", // Must be the target language code.
    "text": "string", // The definition text. Aim for clarity using simple vocabulary (e.g., A1/A2 level if possible).
    "definition_level": "A1" // Estimate the CEFR level (A1-C2) of the vocabulary used in *your* definition text.
  }},
  "translations": [ // REQUIRED: List of accurate translations of *this specific sense* into {target_language}.
    {{
      "text": "string", // The translation text in {target_language}.
      "nuance": "string or null" // Optional note on subtle meaning differences compared to other translations.
    }}, ...
  ],
  "examples": [ // REQUIRED: Generate exactly {num_examples} distinct example sentences using '{headword}' *in this specific sense*.
    {{
      "text": "string", // The example sentence in the original language ({language}).
      "language": "{language}", // Must be the source language code.
      "translations": {{
         "{target_language}": "string" // REQUIRED: Accurate translation of the example sentence into {target_language}.
       }},
      "example_level": "A1" // Estimate the CEFR level (A1-C2) of the vocabulary used in the original example sentence.
    }}, ...
  ],
  "sense_register": "string or null", // Formality specific to this sense (e.g., "formal", "informal"), if different from the word's general register.
  "sense_collocations": [ // List of collocations specifically for *this sense*, presented in {target_language}. Null if none.
     "string", ...
  ],
  "sense_semantic_relations": {{ // Synonyms/antonyms specifically for *this sense*, presented in {target_language}. Null if none.
    "synonyms": ["string", ...],
    "antonyms": ["string", ...],
    "related_concepts": ["string", ...]
  }}
}}

CRITICAL INSTRUCTIONS:
1.  Respond ONLY with the valid JSON object described above.
2.  Ensure all generated content (definitions, translations, examples, collocations, relations) is relevant *only* to the specified sense ({pos} - {sense_desc}).
3.  Provide exactly {num_examples} examples.
4.  Write definitions, translations, collocations, and semantic relations *in the target language: {target_language}*. Example sentences should be in {language} with a {target_language} translation.
5.  Do NOT include any introductory text, explanations, or markdown formatting outside the main JSON structure.
6.  Set fields to null if information is not available or applicable. Ensure required fields are present.
"""
# --- Verbose Prompt for Step 4 ---
get_link_chain_prompt = """You are a creative assistant helping language learners memorize vocabulary using the link chain method.
Your task is to generate {num_chains} distinct and memorable mnemonic link chains for the word '{headword}' ({language}).
This word is being learned by a speaker of {source_language} who wants to learn {target_language}.
Focus on the specific meaning (sense) of '{headword}':
- Part of Speech: {pos}
- Brief Description: {sense_desc}

For each chain, structure your response as a JSON object matching the LlmLinkChainOutput schema (within a parent "link_chains" list):
{{
  "target_language": "{target_language}", // The language being learned.
  "syllables": ["string", ...], // Optional: '{headword}' broken into pronounceable syllables.
  "syllable_links": [ // Optional: Link syllables to concrete keyword nouns in the learner's language ({source_language}).
    {{ "syllable": "string", "keyword_noun": "string", "keyword_language": "{source_language}" }}, ...
  ],
  "narrative": "string", // REQUIRED: A short, vivid story or description in {source_language} that links the keywords/syllables (or the sound of '{headword}') to its meaning ('{sense_desc}'). Make it memorable!
  "mnemonic_rhyme": "string or null", // Optional: A short, catchy rhyme in {source_language} summarizing the mnemonic.
  "explanation": "string or null", // Optional: A brief explanation in {source_language} of how the mnemonic works.
  "image_data": {{ // Provide *only* a prompt for an image that visually represents the narrative.
      "prompt": "string" // A descriptive prompt for an AI image generator (e.g., DALL-E, Imagen) to create a helpful visual for the narrative.
  }},
  "validation_score": null, // Leave as null.
  "prompt_used": null // Leave as null.
}}

CRITICAL INSTRUCTIONS:
1.  Respond ONLY with a valid JSON object containing a "link_chains" key, which holds a list of {num_chains} chain objects as described above.
2.  Write narratives, rhymes, and explanations in the learner's native language: {source_language}.
3.  Ensure the mnemonic clearly connects the sound/syllables of '{headword}' to its specific meaning '{sense_desc}'.
4.  Be creative and aim for memorability! Use concrete imagery in the narrative and image prompt.
5.  For 'image_data', ONLY include the 'prompt' field. Do not include 'url' or 'type'.
6.  Do NOT include any introductory text, explanations, or markdown formatting outside the main JSON structure.
"""

def GET_ENRICHMENT_CONFIG():
    logger.warning("Using placeholder enrichment config! Should load from external source.")
    return {
        "prompts": {
            "get_senses": get_senses_prompt,
            "get_core_details_lang": get_core_details_lang_prompt,
            "get_sense_details": get_sense_details_prompt,
            "get_link_chain": get_link_chain_prompt
        },
        "counts": { "target_examples_per_sense": 3, "max_link_chains_per_sense": 2 },
        "default_provider": DEFAULT_LLM_PROVIDER # Use default from config
    }

# --- Helper Functions ---
# [Helper functions GENERATE_WORD_ID, EXTRACT_CORE_DETAILS_FROM_OBJECT,
#  EXTRACT_SENSES_POS_FROM_OBJECT, MERGE_MULTILINGUAL_DATA, FIND_SENSE_IN_OBJECT,
#  MERGE_OR_CREATE_SENSE, GET_CHAIN_COUNT_FOR_TARGET_LANG
#  remain unchanged]
def GENERATE_WORD_ID(headword: str, language: str) -> str:
    logger.warning("Word ID generation/lookup strategy needs refinement. Using UUIDs.")
    return str(uuid4())

def EXTRACT_CORE_DETAILS_FROM_OBJECT(word_obj: Word) -> Dict[str, Any]:
    """Extracts core details, ensuring a consistent structure. Senses remain Pydantic objects."""
    base_structure = {
        "headword": None, "language": None, "pronunciation": None, "frequency_rank": None,
        "register": None, "etymology": {}, "collocations": {}, "semantic_relations": {},
        "usage_notes": {}, "senses": []
    }
    if not word_obj:
        logger.warning("EXTRACT_CORE_DETAILS_FROM_OBJECT received None, returning base structure.")
        return base_structure
    try:
        core_data = word_obj.model_dump(exclude={'word_id', 'created_at', 'updated_at', 'enrichment_history'})
        core_data['etymology'] = core_data.get('etymology') or {}
        core_data['collocations'] = core_data.get('collocations') or {}
        core_data['semantic_relations'] = core_data.get('semantic_relations') or {}
        core_data['usage_notes'] = core_data.get('usage_notes') or {}
        core_data['senses'] = core_data.get('senses') or []
        logger.debug(f"Extracted core details for {word_obj.headword}: {list(core_data.keys())}")
        return core_data
    except Exception as e:
        logger.exception(f"Error during EXTRACT_CORE_DETAILS_FROM_OBJECT for {getattr(word_obj, 'headword', 'N/A')}:")
        return base_structure

def EXTRACT_SENSES_POS_FROM_OBJECT(word_obj: Word) -> List[Dict[str, Any]]:
    """Extracts simplified sense info (POS, brief desc, ID) from a Word object's Sense list."""
    senses_info = []
    if not word_obj or not word_obj.senses:
        logger.debug("EXTRACT_SENSES_POS_FROM_OBJECT: No word object or senses found.")
        return senses_info
    source_lang = word_obj.language
    logger.debug(f"Extracting sense POS/Desc for {word_obj.headword} (source lang: {source_lang})")
    for sense in word_obj.senses:
        source_def_text = "N/A"
        for definition in sense.definitions:
            if definition.language == source_lang:
                source_def_text = definition.text
                break
        if source_def_text == "N/A": logger.warning(f"Could not find definition in source language ({source_lang}) for sense {sense.sense_id}")
        senses_info.append({
            "part_of_speech": sense.part_of_speech,
            "brief_description": source_def_text,
            "sense_id": sense.sense_id
        })
    logger.debug(f"Extracted {len(senses_info)} sense POS/Desc items.")
    return senses_info

def MERGE_MULTILINGUAL_DATA(existing_details: Dict, new_lang_details: Optional[LlmCoreLangOutput], lang_code: str, force_overwrite: bool = False):
    """Merges LLM-generated language-specific details into the existing core details dict."""
    if not new_lang_details: return existing_details
    logger.info(f"Merging multilingual data for language: {lang_code} (Force Overwrite: {force_overwrite})")
    new_data = new_lang_details.model_dump(exclude_unset=True)
    for field, value in new_data.items():
        if value is None: continue
        target_field = field
        if target_field in ["etymology", "usage_notes"]:
            existing_details.setdefault(target_field, {})
            if force_overwrite or lang_code not in existing_details[target_field]: existing_details[target_field][lang_code] = value
        elif target_field == "collocations":
            existing_details.setdefault(target_field, {})
            if force_overwrite or lang_code not in existing_details[target_field]:
                 if isinstance(value, list): existing_details[target_field][lang_code] = value
                 else: logger.warning(f"Expected list for '{target_field}' but got {type(value)}, skipping.")
        elif target_field == "semantic_relations":
             existing_details.setdefault(target_field, {})
             if force_overwrite or lang_code not in existing_details[target_field]:
                 if isinstance(value, dict):
                     value.setdefault('synonyms', []); value.setdefault('antonyms', []); value.setdefault('related_concepts', [])
                     existing_details[target_field][lang_code] = value
                 else: logger.warning(f"Expected dict for '{target_field}' but got {type(value)}, skipping.")
        else: logger.warning(f"MERGE_MULTILINGUAL_DATA: Unhandled field '{field}' during merge.")
    return existing_details

def FIND_SENSE_IN_OBJECT(word_obj: Optional[Word], pos: str, description: str) -> Optional[Sense]:
    """Finds a specific sense within a Word object based on POS and source language description."""
    if not word_obj or not word_obj.senses: return None
    source_lang = word_obj.language
    logger.debug(f"Searching for sense with POS='{pos}', Desc='{description[:50]}...' in lang='{source_lang}'")
    for sense in word_obj.senses:
        source_def = next((d.text for d in sense.definitions if d.language == source_lang), None)
        if sense.part_of_speech == pos and source_def == description:
            logger.debug(f"Found matching sense: {sense.sense_id}")
            return sense
    logger.debug(f"No matching sense found for POS='{pos}', Desc='{description[:50]}...'")
    return None

def MERGE_OR_CREATE_SENSE(
    existing_sense: Optional[Sense],
    sense_info: LlmSenseInfo,
    new_details: Optional[LlmSenseDetailsOutput],
    source_language: Language,
    target_language: Language,
    force_overwrite: bool = False
) -> Dict[str, Any]:
    """Creates or updates a dictionary representing a Sense object."""
    logger.info(f"Merge/Create Sense Data: POS='{sense_info.part_of_speech}', Desc='{sense_info.brief_description[:50]}...'")
    logger.info(f"Target Lang: {target_language}, Force Overwrite: {force_overwrite}")
    sense_data: Dict[str, Any] = {}
    try:
        if existing_sense:
            logger.debug(f"Using existing sense data: {existing_sense.sense_id}")
            sense_data = existing_sense.model_dump()
        else:
            logger.debug("Creating new sense data structure.")
            sense_data = {
                "sense_id": uuid4(), "part_of_speech": sense_info.part_of_speech,
                "definitions": [SenseDefinition(language=source_language, text=sense_info.brief_description).model_dump()],
                "translations": {}, "examples": [], "sense_register": None, "sense_collocations": {},
                "sense_semantic_relations": {}, "link_chain_variations": [], "related_forms": None,
                "CEFR_level": None, "usage_frequency": None, "phonetic_transcription": None
            }
        # Ensure essential lists/dicts exist after initial creation/dump
        sense_data.setdefault('definitions', []); sense_data.setdefault('translations', {})
        sense_data.setdefault('examples', []); sense_data.setdefault('sense_collocations', {})
        sense_data.setdefault('sense_semantic_relations', {}); sense_data.setdefault('link_chain_variations', [])

        if new_details:
            logger.debug("Merging details from LlmSenseDetailsOutput into sense data dict...")
            details_dump = new_details.model_dump(exclude_unset=True)
            # Merge definition
            if 'definition' in details_dump and details_dump['definition']:
                new_def = details_dump['definition']
                if new_def.get('language') == target_language:
                    idx = next((i for i, d in enumerate(sense_data['definitions']) if d.get('language') == target_language), -1)
                    if idx != -1:
                        if force_overwrite: sense_data['definitions'][idx] = new_def
                    else: sense_data['definitions'].append(new_def)
            # Merge translations
            if 'translations' in details_dump and details_dump['translations']:
                new_trans = details_dump['translations']
                if force_overwrite or target_language not in sense_data['translations']: sense_data['translations'][target_language] = new_trans
            # Merge examples
            if 'examples' in details_dump and details_dump['examples']:
                new_ex = details_dump['examples']
                if force_overwrite: sense_data['examples'] = new_ex
                else: sense_data['examples'].extend(new_ex)
            # Merge sense_register
            if 'sense_register' in details_dump and (force_overwrite or sense_data.get('sense_register') is None):
                sense_data['sense_register'] = details_dump['sense_register']
            # Merge sense_collocations
            if 'sense_collocations' in details_dump and details_dump['sense_collocations']:
                new_coll = details_dump['sense_collocations']
                if force_overwrite or target_language not in sense_data['sense_collocations']: sense_data['sense_collocations'][target_language] = new_coll
            # Merge sense_semantic_relations
            if 'sense_semantic_relations' in details_dump and details_dump['sense_semantic_relations']:
                new_rel = details_dump['sense_semantic_relations']
                if force_overwrite or target_language not in sense_data['sense_semantic_relations']: sense_data['sense_semantic_relations'][target_language] = new_rel
        else:
            logger.debug("No new sense details provided for merge.")

        # Remove base_word_id if it exists (Word validator handles it)
        if 'base_word_id' in sense_data: del sense_data['base_word_id']

        logger.info(f"Sense data dictionary prepared/updated for ID: {sense_data.get('sense_id')}")
        return sense_data
    except Exception as e:
         logger.exception("Unexpected error during MERGE_OR_CREATE_SENSE data preparation:")
         return {}

def GET_CHAIN_COUNT_FOR_TARGET_LANG(sense_data: Dict[str, Any], target_language: str) -> int:
    """Counts existing link chains for a specific target language within a Sense data dictionary."""
    link_chains = sense_data.get('link_chain_variations', [])
    if not link_chains: return 0
    count = 0
    for chain in link_chains:
         if isinstance(chain, LinkChain) and chain.target_language == target_language: count += 1
         elif isinstance(chain, dict) and chain.get('target_language') == target_language: count += 1
    sense_id_str = str(sense_data.get('sense_id'))[:8]; logger.debug(f"Found {count} existing link chains for sense {sense_id_str} and target lang {target_language}.")
    return count

# *** MODIFIED Function v1.21 ***
def CREATE_LinkChainObject(chain_data: LlmLinkChainOutput, target_language: str) -> LinkChain:
    """Creates a full LinkChain object from LLM output, handling potentially incomplete image_data."""
    logger.debug(f"Creating LinkChain object for target language {target_language}")
    # Start with the base data from the LLM output model
    lc_dict = chain_data.model_dump(exclude_unset=True, exclude={'image_data'}) # Exclude image_data for now

    # Add required fields
    lc_dict['target_language'] = target_language
    lc_dict['feedback_data'] = {}
    lc_dict['chain_id'] = uuid4()

    # --- Process Image Data ---
    final_image_data: Optional[ImageData] = None
    llm_image_data = chain_data.image_data # This is LlmImageDataOutput or None

    if llm_image_data and llm_image_data.prompt:
        # LLM provided a prompt, create placeholder ImageData
        logger.info("LLM provided image prompt. Creating placeholder image data.")
        try:
            final_image_data = ImageData(
                prompt=llm_image_data.prompt,
                type='placeholder',
                url="http://placeholder.com/image_pending" # Needs scheme for HttpUrl
            )
        except ValidationError as img_ve:
             logger.error(f"Failed to create placeholder ImageData: {img_ve}")
             # Proceed without image data if placeholder creation fails
             final_image_data = None
    elif llm_image_data:
        # LLM provided image_data but no prompt? Log warning.
         logger.warning(f"LLM provided image_data object but no prompt found: {llm_image_data}")
         final_image_data = None
    else:
         # LLM did not provide image_data at all
         logger.warning("LLM did not provide image_data for link chain.")
         # Create a default placeholder? Or allow it to be None?
         # Let's create a default placeholder indicating missing prompt
         try:
             final_image_data = ImageData(
                 prompt="Missing prompt from LLM.",
                 type='placeholder',
                 url="http://placeholder.com/image_missing"
             )
             logger.info("Created default placeholder image data due to missing LLM image_data.")
         except ValidationError as img_ve:
             logger.error(f"Failed to create default placeholder ImageData: {img_ve}")
             final_image_data = None


    # Assign the processed or placeholder image data to the dictionary
    # The LinkChain model itself requires image_data, so we must provide something
    if final_image_data:
        lc_dict['image_data'] = final_image_data
    else:
        # If even placeholder failed, we have a problem as LinkChain requires image_data
        logger.critical(f"Could not create valid ImageData for LinkChain {lc_dict['chain_id']}. Validation will likely fail.")
        # Assigning None will cause validation error later, which is correct.
        lc_dict['image_data'] = None


    # --- Validate final LinkChain structure ---
    try:
        # Now validate the complete dictionary against the final LinkChain model
        link_chain_obj = LinkChain.model_validate(lc_dict)
        logger.debug(f"LinkChain object created successfully: {link_chain_obj.chain_id}")
        return link_chain_obj
    except ValidationError as ve:
        logger.error(f"Pydantic validation error creating final LinkChain object: {ve}")
        logger.error(f"Data causing error: {lc_dict}")
        # Re-raise the error to be caught by the calling function
        raise ve


# --- Check LLM Result Helper ---
T = TypeVar('T', bound=BaseModel)

def _check_llm_result(result: Optional[Union[T, str, Dict[str, Any]]], expected_type: Type[T], step_name: str) -> Optional[T]:
    """Checks LLM results, returns validated model or None."""
    # [Function remains unchanged]
    if result is None:
        logger.error(f"LLM {step_name}: Failed - Received None response.")
        return None
    elif isinstance(result, dict) and 'error' in result:
        logger.error(f"LLM {step_name}: Failed - Error: {result.get('error')}")
        logger.debug(f"LLM {step_name}: Raw text was: {result.get('raw_text', 'N/A')[:500]}...")
        return None
    elif isinstance(result, expected_type):
        logger.info(f"LLM {step_name}: Successfully received and validated {expected_type.__name__}.")
        return result
    elif isinstance(result, str):
         logger.error(f"LLM {step_name}: Failed - Received raw string unexpectedly: {result[:100]}...")
         return None
    else:
        logger.error(f"LLM {step_name}: Failed - Received unexpected result type: {type(result)}.")
        return None


# --- Core Enrichment Function ---
async def run_enrichment_for_word(
    headword: str,
    source_language: Language,
    target_language: Language,
    categories: List[str],
    provider: Optional[str] = None,
    force_reenrich: bool = False,
    batch_info: Optional[EnrichmentInfo] = None,
    model_name: Optional[str] = None # Added model_name parameter
) -> Optional[Word]:
    """Performs the multi-step enrichment process for a given word."""
    # Added model_name pass-through
    enrichment_step = "Initialization"
    logger.info(f"--- Starting Enrichment for '{headword}' ({source_language} -> {target_language}) ---")
    provider_to_use = provider or DEFAULT_LLM_PROVIDER
    # Use specific model if provided, otherwise None (llm_client will use default)
    model_to_use = model_name
    logger.info(f"Using LLM Provider: {provider_to_use}, Model: {model_to_use or 'default'}")
    if force_reenrich: logger.info("Force Re-enrich Enabled for Target Language data.")

    try:
        # --- Load Config ---
        enrichment_step = "Load Config"
        config = GET_ENRICHMENT_CONFIG()
        config["default_provider"] = provider_to_use
        prompts = config['prompts']
        counts = config['counts']
        logger.info("Enrichment configuration loaded.")

        # --- Step 0: Get Existing Data or Initialize ---
        # [This step remains unchanged]
        enrichment_step = "Get Existing Data"
        existing_word_object: Optional[Word] = None
        core_details: Dict[str, Any] = {}
        word_id_to_use: Optional[UUID] = None
        logger.info(f"Searching for existing word: {headword} ({source_language})")
        search_results = await search_words(query=headword, language=source_language, limit=1)
        if search_results and search_results[0].headword == headword:
            existing_word_object = search_results[0]
            word_id_to_use = existing_word_object.word_id
            logger.info(f"Found existing word with ID: {word_id_to_use}")
            core_details = EXTRACT_CORE_DETAILS_FROM_OBJECT(existing_word_object)
        else:
            logger.info(f"No exact match found for '{headword}' ({source_language}). Creating new entry.")
            word_id_to_use = uuid4()
            core_details = {"headword": headword, "language": source_language, "categories": categories or [],
                            "pronunciation": None, "frequency_rank": None, "register": None, "etymology": {},
                            "collocations": {}, "semantic_relations": {}, "usage_notes": {}, "senses": []}
            logger.info(f"Generated new Word ID: {word_id_to_use}")
        if not word_id_to_use: logger.critical("CRITICAL ERROR: word_id_to_use not set."); return None


        # --- Step 1: Get Core Details & Senses (if needed) ---
        # [This step remains unchanged, uses model_to_use]
        enrichment_step = "Get Core Details/Senses (LLM)"
        initial_senses_llm: List[LlmSenseInfo] = []
        current_senses_data: List[Dict[str, Any]] = core_details.get('senses', []) # Start with dicts if existing
        needs_core_llm_call = (not existing_word_object) or (not current_senses_data) or force_reenrich
        if needs_core_llm_call:
            logger.info("Calling LLM for core details and senses...")
            prompt = prompts['get_senses'].format(headword=headword, language=source_language)
            llm_core_result = await generate_structured_content(
                prompt=prompt, response_model=LlmCoreDetailsOutput, provider=provider_to_use, model_name=model_to_use
            )
            validated_core_result = _check_llm_result(llm_core_result, LlmCoreDetailsOutput, "Get Core Details/Senses")
            if validated_core_result:
                 core_details['pronunciation'] = validated_core_result.pronunciation.model_dump() if validated_core_result.pronunciation else core_details.get('pronunciation')
                 core_details['frequency_rank'] = validated_core_result.frequency_rank if validated_core_result.frequency_rank is not None else core_details.get('frequency_rank')
                 core_details['register'] = validated_core_result.register if validated_core_result.register else core_details.get('register')
                 initial_senses_llm = validated_core_result.senses
                 logger.info(f"LLM identified {len(initial_senses_llm)} potential senses.")
                 processed_senses_data = []
                 existing_senses_map = {s_data['sense_id']: s_data for s_data in current_senses_data}
                 for llm_sense in initial_senses_llm:
                     found_sense_obj = FIND_SENSE_IN_OBJECT(existing_word_object, llm_sense.part_of_speech, llm_sense.brief_description)
                     merged_sense_data = MERGE_OR_CREATE_SENSE(found_sense_obj, llm_sense, None, source_language, target_language, force_reenrich)
                     if merged_sense_data: processed_senses_data.append(merged_sense_data)
                     else: logger.error(f"Failed to create/merge sense data dict for POS {llm_sense.part_of_speech}")
                 core_details['senses'] = processed_senses_data
                 current_senses_data = processed_senses_data
            else: logger.error(f"Failed to get core details/senses from LLM for {headword}. Aborting."); return None
        else: logger.info("Skipping LLM call for core details/senses.")
        if not current_senses_data:
             logger.error(f"No senses available for {headword} after Step 1."); return None # Removed partial save for simplicity
        logger.info(f"Proceeding to enrich {len(current_senses_data)} senses.")


        # --- Step 2: Get Core Details (Target Language) ---
        # [This step remains unchanged, uses model_to_use]
        enrichment_step = "Get Core Details Lang (LLM)"
        needs_lang_details_llm = force_reenrich or any(target_language not in (core_details.get(field) or {}) for field in ['etymology', 'collocations', 'semantic_relations', 'usage_notes'])
        if needs_lang_details_llm:
            logger.info(f"Calling LLM for target language ({target_language}) core details...")
            prompt = prompts['get_core_details_lang'].format(headword=headword, language=source_language, target_language=target_language)
            llm_lang_result = await generate_structured_content(
                 prompt=prompt, response_model=LlmCoreLangOutput, provider=provider_to_use, model_name=model_to_use
            )
            validated_lang_result = _check_llm_result(llm_lang_result, LlmCoreLangOutput, "Get Core Details Lang")
            if validated_lang_result: core_details = MERGE_MULTILINGUAL_DATA(core_details, validated_lang_result, target_language, force_overwrite=force_reenrich); logger.info(f"Successfully merged target language ({target_language}) core details.")
            else: logger.warning(f"Failed to get/merge target language ({target_language}) core details from LLM.")
        else: logger.info(f"Skipping LLM call for target language ({target_language}) core details.")


        # --- Step 3 & 4: Enrich Each Sense ---
        # [Uses model_to_use in calls]
        target_examples_per_sense = counts.get('target_examples_per_sense', 3)
        max_link_chains_per_sense = counts.get('max_link_chains_per_sense', 2)
        final_senses_data: List[Dict[str, Any]] = []

        for sense_data_dict in current_senses_data:
            sense_id = sense_data_dict.get('sense_id')
            pos = sense_data_dict.get('part_of_speech')
            source_def = next((d.get('text', 'N/A') for d in sense_data_dict.get('definitions', []) if d.get('language') == source_language), "N/A")
            enrichment_step = f"Enrich Sense Dict (ID: {str(sense_id)[:8]})"; logger.info(f"--- Processing Sense Dict: POS='{pos}', Desc='{source_def[:50]}...', ID='{sense_id}' ---")

            # Step 3: Get Sense Details
            enrichment_step = f"Get Sense Details (ID: {str(sense_id)[:8]}, LLM)"
            has_target_def = any(d.get('language') == target_language for d in sense_data_dict.get('definitions', []))
            has_target_trans = target_language in (sense_data_dict.get('translations', None) or {})
            needs_sense_details_llm = force_reenrich or not (has_target_def and has_target_trans)
            sense_details_result: Optional[LlmSenseDetailsOutput] = None
            if needs_sense_details_llm:
                logger.info(f"Calling LLM for target language ({target_language}) sense details...")
                prompt = prompts['get_sense_details'].format(headword=headword, language=source_language, pos=pos, sense_desc=source_def, target_language=target_language, num_examples=target_examples_per_sense)
                llm_sense_details_result = await generate_structured_content(prompt=prompt, response_model=LlmSenseDetailsOutput, provider=provider_to_use, model_name=model_to_use)
                sense_details_result = _check_llm_result(llm_sense_details_result, LlmSenseDetailsOutput, f"Get Sense Details (ID: {str(sense_id)[:8]})")
                if not sense_details_result: logger.warning(f"Failed to get target language ({target_language}) details for sense {sense_id}.")
            else: logger.info(f"Skipping LLM call for target language ({target_language}) sense details.")

            # Merge Sense Details into Dict
            llm_sense_info_context = LlmSenseInfo(part_of_speech=pos, brief_description=source_def)
            updated_sense_data_dict = MERGE_OR_CREATE_SENSE(None, llm_sense_info_context, sense_details_result, source_language, target_language, force_reenrich)
            if not updated_sense_data_dict: logger.error(f"Failed to update sense data dictionary for sense ID {sense_id}. Skipping."); continue
            sense_data_dict = updated_sense_data_dict # Use the updated dict

            # Step 4: Get Link Chains
            enrichment_step = f"Get Link Chains (ID: {str(sense_id)[:8]}, LLM)"
            current_chain_count = GET_CHAIN_COUNT_FOR_TARGET_LANG(sense_data_dict, target_language)
            chains_needed = max(0, max_link_chains_per_sense - current_chain_count)
            needs_link_chain_llm = (force_reenrich and max_link_chains_per_sense > 0) or (chains_needed > 0)
            if needs_link_chain_llm:
                num_chains_to_request = max_link_chains_per_sense if force_reenrich else chains_needed
                if num_chains_to_request > 0:
                    logger.info(f"Calling LLM to generate {num_chains_to_request} link chain(s)...")
                    prompt = prompts['get_link_chain'].format(headword=headword, language=source_language, pos=pos, sense_desc=source_def, source_language=source_language, target_language=target_language, num_chains=num_chains_to_request)
                    llm_link_chain_result = await generate_structured_content(prompt=prompt, response_model=LlmLinkChainsResponse, provider=provider_to_use, model_name=model_to_use)
                    validated_chains_result = _check_llm_result(llm_link_chain_result, LlmLinkChainsResponse, f"Get Link Chains (ID: {str(sense_id)[:8]})")
                    if validated_chains_result:
                        new_chains_created = 0
                        sense_data_dict.setdefault('link_chain_variations', [])
                        if force_reenrich:
                            logger.warning(f"Force re-enrich: Clearing existing link chains for sense {sense_id}, lang {target_language}")
                            sense_data_dict['link_chain_variations'] = [c for c in sense_data_dict['link_chain_variations'] if isinstance(c, dict) and c.get('target_language') != target_language]
                        for chain_data in validated_chains_result.link_chains:
                            if not force_reenrich and GET_CHAIN_COUNT_FOR_TARGET_LANG(sense_data_dict, target_language) >= max_link_chains_per_sense: break
                            try:
                                link_chain_obj = CREATE_LinkChainObject(chain_data, target_language)
                                # *** Append the OBJECT to the list within the dict ***
                                sense_data_dict['link_chain_variations'].append(link_chain_obj)
                                new_chains_created += 1
                            except Exception as chain_e: logger.error(f"Failed to create LinkChain object: {chain_e}")
                        logger.info(f"Successfully created {new_chains_created} new link chain(s) for sense {sense_id}.")
                    else: logger.warning(f"Failed to get link chains from LLM for sense {sense_id}.")
                else: logger.info("Skipping link chain LLM call as 0 chains are needed/requested.")
            else: logger.info(f"Skipping LLM call for link chains for sense {sense_id}.")

            final_senses_data.append(sense_data_dict); logger.info(f"--- Finished Processing Sense Dict ID: {str(sense_id)[:8]} ---")

        core_details['senses'] = final_senses_data


        # --- Step 5: Assemble Final Word Object ---
        # [This step remains unchanged]
        enrichment_step = "Assemble Final Word"; logger.info("Assembling final Word object...")
        enrichment_info_list = core_details.get('enrichment_history', []);
        if isinstance(enrichment_info_list, list) and batch_info: enrichment_info_list.append(batch_info)
        elif batch_info: enrichment_info_list = [batch_info]
        final_word_data = {**core_details, "word_id": word_id_to_use, "enrichment_history": enrichment_info_list, "senses": core_details['senses']}
        if '_sense_obj_' in final_word_data: del final_word_data['_sense_obj_']
        try:
             final_word = Word.model_validate(final_word_data); logger.info(f"Final Word object validated for ID: {final_word.word_id}")
        except ValidationError as ve:
            logger.error(f"Pydantic validation error assembling final Word object: {ve}")
            try: import json; error_data_json = json.dumps(final_word_data, default=str, indent=2); logger.error(f"Data causing error (JSON):\n{error_data_json}")
            except Exception as json_err: logger.error(f"Could not serialize error data to JSON: {json_err}"); logger.error(f"Data (raw): {final_word_data}")
            return None


        # --- Step 6: Save to Firestore ---
        # [This step remains unchanged]
        enrichment_step = "Save Word"; logger.info(f"Saving word {final_word.word_id} to Firestore...")
        saved_word = await save_word(final_word)
        if saved_word: logger.info(f"--- Enrichment SUCCESSFUL for '{headword}' (ID: {saved_word.word_id}) ---"); return saved_word
        else: logger.error(f"--- Enrichment FAILED for '{headword}' (Save operation returned None) ---"); return None

    except Exception as e:
        logger.exception(f"--- Enrichment FAILED for '{headword}' (Unexpected error during step: {enrichment_step}) ---")
        return None

# --- Main Execution Block (for testing) ---
# [Main execution block remains unchanged]
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
    parser = argparse.ArgumentParser(description="Run word enrichment process.")
    parser.add_argument("headword", help="Word"); parser.add_argument("language", help="Src Lang"); parser.add_argument("target_language", help="Tgt Lang")
    parser.add_argument("-c", "--categories", nargs='*', default=[]); parser.add_argument("-p", "--provider", help="LLM Provider"); parser.add_argument("-f", "--force", action='store_true')
    parser.add_argument("-m", "--model", help="LLM Model Name") # Add argument for model name
    args = parser.parse_args()
    test_batch_info = EnrichmentInfo(batch_id=f"manual-test-{uuid4()}", tags=["manual", "test"])

    async def run_test_enrichment():
        print(f"\n--- Running Enrichment Test ---"); print(f"Word: {args.headword}, Lang: {args.language}, Target: {args.target_language}, Provider: {args.provider or DEFAULT_LLM_PROVIDER}, Model: {args.model or 'default'}, Force: {args.force}"); print(f"---")
        result_word = await run_enrichment_for_word(
            headword=args.headword, source_language=args.language, target_language=args.target_language, categories=args.categories,
            provider=args.provider, force_reenrich=args.force, batch_info=test_batch_info, model_name=args.model # Pass model_name
        )
        print(f"\n--- Enrichment Test Complete ---"); print(f"Result: {'SUCCESS' if result_word else 'FAILED'}"); print(f"---")

    try: asyncio.run(run_test_enrichment())
    except RuntimeError as e:
       if "cannot run nested event loops" in str(e): logger.warning("Could not run async main directly."); print("Warning: Could not run async main directly.")
       else: raise e
    except Exception as e: logger.exception("Error running standalone enrichment test:"); print(f"An error occurred: {e}")