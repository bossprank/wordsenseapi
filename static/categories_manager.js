// static/categories_manager.js

document.addEventListener('DOMContentLoaded', () => {
    const categoryTableBody = document.getElementById('category-table-body');
    const languageFilterInput = document.getElementById('language-filter');
    const filterButton = document.getElementById('filter-button');
    const clearFilterButton = document.getElementById('clear-filter-button');
    const addCategoryButton = document.getElementById('add-category-button');
    const categoryFormSection = document.getElementById('category-form-section');
    const categoryForm = document.getElementById('category-form');
    const formTitle = document.getElementById('form-title');
    const formModeInput = document.getElementById('form-mode');
    const categoryIdInput = document.getElementById('category_id');
    const saveButton = document.getElementById('save-button');
    const cancelButton = document.getElementById('cancel-button');
    const formErrorDiv = document.getElementById('form-error');

    // --- Dynamic Form Field Elements ---
    const displayNameInputsDiv = document.getElementById('display_name_inputs');
    const descriptionInputsDiv = document.getElementById('description_inputs');
    const exampleWordsInputsDiv = document.getElementById('example_words_inputs');
    const addDisplayNameLangButton = document.getElementById('add-display-name-lang');
    const addDescriptionLangButton = document.getElementById('add-description-lang');
    const addExampleWordsLangButton = document.getElementById('add-example-words-lang');

    let currentEditId = null; // Store the ID of the category being edited

    // --- API Base URL ---
    const API_BASE_URL = '/api/categories';

    // --- Utility Functions ---
    // Display messages in the form's error div
    function displayFormError(message) {
        formErrorDiv.textContent = message;
        formErrorDiv.style.color = '#721c24'; // Ensure error styling
        formErrorDiv.style.backgroundColor = '#f8d7da';
        formErrorDiv.style.borderColor = '#f5c6cb';
        formErrorDiv.style.display = 'block'; // Make sure it's visible
        console.error("Form Error:", message);
    }

    // Display general feedback (e.g., after delete) - might need a dedicated area later
    function displayFeedback(message, isError = false) {
        // For now, reuse form error div, but ideally have a separate feedback area
        formErrorDiv.textContent = message;
        formErrorDiv.style.color = isError ? '#721c24' : '#155724'; // Red for error, Green for success
        formErrorDiv.style.backgroundColor = isError ? '#f8d7da' : '#d4edda';
        formErrorDiv.style.borderColor = isError ? '#f5c6cb' : '#c3e6cb';
        formErrorDiv.style.display = 'block';
        console.log("Feedback:", message);
        // Optionally hide after a few seconds
        // setTimeout(clearError, 5000);
    }

    function clearError() {
        formErrorDiv.textContent = '';
        formErrorDiv.style.display = 'none'; // Hide the error div
    }

    function showForm(mode = 'add', category = null) {
        clearError(); // Clear any previous errors/feedback first
        formModeInput.value = mode;
        categoryForm.reset(); // Clear previous inputs
        clearDynamicLanguageFields(); // Clear dynamic fields

        if (mode === 'edit' && category) {
            formTitle.textContent = `Edit Category: ${category.category_id}`;
            categoryIdInput.value = category.category_id;
            categoryIdInput.readOnly = true; // Don't allow editing ID
            currentEditId = category.category_id;
            populateForm(category); // Populate form with existing data
        } else {
            formTitle.textContent = 'Add New Category';
            categoryIdInput.value = '';
            categoryIdInput.readOnly = false;
            currentEditId = null;
            // Add default 'en' fields for new entries
            addLanguageField(displayNameInputsDiv, 'display_name', 'en');
        }
        categoryFormSection.style.display = 'block';
    }

    function hideForm() {
        categoryFormSection.style.display = 'none';
        categoryForm.reset();
        clearDynamicLanguageFields();
        clearError();
        currentEditId = null;
    }

    // --- Dynamic Language Field Handling ---
    function addLanguageField(container, fieldName, langCode = '', value = '') {
        const lang = langCode || prompt(`Enter language code (e.g., 'id', 'fr'):`);
        if (!lang || !/^[a-z]{2}$/.test(lang)) {
             // Use displayFeedback for non-form specific alerts
            if (lang) displayFeedback("Invalid language code. Please use 2 lowercase letters.", true);
            return; // Basic validation
        }

        // Check if field for this language already exists
        if (container.querySelector(`input[name="${fieldName}[${lang}]"]`)) {
             displayFeedback(`Field for language '${lang}' already exists.`, true);
            return;
        }

        const label = document.createElement('label');
        label.textContent = `${lang}:`;
        label.style.width = '30px';
        label.style.display = 'inline-block';

        const input = document.createElement('input');
        input.type = 'text';
        input.name = `${fieldName}[${lang}]`;
        input.value = value;
        input.placeholder = fieldName === 'example_words' ? 'Comma-separated words' : '';
        input.style.width = 'calc(95% - 40px)';

        const br = document.createElement('br');

        container.appendChild(label);
        container.appendChild(input);
        container.appendChild(br);
    }

    function clearDynamicLanguageFields() {
        displayNameInputsDiv.innerHTML = '';
        descriptionInputsDiv.innerHTML = '';
        exampleWordsInputsDiv.innerHTML = '';
    }

    function populateForm(category) {
        // Simple fields
        document.getElementById('type').value = category.type || 'thematic';
        document.getElementById('badge_id_association').value = category.badge_id_association || '';

        // CEFR Levels (Checkboxes)
        const cefrLevels = category.applicable_cefr_levels || [];
        document.querySelectorAll('input[name="applicable_cefr_levels"]').forEach(checkbox => {
            checkbox.checked = cefrLevels.includes(checkbox.value);
        });

        // Language Dictionaries
        clearDynamicLanguageFields(); // Clear first
        Object.entries(category.display_name || {}).forEach(([lang, text]) => {
            addLanguageField(displayNameInputsDiv, 'display_name', lang, text);
        });
        Object.entries(category.description || {}).forEach(([lang, text]) => {
            addLanguageField(descriptionInputsDiv, 'description', lang, text);
        });
        Object.entries(category.example_words || {}).forEach(([lang, words]) => {
            addLanguageField(exampleWordsInputsDiv, 'example_words', lang, words.join(', '));
        });
    }

    function getFormData() {
        const formData = new FormData(categoryForm);
        const data = {};
        const displayNames = {};
        const descriptions = {};
        const exampleWords = {};
        const cefrLevels = [];

        for (let [key, value] of formData.entries()) {
            if (key.startsWith('display_name[')) {
                const lang = key.match(/\[(.*?)\]/)[1];
                if (value) displayNames[lang] = value;
            } else if (key.startsWith('description[')) {
                const lang = key.match(/\[(.*?)\]/)[1];
                if (value) descriptions[lang] = value;
            } else if (key.startsWith('example_words[')) {
                const lang = key.match(/\[(.*?)\]/)[1];
                if (value) exampleWords[lang] = value.split(',').map(s => s.trim()).filter(Boolean);
            } else if (key === 'applicable_cefr_levels') {
                cefrLevels.push(value);
            } else {
                // Handle simple fields (category_id, type, badge_id_association)
                if (value || key === 'category_id' || key === 'type') { // Ensure required fields are included even if empty initially
                    data[key] = value;
                }
            }
        }

        data.display_name = displayNames;
        if (Object.keys(descriptions).length > 0) data.description = descriptions;
        if (Object.keys(exampleWords).length > 0) data.example_words = exampleWords;
        if (cefrLevels.length > 0) data.applicable_cefr_levels = cefrLevels;

        // Ensure required fields are present, even if empty from form
        if (!data.category_id) data.category_id = document.getElementById('category_id').value;
        if (!data.type) data.type = document.getElementById('type').value;


        // Remove empty optional fields before sending
        if (!data.badge_id_association) delete data.badge_id_association;
        if (!data.applicable_cefr_levels || data.applicable_cefr_levels.length === 0) delete data.applicable_cefr_levels;
        if (!data.description || Object.keys(data.description).length === 0) delete data.description;
        if (!data.example_words || Object.keys(data.example_words).length === 0) delete data.example_words;


        console.log("Form data prepared:", data);
        return data;
    }


    // --- API Interaction ---
    async function fetchCategories(langFilter = '') {
        categoryTableBody.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';
        let url = API_BASE_URL;
        if (langFilter) {
            url += `?lang=${encodeURIComponent(langFilter)}`;
        }
        console.log(`Fetching categories from: ${url}`);
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const categories = await response.json();
            console.log("Categories received:", categories);
            renderTable(categories, langFilter);
        } catch (error) {
            console.error("Error fetching categories:", error);
            categoryTableBody.innerHTML = `<tr><td colspan="6">Error loading categories: ${error.message}</td></tr>`;
        }
    }

    async function saveCategory(categoryData) {
        clearError();
        const mode = formModeInput.value;
        const url = (mode === 'edit' && currentEditId) ? `${API_BASE_URL}/${currentEditId}` : API_BASE_URL;
        const method = (mode === 'edit') ? 'PUT' : 'POST';

        console.log(`Saving category (${mode}) to ${url} with method ${method}`);
        console.log("Data being sent:", JSON.stringify(categoryData));


        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(categoryData),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.description || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log("Save successful:", result);
            hideForm();
            fetchCategories(languageFilterInput.value); // Refresh table
        } catch (error) {
            console.error("Error saving category:", error);
            displayFormError(`Failed to save category: ${error.message}`); // Use displayFormError here
        }
    }

    async function deleteCategory(categoryId) {
        clearError();
        if (!confirm(`Are you sure you want to delete category '${categoryId}'?`)) {
            return;
        }

        console.log(`Attempting to delete category: ${categoryId}`);
        try {
            const response = await fetch(`${API_BASE_URL}/${categoryId}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                 const errorData = await response.json();
                 throw new Error(errorData.description || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log("Delete successful:", result);
            displayFeedback(`Category '${categoryId}' deleted successfully.`); // Success feedback
            fetchCategories(languageFilterInput.value); // Refresh table
        } catch (error) {
            console.error("Error deleting category:", error);
            displayFeedback(`Failed to delete category: ${error.message}`, true); // Use displayFeedback for errors here
        }
    }

    // --- Rendering ---
    // Helper to format dictionary objects for display in table cells
    function formatDictForDisplay(dict) {
        if (!dict || typeof dict !== 'object' || Object.keys(dict).length === 0) {
            return 'N/A';
        }
        return Object.entries(dict)
            .map(([key, value]) => `<b>${key}:</b> ${Array.isArray(value) ? value.join(', ') : value}`)
            .join('<br>'); // Use line breaks for readability
    }

    // Helper to format Firestore timestamp objects (or ISO strings)
    function formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';
        try {
            // Firestore timestamps might be objects with seconds/nanoseconds,
            // or already converted to ISO strings by the backend/JSON process.
            let date;
            if (typeof timestamp === 'object' && timestamp.seconds) {
                date = new Date(timestamp.seconds * 1000);
            } else if (typeof timestamp === 'string') {
                date = new Date(timestamp);
            } else {
                return 'Invalid Date';
            }
            // Format to a readable string (e.g., "May 6, 2025, 5:08:10 AM")
            return date.toLocaleString();
        } catch (e) {
            console.error("Error formatting timestamp:", timestamp, e);
            return 'Invalid Date';
        }
    }


    function renderTable(categories, filterLang) { // filterLang is not used here anymore, but kept for potential future use
        categoryTableBody.innerHTML = ''; // Clear existing rows

        if (categories.length === 0) {
             // Update colspan to match the new number of columns (9)
            categoryTableBody.innerHTML = '<tr><td colspan="9">No categories found.</td></tr>';
            return;
        }

        categories.forEach(category => {
            const row = categoryTableBody.insertRow();

            // Format complex fields
            const displayNamesHtml = formatDictForDisplay(category.display_name);
            const descriptionsHtml = formatDictForDisplay(category.description);
            const exampleWordsHtml = formatDictForDisplay(category.example_words);
            const cefrLevelsText = (category.applicable_cefr_levels || []).join(', ') || 'N/A';
            const badgeIdText = category.badge_id_association || 'N/A';
            const createdAtText = formatTimestamp(category.created_at);
            const updatedAtText = formatTimestamp(category.updated_at);
            // Combine timestamps for display
            const auditDatesHtml = `Created: ${createdAtText}<br>Updated: ${updatedAtText}`;


            row.innerHTML = `
                <td>${category.category_id}</td>
                <td>${displayNamesHtml}</td>
                <td>${descriptionsHtml}</td>
                <td>${category.type || 'N/A'}</td>
                <td>${cefrLevelsText}</td>
                <td>${exampleWordsHtml}</td>
                <td>${badgeIdText}</td>
                <td>${auditDatesHtml}</td> <!-- Use combined HTML -->
                <td>
                    <button class="bg-yellow-500 text-white px-4 py-2 rounded-md hover:bg-yellow-600 edit-button" data-id="${category.category_id}">Edit</button>
                    <button class="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 delete-button" data-id="${category.category_id}">Delete</button>
                </td>
            `;
        });

        // Add event listeners for the new buttons
        document.querySelectorAll('.edit-button').forEach(button => {
            button.addEventListener('click', handleEditClick);
        });
        document.querySelectorAll('.delete-button').forEach(button => {
            button.addEventListener('click', handleDeleteClick);
        });
    }

    // --- Event Handlers ---
    function handleFilter() {
        fetchCategories(languageFilterInput.value.trim());
    }

    function handleClearFilter() {
        languageFilterInput.value = '';
        fetchCategories();
    }

    function handleAddClick() {
        showForm('add');
    }

    function handleEditClick(event) {
        const categoryId = event.target.dataset.id;
        console.log(`Edit button clicked for ID: ${categoryId}`);
        // Fetch the full category details first
        fetch(`${API_BASE_URL}/${categoryId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(category => {
                showForm('edit', category);
            })
            .catch(error => {
                console.error("Error fetching category details for edit:", error);
                displayFeedback(`Could not load category details: ${error.message}`, true); // Use displayFeedback
            });
    }

    function handleDeleteClick(event) {
        const categoryId = event.target.dataset.id;
        deleteCategory(categoryId);
    }

    function handleFormSubmit(event) {
        event.preventDefault(); // Prevent default form submission
        const categoryData = getFormData();
        if (categoryData) {
            saveCategory(categoryData);
        } else {
            displayFormError("Could not process form data."); // Use displayFormError
        }
    }

    // --- Initial Load ---
    fetchCategories();

    // --- Event Listeners ---
    filterButton.addEventListener('click', handleFilter);
    clearFilterButton.addEventListener('click', handleClearFilter);
    addCategoryButton.addEventListener('click', handleAddClick);
    categoryForm.addEventListener('submit', handleFormSubmit);
    cancelButton.addEventListener('click', hideForm);

    // Add language field buttons
    addDisplayNameLangButton.addEventListener('click', () => addLanguageField(displayNameInputsDiv, 'display_name'));
    addDescriptionLangButton.addEventListener('click', () => addLanguageField(descriptionInputsDiv, 'description'));
    addExampleWordsLangButton.addEventListener('click', () => addLanguageField(exampleWordsInputsDiv, 'example_words'));

});
