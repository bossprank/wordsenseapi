# models.py
# Defines Pydantic models for data validation and structure, similar to Zod schemas.

from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from typing import List, Optional, Dict, Any, Literal, Union
from datetime import datetime
from uuid import UUID, uuid4

# --- Primitive Types ---
Language = Literal['en', 'id']

# --- Nested Schemas ---

class Pronunciation(BaseModel):
    # Allow extra fields temporarily if needed for debugging, but forbid is safer
    # model_config = ConfigDict(extra='allow')
    model_config = ConfigDict(extra='forbid', populate_by_name=True) # Allow population by alias

    # *** Use alias to allow "IPA" (uppercase) from LLM response ***
    # Pydantic will try to populate 'ipa' using the field name 'ipa' first,
    # then using the alias 'IPA'.
    ipa: Optional[str] = Field(default=None, alias='IPA', validation_alias='IPA')
    audio_url: Optional[HttpUrl] = None
    phonetic_spelling: Optional[str] = None

class Translation(BaseModel):
    model_config = ConfigDict(extra='forbid')

    text: str
    language: Language
    nuance: Optional[str] = None

class Example(BaseModel):
    model_config = ConfigDict(extra='forbid')

    text: str
    language: Language
    translation: Optional[str] = None

class SemanticRelations(BaseModel):
    model_config = ConfigDict(extra='forbid')

    synonyms: Optional[List[str]] = None
    antonyms: Optional[List[str]] = None
    related_concepts: Optional[List[str]] = None

class SyllableLink(BaseModel):
    model_config = ConfigDict(extra='forbid')

    syllable: str
    keyword_noun: str # Should be concrete/imageable
    keyword_language: Language

# --- Main Schemas ---

class SenseDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid')

    text: str
    language: Language

class SenseBase(BaseModel):
    """Base model for Sense data, used for creation."""
    model_config = ConfigDict(extra='forbid')

    part_of_speech: str
    definition: SenseDefinition
    translations: List[Translation] = Field(default_factory=list)
    examples: List[Example] = Field(default_factory=list)
    sense_register: Optional[str] = None
    sense_collocations: Optional[List[str]] = None
    sense_semantic_relations: Optional[SemanticRelations] = None

class Sense(SenseBase):
    """Full Sense model including generated ID."""
    model_config = ConfigDict(extra='forbid')

    sense_id: UUID = Field(default_factory=uuid4)
    word_id: UUID # Link back to the word

class LinkChainBase(BaseModel):
    """Base model for LinkChain data, used for creation."""
    model_config = ConfigDict(extra='forbid')

    syllables: List[str]
    syllable_links: List[SyllableLink]
    narrative: str
    image_prompt: Optional[str] = None

class LinkChain(LinkChainBase):
    """Full LinkChain model including generated ID."""
    model_config = ConfigDict(extra='forbid')

    chain_id: UUID = Field(default_factory=uuid4)
    word_id: UUID # Link back to the word

class WordBase(BaseModel):
    """Base model for Word data, used for creation/updates."""
    model_config = ConfigDict(extra='forbid')

    headword: str
    language: Language
    pronunciation: Optional[Pronunciation] = None
    frequency_rank: Optional[int] = None
    register: Optional[str] = None
    etymology: Optional[str] = None
    collocations: Optional[List[str]] = None
    semantic_relations: Optional[SemanticRelations] = None
    usage_notes: Optional[str] = None
    senses: List[SenseBase] = Field(default_factory=list)
    link_chains: List[LinkChainBase] = Field(default_factory=list)

class Word(WordBase):
    """
    Full Word model representing the complete structure in Firestore,
    including generated IDs and timestamps.
    """
    model_config = ConfigDict(extra='forbid')

    word_id: UUID = Field(default_factory=uuid4)
    senses: List[Sense] = Field(default_factory=list)
    link_chains: List[LinkChain] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# --- Schemas for API Flow Inputs/Outputs ---

class EnrichmentInput(BaseModel):
  model_config = ConfigDict(extra='forbid')

  headword: str
  language: Language
  target_language: Language

# --- Schemas for LLM Interaction ---

class LlmSenseInfo(BaseModel):
    model_config = ConfigDict(extra='forbid')

    part_of_speech: str = Field(description="Part of speech for this sense (e.g., noun, verb).")
    brief_description: str = Field(description="A concise definition or description of this specific sense.")

class LlmCoreDetailsOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    headword: str = Field(description="The analyzed headword.")
    language: Language = Field(description="The language of the headword.")
    pronunciation: Optional[Pronunciation] = Field(None, description="Pronunciation details (IPA, audio URL).")
    frequency_rank: Optional[int] = Field(None, description="Estimated frequency rank.")
    register: Optional[str] = Field(None, description="Register (e.g., formal, informal).")
    etymology: Optional[str] = Field(None, description="Word origin information.")
    collocations: Optional[List[str]] = Field(None, description="Common words used with the headword.")
    semantic_relations: Optional[SemanticRelations] = Field(None, description="Synonyms, antonyms, related concepts.")
    usage_notes: Optional[str] = Field(None, description="Notes on how the word is used.")
    senses: List[LlmSenseInfo] = Field(description="An array identifying the distinct senses of the word.")

class LlmSenseDetailsOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    definition: SenseDefinition = Field(description="Detailed definition for this specific sense.")
    translations: List[Translation] = Field(default_factory=list, description="Translations of this sense into the target language.")
    examples: List[Example] = Field(default_factory=list, description="Example sentences using this sense.")
    sense_register: Optional[str] = Field(None, description="Register specific to this sense.")
    sense_collocations: Optional[List[str]] = Field(None, description="Collocations specific to this sense.")
    sense_semantic_relations: Optional[SemanticRelations] = Field(None, description="Semantic relations specific to this sense.")

class LlmLinkChainOutput(LinkChainBase):
    model_config = ConfigDict(extra='forbid')
    pass

class LlmLinkChainsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    link_chains: List[LlmLinkChainOutput] = Field(min_length=0, max_length=2, description="Zero, one, or two generated mnemonic link chains.")
