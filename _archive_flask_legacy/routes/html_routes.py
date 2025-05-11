from flask import Blueprint, render_template, current_app
import logging
import os
import json

logger = logging.getLogger(__name__)

html_bp = Blueprint('html', __name__)

@html_bp.route('/')
def index():
    logger.info("Serving index.html")
    return render_template('index.html')

@html_bp.route('/manage-categories')
def manage_categories():
    logger.info("Serving manage_categories.html")
    return render_template('manage_categories.html')

@html_bp.route('/manage-language-pairs')
def manage_language_pairs():
    logger.info("Serving manage_language_pairs.html")
    return render_template('manage_language_pairs.html')

@html_bp.route('/language-pair-config-detail/<config_id>')
def language_pair_config_detail(config_id):
    if config_id == 'new':
        logger.info("Serving language_pair_config_detail.html for a new configuration.")
        # Pass None for config_id to indicate "new" mode to the template/JS
        # Or pass a default empty object if the template expects certain keys
        return render_template('language_pair_config_detail.html', config_id=None, is_new=True)
    else:
        logger.info(f"Serving language_pair_config_detail.html for config_id: {config_id}")
        # For existing, pass the ID; JS will fetch details.
        return render_template('language_pair_config_detail.html', config_id=config_id, is_new=False)

@html_bp.route('/generate-new-word-list')
def generate_new_word_list():
    logger.info("Serving generate_new_word_list.html")
    default_schema_content = ""
    schema_file_path = os.path.join(current_app.root_path, 'llm_prompts', 'default_word_list_schema.json')
    try:
        if os.path.exists(schema_file_path):
            with open(schema_file_path, 'r') as f:
                # Read and pretty-print the JSON for better readability in textarea
                raw_content = f.read()
                try:
                    parsed_json = json.loads(raw_content)
                    default_schema_content = json.dumps(parsed_json, indent=2)
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse JSON from {schema_file_path}. Serving raw content.")
                    default_schema_content = raw_content # Serve raw if not valid JSON
        else:
            logger.warning(f"Default schema file not found at {schema_file_path}")
    except Exception as e:
        logger.error(f"Error reading default schema file {schema_file_path}: {e}")
        # Keep default_schema_content as empty string

    return render_template('generate_new_word_list.html', default_schema=default_schema_content)

@html_bp.route('/view-generated-word-lists')
def view_generated_word_lists():
    logger.info("Serving view_generated_word_lists.html")
    return render_template('view_generated_word_lists.html')

@html_bp.route('/generated-list-details/<list_id>')
def generated_list_details(list_id):
    logger.info(f"Serving generated_list_details.html for list_id: {list_id}")
    return render_template('generated_list_details.html', list_id=list_id)

@html_bp.route('/edit-list-metadata/<list_id>')
def edit_list_metadata(list_id):
    logger.info(f"Serving edit_list_metadata.html for list_id: {list_id}")
    return render_template('edit_list_metadata.html', list_id=list_id)
