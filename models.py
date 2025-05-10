# models.py v1.4 - Adjusted LLM Link Chain Output
# Defines Pydantic models reflecting Specification: Word Data Structure v1.2

from pydantic import (
    BaseModel, Field, HttpUrl, field_validator, model_validator,
    ConfigDict, ValidationError, validator
)
from typing import List, Optional, Dict, Any, Literal, Union
from datetime import datetime
from uuid import UUID, uuid4
import re
import logging

logger = logging.getLogger(__name__)

# --- Primitive Types ---
Language = Literal['en', 'id', 'fr', 'es', 'de', 'ja', 'ko', 'zh']
def is_valid_language_code(code: str) -> bool:
    return bool(re.fullmatch(r'[a-z]{2}', code))

# --- Nested Schemas ---

class Pronunciation(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    ipa: Optional[str] = Field(default=None, alias='IPA', validation_alias='IPA')
    audio_url: Optional[HttpUrl] = None
    phonetic_spelling: Optional[str] = None

class TranslationDetail(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(..., description="The translated text.")
    nuance: Optional[str] = Field(default=None, description="Explanation of subtle differences in meaning, if any.")

class Example(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(..., description="The example sentence in the original language.")
    language: Language = Field(..., description="The language code of the example sentence text.")
    translations: Optional[Dict[Language, str]] = Field(default_factory=dict, description="Translations of the example sentence into various target languages.")
    example_level: Optional[Literal['A1', 'A2', 'B1', 'B2', 'C1', 'C2']] = Field(default=None, description="Estimated CEFR level of the example sentence vocabulary.")

class SemanticRelationDetail(BaseModel):
    model_config = ConfigDict(extra='forbid')
    synonyms: Optional[List[str]] = Field(default=None, description="List of words with similar meaning.")
    antonyms: Optional[List[str]] = Field(default=None, description="List of words with opposite meaning.")
    related_concepts: Optional[List[str]] = Field(default=None, description="List of related terms or concepts.")

class SyllableLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    syllable: str = Field(..., description="A syllable from the headword.")
    keyword_noun: str = Field(..., description="A concrete keyword (often a noun) in the learner's language that sounds like the syllable.")
    keyword_language: Language = Field(..., description="The language of the keyword noun.")

class ImageData(BaseModel):
    # Defines structure for associated images - KEPT STRICT HERE for final object
    model_config = ConfigDict(extra='forbid')
    type: Literal['ai_generated', 'stock', 'user_uploaded', 'placeholder'] = Field(..., description="Source/type of the image.")
    url: HttpUrl = Field(..., description="URL of the image file.")
    prompt: Optional[str] = Field(default=None, description="The prompt used to generate the image, if applicable.")
    source_model: Optional[str] = Field(default=None, description="The AI model used for generation, if applicable.")
    source: Optional[str] = Field(default=None, description="Original source attribution or description (e.g., stock photo site).")

class FeedbackCounts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    upvotes: int = Field(default=0, ge=0)
    downvotes: int = Field(default=0, ge=0)
    pins: int = Field(default=0, ge=0)

class RelatedForm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    form: str = Field(..., description="The related word form (e.g., 'computation').")
    explanation: str = Field(..., description="Explanation of the relationship (e.g., 'Noun form').")

class EnrichmentInfo(BaseModel):
    model_config = ConfigDict(extra='forbid')
    batch_id: str = Field(..., description="Identifier for the enrichment batch or process.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the enrichment event (UTC).")
    tags: Optional[List[str]] = Field(default=None, description="Optional tags for categorization.")


# --- Main Schemas ---

class SenseDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    language: Language = Field(..., description="Language code of the definition text.")
    text: str = Field(..., description="The definition text.")
    definition_level: Optional[Literal['A1', 'A2', 'B1', 'B2', 'C1', 'C2']] = Field(default=None, description="Estimated CEFR level of the definition vocabulary.")

class LinkChainBase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target_language: Optional[Language] = Field(default=None, description="The language this chain helps learn.")
    syllables: Optional[List[str]] = Field(default=None, description="Headword broken into pronounceable syllables.")
    syllable_links: Optional[List[SyllableLink]] = Field(default=None, description="Links between syllables and keywords.")
    narrative: str = Field(..., description="The mnemonic story/description (in learner's native language).")
    mnemonic_rhyme: Optional[str] = Field(default=None, description="Optional catchy rhyme summarizing the mnemonic.")
    explanation: Optional[str] = Field(default=None, description="Optional explanation of how the mnemonic works.")
    # Image data is required in the *final* LinkChain object
    image_data: Optional[ImageData] = Field(default=None, description="Associated image data.")
    validation_score: Optional[float] = Field(default=None, description="Internal score indicating quality/validity.")
    prompt_used: Optional[str] = Field(default=None, description="The specific LLM prompt used to generate this chain.")

class LinkChain(LinkChainBase):
    model_config = ConfigDict(extra='forbid')
    chain_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this link chain.")
    feedback_data: Dict[Language, FeedbackCounts] = Field(default_factory=dict, description="User feedback aggregated by learner language.")
    # Override image_data to make it required in the final object
    image_data: ImageData = Field(..., description="Associated image data (URL and type required).")


class SenseBase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    part_of_speech: str = Field(..., description="Grammatical part of speech.")
    definitions: List[SenseDefinition] = Field(default_factory=list, description="List of definitions in various languages.")
    translations: Optional[Dict[Language, List[TranslationDetail]]] = Field(default_factory=dict, description="Translations of this sense.")
    examples: List[Example] = Field(default_factory=list, description="Example sentences using this sense.")
    sense_register: Optional[str] = Field(default=None, description="Formality level specific to this sense.")
    sense_collocations: Optional[Dict[Language, List[str]]] = Field(default_factory=dict, description="Common word combinations specific to this sense.")
    sense_semantic_relations: Optional[Dict[Language, SemanticRelationDetail]] = Field(default_factory=dict, description="Semantic relations specific to this sense.")
    related_forms: Optional[List[RelatedForm]] = Field(default=None, description="Related word forms for this sense.")
    CEFR_level: Optional[Literal['A1', 'A2', 'B1', 'B2', 'C1', 'C2']] = Field(default=None, description="Estimated overall CEFR level for this sense.")
    usage_frequency: Optional[float] = Field(default=None, description="Relative frequency of this sense.")
    phonetic_transcription: Optional[str] = Field(default=None, description="Phonetic transcription specific to this sense.")

class Sense(SenseBase):
    model_config = ConfigDict(extra='forbid')
    sense_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this sense.")
    # Make base_word_id non-optional here, it *must* be set by the Word validator
    base_word_id: UUID = Field(..., description="Identifier of the parent Word object.")
    link_chain_variations: List[LinkChain] = Field(default_factory=list, description="List of mnemonic link chains for this sense.")


class WordBase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    headword: str = Field(..., description="The primary word form (lemma).")
    language: Language = Field(..., description="Language code of the headword.")
    categories: Optional[List[str]] = Field(default_factory=list, description="User-defined categories or tags.")
    pronunciation: Optional[Pronunciation] = Field(default=None, description="Pronunciation details for the headword.")
    frequency_rank: Optional[int] = Field(default=None, ge=1, description="Estimated frequency rank (1 = most frequent).")
    formality_register: Optional[str] = Field(default=None, alias="register", description="General formality level.") # Renamed field, kept alias for potential compatibility
    etymology: Optional[Dict[Language, str]] = Field(default_factory=dict, description="Word origin explanations by language.")
    collocations: Optional[Dict[Language, List[str]]] = Field(default_factory=dict, description="Common word combinations by language.")
    semantic_relations: Optional[Dict[Language, SemanticRelationDetail]] = Field(default_factory=dict, description="General semantic relations by language.")
    usage_notes: Optional[Dict[Language, str]] = Field(default_factory=dict, description="Usage notes or common mistakes by language.")
    # Senses list holds dictionaries during processing, validated into Sense objects by Word validator
    senses: List[Union[Sense, Dict[str, Any]]] = Field(default_factory=list, description="List of meanings (senses) of the word.")


class Word(WordBase):
    model_config = ConfigDict(extra='forbid')
    word_id: UUID = Field(default_factory=uuid4, description="Unique identifier for this word entry.")
    # Override senses to be list of validated Sense objects
    senses: List[Sense] = Field(default_factory=list, description="List of fully defined Sense objects.")
    enrichment_history: List[EnrichmentInfo] = Field(default_factory=list, description="Record of enrichment events.")
    created_at: Optional[datetime] = Field(default=None, description="Timestamp when the word entry was first created (UTC).")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp when the word entry was last updated (UTC).")

    @model_validator(mode='before')
    @classmethod
    def set_base_word_id_in_senses(cls, data: Any) -> Any:
        """Ensure base_word_id in each sense matches the parent word_id before validation."""
        if isinstance(data, dict) and 'word_id' in data and 'senses' in data:
            word_id = data['word_id']
            updated_senses = []
            has_changes = False
            for sense_data in data['senses']:
                # Ensure sense_data is a dict before modifying
                if isinstance(sense_data, dict):
                    current_base_id = sense_data.get('base_word_id')
                    if current_base_id != word_id:
                         logger.debug(f"Setting/Updating base_word_id for sense {sense_data.get('sense_id','NEW')} to {word_id}")
                         sense_data['base_word_id'] = word_id
                         has_changes = True
                    updated_senses.append(sense_data)
                elif isinstance(sense_data, Sense): # Should not happen with mode='before' but handle defensively
                     if sense_data.base_word_id != word_id:
                          logger.warning(f"Correcting base_word_id on Sense object {sense_data.sense_id} in before validator.")
                          sense_data.base_word_id = word_id # Note: Modifying model instance directly
                          has_changes = True
                     updated_senses.append(sense_data)
                else:
                     updated_senses.append(sense_data) # Append unchanged if not dict/Sense

            if has_changes:
                 data['senses'] = updated_senses
        elif not isinstance(data, dict):
             logger.warning(f"Word validator received unexpected data type: {type(data)}")

        return data

# --- Schemas for API Flow Inputs/Outputs ---

class EnrichmentInput(BaseModel):
  # Added protected_namespaces to resolve warning for 'model_name'
  model_config = ConfigDict(extra='forbid', protected_namespaces=()) 
  headword: str = Field(..., min_length=1)
  language: Language
  target_language: Language
  categories: List[str] = Field(default_factory=list)
  provider: Optional[str] = Field(default=None, description="Override default LLM provider.")
  force_reenrich: bool = Field(default=False, description="If true, overwrite existing target language data.")
  # Add model_name field
  model_name: Optional[str] = Field(default=None, description="Specify exact LLM model name (e.g., 'gemini-1.5-flash-preview-0514').")


class WordListItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    word_id: UUID
    headword: str
    language: Language
    categories: Optional[List[str]] = None
    primary_definition: Optional[str] = Field(default=None, description="A primary definition.")

# --- Schemas for LLM Interaction ---

class LlmSenseInfo(BaseModel):
    model_config = ConfigDict(extra='allow')
    part_of_speech: str
    brief_description: str

class LlmCoreDetailsOutput(BaseModel):
    model_config = ConfigDict(extra='allow')
    headword: Optional[str] = None
    language: Optional[Language] = None
    pronunciation: Optional[Pronunciation] = None
    frequency_rank: Optional[int] = None
    formality_register: Optional[str] = Field(default=None, alias="register") # Renamed field
    etymology: Optional[Dict[Language, str]] = None
    collocations: Optional[Dict[Language, List[str]]] = None
    semantic_relations: Optional[Dict[Language, SemanticRelationDetail]] = None
    usage_notes: Optional[Dict[Language, str]] = None
    senses: List[LlmSenseInfo] = Field(..., description="List of identified senses. MUST be present.")

class LlmCoreLangOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    etymology: Optional[str] = None
    collocations: Optional[List[str]] = None
    semantic_relations: Optional[SemanticRelationDetail] = None
    usage_notes: Optional[str] = None

class LlmSenseDetailsOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    definition: SenseDefinition
    translations: List[TranslationDetail] = Field(default_factory=list)
    examples: List[Example] = Field(default_factory=list)
    sense_register: Optional[str] = None
    sense_collocations: Optional[List[str]] = None
    sense_semantic_relations: Optional[SemanticRelationDetail] = None

# --- LLM Output Schemas for Link Chains ---

class LlmImageDataOutput(BaseModel):
     # Allow only prompt from LLM for image data
     model_config = ConfigDict(extra='allow') # Allow extra fields but only define prompt
     prompt: Optional[str] = None

class LlmLinkChainOutput(LinkChainBase):
    # Base fields from LinkChainBase, but make image_data optional and use LlmImageDataOutput
    model_config = ConfigDict(extra='forbid')
    # Override image_data to be optional and use the simpler LLM output model
    image_data: Optional[LlmImageDataOutput] = Field(default=None, description="Image prompt from LLM.")


class LlmLinkChainsResponse(BaseModel):
    # Expects a list of LlmLinkChainOutput objects
    model_config = ConfigDict(extra='forbid')
    link_chains: List[LlmLinkChainOutput] = Field(min_length=0)


# --- Vocabulary Category Schema ---

class LanguagePairConfiguration(BaseModel):
    """
    Defines configuration settings for specific language pairs based on the specification.
    """
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    id: Optional[str] = Field(default=None, description="Unique identifier for the configuration entry (auto-generated by Firestore on create)")
    language_pair: str = Field(..., description="Language pair in format 'source-target' (e.g., 'en-id')")
    config_key: str = Field(..., description="Identifier for the configuration setting")
    config_value: str = Field(..., description="Value of the configuration setting")
    value_type: Literal['string', 'number', 'boolean', 'array'] = Field(..., description="Data type of the configuration value")
    effective_date: datetime = Field(..., description="When this configuration becomes active")
    expiry_date: Optional[datetime] = Field(default=None, description="When this configuration should be retired")
    description: Optional[Dict[str, str]] = Field(default=None, description="Descriptions in different languages")
    updated_by: Optional[str] = Field(default=None, description="User/service that last updated this configuration")
    created_at: Optional[datetime] = Field(default=None, description="Timestamp when the configuration was created (UTC)")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp when the configuration was last updated (UTC)")

    @field_validator('language_pair')
    @classmethod
    def validate_language_pair_format(cls, v: str) -> str:
        if not re.match(r'^[a-z]{2}-[a-z]{2}$', v):
            raise ValueError("Language pair must be in format 'xx-yy' where xx and yy are 2-letter language codes")
        return v

class VocabularyCategory(BaseModel):
    """
    Defines the structure for a single vocabulary category used within the application.
    """
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    category_id: str = Field(..., description="Unique identifier for the category (e.g., 'basics_greetings', 'theme_food_drink'). Could be human-readable.")
    display_name: Dict[str, str] = Field(..., description="Dictionary holding user-facing names in different UI languages.")
    description: Optional[Dict[str, str]] = Field(default=None, description="Optional dictionary holding brief descriptions of the category content.")
    type: Literal['thematic', 'grammatical', 'functional', 'other'] = Field(..., description="Broad type of category.")
    applicable_cefr_levels: Optional[List[Literal['A1', 'A2', 'B1', 'B2', 'C1', 'C2']]] = Field(default=None, description="Optional: CEFR levels where this category is most relevant.")
    example_words: Optional[Dict[str, List[str]]] = Field(default=None, description="Optional dictionary holding a few illustrative example words (headwords) per language.")
    badge_id_association: Optional[str] = Field(default=None, description="Optional: Identifier for a related achievement badge in the app.")
    created_at: Optional[datetime] = Field(default=None, description="Timestamp when the category was first created (UTC).")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp when the category was last updated (UTC).")

    @field_validator('display_name', 'description', 'example_words')
    @classmethod
    def check_language_keys(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate that keys in language-keyed dictionaries are valid language codes."""
        if v is None:
            return v
        for key in v.keys():
            # Using a simple regex check for 2 lowercase letters for flexibility,
            # but could be tied to the Language Literal if strictness is needed.
            if not is_valid_language_code(key):
                 raise ValueError(f"Invalid language code '{key}' used as a key.")
        return v

# --- Schemas for Vocabulary List Generation & Management ---

class GeneratedWordListParameters(BaseModel):
    """Parameters used for generating a vocabulary list."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    list_readable_id: str = Field(..., description="Backend-generated, unique, human-readable ID.")
    status: str = Field(..., description="Workflow status of the list.") # Consider Enum later
    language: str = Field(..., description="Target language code.") # Consider Language Literal
    cefr_level: str = Field(..., description="Selected CEFR level.") # Consider CEFR Literal
    list_category_id: str = Field(..., description="Category ID from the 'master_categories' collection.")
    admin_notes: Optional[str] = Field(default=None, description="Optional internal notes by an administrator.")
    requested_word_count: int = Field(..., description="The number of words initially requested.")
    generated_word_count: Optional[int] = Field(default=None, description="The actual number of unique word items generated.")
    # enriched_word_ids: Optional[List[str]] = Field(default_factory=list, description="List of Firestore IDs for the fully enriched Word objects associated with this list.") # Field removed
    
    base_instruction_file_ref: str = Field(..., description="Path/reference to the base instruction file.")
    custom_instruction_file_ref: Optional[str] = Field(default=None, description="Path/reference to a custom instruction file.")
    ui_text_refinements: Optional[str] = Field(default=None, description="Text entered in UI for final small adjustments.")
    final_llm_prompt_text_sent: Optional[str] = Field(default=None, description="Log of the textual instructions sent to LLM.")
    
    source_model: str = Field(..., description="Specific Gemini model used.")
    gemini_temperature: float = Field(..., ge=0.0, le=2.0)
    gemini_top_p: float = Field(..., ge=0.0, le=1.0)
    gemini_top_k: int = Field(..., ge=1)
    gemini_max_output_tokens: int = Field(..., ge=1)
    gemini_stop_sequences: Optional[List[str]] = Field(default=None, description="Optional stop sequences for Gemini.")
    gemini_response_mime_type: str = Field(..., description="Expected response MIME type from Gemini (e.g., 'application/json', 'text/plain').")
    gemini_response_schema_used: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Schema provided to Gemini if JSON output, or reference to it.")
    
    include_english_translation: bool = Field(..., description="Indicates if English translations were requested.")
    generation_timestamp: Optional[datetime] = Field(default=None, description="Server-side timestamp of list creation (set by Firestore).")
    last_status_update_timestamp: Optional[datetime] = Field(default=None, description="Server-side timestamp of last status change (set by Firestore).")
    generated_by: str = Field(..., description="User ID of the admin who initiated generation.")
    reviewed_by: Optional[str] = Field(default=None, description="User ID of the admin who last reviewed/changed status.")

class WordItem(BaseModel):
    """Represents a single generated word item in a list, as expected from LLM output."""
    # model_config = ConfigDict(extra='allow') # Changed to 'forbid'
    model_config = ConfigDict(extra='forbid', populate_by_name=True) # Ensure populate_by_name for aliases

    word: str = Field(..., description="The generated word in the target language.", alias="headword") # Alias for consistency if LLM uses 'word'
    part_of_speech: Optional[str] = Field(default=None, description="e.g., 'noun', 'verb'")
    definition: Optional[str] = Field(default=None, description="A concise definition of the word.")
    example_sentence: Optional[str] = Field(default=None, description="An example sentence using the word.")
    difficulty_level: Optional[int] = Field(default=None, description="1-5, 5 being most difficult")
    cefr_level: Optional[str] = Field(default=None, description="e.g., 'A1', 'B2'") # Consider Literal if values are fixed
    
    # Define a specific model for translations to ensure additionalProperties: false
    class WordItemTranslations(BaseModel):
        model_config = ConfigDict(extra='forbid')
        es: Optional[str] = Field(default=None, description="Spanish translation")
        en: Optional[str] = Field(default=None, description="English translation")
        # Add other common languages if the LLM might provide them based on context
        # Or, make the prompt very specific about *only* providing 'es'.

    translations: Optional[WordItemTranslations] = Field(default=None, description="Translations into other languages.")
    # translation_en: Optional[str] = Field(default=None, description="English translation, if requested/provided.") # Covered by translations dict

    # If LLM might use 'headword' instead of 'word', ensure validation handles it.
    # Pydantic v2 with populate_by_name and alias in Field should handle this.
    # Alternatively, a root_validator could map 'headword' to 'word' if needed.

# --- Simplified Models for Direct LLM Output (Word List Generation) ---
# These models define the minimal JSON structure we expect directly from the LLM
# for the initial word list generation, focusing only on headword and English translation.

class SimpleWordEntry(BaseModel):
    """Represents a single word-translation pair expected directly from LLM."""
    model_config = ConfigDict(extra='forbid')
    headword: str = Field(..., description="The vocabulary word in the target language.")
    translation_en: Optional[str] = Field(default=None, description="The English translation of the headword.")

class LlmSimpleWordList(BaseModel):
    """
    Expected simple JSON structure from LLM for word list generation,
    containing a list of headword-translation_en pairs.
    This corresponds to the schema in 'llm_prompts/default_word_list_schema.json'.
    """
    model_config = ConfigDict(extra='forbid')
    words: List[SimpleWordEntry] = Field(..., description="List of generated word-translation pairs.")


# --- More Complex/Detailed Models (Potentially for LLM or internal use) ---

class LlmWordListResponse(BaseModel):
    """
    Expected structure from LLM for word list generation if it were to provide more detailed WordItems directly.
    NOTE: For the current simplified approach, LlmSimpleWordList is used for direct LLM output.
    This model (LlmWordListResponse with full WordItem) might be used if LLM capabilities or requirements change.
    """
    model_config = ConfigDict(extra='forbid')
    words: List[WordItem] = Field(..., description="List of generated word items.")

class GeneratedWordList(BaseModel):
    """Main model for a document in the GeneratedWordLists Firestore collection."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    list_firestore_id: Optional[str] = Field(default=None, description="Firestore document ID (not stored as a field in the document itself).")
    generation_parameters: GeneratedWordListParameters
    word_items: List[WordItem] = Field(default_factory=list, description="List of simple word items, potentially to be deprecated or used for quick preview.") # Clarified purpose

    # To be used when fetching from Firestore, to populate list_firestore_id
    @model_validator(mode='before')
    @classmethod
    def add_id_from_snapshot(cls, data: Any) -> Any:
        if hasattr(data, '_snapshot') and hasattr(data._snapshot, 'id'):
            data.list_firestore_id = data._snapshot.id
        return data

class GeneratedWordListSummary(BaseModel):
    """A summarized version of GeneratedWordList for table views."""
    model_config = ConfigDict(extra='forbid')

    list_firestore_id: str
    list_readable_id: str
    language: str
    cefr_level: str
    list_category_display_name: str # This will be resolved from list_category_id
    status: str
    generated_word_count: Optional[int] = None
    generation_timestamp: datetime

# --- Input Schema for Generate List API ---

class GenerateListInput(BaseModel):
    """Input payload structure for the POST /api/v1/generated-lists endpoint."""
    model_config = ConfigDict(extra='forbid')

    language: str = Field(..., description="Target language code.")
    cefr_level: str = Field(..., description="Selected CEFR level.")
    requested_word_count: int = Field(..., description="The number of words initially requested.")
    list_category_id: str = Field(..., description="Category ID from the 'master_categories' collection.")
    
    base_instruction_file_ref: str = Field(..., description="Path/reference to the base instruction file.")
    custom_instruction_file_ref: Optional[str] = Field(default=None, description="Path/reference to a custom instruction file.")
    ui_text_refinements: Optional[str] = Field(default=None, description="Text entered in UI for final small adjustments.")
    
    # Gemini API Parameters
    source_model: str = Field(..., description="Specific Gemini model used.")
    gemini_temperature: float = Field(..., ge=0.0, le=2.0)
    gemini_top_p: float = Field(..., ge=0.0, le=1.0)
    gemini_top_k: int = Field(..., ge=1)
    gemini_max_output_tokens: int = Field(..., ge=1)
    gemini_stop_sequences: Optional[List[str]] = Field(default=None, description="Optional stop sequences for Gemini.")
    gemini_response_mime_type: str = Field(..., description="Expected response MIME type from Gemini (e.g., 'application/json', 'text/plain').")
    gemini_response_schema_used: Optional[Union[Dict[str, Any], str]] = Field(default=None, description="Schema provided to Gemini if JSON output, or reference to it.")
    
    include_english_translation: bool = Field(..., description="Indicates if English translations were requested.")
    admin_notes: Optional[str] = Field(default=None, description="Optional internal notes by an administrator.")
    generated_by: str = Field(..., description="User ID of the admin who initiated generation.") # Assuming this comes from authenticated user context

# --- Schemas for Vocabulary List Generation & Management ---

class InstructionFile(BaseModel):
    file_path: str
    content: str

# --- Input Schema for Update List Metadata API ---

class UpdateListMetadataInput(BaseModel):
    """Input payload structure for the PATCH /api/v1/generated-lists/{id}/metadata endpoint."""
    model_config = ConfigDict(extra='forbid') # Forbid extra fields in PATCH

    status: Optional[str] = Field(default=None, description="New workflow status.")
    list_category_id: Optional[str] = Field(default=None, description="New category ID.")
    admin_notes: Optional[str] = Field(default=None, description="Updated admin notes (can be empty string to clear).")
    reviewed_by: Optional[str] = Field(default=None, description="User ID of the reviewer.")
    # enriched_word_ids: Optional[List[str]] = Field(default=None, description="Update the list of enriched word IDs.") # Field removed

    # Ensure at least one field is provided for update
    @model_validator(mode='before')
    @classmethod
    def check_at_least_one_value(cls, data: Any) -> Any:
        if isinstance(data, dict) and not any(v is not None for v in data.values()): # Check for any non-None value
            raise ValueError("At least one field must be provided for update.")
        return data
