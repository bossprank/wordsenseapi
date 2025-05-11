#!/bin/bash

# Script to stop any existing process on port 5000 and start the Uvicorn ASGI server.

echo "Attempting to free port 5000..."
# Try to kill process on port 5000. Suppress errors if lsof not found or no process.
kill $(lsof -t -i:5000) 2>/dev/null || true
echo "Port 5000 cleared or was already free."

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Starting Uvicorn server for main_fastapi:app on http://0.0.0.0:8080 with auto-reload..."
uvicorn main_fastapi:app --host 0.0.0.0 --port 8080 --reload
