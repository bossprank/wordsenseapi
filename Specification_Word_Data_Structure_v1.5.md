# Project Data Structure Specification v1.5 (Reflecting Codebase State)

This document describes the key JSON data structures used throughout the `wordsenseapi` project, including the Word Enrichment API and administration interfaces, based on the current implementation in the codebase (as of `models.py v1.4`, `main.py v1.10`, `main_enrichment.py v1.21`, and administration-related code).

**Key Changes from v1.0 Baseline (Word Data Structure) and subsequent updates:**

*   Expanded scope to include administration-related data structures.
*   Introduced `EnrichmentInput` model for API request payload.
*   Refined `Word` and `Sense` structures based on Pydantic model definitions.
*   Added `EnrichmentInfo` to track enrichment history within the `Word` object.
*   Added `ImageData` structure for image details within `LinkChain`.
*   Added `FeedbackCounts` structure for user feedback within `LinkChain`.
*   Added `RelatedForm` structure for related word forms within `Sense`.
*   Added `SenseDefinition` structure for definitions within `Sense`.
*   Added `TranslationDetail` structure for translations within `Sense`.
*   Added `SyllableLink` structure for mnemonic links within `LinkChain`.
*   The `User Learning Data Object` from v1.0 does *not* appear to be directly implemented as a Pydantic model or explicitly used in the core enrichment/API flow in the analyzed files. It might be handled elsewhere (e.g., frontend, separate service) or is a planned future feature. It is therefore omitted from this code-validated specification.
*   Added various LLM-specific input/output models (`LlmSenseInfo`, `LlmCoreDetailsOutput`, `LlmCoreLangOutput`, `LlmSenseDetailsOutput`, `LlmImageDataOutput`, `LlmLinkChainOutput`, `LlmLinkChainsResponse`) which represent intermediate data structures used during the enrichment process, but are not part of the final `Word` object structure returned by the main API endpoint. These are included for completeness regarding codebase structures but are marked as internal.
*   Added `LanguagePairConfiguration` structure for language-pair specific settings.
*   Added `VocabularyCategory` structure for managing vocabulary categories.

---

**1. EnrichmentInput Object (API Request Payload)**

Represents the input payload for the `/api/v1/enrich` endpoint.

*   `headword` (string, **required**): The primary word form (lemma) to enrich. Must have a minimum length of 1.
*   `language` (string, **required**): Language code of the `headword` (e.g., 'en', 'id'). Validated against a predefined set of languages.
*   `target_language` (string, **required**): The language for which enrichment details (definitions, translations, etc.) are requested. Validated against a predefined set of languages.
*   `categories` (array of strings, optional): User-defined categories or tags for the word. Defaults to an empty list `[]`.
*   `provider` (string, optional): Override the default LLM provider. Defaults to `null`.
*   `force_reenrich` (boolean, optional): If `true`, forces re-enrichment and overwrites existing data for the target language. Defaults to `false`.
*   `model_name` (string, optional): Specify an exact LLM model name (e.g., 'gemini-1.5-flash-preview-0514'). Defaults to `null`.

---

**2. Word Object (API Response Payload)**

Represents the enriched word entry returned by the `/api/v1/enrich` endpoint.

*   `word_id` (UUID, **required**): Unique identifier for this word entry. Generated automatically.
*   `headword` (string, **required**): The primary word form (lemma).
*   `language` (string, **required**): Language code of the headword.
*   `categories` (array of strings, optional): User-defined categories or tags. Defaults to `[]`.
*   `pronunciation` (Pronunciation Object, optional): Pronunciation details for the headword. Defaults to `null`.
*   `frequency_rank` (integer, optional): Estimated frequency rank (1 = most frequent). Must be greater than or equal to 1. Defaults to `null`.
*   `register` (string, optional): General formality level (e.g., "formal", "informal", "neutral", "slang"). Defaults to `null`.
*   `etymology` (dictionary, optional): Word origin explanations, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: Etymology text (string)
*   `collocations` (dictionary, optional): Common word combinations, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: List of collocations (array of strings)
*   `semantic_relations` (dictionary, optional): General semantic relations, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: SemanticRelationDetail Object
*   `usage_notes` (dictionary, optional): Usage notes or common mistakes, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: Usage notes text (string)
*   `senses` (array of Sense Objects, **required**): List of meanings (senses) of the word. Defaults to `[]`.
*   `enrichment_history` (array of EnrichmentInfo Objects, **required**): Record of enrichment events. Defaults to `[]`.
*   `created_at` (datetime, optional): Timestamp when the word entry was first created (UTC). Defaults to `null`.
*   `updated_at` (datetime, optional): Timestamp when the word entry was last updated (UTC). Defaults to `null`.

---

**3. Sense Object (Nested within Word Object)**

Represents a specific meaning/part-of-speech of a word.

*   `sense_id` (UUID, **required**): Unique identifier for this sense. Generated automatically.
*   `base_word_id` (UUID, **required**): Identifier of the parent Word object. Set by the Word validator.
*   `part_of_speech` (string, **required**): Grammatical part of speech (e.g., "VERB", "NOUN").
*   `definitions` (array of SenseDefinition Objects, **required**): List of definitions in various languages. Defaults to `[]`.
*   `translations` (dictionary, optional): Translations of this sense, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: List of TranslationDetail Objects
*   `examples` (array of Example Objects, **required**): Example sentences using this sense. Defaults to `[]`.
*   `sense_register` (string, optional): Formality level specific to this sense. Defaults to `null`.
*   `sense_collocations` (dictionary, optional): Common word combinations specific to this sense, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: List of collocations (array of strings)
*   `sense_semantic_relations` (dictionary, optional): Semantic relations specific to this sense, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: SemanticRelationDetail Object
*   `related_forms` (array of RelatedForm Objects, optional): Related word forms for this sense. Defaults to `null`.
*   `CEFR_level` (string, optional): Estimated overall CEFR level for this sense (e.g., 'A1', 'B2'). Defaults to `null`.
*   `usage_frequency` (float, optional): Relative frequency of this sense. Defaults to `null`.
*   `phonetic_transcription` (string, optional): Phonetic transcription specific to this sense. Defaults to `null`.
*   `link_chain_variations` (array of LinkChain Objects, **required**): List of mnemonic link chains for this sense. Defaults to `[]`.

---

**4. Pronunciation Object (Nested within Word Object)**

Details about the headword's pronunciation.

*   `ipa` (string, optional): International Phonetic Alphabet transcription. Defaults to `null`.
*   `audio_url` (HttpUrl, optional): URL of an audio file for pronunciation. Defaults to `null`.
*   `phonetic_spelling` (string, optional): Simplified spelling for learners (e.g., "mah-KAHN"). Defaults to `null`.

---

**5. SemanticRelationDetail Object (Nested within Word and Sense Objects)**

Details about semantic relationships.

*   `synonyms` (array of strings, optional): List of words with similar meaning. Defaults to `null`.
*   `antonyms` (array of strings, optional): List of words with opposite meaning. Defaults to `null`.
*   `related_concepts` (array of strings, optional): List of related terms or concepts. Defaults to `null`.

---

**6. EnrichmentInfo Object (Nested within Word Object)**

Record of an enrichment event.

*   `batch_id` (string, **required**): Identifier for the enrichment batch or process.
*   `timestamp` (datetime, **required**): Timestamp of the enrichment event (UTC). Defaults to the current UTC time.
*   `tags` (array of strings, optional): Optional tags for categorization. Defaults to `null`.

---

**7. SenseDefinition Object (Nested within Sense Object)**

A definition for a specific sense.

*   `language` (string, **required**): Language code of the definition text.
*   `text` (string, **required**): The definition text.
*   `definition_level` (string, optional): Estimated CEFR level of the vocabulary used in the definition text (e.g., 'A1', 'C2'). Defaults to `null`.

---

**8. TranslationDetail Object (Nested within Sense Object)**

A translation for a specific sense.

*   `text` (string, **required**): The translated text.
*   `nuance` (string, optional): Explanation of subtle differences in meaning, if any. Defaults to `null`.

---

**9. Example Object (Nested within Sense Object)**

An example sentence using a specific sense.

*   `text` (string, **required**): The example sentence in the original language.
*   `language` (string, **required**): The language code of the example sentence text.
*   `translations` (dictionary, optional): Translations of the example sentence into various target languages, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: Translation text (string)
*   `example_level` (string, optional): Estimated CEFR level of the example sentence vocabulary (e.g., 'A1', 'C2'). Defaults to `null`.

---

**10. RelatedForm Object (Nested within Sense Object)**

A related word form for a specific sense.

*   `form` (string, **required**): The related word form (e.g., 'computation').
*   `explanation` (string, **required**): Explanation of the relationship (e.g., 'Noun form').

---

**11. LinkChain Object (Nested within Sense Object)**

A mnemonic link chain for a specific sense.

*   `chain_id` (UUID, **required**): Unique identifier for this link chain. Generated automatically.
*   `target_language` (string, optional): The language this chain helps learn. Defaults to `null`.
*   `syllables` (array of strings, optional): Headword broken into pronounceable syllables. Defaults to `null`.
*   `syllable_links` (array of SyllableLink Objects, optional): Links between syllables and keywords. Defaults to `null`.
*   `narrative` (string, **required**): The mnemonic story/description (in learner's native language).
*   `mnemonic_rhyme` (string, optional): Optional catchy rhyme summarizing the mnemonic. Defaults to `null`.
*   `explanation` (string, optional): Optional explanation of how the mnemonic works. Defaults to `null`.
*   `image_data` (ImageData Object, **required**): Associated image data (URL and type required).
*   `validation_score` (float, optional): Internal score indicating quality/validity. Defaults to `null`.
*   `prompt_used` (string, optional): The specific LLM prompt used to generate this chain. Defaults to `null`.
*   `feedback_data` (dictionary, **required**): User feedback aggregated by learner language, keyed by language code. Defaults to `{}`.
    *   Key: Language code (string)
    *   Value: FeedbackCounts Object

---

**12. SyllableLink Object (Nested within LinkChain Object)**

A link between a syllable and a keyword for a mnemonic.

*   `syllable` (string, **required**): A syllable from the headword.
*   `keyword_noun` (string, **required**): A concrete keyword (often a noun) in the learner's language that sounds like the syllable.
*   `keyword_language` (string, **required**): The language of the keyword noun.

---

**13. ImageData Object (Nested within LinkChain Object)**

Structure for associated images.

*   `type` (string, **required**): Source/type of the image ('ai_generated', 'stock', 'user_uploaded', 'placeholder').
*   `url` (HttpUrl, **required**): URL of the image file.
*   `prompt` (string, optional): The prompt used to generate the image, if applicable. Defaults to `null`.
*   `source_model` (string, optional): The AI model used for generation, if applicable. Defaults to `null`.
*   `source` (string, optional): Original source attribution or description (e.g., stock photo site). Defaults to `null`.

---

**14. FeedbackCounts Object (Nested within LinkChain Object)**

User feedback counts.

*   `upvotes` (integer, **required**): Number of upvotes. Must be greater than or equal to 0. Defaults to 0.
*   `downvotes` (integer, **required**): Number of downvotes. Must be greater than or equal to 0. Defaults to 0.
*   `pins` (integer, **required**): Number of pins. Must be greater than or equal to 0. Defaults to 0.

---

**15. VocabularyCategory Object (Stored in `master_categories` Collection)**

Defines the structure for a single vocabulary category used within the application. This structure is managed via the `/manage-categories` UI.

*   `category_id` (string, **required**): Unique identifier for the category (e.g., "basics_greetings", "theme_food_drink"). Used as the Firestore document ID.
*   `display_name` (dictionary, **required**): Dictionary holding user-facing names in different UI languages.
    *   Key: Language code (string, e.g., "en", "id")
    *   Value: Display name (string)
*   `description` (dictionary, optional): Optional dictionary holding brief descriptions of the category content. Defaults to `null`.
    *   Key: Language code (string)
    *   Value: Description text (string)
*   `type` (string, **required**): Broad type of category (enum: 'thematic', 'grammatical', 'functional', 'other').
*   `applicable_cefr_levels` (array of strings, optional): Optional: CEFR levels where this category is most relevant (enum values: 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'). Defaults to `null`.
*   `example_words` (dictionary, optional): Optional dictionary holding a few illustrative example words (headwords) per language. Defaults to `null`.
    *   Key: Language code (string)
    *   Value: List of example words (array of strings)
*   `badge_id_association` (string, optional): Optional: Identifier for a related achievement badge in the app. Defaults to `null`.
*   `created_at` (datetime, optional): Timestamp when the category was first created (UTC). Set automatically by the server. Defaults to `null` until set.
*   `updated_at` (datetime, optional): Timestamp when the category was last updated (UTC). Set automatically by the server on create and update. Defaults to `null` until set.

---

**16. Language Pair Configuration Object**

Defines configuration settings that vary based on language pairs, used for nuanced localization and configuration management. This structure is managed via the `/manage-language-pairs` UI and stored in Firestore (conceptually similar to the `LanguagePairConfigurations` table described in the separate specification).

*   `id` (string, optional): Unique identifier for the configuration entry (auto-generated by Firestore on create).
*   `language_pair` (string, **required**): Identifier for the language pair (format: source\_lang-target\_lang, e.g., 'en-id').
*   `config_key` (string, **required**): The unique name/key identifying the configuration parameter (e.g., 'date\_format').
*   `config_value` (string): The actual value of the configuration setting. Stored as a string, but can represent various types (number, boolean, array, etc.) as indicated by `value_type`.
*   `value_type` (string, **required**): Indicates the data type stored in `config_value` (enum: 'string', 'number', 'boolean', 'array').
*   `effective_date` (datetime, **required**): When this configuration becomes active.
*   `expiry_date` (datetime, optional): When this configuration should be retired (null indicates currently active).
*   `description` (dictionary, optional): Optional explanations in different languages, keyed by language code.
*   `updated_by` (string, optional): User/service that last updated this configuration.
*   `created_at` (datetime, optional): Timestamp when the configuration was created (UTC).
*   `updated_at` (datetime, optional): Timestamp when the configuration was last updated (UTC).

---

**17. Vocabulary Category Object**

Defines the structure for a single vocabulary category used within the application. This structure is managed via the `/manage-categories` UI and stored in Firestore (conceptually in a `master_categories` collection).

*   `category_id` (string, **required**): Unique identifier for the category (e.g., "basics_greetings", "theme_food_drink"). Used as the Firestore document ID.
*   `display_name` (dictionary, **required**): Dictionary holding user-facing names in different UI languages, keyed by language code.
*   `description` (dictionary, optional): Optional brief descriptions of the category content, keyed by language code.
*   `type` (string, **required**): Broad type of category (enum: 'thematic', 'grammatical', 'functional', 'other').
*   `applicable_cefr_levels` (array of strings, optional): Optional: CEFR levels where this category is most relevant (enum values: 'A1', 'A2', 'B1', 'B2', 'C1', 'C2').
*   `example_words` (dictionary, optional): Optional dictionary holding a few illustrative example words (headwords) per language, keyed by language code.
*   `badge_id_association` (string, optional): Optional: Identifier for a related achievement badge in the app.
*   `created_at` (datetime, optional): Timestamp when the category was first created (UTC).
*   `updated_at` (datetime, optional): Timestamp when the category was last updated (UTC).

---

**18. Firestore Connection and Google Cloud Secret Key Usage**

The application connects to Google Cloud Firestore for data persistence. The connection is managed using the `google-cloud-firestore` Python client library, specifically the `AsyncClient`.

*   **Configuration:** The Google Cloud Project ID (`GCLOUD_PROJECT`) and an optional Firestore Database ID (`FIRESTORE_DATABASE_ID`) are loaded from environment variables, typically sourced from a `.env` file using the `python-dotenv` library.
*   **Authentication:** Authentication to Google Cloud services, including Firestore, relies on Google Cloud's standard authentication mechanisms, such as Application Default Credentials (ADC). ADC automatically discovers credentials from the environment in which the application is running.
*   **Secret Key Usage:** While the application code itself does not explicitly load secret keys from files or directly interact with Google Cloud Secret Manager APIs for Firestore credentials, it leverages secret keys (such as service account keys or API keys) if they are made available in the environment where the application runs and if ADC is configured to use them. For example, a service account key file path might be set via the `GOOGLE_APPLICATION_CREDENTIALS` environment variable, or secrets stored in Google Cloud Secret Manager might be exposed as environment variables. The Google Cloud client library uses these available credentials to authenticate with Firestore, provided they have the necessary Identity and Access Management (IAM) roles (e.g., `roles/datastore.user` or `roles/firestore.viewer`).

---

**Internal LLM Interaction Structures (Not part of final API output)**

These models are used internally for communication with the LLM during the enrichment process.

*   `LlmSenseInfo`
*   `LlmCoreDetailsOutput`
*   `LlmCoreLangOutput`
*   `LlmSenseDetailsOutput`
*   `LlmImageDataOutput`
*   `LlmLinkChainOutput`
*   `LlmLinkChainsResponse`
