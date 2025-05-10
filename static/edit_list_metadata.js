document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('edit-metadata-form');
    const statusMessageEl = document.getElementById('status-message');
    const listHeaderInfo = document.getElementById('list-header-info');
    const referenceInfoP = document.getElementById('reference-info');
    
    // Form fields
    const statusSelect = document.getElementById('status');
    const categorySelect = document.getElementById('list_category_id');
    const adminNotesTextarea = document.getElementById('admin_notes');
    const reviewedByInput = document.getElementById('reviewed_by');

    if (!LIST_FIRESTORE_ID) {
        console.error("LIST_FIRESTORE_ID not defined.");
        setStatusMessage('Error: List ID not found.', 'error');
        return;
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

    // --- Populate Dropdowns ---
    async function populateDropdowns() {
        try {
            const response = await fetch('/api/v1/generated-lists/filter-options');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const options = await response.json();

            // Populate Statuses
            statusSelect.innerHTML = '<option value="">Select Status...</option>'; 
            options.statuses.forEach(statusObj => { // Renamed to statusObj for clarity
                const option = document.createElement('option');
                option.value = statusObj.id; // Corrected: use statusObj.id
                option.textContent = statusObj.name; // Corrected: use statusObj.name
                statusSelect.appendChild(option);
            });

            // Populate Categories
            categorySelect.innerHTML = '<option value="">Select Category...</option>';
            options.categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat.id; // Corrected: use cat.id
                option.textContent = cat.name; // Corrected: use cat.name
                categorySelect.appendChild(option);
            });

        } catch (error) {
            console.error('Error fetching filter options:', error);
            setStatusMessage('Error loading dropdown options. Please try refreshing.', 'error');
        }
    }

    // --- Fetch Current Data and Pre-fill Form ---
    async function loadCurrentData() {
        const apiUrl = `/api/v1/generated-lists/${LIST_FIRESTORE_ID}`;
        try {
            const response = await fetch(apiUrl);
             if (!response.ok) {
                 const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
                 throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            const responseData = await response.json(); // Renamed to avoid confusion
            const listDetails = responseData.details; // Access the 'details' object
            if (!listDetails || !listDetails.generation_parameters) {
                throw new Error('generation_parameters not found in API response details.');
            }
            const params = listDetails.generation_parameters;

            // Update Header
            listHeaderInfo.textContent = `${params.list_readable_id || 'N/A'} (Lang: ${params.language || 'N/A'} | CEFR: ${params.cefr_level || 'N/A'})`;

            // Pre-fill form fields
            statusSelect.value = params.status || '';
            categorySelect.value = params.list_category_id || '';
            adminNotesTextarea.value = params.admin_notes || '';
            reviewedByInput.value = params.reviewed_by || '';

            // Populate Reference Info
            referenceInfoP.innerHTML = `
                Requested Words: ${params.requested_word_count ?? 'N/A'} | 
                Generated Words: ${params.generated_word_count ?? 'N/A'} | 
                Model: ${params.source_model || 'N/A'} |
                Generated: ${params.generation_timestamp ? new Date(params.generation_timestamp).toLocaleString() : 'N/A'}
            `;
            referenceInfoP.classList.remove('text-muted');


        } catch (error) {
             console.error('Error fetching list details:', error);
             setStatusMessage(`Error loading current data: ${error.message}`, 'error');
             referenceInfoP.textContent = 'Error loading reference info.';
             referenceInfoP.classList.remove('text-muted');
             referenceInfoP.classList.add('text-danger');
        }
    }

     // --- Form Submission Handler ---
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearStatusMessage();
        setStatusMessage('Saving changes...', 'info');
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        const formData = new FormData(form);
        const dataToUpdate = {};

        // Only include fields that have a value set in the form
        // Use exclude_unset=True logic on backend Pydantic model
        if (formData.get('status')) {
            dataToUpdate.status = formData.get('status');
        }
         if (formData.get('list_category_id')) {
            dataToUpdate.list_category_id = formData.get('list_category_id');
        }
        // Allow sending empty strings to clear these fields
        dataToUpdate.admin_notes = formData.get('admin_notes'); 
        dataToUpdate.reviewed_by = formData.get('reviewed_by'); 

        // Filter out null/undefined values before sending (optional, Pydantic handles it too)
        const finalPayload = Object.entries(dataToUpdate)
            .filter(([_, value]) => value !== null && typeof value !== 'undefined')
            .reduce((obj, [key, value]) => {
                obj[key] = value;
                return obj;
            }, {});

        if (Object.keys(finalPayload).length === 0) {
             setStatusMessage('No changes detected to save.', 'info');
             submitButton.disabled = false;
             return;
        }

        console.log("Submitting PATCH data:", finalPayload); // For debugging

        try {
            const response = await fetch(`/api/v1/generated-lists/${LIST_FIRESTORE_ID}/metadata`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(finalPayload),
            });

            const result = await response.json();

            if (response.ok) {
                setStatusMessage(result.message || 'Metadata updated successfully. Redirecting...', 'info');
                 // Redirect back to the view page after a short delay
                setTimeout(() => {
                    window.location.href = '/view-generated-word-lists'; // Corrected URL
                }, 1500);
            } else {
                setStatusMessage(`Error: ${result.message || 'Failed to update metadata.'}`, 'error');
                console.error("Update failed:", result);
                submitButton.disabled = false;
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            setStatusMessage('An unexpected error occurred. Please check the console.', 'error');
            submitButton.disabled = false;
        } 
    });


    // --- Initial Load ---
    async function initializePage() {
        await populateDropdowns(); // Wait for dropdowns to populate
        await loadCurrentData();   // Then load data and pre-select
    }

    initializePage();

});
