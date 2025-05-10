document.addEventListener('DOMContentLoaded', () => {
    const filterForm = document.getElementById('filter-form');
    const clearFiltersBtn = document.getElementById('clear-filters-btn');
    const tableBody = document.getElementById('lists-table-body');
    const paginationControls = document.getElementById('pagination-controls'); // Placeholder

    // Filter Select Elements
    const languageSelect = document.getElementById('filter-language');
    const cefrSelect = document.getElementById('filter-cefr');
    const categorySelect = document.getElementById('filter-category');
    const statusSelect = document.getElementById('filter-status');

    // --- Populate Filter Dropdowns ---
    async function populateFilters() {
        try {
            const response = await fetch('/api/v1/generated-lists/filter-options');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const options = await response.json();

            // Populate Languages
            options.languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang;
                option.textContent = lang; // Consider mapping codes to full names later
                languageSelect.appendChild(option);
            });

            // Populate CEFR Levels
            options.cefr_levels.forEach(level => {
                const option = document.createElement('option');
                option.value = level;
                option.textContent = level;
                cefrSelect.appendChild(option);
            });

            // Populate Categories
            options.categories.forEach(cat => {
                const option = document.createElement('option');
                option.value = cat.id; // Corrected: use cat.id
                option.textContent = cat.name; // Corrected: use cat.name
                categorySelect.appendChild(option);
            });

            // Populate Statuses
            options.statuses.forEach(statusObj => { // Renamed to statusObj for clarity
                const option = document.createElement('option');
                option.value = statusObj.id; // Corrected: use statusObj.id
                option.textContent = statusObj.name; // Corrected: use statusObj.name
                statusSelect.appendChild(option);
            });

        } catch (error) {
            console.error('Error fetching filter options:', error);
            // Display error message?
        }
    }

    // --- Fetch and Display Lists ---
    async function fetchAndDisplayLists(params = {}) {
        tableBody.innerHTML = '<tr><td colspan="8" class="text-center">Loading lists...</td></tr>';
        
        // Construct query string from params
        const queryParams = new URLSearchParams(params).toString();
        const apiUrl = `/api/v1/generated-lists?${queryParams}`;
        console.log("Fetching:", apiUrl); // Debug

        try {
            const response = await fetch(apiUrl);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const lists = await response.json();

            tableBody.innerHTML = ''; // Clear loading message

            if (lists.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center">No lists found matching criteria.</td></tr>';
                return;
            }

            lists.forEach(list => {
                const row = tableBody.insertRow();
                
                // Format date nicely
                const dateCreated = new Date(list.generation_timestamp).toLocaleString();

                // Action buttons (placeholders for URLs)
                // TODO: Update URLs when detail/edit routes are created
                const detailsUrl = `/generated-list-details/${list.list_firestore_id}`; // Corrected URL
                const editMetaUrl = `/edit-list-metadata/${list.list_firestore_id}`;
                // Pass the original list ID as a query parameter for regeneration
                const regenUrl = `/generate-new-word-list?regenerate_id=${list.list_firestore_id}`; // Corrected base path

                row.innerHTML = `
                    <td>${list.list_readable_id || 'N/A'}</td>
                    <td>${list.language || 'N/A'}</td>
                    <td>${list.cefr_level || 'N/A'}</td>
                    <td>${list.list_category_display_name || 'N/A'}</td>
                    <td>${list.status || 'N/A'}</td>
                    <td>${list.generated_word_count ?? 'N/A'}</td>
                    <td>${dateCreated}</td>
                    <td>
                        <a href="${detailsUrl}" class="btn btn-xs btn-info" title="Details">Det</a>
                        <a href="${editMetaUrl}" class="btn btn-xs btn-warning" title="Edit Metadata">Edit</a>
                        <a href="${regenUrl}" class="btn btn-xs btn-secondary" title="Regenerate (New)">Regen</a>
                        <button class="btn btn-xs btn-danger delete-btn" data-id="${list.list_firestore_id}" title="Delete">Del</button>
                    </td>
                `;
            });

            // TODO: Update pagination controls based on response headers or metadata

        } catch (error) {
            console.error('Error fetching lists:', error);
            tableBody.innerHTML = '<tr><td colspan="8" class="text-center">Error loading lists.</td></tr>';
        }
    }

    // --- Event Listeners ---

    // Filter form submission
    filterForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const formData = new FormData(filterForm);
        const params = {};
        formData.forEach((value, key) => {
            if (value) { // Only include non-empty filter values
                params[key] = value;
            }
        });
        // TODO: Add sorting and pagination params
        fetchAndDisplayLists(params);
    });

    // Clear filters button
    clearFiltersBtn.addEventListener('click', () => {
        filterForm.reset();
        fetchAndDisplayLists(); // Fetch with default params
    });

    // Delete button (using event delegation)
    tableBody.addEventListener('click', async (event) => {
        if (event.target.classList.contains('delete-btn')) {
            const button = event.target;
            const listId = button.dataset.id;
            const listReadableId = button.closest('tr')?.cells[0]?.textContent || 'this list';

            if (confirm(`Are you sure you want to delete list ${listReadableId} (${listId})?`)) {
                button.disabled = true;
                button.textContent = '...'; // Indicate processing

                try {
                    const response = await fetch(`/api/v1/generated-lists/${listId}`, {
                        method: 'DELETE',
                    });
                    const result = await response.json();

                    if (response.ok) {
                        alert(result.message || 'List deleted successfully.');
                        button.closest('tr').remove(); // Remove row from table
                        // Or call fetchAndDisplayLists() to refresh the current page
                    } else {
                        alert(`Error: ${result.message || 'Failed to delete list.'}`);
                        button.disabled = false;
                        button.textContent = 'Del';
                    }
                } catch (error) {
                    console.error('Error deleting list:', error);
                    alert('An unexpected error occurred during deletion.');
                    button.disabled = false;
                    button.textContent = 'Del';
                }
            }
        }
    });


    // --- Initial Load ---
    populateFilters();
    fetchAndDisplayLists(); // Load initial data

});
