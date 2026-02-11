"""
Server configuration management.

This module handles persistent server-level configuration that overrides environment variables.
Configuration is stored in a JSON file at data/config.json.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("lamb-kb")

# Configuration file path
CONFIG_FILE = Path(os.getenv("KB_CONFIG_PATH", "data/config.json"))


def _load_config() -> Dict[str, Any]:
    """Load configuration from JSON file.
    
    Returns:
        Dictionary with configuration values, empty dict if file doesn't exist
    """
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config file {CONFIG_FILE}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading config file {CONFIG_FILE}: {e}")
        return {}


def _save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to JSON file.
    
    Args:
        config: Dictionary with configuration values
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        # Ensure data directory exists
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving config file {CONFIG_FILE}: {e}")
        return False


def get_embeddings_config() -> Dict[str, Any]:
    """Get embeddings configuration.
    
    Returns the configured embeddings settings, falling back to environment variables
    if not set in the config file.
    
    Returns:
        Dictionary with vendor, model, api_endpoint, and apikey
    """
    config = _load_config()
    embeddings_config = config.get("embeddings", {})
    
    return {
        "vendor": embeddings_config.get("vendor", os.getenv("EMBEDDINGS_VENDOR", "ollama")),
        "model": embeddings_config.get("model", os.getenv("EMBEDDINGS_MODEL", "nomic-embed-text")),
        "api_endpoint": embeddings_config.get("api_endpoint", os.getenv("EMBEDDINGS_ENDPOINT", "http://localhost:11434/api/embeddings")),
        "apikey": embeddings_config.get("apikey", os.getenv("EMBEDDINGS_APIKEY", ""))
    }


def update_embeddings_config(
    vendor: Optional[str] = None,
    model: Optional[str] = None,
    api_endpoint: Optional[str] = None,
    apikey: Optional[str] = None
) -> bool:
    """Update embeddings configuration.
    
    Only updates the fields that are provided (not None). The config file
    overrides environment variables for fields that are set.
    
    Args:
        vendor: Embeddings vendor (e.g., 'ollama', 'local', 'openai')
        model: Model name
        api_endpoint: API endpoint URL
        apikey: API key for the embeddings service
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        config = _load_config()
        
        # Initialize embeddings config if it doesn't exist
        if "embeddings" not in config:
            config["embeddings"] = {}
        
        # Update only provided fields
        if vendor is not None:
            config["embeddings"]["vendor"] = vendor
        if model is not None:
            config["embeddings"]["model"] = model
        if api_endpoint is not None:
            config["embeddings"]["api_endpoint"] = api_endpoint
        if apikey is not None:
            config["embeddings"]["apikey"] = apikey
        
        return _save_config(config)
    except Exception as e:
        logger.error(f"Error updating embeddings config: {e}")
        return False


def reset_embeddings_config() -> bool:
    """Reset embeddings configuration to use environment variables.
    
    Removes the embeddings configuration from the config file, causing
    the system to fall back to environment variables.
    
    Returns:
        True if reset was successful, False otherwise
    """
    try:
        config = _load_config()
        
        if "embeddings" in config:
            del config["embeddings"]
            
        return _save_config(config)
    except Exception as e:
        logger.error(f"Error resetting embeddings config: {e}")
        return False


def has_embeddings_config() -> bool:
    """Check if embeddings configuration is set in the config file.
    
    Returns:
        True if embeddings config exists in config file, False otherwise
    """
    config = _load_config()
    return "embeddings" in config
