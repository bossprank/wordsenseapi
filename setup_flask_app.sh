#!/bin/bash

# Script to add the necessary files and directories for the Flask web UI
# on top of the existing Python backend structure.
# Assumes it's run from the project root directory.

# --- Configuration ---
LOG_DIR="mylogs"
LOG_FILE="$LOG_DIR/flask_setup.log"
FLASK_APP_FILE="app.py" # Or main.py if you prefer
TEMPLATE_DIR="templates"
STATIC_DIR="static"
HTML_FILE="$TEMPLATE_DIR/index.html"
JS_FILE="$STATIC_DIR/app.js"
CSS_FILE="$STATIC_DIR/style.css" # Optional CSS file

# --- Script Logic ---

# Create log directory
mkdir -p "$LOG_DIR"
if [ $? -ne 0 ]; then
  echo "Error: Failed to create log directory '$LOG_DIR'"
  exit 1
fi

# Run main setup logic in a subshell and pipe output to tee
(
  echo "Adding Flask app structure..."
  echo "Log file: $LOG_FILE"
  echo "Timestamp: $(date)"
  echo "--------------------------------------"

  # Create Flask app file (if it doesn't exist)
  if [ ! -f "$FLASK_APP_FILE" ]; then
    echo "Creating Flask app file '$FLASK_APP_FILE'..."
    touch "$FLASK_APP_FILE"
    if [ $? -ne 0 ]; then echo "Error: Failed to create $FLASK_APP_FILE"; exit 1; fi
    echo " - Created $FLASK_APP_FILE"
  else
    echo " - Flask app file '$FLASK_APP_FILE' already exists."
  fi

  # Create templates directory (if it doesn't exist)
  if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "Creating directory '$TEMPLATE_DIR'..."
    mkdir -p "$TEMPLATE_DIR"
    if [ $? -ne 0 ]; then echo "Error: Failed to create $TEMPLATE_DIR"; exit 1; fi
    echo " - Created $TEMPLATE_DIR"
  else
    echo " - Directory '$TEMPLATE_DIR' already exists."
  fi

  # Create static directory (if it doesn't exist)
  if [ ! -d "$STATIC_DIR" ]; then
    echo "Creating directory '$STATIC_DIR'..."
    mkdir -p "$STATIC_DIR"
    if [ $? -ne 0 ]; then echo "Error: Failed to create $STATIC_DIR"; exit 1; fi
    echo " - Created $STATIC_DIR"
  else
    echo " - Directory '$STATIC_DIR' already exists."
  fi

  # Create empty index.html (if it doesn't exist)
  if [ ! -f "$HTML_FILE" ]; then
    echo "Creating empty HTML file '$HTML_FILE'..."
    touch "$HTML_FILE"
    if [ $? -ne 0 ]; then echo "Error: Failed to create $HTML_FILE"; exit 1; fi
    echo " - Created $HTML_FILE"
  else
    echo " - HTML file '$HTML_FILE' already exists."
  fi

  # Create empty app.js (if it doesn't exist)
  if [ ! -f "$JS_FILE" ]; then
    echo "Creating empty JS file '$JS_FILE'..."
    touch "$JS_FILE"
    if [ $? -ne 0 ]; then echo "Error: Failed to create $JS_FILE"; exit 1; fi
    echo " - Created $JS_FILE"
  else
    echo " - JS file '$JS_FILE' already exists."
  fi

   # Create empty style.css (if it doesn't exist)
  if [ ! -f "$CSS_FILE" ]; then
    echo "Creating empty CSS file '$CSS_FILE'..."
    touch "$CSS_FILE"
    if [ $? -ne 0 ]; then echo "Error: Failed to create $CSS_FILE"; exit 1; fi
    echo " - Created $CSS_FILE"
  else
    echo " - CSS file '$CSS_FILE' already exists."
  fi


  echo ""
  echo "--------------------------------------"
  echo "Flask app structure added successfully!"
  echo ""
  echo "Next Steps:"
  echo "1. Add Flask application code to '$FLASK_APP_FILE'."
  echo "2. Add HTML structure to '$HTML_FILE'."
  echo "3. Add JavaScript logic to '$JS_FILE'."
  echo "4. Add CSS styles to '$CSS_FILE'."
  echo "5. Run the Flask development server (after adding code to $FLASK_APP_FILE):"
  echo "   flask --app $FLASK_APP_FILE run --debug"

) 2>&1 | tee "$LOG_FILE" # Redirect subshell stdout/stderr to tee and the log file

# Check the exit status of the subshell
if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo ""
  echo "!!! Flask setup script encountered an error. Please check the log file: $LOG_FILE !!!"
  exit 1
fi

exit 0
