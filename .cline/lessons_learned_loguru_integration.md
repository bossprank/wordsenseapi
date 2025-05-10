# Lessons Learned: Loguru Integration for Enhanced Logging

## 1. Problem Statement

The existing logging setup using Python's standard `logging` module was proving difficult to configure reliably for capturing `DEBUG` level messages from specific application modules into a rotating file log, especially within a Uvicorn/FastAPI (via WSGIMiddleware for Flask) environment. Despite various attempts to configure handlers, levels, and propagation, `DEBUG` messages were not consistently appearing in the log files, hindering debugging efforts for issues like LLM word generation failures.

## 2. Solution: Integration of Loguru

Loguru, a third-party Python library, was chosen to simplify and enhance the logging mechanism due to its user-friendly API for configuration, built-in support for file rotation, retention, compression, and better handling in asynchronous/multiprocessing contexts.

## 3. Implementation Steps

### 3.1. Add Dependency
`loguru==0.7.2` was added to `requirements.txt`. The version was chosen based on the latest stable release found on PyPI.

### 3.2. Configure Loguru in `app_factory.py`
The `create_app()` function in `app_factory.py` was modified to set up Loguru as the primary logging system:

```python
# app_factory.py
import sys
from loguru import logger as loguru_logger
# ... other imports ...

LOGURU_LOG_DIR = 'mylogs'
LOGURU_LOG_FILE_PATH = os.path.join(LOGURU_LOG_DIR, 'main_app_loguru.log')
LOGURU_ROTATION = "10 MB"
LOGURU_RETENTION = "5 days"
LOGURU_COMPRESSION = "zip"
LOGURU_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
LOGURU_CONSOLE_LEVEL = "INFO"
LOGURU_FILE_LEVEL = "DEBUG"

def create_app():
    # ... (ensure LOGURU_LOG_DIR exists) ...

    loguru_logger.remove() # Remove default Loguru handler

    # Console sink
    loguru_logger.add(
        sys.stderr,
        level=LOGURU_CONSOLE_LEVEL,
        format=LOGURU_FORMAT,
        colorize=True
    )

    # File sink
    loguru_logger.add(
        LOGURU_LOG_FILE_PATH,
        level=LOGURU_FILE_LEVEL,
        rotation=LOGURU_ROTATION,
        retention=LOGURU_RETENTION,
        compression=LOGURU_COMPRESSION,
        enqueue=True,  # Important for async/multiprocess safety
        format=LOGURU_FORMAT,
        encoding="utf-8"
    )
    
    loguru_logger.info("--- create_app(): Application factory started (Loguru configured) ---")
    
    # ... rest of app factory setup ...
    # Note: The factory's own logger (logging.getLogger(__name__)) was kept for its direct messages,
    # but application modules were switched to Loguru.
    return asgi_app 
```
- The standard `logging` setup (root logger configuration, `RotatingFileHandler`) was removed.
- Loguru's default handler is removed, and two new sinks are added:
    - A console sink (to `sys.stderr`) logging at `INFO` level with colorization.
    - A file sink logging to `mylogs/main_app_loguru.log` (new name) at `DEBUG` level, with rotation (10MB), retention (5 days), compression (zip), and `enqueue=True` for async safety.
- A custom `LOGURU_FORMAT` was defined for rich log messages.

### 3.3. Update Application Modules to Use Loguru
Modules critical for debugging the LLM call were updated:
- `llm_client.py`
- `routes/api_list_generation_routes.py`
- `firestore_client.py`

In these files, the standard logging import and `getLogger` call:
```python
import logging
logger = logging.getLogger(__name__)
```
were replaced with:
```python
from loguru import logger
# The imported 'logger' object is used directly.
```
Existing `logger.debug()`, `logger.info()`, `logger.error()`, `logger.exception()` calls work seamlessly with the Loguru logger.

### 3.4. Uvicorn Configuration
The `devserver.sh` script was already updated to run Uvicorn with `--log-level debug`. This is important so Uvicorn itself doesn't filter out debug messages before Loguru can process them.

## 4. How Loguru Works in This System

- **Central Configuration**: Loguru is configured once in `app_factory.py` when the application starts.
- **Global Logger**: Importing `from loguru import logger` in any module provides access to the same pre-configured logger instance.
- **Sinks**:
    - The console sink provides immediate feedback at `INFO` level during development.
    - The file sink captures detailed `DEBUG` messages, including those from `llm_client` and the generation routes, into a rotating log file (`mylogs/main_app_loguru.log`). This file is managed by Loguru for size and retention.
- **Async/Multiprocess Safety**: The `enqueue=True` parameter for the file sink makes it suitable for the asynchronous operations in FastAPI (via WSGIMiddleware) and background tasks. Log messages are put into a queue and processed by a separate thread, preventing blocking.
- **Structured Formatting**: The custom format string provides rich, readable logs including timestamp, level, module name, function name, line number, and the message. Colorization is active for the console.

## 5. Expected Benefits

- **Reliable DEBUG Logging**: `DEBUG` level messages from application modules should now be consistently captured in the file log.
- **Simplified Configuration**: Loguru's API simplifies the setup of complex logging features like rotation and async safety.
- **Improved Readability**: Richer formatting and colorization (on console) improve log readability.
- **Managed Log Files**: Automatic rotation, retention, and compression prevent log files from consuming excessive disk space.

## 6. Next Steps & Potential Refinements

- **Verify**: Confirm that `DEBUG` logs from `llm_client.py` and `routes.api_list_generation_routes.py` now appear in `mylogs/main_app_loguru.log`.
- **Intercept Standard Logging**: If other parts of the application or third-party libraries still use the standard `logging` module and their logs are desired, Loguru's `InterceptHandler` can be configured to capture these and route them through Loguru's sinks.
- **Fine-tune Levels**: Adjust console and file log levels as needed once debugging is complete (e.g., raise console level in production).
- **Contextual Data**: Explore Loguru's `bind()` or `contextualize()` features if there's a need to add more dynamic context (e.g., request IDs) to log messages.
- **Update Other Modules**: Gradually update other modules (e.g., other route files, `config.py`, `gcp_utils.py`) to use Loguru for consistency if desired.
