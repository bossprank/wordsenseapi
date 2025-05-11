document.addEventListener('DOMContentLoaded', () => {
    const pageTitle = document.getElementById('page-title');
    const listHeaderInfo = document.getElementById('list-header-info');
    const listStatusBadge = document.getElementById('list-status');
    const paramsDetailsDiv = document.getElementById('generation-params-details');
    const wordCountSpan = document.getElementById('word-count');
    const wordItemsTableBody = document.getElementById('word-items-table-body');

    // Helper to safely display text (prevent XSS)
    function safeText(text) {
        const el = document.createElement('div');
        el.textContent = text ?? 'N/A';
        return el.innerHTML;
    }
    
    // Helper to format object/array for display
    function formatValue(value) {
        if (value === null || typeof value === 'undefined') return 'N/A';
        if (typeof value === 'object') {
            try {
                // Pretty print JSON for objects/arrays, add scrolling
                return `<pre style="white-space: pre-wrap; word-wrap: break-word; overflow-x: auto; max-height: 300px; overflow-y: auto;">${safeText(JSON.stringify(value, null, 2))}</pre>`;
            } catch (e) {
                return safeText(String(value)); // Fallback
            }
        }
        if (typeof value === 'string' && (value.includes('\n') || value.length > 100)) {
             // Use pre for long strings or strings with newlines, add scrolling
             return `<pre style="white-space: pre-wrap; word-wrap: break-word; overflow-x: auto; max-height: 300px; overflow-y: auto;">${safeText(value)}</pre>`;
        }
        // Format dates
        if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) {
             try {
                 return new Date(value).toLocaleString();
             } catch(e) { /* ignore */ }
        }
        return safeText(String(value));
    }

    // Fetch List Details
    async function fetchListDetails() {
        if (!LIST_FIRESTORE_ID) {
            console.error("LIST_FIRESTORE_ID not defined.");
            paramsDetailsDiv.innerHTML = '<p class="text-danger">Error: List ID not found.</p>';
            wordItemsTableBody.innerHTML = '<tr><td colspan="3" class="text-danger">Error: List ID not found.</td></tr>';
            return;
        }

        // Add cache-busting timestamp parameter
        const apiUrl = `/api/v1/generated-lists/${LIST_FIRESTORE_ID}?t=${Date.now()}`; 
        console.log("Fetching details from:", apiUrl);

        try {
            const response = await fetch(apiUrl);
            if (!response.ok) {
                 const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
                 throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            const listData = await response.json();
            console.log("Received data for list details:", listData);

            if (!listData || !listData.generation_parameters) { // Check for listData and generation_parameters directly
                console.error("API response is missing 'generation_parameters' field.", listData);
                paramsDetailsDiv.innerHTML = '<p class="text-danger">Error: Incomplete data received from server (missing generation_parameters).</p>';
                wordItemsTableBody.innerHTML = '<tr><td colspan="3" class="text-danger">Error: Incomplete data received.</td></tr>';
                pageTitle.textContent = 'Error Loading Details';
                listHeaderInfo.textContent = 'Error';
                listStatusBadge.textContent = 'Error';
                return;
            }

            const generationParams = listData.generation_parameters;
            // Summary information is now part of generationParams or listData itself

            // Update Header
            pageTitle.textContent = `Details for ${generationParams.list_readable_id || 'List'}`;
            // Assuming list_category_display_name needs to be fetched or resolved if not directly in generationParams
            // For now, using list_category_id from generationParams
            listHeaderInfo.textContent = `${generationParams.list_readable_id || 'N/A'} | Lang: ${generationParams.language || 'N/A'} | CEFR: ${generationParams.cefr_level || 'N/A'} | Cat: ${generationParams.list_category_id || 'N/A'}`;
            listStatusBadge.textContent = generationParams.status || 'N/A';
            listStatusBadge.className = `badge badge-info`; // Default badge, can be enhanced

            // Populate Generation Parameters
            paramsDetailsDiv.innerHTML = ''; // Clear loading
            const dl = document.createElement('dl');
            dl.className = 'row';

            // Define order and labels (can be extended)
            const paramOrder = [
                'list_readable_id', 'status', 'language', 'cefr_level', 'list_category_id',
                'requested_word_count', 'generated_word_count', 'include_english_translation',
                'generation_timestamp', 'last_status_update_timestamp', 'generated_by', 'reviewed_by', 'admin_notes',
                'source_model', 'gemini_temperature', 'gemini_top_p', 'gemini_top_k', 'gemini_max_output_tokens',
                'gemini_stop_sequences', 'gemini_response_mime_type', 'gemini_response_schema_used',
                'base_instruction_file_ref', 'custom_instruction_file_ref', 'ui_text_refinements',
                'final_llm_prompt_text_sent'
            ];
            
            paramOrder.forEach(key => {
                if (generationParams.hasOwnProperty(key)) {
                    const dt = document.createElement('dt');
                    dt.className = 'col-sm-3';
                    dt.textContent = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                    const dd = document.createElement('dd');
                    dd.className = 'col-sm-9';
                    dd.innerHTML = formatValue(generationParams[key]);

                    dl.appendChild(dt);
                    dl.appendChild(dd);
                }
            });
            paramsDetailsDiv.appendChild(dl);


            // Populate Word Items Table
            wordItemsTableBody.innerHTML = ''; // Clear loading
            const words = listData.word_items || []; // Access word_items directly from listData
            wordCountSpan.textContent = words.length;

            if (words.length === 0) {
                wordItemsTableBody.innerHTML = '<tr><td colspan="3" class="text-center">No word items found in this list.</td></tr>';
            } else {
                words.forEach((item, index) => {
                    const row = wordItemsTableBody.insertRow();
                    row.innerHTML = `
                        <td>${index + 1}</td>
                        <td>${safeText(item.word || item.headword)}</td>
                        <td>${safeText(item.translations && item.translations.en ? item.translations.en : 'N/A')}</td>
                    `;
                });
            }

        } catch (error) {
            console.error('Error fetching list details:', error);
            paramsDetailsDiv.innerHTML = `<p class="text-danger">Error loading details: ${error.message}</p>`;
            wordItemsTableBody.innerHTML = `<tr><td colspan="3" class="text-danger">Error loading words: ${error.message}</td></tr>`;
        }
    }

    // --- Initial Load ---
    fetchListDetails();

});
