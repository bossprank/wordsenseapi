from flask import Blueprint, jsonify, request, abort
from app_factory import get_db
from firestore_client import get_master_categories, add_master_category, update_master_category, delete_master_category
# from firestore_client import get_master_categories # Keep this one
from models import VocabularyCategory
from pydantic import ValidationError # Added missing import
import logging

logger = logging.getLogger(__name__)

categories_api_bp = Blueprint('categories_api', __name__, url_prefix='/api/categories')

@categories_api_bp.route('/', methods=['GET'])
async def get_categories():
    """Fetches all master categories."""
    try:
        categories = await get_master_categories()
        return jsonify([cat.model_dump(mode='json') for cat in categories])
    except Exception as e:
        logger.exception("Error fetching categories:")
        abort(500, description="Failed to fetch categories.")

@categories_api_bp.route('/', methods=['POST'])
async def create_category():
    """Creates a new master category. Client must provide a unique category_id."""
    try:
        # Parse request data into Pydantic model
        category_data = VocabularyCategory.model_validate(request.json)
        
        # The category_id is now expected from the client and used as document ID.
        # add_master_category will use category_data.category_id as the Firestore document ID.

        new_category = await add_master_category(category_data)

        if new_category:
            return jsonify(new_category.model_dump(mode='json')), 201 # 201 Created
        else:
            # This could be due to various reasons, e.g., Firestore error, or if add_master_category
            # had a pre-check and found an existing ID (though current impl overwrites).
            abort(500, description="Failed to create category. Check server logs for details.")

    except ValidationError as e:
        logger.error(f"Validation error in create_category input: {e.errors()}")
        abort(400, description=f"Invalid input data: {e.errors()}")
    except Exception as e:
        logger.exception("Error creating category:")
        abort(500, description="Failed to create category.")


@categories_api_bp.route('/<category_id>', methods=['PUT'])
async def update_category(category_id: str):
    """Updates an existing master category by ID.
    The request body should be a dictionary of fields to update.
    """
    try:
        # The request.json directly contains the updates.
        # No need to validate against VocabularyCategory directly here,
        # as update_master_category in firestore_client handles partial updates.
        # However, the API consumer should know which fields are updatable.
        update_payload = request.json
        if not update_payload:
            abort(400, description="Request body cannot be empty for update.")

        updated_category_obj = await update_master_category(category_id, update_payload)

        if updated_category_obj:
            return jsonify(updated_category_obj.model_dump(mode='json')), 200
        else:
            # This could mean the category was not found, or the update failed for other reasons.
            # update_master_category returns None if not found or on error.
            abort(404, description=f"Category with ID '{category_id}' not found or update failed.")

    except Exception as e: # Catch generic exceptions, specific validation is less direct here
        logger.exception(f"Error updating category ID {category_id}:")
        abort(500, description="Failed to update category.")


@categories_api_bp.route('/<category_id>', methods=['DELETE'])
async def delete_category(category_id: str):
    """Deletes a master category by ID."""
    try:
        success = await delete_master_category(category_id)
        if success:
            return jsonify({"message": f"Category with ID '{category_id}' deleted successfully"}), 200
        else:
            # This implies category not found or delete operation failed.
            abort(404, description=f"Category with ID '{category_id}' not found or delete failed.")
    except Exception as e:
        logger.exception(f"Error deleting category ID {category_id}:")
        abort(500, description="Failed to delete category.")
