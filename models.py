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
    register: Optional[str] = Field(default=None, description="General formality level.")
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
  model_config = ConfigDict(extra='forbid')
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
    register: Optional[str] = None
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