from flask import Blueprint, jsonify, request, abort
from app_factory import get_db
from firestore_client import get_language_pair_configurations, add_language_pair_configuration, update_language_pair_configuration, delete_language_pair_configuration
from models import LanguagePairConfiguration
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

lang_pairs_api_bp = Blueprint('lang_pairs_api', __name__, url_prefix='/api/language-pair-configurations')

@lang_pairs_api_bp.route('/', methods=['GET'])
async def get_language_pairs():
    """Fetches all language pair configurations.
    Can be filtered by 'language_pair' query parameter.
    e.g., /api/language-pair-configurations/?language_pair=en-id
    """
    try:
        language_pair_filter = request.args.get('language_pair')
        configs = await get_language_pair_configurations(language_pair_filter=language_pair_filter)
        return jsonify([config.model_dump(mode='json') for config in configs])
    except Exception as e:
        logger.exception("Error fetching language pair configurations:")
        abort(500, description="Failed to fetch language pair configurations.")

@lang_pairs_api_bp.route('/', methods=['POST'])
async def create_language_pair():
    """Creates a new language pair configuration. ID is auto-generated."""
    try:
        # Parse request data into Pydantic model
        # The 'id' field in LanguagePairConfiguration is Optional and will be None here.
        config_data = LanguagePairConfiguration.model_validate(request.json)
        
        # add_language_pair_configuration will handle auto-ID generation.
        new_config = await add_language_pair_configuration(config_data)

        if new_config:
            return jsonify(new_config.model_dump(mode='json')), 201 # 201 Created
        else:
            abort(500, description="Failed to create language pair configuration.")

    except ValidationError as e:
        logger.error(f"Validation error in create_language_pair input: {e.errors()}")
        abort(400, description=f"Invalid input data: {e.errors()}")
    except Exception as e:
        logger.exception("Error creating language pair configuration:")
        abort(500, description="Failed to create language pair configuration.")


@lang_pairs_api_bp.route('/<config_id>', methods=['PUT'])
async def update_language_pair(config_id: str):
    """Updates an existing language pair configuration by ID.
    The request body should be a dictionary of fields to update.
    """
    try:
        update_payload = request.json
        if not update_payload:
            abort(400, description="Request body cannot be empty for update.")

        # The update_language_pair_configuration function in firestore_client
        # expects the config_id and a dictionary of updates.
        updated_config_obj = await update_language_pair_configuration(config_id, update_payload)

        if updated_config_obj:
            return jsonify(updated_config_obj.model_dump(mode='json')), 200
        else:
            abort(404, description=f"Configuration with ID '{config_id}' not found or update failed.")

    except Exception as e:
        logger.exception(f"Error updating language pair configuration ID {config_id}:")
        abort(500, description="Failed to update language pair configuration.")


@lang_pairs_api_bp.route('/<config_id>', methods=['DELETE'])
async def delete_language_pair(config_id: str):
    """Deletes a language pair configuration by ID."""
    try:
        success = await delete_language_pair_configuration(config_id)
        if success:
            return jsonify({"message": f"Configuration with ID '{config_id}' deleted successfully"}), 200
        else:
            abort(404, description=f"Configuration with ID '{config_id}' not found or delete failed.")
    except Exception as e:
        logger.exception(f"Error deleting language pair configuration ID {config_id}:")
        abort(500, description="Failed to delete language pair configuration.")
