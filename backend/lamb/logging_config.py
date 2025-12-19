import os
import sys
import logging


# Log levels supported
_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


# Global level from env (default WARNING)
GLOBAL_LOG_LEVEL = os.environ.get("GLOBAL_LOG_LEVEL", "WARNING").strip().upper()
if GLOBAL_LOG_LEVEL not in _LOG_LEVELS:
    GLOBAL_LOG_LEVEL = "WARNING"

# Configure root logging once to stdout; force=True to override prior configs
logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL, force=True)

# Set the root logger level explicitly to ensure it propagates
logging.getLogger().setLevel(GLOBAL_LOG_LEVEL)

# Component-specific levels (override via env)
_LOG_SOURCES = [
    "MAIN",
    "API",
    "DB",
    "RAG",
    "EVALUATOR",
    "OWI",
]

SRC_LOG_LEVELS: dict[str, str] = {}
for source in _LOG_SOURCES:
    env_var = f"{source}_LOG_LEVEL"
    level = os.environ.get(env_var, "").strip().upper()
    if level not in _LOG_LEVELS:
        level = GLOBAL_LOG_LEVEL
    SRC_LOG_LEVELS[source] = level

def get_logger(name: str, component: str = "MAIN") -> logging.Logger:
    """Return a module logger configured for the given component.

    The component level is taken from SRC_LOG_LEVELS; defaults to GLOBAL.
    """
    logger = logging.getLogger(name)
    level = SRC_LOG_LEVELS.get(component, GLOBAL_LOG_LEVEL)
    logger.setLevel(level)
    return logger
