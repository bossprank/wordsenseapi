document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('config-detail-form');
    const configIdField = document.getElementById('config_id');
    const configId = configIdField.value;

    // Function to parse datetime-local string to ISO string
    function formatDateTimeForAPI(dateTimeLocalStr) {
        if (!dateTimeLocalStr) return null;
        // Ensure it's in a format that Pydantic/Python's datetime.fromisoformat can handle
        // datetime-local format is 'YYYY-MM-DDTHH:MM', which is mostly ISO 8601
        // We might need to add seconds and timezone info if backend expects full ISO
        return new Date(dateTimeLocalStr).toISOString();
    }
    
    // Function to parse ISO string to datetime-local string
    function formatDateTimeForInput(isoString) {
        if (!isoString) return '';
        const date = new Date(isoString);
        // Adjust for timezone offset to display correctly in local time
        const timezoneOffset = date.getTimezoneOffset() * 60000; //offset in milliseconds
        const localISOTime = (new Date(date.getTime() - timezoneOffset)).toISOString().slice(0,16);
        return localISOTime;
    }


    if (configId && configId !== 'new') {
        // Fetch existing config data for editing
        fetch(`/api/language-pair-configurations/${configId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to fetch configuration details');
                }
                return response.json();
            })
            .then(data => {
                const [sourceLang, targetLang] = data.language_pair.split('-');
                document.getElementById('language_pair_source').value = sourceLang || '';
                document.getElementById('language_pair_target').value = targetLang || '';
                document.getElementById('config_key').value = data.config_key || '';
                document.getElementById('config_value').value = data.config_value || '';
                document.getElementById('value_type').value = data.value_type || 'string';
                document.getElementById('effective_date').value = formatDateTimeForInput(data.effective_date);
                document.getElementById('expiry_date').value = data.expiry_date ? formatDateTimeForInput(data.expiry_date) : '';
                document.getElementById('description_en').value = data.description && data.description.en ? data.description.en : '';
                document.getElementById('updated_by').value = data.updated_by || '';
            })
            .catch(error => {
                console.error('Error fetching configuration:', error);
                alert('Could not load configuration data for editing.');
            });
    }

    form.addEventListener('submit', async function(event) {
        event.preventDefault();

        const sourceLang = document.getElementById('language_pair_source').value;
        const targetLang = document.getElementById('language_pair_target').value;
        const language_pair = `${sourceLang}-${targetLang}`;

        const payload = {
            language_pair: language_pair,
            config_key: document.getElementById('config_key').value,
            config_value: document.getElementById('config_value').value,
            value_type: document.getElementById('value_type').value,
            effective_date: formatDateTimeForAPI(document.getElementById('effective_date').value),
            expiry_date: document.getElementById('expiry_date').value ? formatDateTimeForAPI(document.getElementById('expiry_date').value) : null,
            description: { // Simple structure for now, can be expanded
                en: document.getElementById('description_en').value || null
            },
            updated_by: document.getElementById('updated_by').value || null,
        };
        
        // Remove null description if 'en' is null
        if (payload.description.en === null) {
            payload.description = null;
        }


        const method = (configId && configId !== 'new') ? 'PUT' : 'POST';
        const url = (configId && configId !== 'new') ? `/api/language-pair-configurations/${configId}` : '/api/language-pair-configurations';

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.description || `HTTP error! status: ${response.status}`);
            }
            
            window.location.href = '/manage-language-pairs'; // Redirect to list page
        } catch (error) {
            console.error('Error saving configuration:', error);
            alert(`Failed to save configuration: ${error.message}`);
        }
    });
});
