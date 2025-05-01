#!/bin/bash

# Script to test various Gemini model names using test_model.py

# --- Configuration ---
# List of common text-based Gemini model names to try
# Add or remove models as needed based on Google's documentation
MODELS_TO_TEST=(
  "gemini-pro"             # The one causing issues
  "gemini-1.0-pro"         # Often an alias for gemini-pro
  "gemini-1.5-flash-latest" # A newer, faster model
  "gemini-1.5-pro-latest"   # The latest Pro model
  # "gemini-pro-vision"    # Vision model - requires different input, skip for now
)

LOG_DIR="mylogs"
LOG_FILE="$LOG_DIR/model_test_results.log"
PYTHON_SCRIPT="test_model.py"

# --- Script Logic ---

# Ensure log directory exists
mkdir -p "$LOG_DIR"
if [ $? -ne 0 ]; then
  echo "Error: Failed to create log directory '$LOG_DIR'"
  exit 1
fi

# Ensure Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python test script '$PYTHON_SCRIPT' not found in the current directory."
    exit 1
fi

# Clear previous log or add timestamp
echo "--- Starting Model Tests: $(date) ---" > "$LOG_FILE"
echo "Logging results to: $LOG_FILE"
echo "" | tee -a "$LOG_FILE" # Add a blank line

# Activate virtual environment if it exists and isn't already active
# Basic check - might need adjustment based on specific shell/setup
if [ -d "venv/bin/activate" ] && [ -z "$VIRTUAL_ENV" ]; then
    echo "Attempting to activate virtual environment 'venv'..."
    source venv/bin/activate
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to activate virtual environment automatically."
        echo "Please ensure 'venv' is activated manually before running if needed."
    else
         echo "Virtual environment activated."
    fi
elif [ -n "$VIRTUAL_ENV" ]; then
     echo "Virtual environment '$VIRTUAL_ENV' already active."
fi


# Loop through models and run the Python test script
for model in "${MODELS_TO_TEST[@]}"; do
  echo "-----------------------------------------" | tee -a "$LOG_FILE"
  echo "Running test for model: $model" | tee -a "$LOG_FILE"
  echo "-----------------------------------------" | tee -a "$LOG_FILE"

  # Run the python script, capture stdout/stderr, append to log, show on terminal
  python "$PYTHON_SCRIPT" "$model" 2>&1 | tee -a "$LOG_FILE"

  # Check exit status of the python script (last command in the pipe)
  if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "-> Test FAILED for model: $model" | tee -a "$LOG_FILE"
  else
    echo "-> Test SUCCEEDED for model: $model" | tee -a "$LOG_FILE"
  fi
   echo "" | tee -a "$LOG_FILE" # Add a blank line for readability
done

echo "--- Model Tests Complete: $(date) ---" | tee -a "$LOG_FILE"
echo "Full results logged to: $LOG_FILE"

exit 0
