document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('generate-list-form');
    const statusMessageEl = document.getElementById('status-message');
    const categorySelect = document.getElementById('list_category_id');
    const responseFormatSelect = document.getElementById('gemini_response_mime_type');
    const jsonSchemaGroup = document.getElementById('json-schema-group');
    const formElements = form.elements; // Easier access to form elements by name/id

    // --- Populate Categories Dropdown ---
    async function populateCategories() { // Make async to allow awaiting
        try {
            const response = await fetch('/api/categories');
            if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const categories = await response.json();
                categorySelect.innerHTML = '<option value="">Select Category...</option>'; // Clear loading/default
                categories.forEach(cat => {
                    const displayName = cat.display_name?.en || cat.category_id;
                    const option = document.createElement('option');
                    option.value = cat.category_id;
                    option.textContent = displayName;
                    categorySelect.appendChild(option);
                });
            } catch (error) {
                console.error('Error fetching categories:', error);
                categorySelect.innerHTML = '<option value="">Error loading categories</option>';
                setStatusMessage('Error loading categories. Please try refreshing.', 'error');
                throw error; // Re-throw to prevent further processing if needed
            }
    }

    // --- Show/Hide JSON Schema Textarea ---
    function toggleJsonSchemaVisibility() {
        if (responseFormatSelect.value === 'application/json') {
            jsonSchemaGroup.style.display = 'block';
        } else {
            jsonSchemaGroup.style.display = 'none';
        }
    }

    // --- Set Status Message ---
    function setStatusMessage(message, type = 'info') {
        statusMessageEl.textContent = message;
        statusMessageEl.className = `mt-3 alert alert-${type === 'error' ? 'danger' : 'info'}`;
        statusMessageEl.style.display = 'block';
    }

    function clearStatusMessage() {
        statusMessageEl.textContent = '';
        statusMessageEl.style.display = 'none';
    }

    // --- Load Data for Regeneration ---
    async function loadDataForRegeneration() {
        const urlParams = new URLSearchParams(window.location.search);
        const regenerateId = urlParams.get('regenerate_id');

        if (!regenerateId) {
            console.log("No regenerate_id found in URL.");
            return; // Not a regeneration request
        }

        console.log(`Regeneration requested for ID: ${regenerateId}`);
        setStatusMessage('Loading data from original list...', 'info');

        try {
            const response = await fetch(`/api/v1/generated-lists/${regenerateId}`);
            if (!response.ok) {
                if (response.status === 404) {
                     throw new Error(`Original list with ID ${regenerateId} not found.`);
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const listData = await response.json();
            const params = listData.generation_parameters;

            if (!params) {
                throw new Error("Original list data does not contain generation parameters.");
            }

            console.log("Original generation parameters:", params);

            // Populate form fields
            formElements['language'].value = params.language || '';
            formElements['cefr_level'].value = params.cefr_level || '';
            formElements['requested_word_count'].value = params.requested_word_count || 50;
            formElements['list_category_id'].value = params.list_category_id || ''; // Category dropdown needs to be populated first
            formElements['base_instruction_file_ref'].value = params.base_instruction_file_ref || 'base.txt';
            formElements['custom_instruction_file_ref'].value = params.custom_instruction_file_ref || '';
            formElements['ui_text_refinements'].value = params.ui_text_refinements || '';
            formElements['source_model'].value = params.source_model || 'gemini-1.5-flash-latest';
            formElements['gemini_temperature'].value = params.gemini_temperature ?? 0.7; // Use ?? for nullish coalescing
            formElements['gemini_top_p'].value = params.gemini_top_p ?? 0.95;
            formElements['gemini_top_k'].value = params.gemini_top_k ?? 40;
            formElements['gemini_max_output_tokens'].value = params.gemini_max_output_tokens ?? 2048;
            
            // Handle stop sequences array -> comma-separated string
            formElements['gemini_stop_sequences'].value = (params.gemini_stop_sequences || []).join(', ');

            formElements['gemini_response_mime_type'].value = params.gemini_response_mime_type || 'application/json';
            
            // Handle schema (might be string or object/null)
            let schemaValue = params.gemini_response_schema_used;
            if (schemaValue && typeof schemaValue === 'object') {
                try {
                    schemaValue = JSON.stringify(schemaValue, null, 2); // Pretty print
                } catch (e) {
                    console.error("Error stringifying schema object:", e);
                    schemaValue = '';
                }
            }
            formElements['gemini_response_schema_used'].value = schemaValue || '';

            formElements['include_english_translation'].checked = params.include_english_translation ?? true;
            formElements['admin_notes'].value = params.admin_notes || ''; // Keep original admin notes? Or clear? Keeping for now.

            // Trigger change event for response format select to update schema visibility
            responseFormatSelect.dispatchEvent(new Event('change'));

            clearStatusMessage();
            setStatusMessage('Form populated with data from original list. Review and adjust before generating.', 'info');

        } catch (error) {
            console.error('Error loading data for regeneration:', error);
            setStatusMessage(`Error loading original list data: ${error.message}`, 'error');
        }
    }

    // --- Form Submission Handler ---
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearStatusMessage();
        setStatusMessage('Generating word list, please wait...', 'info');
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const formData = new FormData(form);
        const data = {};

        // Convert FormData to simple object, handle types
        formData.forEach((value, key) => {
            // Handle numeric fields
            if (['requested_word_count', 'gemini_temperature', 'gemini_top_p', 'gemini_top_k', 'gemini_max_output_tokens'].includes(key)) {
                data[key] = parseFloat(value) || 0; // Default to 0 if parsing fails
                 if (['gemini_top_k', 'gemini_max_output_tokens', 'requested_word_count'].includes(key)) {
                     data[key] = parseInt(value, 10) || 0; // Ensure integer for these
                 }
            } else {
                data[key] = value;
            }
        });

        // Handle checkbox (only present if checked)
        data.include_english_translation = formData.has('include_english_translation');

        // Handle stop sequences (comma-separated string to array)
        if (data.gemini_stop_sequences && data.gemini_stop_sequences.trim()) {
            data.gemini_stop_sequences = data.gemini_stop_sequences.split(',').map(s => s.trim()).filter(s => s);
        } else {
            data.gemini_stop_sequences = null; // Send null if empty
        }
        
        // Handle JSON schema (send null if mime type is not JSON or if empty)
        if (data.gemini_response_mime_type !== 'application/json' || !data.gemini_response_schema_used?.trim()) {
            data.gemini_response_schema_used = null;
        } else {
            // Attempt to parse to ensure it's valid JSON before sending (optional, backend validates too)
            try {
                JSON.parse(data.gemini_response_schema_used);
            } catch (e) {
                 setStatusMessage('Error: Invalid JSON provided in the schema field.', 'error');
                 submitButton.disabled = false;
                 return; // Stop submission
            }
        }


        console.log("Submitting data:", data); // For debugging

        try {
            const response = await fetch('/api/v1/generated-lists', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();

            if (response.ok) {
                setStatusMessage(`Success! List generated. ID: ${result.list_readable_id}. Redirecting...`, 'info');
                // Redirect to the view page after a short delay
                setTimeout(() => {
                    // TODO: Update this URL when the view page route is created
                    window.location.href = '/'; // Redirect to home for now
                }, 2000);
            } else {
                setStatusMessage(`Error: ${result.message || 'Failed to generate list.'}`, 'error');
                console.error("Generation failed:", result);
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            setStatusMessage('An unexpected error occurred. Please check the console.', 'error');
        } finally {
             // Re-enable button only if not redirecting soon
             if (!statusMessageEl.textContent.includes('Redirecting')) {
                 submitButton.disabled = false;
             }
        }
    });

    // --- Initial Setup ---
    // Populate categories first, then attempt to load regeneration data
    populateCategories()
        .then(() => {
            // Now that categories are loaded, load regeneration data (which might set category)
            return loadDataForRegeneration();
        })
        .catch(error => {
            console.error("Error during initial setup:", error);
            // Error already shown by populateCategories or loadDataForRegeneration
        });

    toggleJsonSchemaVisibility(); // Set initial visibility based on default select value
    responseFormatSelect.addEventListener('change', toggleJsonSchemaVisibility); // Add listener

});
