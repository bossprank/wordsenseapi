#!/bin/bash

# Script to set up the initial directory structure and files for the
# Python Word Sense Enrichment project.
# Also logs its own execution output to mylogs/setup.log.

# --- Configuration ---
VENV_NAME="venv" # Name of the virtual environment directory
LOG_DIR="mylogs"
LOG_FILE="$LOG_DIR/setup.log"
PROJECT_FILES=(
  "main_enrichment.py"
  "config.py"
  "firestore_client.py"
  "llm_client.py"
  "models.py"
  "requirements.txt"
  ".env"
)

# --- Gitignore Content ---
GITIGNORE_CONTENT=$(cat << 'EOF'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal
media/

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# Environments
.env
.venv
venv/
ENV/
env/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.type/

# Cython debug symbols
cython_debug/

# VS Code settings folder
.vscode/

# PyCharm settings folder
.idea/

# Sensitive files
*.pem
*.key
credentials*.json
serviceAccountKey.json

# Log files
*.log
logs/
terminal_logs/
mylogs/ # Ignore the log directory created by this script

# OS generated files
.DS_Store
Thumbs.db
EOF
)

# --- Script Logic ---

# Create log directory
mkdir -p "$LOG_DIR"
if [ $? -ne 0 ]; then
  echo "Error: Failed to create log directory '$LOG_DIR'"
  exit 1
fi

# Run main setup logic in a subshell and pipe output to tee
(
  echo "Setting up Python project structure..."
  echo "Log file: $LOG_FILE"
  echo "Timestamp: $(date)"
  echo "--------------------------------------"

  # Create empty project files
  echo "Creating Python files and config files..."
  for FILE in "${PROJECT_FILES[@]}"; do
    touch "$FILE"
    if [ $? -ne 0 ]; then
      echo "Error: Failed to create $FILE"
      exit 1 # Exit subshell on error
    fi
    echo " - Created $FILE"
  done

  # Create .gitignore file
  echo "Creating .gitignore..."
  echo "$GITIGNORE_CONTENT" > .gitignore
  if [ $? -ne 0 ]; then
    echo "Error: Failed to create .gitignore"
    exit 1 # Exit subshell on error
  fi
  echo " - Created .gitignore"

  # Create Python virtual environment
  echo "Creating virtual environment named '$VENV_NAME'..."
  PYTHON_CMD=""
  # Check if python3 command exists, otherwise try python
  if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
  elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
  else
    echo "Error: Could not find 'python3' or 'python' command."
    echo "Please ensure Python 3 is installed and in your PATH."
    exit 1 # Exit subshell on error
  fi

  echo "Using command: $PYTHON_CMD -m venv $VENV_NAME"
  $PYTHON_CMD -m venv "$VENV_NAME"
  if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment '$VENV_NAME'."
    exit 1 # Exit subshell on error
  fi
  echo " - Created virtual environment '$VENV_NAME'"

  echo ""
  echo "--------------------------------------"
  echo "Project structure created successfully!"
  echo ""
  echo "Next Steps:"
  echo "1. Activate the virtual environment:"
  echo "   On Linux/macOS: source $VENV_NAME/bin/activate"
  echo "   On Windows (cmd): $VENV_NAME\\Scripts\\activate.bat"
  echo "   On Windows (PowerShell): $VENV_NAME\\Scripts\\Activate.ps1"
  echo "2. Install dependencies (once activated):"
  echo "   pip install -r requirements.txt"
  echo "   (Add packages like flask, google-cloud-firestore, google-generativeai, python-dotenv, flake8 to requirements.txt first)"
  echo "3. Add your API keys and project ID to the '.env' file."

) 2>&1 | tee "$LOG_FILE" # Redirect subshell stdout/stderr to tee and the log file

# Check the exit status of the subshell (captured by tee)
# $? reflects the exit status of the last command in the pipe (tee)
# Use ${PIPESTATUS[0]} for the exit status of the subshell command (bash specific)
if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo ""
  echo "!!! Setup script encountered an error. Please check the log file: $LOG_FILE !!!"
  exit 1
fi

exit 0
