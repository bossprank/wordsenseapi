document.addEventListener('DOMContentLoaded', function() {
    const configListTbody = document.getElementById('config-list-tbody');

    // Function to format date for display
    function formatDateForDisplay(isoString) {
        if (!isoString) return 'N/A';
        try {
            // Attempt to create a date object. Handle potential invalid formats from Firestore if any.
            const date = new Date(isoString);
            if (isNaN(date.getTime())) { // Check if date is invalid
                 // Try to parse if it's a Firestore Timestamp-like object string
                if (typeof isoString === 'object' && isoString.seconds) {
                    date = new Date(isoString.seconds * 1000);
                } else {
                    return 'Invalid Date'; // Or handle as per requirements
                }
            }
            return date.toLocaleString(); // Or use more specific formatting
        } catch (e) {
            console.warn("Could not parse date:", isoString, e);
            return 'Invalid Date';
        }
    }


    // Function to fetch and display configurations
    async function loadConfigs() {
        try {
            const response = await fetch('/api/language-pair-configurations');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const configs = await response.json();

            configListTbody.innerHTML = ''; // Clear existing list
            if (configs.length === 0) {
                const row = configListTbody.insertRow();
                const cell = row.insertCell();
                cell.colSpan = 5; // Span across all columns
                cell.textContent = 'No configurations found.';
                return;
            }

            configs.forEach(config => {
                const row = configListTbody.insertRow();
                row.insertCell().textContent = config.language_pair;
                row.insertCell().textContent = config.config_key;

                // Truncate long values for display in the table
                let displayValue = config.config_value;
                if (displayValue && displayValue.length > 50) {
                    displayValue = displayValue.substring(0, 47) + "...";
                }
                row.insertCell().textContent = displayValue;

                // Version Control Column
                const effectiveStr = formatDateForDisplay(config.effective_date);
                const expiryStr = config.expiry_date ? formatDateForDisplay(config.expiry_date) : 'Never';
                row.insertCell().textContent = `Effective: ${effectiveStr}\nExpiry: ${expiryStr}`;

                // Audit Dates Column
                const createdStr = formatDateForDisplay(config.created_at);
                const updatedStr = formatDateForDisplay(config.updated_at);
                row.insertCell().textContent = `Created: ${createdStr}\nUpdated: ${updatedStr}`;


                // Actions Column
                const actionsCell = row.insertCell();

                // Edit Button
                const editButton = document.createElement('button');
                editButton.textContent = 'Edit';
                editButton.className = 'bg-yellow-500 text-white px-4 py-2 rounded-md hover:bg-yellow-600 edit-button'; // Tailwind classes + custom class
                editButton.dataset.id = config.id; // Store config ID
                actionsCell.appendChild(editButton);
                actionsCell.appendChild(document.createTextNode(' ')); // Add space

                // Delete Button
                const deleteButton = document.createElement('button');
                deleteButton.textContent = 'Delete';
                deleteButton.className = 'bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 delete-button'; // Tailwind classes + custom class
                deleteButton.dataset.id = config.id; // Store config ID
                actionsCell.appendChild(deleteButton);
            });
        } catch (error) {
            console.error('Error loading configurations:', error);
            const row = configListTbody.insertRow();
            const cell = row.insertCell();
            cell.colSpan = 6; // Adjusted colspan
            cell.textContent = 'Error loading configurations.';
        }
    }

    // Initial load of configurations
    loadConfigs();

    // Event listener for "Add New Configuration" button
    const addConfigButton = document.getElementById('add-config-button');
    if (addConfigButton) {
        addConfigButton.addEventListener('click', function() {
            window.location.href = '/language-pair-config-detail/new';
        });
    }

    // Event delegation for Edit and Delete buttons
    configListTbody.addEventListener('click', async function(event) {
        // Handle Edit button click
        if (event.target.classList.contains('edit-button')) {
            const configId = event.target.dataset.id;
            window.location.href = `/language-pair-config-detail/${configId}`; // Navigate to edit page
        }

        // Handle Delete button click
        if (event.target.classList.contains('delete-button')) {
            const configId = event.target.dataset.id;
            if (confirm(`Are you sure you want to delete configuration ID: ${configId}?`)) {
                try {
                    const response = await fetch(`/api/language-pair-configurations/${configId}`, {
                        method: 'DELETE',
                    });
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.description || `HTTP error! status: ${response.status}`);
                    }
                    loadConfigs(); // Reload configurations after deletion
                } catch (error) {
                    console.error('Error deleting configuration:', error);
                    alert(`Failed to delete configuration: ${error.message}`);
                }
            }
        }
    });
});
