# gcp_utils.py
# Utilities for interacting with Google Cloud Platform services.

import logging
from typing import Optional
from google.cloud import secretmanager

logger = logging.getLogger(__name__)

def fetch_secret(project_id: str, secret_id: str, version_id: str = "latest") -> Optional[str]:
    """
    Fetches a secret from Google Cloud Secret Manager.

    Args:
        project_id: The Google Cloud project ID.
        secret_id: The ID of the secret.
        version_id: The version of the secret (defaults to "latest").

    Returns:
        The secret payload as a string, or None if an error occurs.
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        logger.info(f"Attempting to fetch secret: {secret_name}")
        
        response = client.access_secret_version(name=secret_name)
        payload = response.payload.data.decode("UTF-8")
        
        logger.info(f"Successfully fetched secret '{secret_id}' (version: {version_id}).")
        return payload
    except Exception as e:
        logger.error(f"Failed to fetch secret '{secret_id}' (version: {version_id}) from project '{project_id}': {e}")
        return None

if __name__ == '__main__':
    # Example usage (requires appropriate environment setup for authentication)
    # Replace with your actual project_id and secret_id for testing
    # Ensure the GOOGLE_APPLICATION_CREDENTIALS environment variable is set
    # or you are running in an environment with Application Default Credentials.

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test with a placeholder - this will likely fail if the secret doesn't exist
    # or if auth isn't set up for direct script execution.
    # For this project, the primary use is from within the Flask app context.
    PROJECT_ID_TEST = "your-gcp-project-id" # Replace for local testing
    SECRET_ID_TEST = "your-secret-id"     # Replace for local testing

    print(f"Attempting to fetch test secret '{SECRET_ID_TEST}' from project '{PROJECT_ID_TEST}'...")
    secret_value = fetch_secret(PROJECT_ID_TEST, SECRET_ID_TEST)

    if secret_value:
        print(f"Test secret '{SECRET_ID_TEST}' fetched successfully (first 10 chars): {secret_value[:10]}...")
    else:
        print(f"Failed to fetch test secret '{SECRET_ID_TEST}'. This might be expected if not configured for standalone run.")
