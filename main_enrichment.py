# main_enrichment.py
# Orchestrates the word enrichment process using Firestore and LLM clients.
# Accepts LLM provider via command-line argument.

import asyncio
import sys
import argparse # *** Import argparse ***
from uuid import uuid4
from typing import Optional, List

# Import Pydantic models and types
try:
    from models import (
        Word, WordBase, Sense, SenseBase, LinkChain, LinkChainBase,
        EnrichmentInput, Language, LlmSenseInfo,
        LlmCoreDetailsOutput, LlmSenseDetailsOutput, LlmLinkChainsResponse
    )
except ImportError as e:
    print(f"Error: Could not import Pydantic models from models.py: {e}")
    sys.exit(1)

# Import client functions
try:
    # Assuming firestore_client.py is in the same directory
    from firestore_client import save_word
except ImportError as e:
    print(f"Error: Could not import Firestore client functions from firestore_client.py: {e}")
    sys.exit(1)

try:
    # Assuming llm_client.py is in the same directory
    from llm_client import generate_structured_content
    # *** Import default provider from config ***
    from config import DEFAULT_LLM_PROVIDER
except ImportError as e:
    print(f"Error: Could not import from llm_client.py or config.py: {e}")
    sys.exit(1)

# *** Modified function to accept provider ***
async def run_enrichment_for_word(
    input_data: EnrichmentInput,
    llm_provider: str # Added provider argument
) -> Optional[Word]:
    """
    Performs the multi-step enrichment process for a single word using the specified LLM provider.

    Args:
        input_data: An EnrichmentInput object containing headword, language, target_language.
        llm_provider: The LLM provider to use ('googleai' or 'deepseek').

    Returns:
        The fully enriched and saved Word object, or None if enrichment failed.
    """
    print(f"\n--- Starting Enrichment for '{input_data.headword}' ({input_data.language} -> {input_data.target_language}) ---")
    print(f"--- Using LLM Provider: {llm_provider} ---")

    try:
        # --- Step 1: Generate Core Details & Identify Senses ---
        core_prompt = f"""Analyze the word "{input_data.headword}" (language: {input_data.language}).
Provide its core linguistic details including:
- headword (as provided)
- language (as provided)
- pronunciation (IPA, phonetic spelling if applicable, as an object or null)
- frequency_rank (estimated integer, or null)
- register (e.g., formal, informal, null)
- etymology (brief, or null)
- collocations (list of strings, or null)
- semantic_relations (object with synonyms, antonyms, related_concepts as lists of strings, or null)
- usage_notes (brief notes, or null)
- senses: A list identifying distinct senses, each with 'part_of_speech' and a 'brief_description'.
Structure the output strictly as JSON matching the LlmCoreDetailsOutput schema."""

        core_details_result = await generate_structured_content(
            prompt=core_prompt,
            response_model=LlmCoreDetailsOutput,
            provider=llm_provider, # *** Pass provider ***
            temperature=0.3
        )

        if not isinstance(core_details_result, LlmCoreDetailsOutput):
            print(f"ERROR: Failed to get valid core details for '{input_data.headword}'. Aborting enrichment.")
            return None
        print("Step 1: Core details generated successfully.")

        # --- Step 2: Generate Details for Each Sense ---
        enriched_senses_data: List[SenseBase] = []
        if core_details_result.senses:
            print(f"Step 2: Enriching {len(core_details_result.senses)} identified senses...")
            for sense_info in core_details_result.senses:
                sense_prompt = f"""For the word "{input_data.headword}" ({input_data.language}), specifically the sense meaning "{sense_info.brief_description}" ({sense_info.part_of_speech}):
Provide detailed enrichment data including:
- definition (object with text and language '{input_data.language}')
- translations into {input_data.target_language} (list of objects with text, language '{input_data.target_language}', optional nuance)
- examples (list of objects with text in '{input_data.language}', language '{input_data.language}', optional translation)
- sense_register (optional string)
- sense_collocations (optional list of strings)
- sense_semantic_relations (optional object with synonyms, antonyms, related_concepts lists)
Structure the output strictly as JSON matching the LlmSenseDetailsOutput schema."""

                sense_details_result = await generate_structured_content(
                    prompt=sense_prompt,
                    response_model=LlmSenseDetailsOutput,
                    provider=llm_provider, # *** Pass provider ***
                    temperature=0.4
                )

                if isinstance(sense_details_result, LlmSenseDetailsOutput):
                    enriched_senses_data.append(SenseBase(
                        part_of_speech=sense_info.part_of_speech,
                        definition=sense_details_result.definition,
                        translations=sense_details_result.translations,
                        examples=sense_details_result.examples,
                        sense_register=sense_details_result.sense_register,
                        sense_collocations=sense_details_result.sense_collocations,
                        sense_semantic_relations=sense_details_result.sense_semantic_relations
                    ))
                    print(f" - Enriched sense: {sense_info.brief_description}")
                else:
                    print(f"WARNING: Failed to get valid details for sense: {sense_info.brief_description}. Skipping sense.")
        else:
            print("Step 2: No senses identified by LLM in Step 1.")

        # --- Step 3: Generate Link Chains ---
        enriched_link_chains_data: List[LinkChainBase] = []
        link_chain_prompt = f"""Generate 1 or 2 distinct, creative, and memorable mnemonic link chains for the word "{input_data.headword}" ({input_data.language}) to help someone learning {input_data.target_language}.
Each chain should include:
- syllables (list of strings)
- syllable_links (list of objects with syllable, keyword_noun, keyword_language)
- narrative (string explaining the mnemonic story)
- image_prompt (optional string describing an image for the narrative)
Structure the output strictly as JSON matching the LlmLinkChainsResponse schema."""

        print("Step 3: Generating link chains...")
        link_chain_result = await generate_structured_content(
            prompt=link_chain_prompt,
            response_model=LlmLinkChainsResponse,
            provider=llm_provider, # *** Pass provider ***
            temperature=0.7
        )

        if isinstance(link_chain_result, LlmLinkChainsResponse) and link_chain_result.link_chains:
            enriched_link_chains_data = [LinkChainBase(**lc.model_dump()) for lc in link_chain_result.link_chains]
            print(f" - Generated {len(enriched_link_chains_data)} link chains.")
        else:
            print("WARNING: Failed to generate valid link chains or none were generated.")

        # --- Step 4: Assemble the Full Word Object ---
        print("Step 4: Assembling final word object...")
        new_word_id = uuid4()
        final_senses = [Sense(sense_id=uuid4(), word_id=new_word_id, **s.model_dump()) for s in enriched_senses_data]
        final_link_chains = [LinkChain(chain_id=uuid4(), word_id=new_word_id, **lc.model_dump()) for lc in enriched_link_chains_data]

        word_to_save = Word(
            word_id=new_word_id,
            headword=core_details_result.headword,
            language=core_details_result.language,
            pronunciation=core_details_result.pronunciation,
            frequency_rank=core_details_result.frequency_rank,
            register=core_details_result.register,
            etymology=core_details_result.etymology,
            collocations=core_details_result.collocations,
            semantic_relations=core_details_result.semantic_relations,
            usage_notes=core_details_result.usage_notes,
            senses=final_senses,
            link_chains=final_link_chains
        )
        print(f" - Assembled Word object with ID: {new_word_id}")

        # --- Step 5: Save to Firestore ---
        print(f"Step 5: Saving word '{input_data.headword}' to Firestore...")
        saved_word = await save_word(word_to_save)

        if saved_word:
            print(f"--- Enrichment SUCCESS for '{input_data.headword}' ---")
            return saved_word
        else:
            print(f"--- Enrichment FAILED for '{input_data.headword}' (Save operation failed) ---")
            return None

    except Exception as e:
        print(f"--- Enrichment FAILED for '{input_data.headword}' (Unexpected error in run_enrichment_for_word) ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


# --- Main Execution Block ---
if __name__ == '__main__':

    # *** Set up argument parser ***
    parser = argparse.ArgumentParser(description="Run word enrichment using a specified LLM provider.")
    parser.add_argument(
        "-p", "--provider",
        choices=['googleai', 'deepseek'],
        default=DEFAULT_LLM_PROVIDER, # Default from config.py
        help="Specify the LLM provider to use ('googleai' or 'deepseek')."
    )
    # Add arguments for headword, language, target_language if needed later
    # parser.add_argument("headword", help="The headword to enrich.")
    # parser.add_argument("language", choices=['en', 'id'], help="The source language.")
    # parser.add_argument("target_language", choices=['en', 'id'], help="The target language.")

    args = parser.parse_args()
    selected_provider = args.provider
    # --- End argument parser setup ---

    async def run_example():
        # Define the word to enrich (currently hardcoded)
        example_input = EnrichmentInput(
            headword="makan",
            language="id",
            target_language="en"
        )
        # Run the enrichment process using the selected provider
        enriched_word = await run_enrichment_for_word(
            input_data=example_input,
            llm_provider=selected_provider # *** Pass selected provider ***
        )

        if enriched_word:
            print("\n--- Final Saved Word Data ---")
            print(enriched_word.model_dump_json(indent=2))
        else:
            print("\nEnrichment process did not complete successfully.")

    # Run the async example function
    try:
       asyncio.run(run_example())
    except RuntimeError as e:
       if "cannot run nested event loops" in str(e):
           print("Warning: Could not run async main directly (likely due to existing event loop).")
       else:
           raise e
