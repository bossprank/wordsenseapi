#!/bin/bash

# Script to activate the virtual environment,
# stop any existing process on port 5000,
# and start the Uvicorn ASGI server for the wordsense-api-fe application.

echo "Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment. Please ensure .venv exists and is set up correctly."
    exit 1
fi

echo "Attempting to forcefully free port 5000..."
# Try to forcefully kill process on port 5000. Suppress errors.
if command -v lsof &> /dev/null; then
    PID_TO_KILL=$(lsof -t -i:5000)
    if [ -n "$PID_TO_KILL" ]; then
        echo "Found process(es) $PID_TO_KILL on port 5000. Sending SIGKILL..."
        # Use xargs to handle multiple PIDs if necessary
        echo "$PID_TO_KILL" | xargs kill -9 2>/dev/null
        sleep 1 # Give time for port release
        echo "Port 5000 should be free."
    else
        echo "No process found on port 5000."
    fi
else
    echo "Warning: 'lsof' command not found. Cannot guarantee port 5000 is free."
fi

echo "Constructing public URL..."
# Construct the URL using the WEB_HOST environment variable (common in IDX/Cloud Workstations)
if [ -z "$WEB_HOST" ]; then
  echo "Warning: WEB_HOST environment variable not set. Cannot determine public URL automatically."
  PUBLIC_URL="http://localhost:5000 (or your environment's preview URL)"
else
  PUBLIC_URL="https://5000-${WEB_HOST}/"
fi

echo "-----------------------------------------------------"
echo "Server starting..."
echo "Access the application at: ${PUBLIC_URL}"
echo "-----------------------------------------------------"

echo "Starting Uvicorn server for app:asgi_app on http://0.0.0.0:5000 with auto-reload..."
uvicorn app:asgi_app --host 0.0.0.0 --port 5000 --reload
