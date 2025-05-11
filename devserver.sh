#!/bin/bash

# Script to activate the virtual environment,
# stop any existing process on port 5000,
# and start the Uvicorn ASGI server for the wordsense-api-fe application.

# --- Plan Changes History ---
# - Added improved error handling for virtual environment activation (2023-10-27)
# - Enhanced port 5000 conflict resolution, verification, and error reporting (2023-10-27)
# - Added suggestion for manually setting WEB_HOST if needed (2023-10-27)
# - Added dependency reminder and Uvicorn exit status check (2023-10-27)
# ----------------------------

echo "Activating virtual environment..."
# Check if the .venv directory exists first
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment directory '.venv' not found."
    echo "Please ensure the virtual environment is created (e.g., python3 -m venv .venv) and dependencies are installed (e.g., pip install -r requirements.txt)."
    exit 1
fi
# Activate the virtual environment
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment."
    # The previous check covers the case where .venv is missing, so this is for other source errors.
    echo "Ensure the virtual environment is set up correctly."
    exit 1
fi
echo "Virtual environment activated."

echo "Installing/updating dependencies from requirements.txt..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies from requirements.txt."
    echo "Please check requirements.txt and ensure pip is working correctly."
    exit 1
fi
echo "Dependencies installed/updated."

echo "Attempting to forcefully free port 8080..." # Changed port
# Try to forcefully kill process on port 8080.
# Added enhanced port checking and error handling.
if command -v lsof &> /dev/null; then
    PID_TO_KILL=$(lsof -t -i:8080) # Changed port
    if [ -n "$PID_TO_KILL" ]; then
        echo "Found process(es) $PID_TO_KILL on port 8080. Sending SIGKILL..." # Changed port
        # Use xargs to handle multiple PIDs if necessary. Suppress kill errors initially.
        echo "$PID_TO_KILL" | xargs kill -9 2>/dev/null
        # Give time for port release and verify
        sleep 2 # Increased sleep time slightly
        if lsof -i:8080 &> /dev/null; then # Changed port
            echo "Error: Port 8080 is still in use after attempted kill." # Changed port
            echo "Please manually identify and terminate the process using port 8080 (e.g., lsof -i:8080)." # Changed port
            exit 1
        else
             echo "Port 8080 successfully freed." # Changed port
        fi
    else
        echo "No process found on port 8080." # Changed port
    fi
else
    echo "Warning: 'lsof' command not found."
    echo "Cannot check or guarantee port 8080 is free." # Changed port
    # Optional: Suggest installing lsof
    # echo "Consider installing lsof (e.g., sudo apt-get install lsof on Debian/Ubuntu, brew install lsof on macOS)."
fi

echo "Constructing public URL..."
# Construct the URL using the WEB_HOST environment variable (common in IDX/Cloud Workstations)
# Added suggestion for manual setting if needed.
if [ -z "$WEB_HOST" ]; then
  echo "Warning: WEB_HOST environment variable not set. Cannot determine public URL automatically."
  PUBLIC_URL="http://localhost:8080 (or your environment's preview URL)" # Changed port
  echo "If you need a specific public URL displayed, you can set the WEB_HOST environment variable."
else
  PUBLIC_URL="https://8080-${WEB_HOST}/" # Changed port
fi

echo "-----------------------------------------------------"
echo "Server starting..."
echo "Access the application at: ${PUBLIC_URL}"
echo "-----------------------------------------------------"

echo "Starting Uvicorn server for main_fastapi:app on http://0.0.0.0:8080 with auto-reload and debug logging..." # Changed app target and added reload
# Ensure required packages like uvicorn are installed in the virtual environment.
# Example: pip install -r requirements.txt
uvicorn main_fastapi:app --host 0.0.0.0 --port 8080 --reload --log-level debug

# Added check for Uvicorn exit status
if [ $? -ne 0 ]; then
    echo "-----------------------------------------------------"
    echo "Error: Uvicorn server failed to start."
    echo "Please review the output above for specific error messages (e.g., port conflicts, import errors, application initialization failures)."
    echo "-----------------------------------------------------"
    exit 1
else
    echo "-----------------------------------------------------"
    echo "Uvicorn server started successfully."
    echo "-----------------------------------------------------"
fi
