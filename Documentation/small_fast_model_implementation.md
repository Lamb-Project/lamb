# Global Model Configuration Implementation Plan

**Version:** 2.0  
**Date:** December 16, 2025  
**Status:** Planning

---

## Executive Summary

This document outlines the implementation plan for adding **two global model configurations** to LAMB organizations:

1. **Global Default Model**: A single organization-wide default model that serves as the primary model for assistants and completions when no specific model is configured
2. **Global Small-Fast Model**: A lightweight model for auxiliary plugin operations (query rewriting, classification, etc.)

Both configurations will be **global organization settings** (not per-provider), specifying both the provider and model to use. This provides a unified approach to model configuration while maintaining flexibility.

---

## Motivation

### Global Default Model

Currently, each provider has its own `default_model`, but there's no single organization-wide default. This creates challenges:
- Assistants must specify which provider/model to use
- No clear "organization default" for new assistants
- Difficult to change the primary model across all assistants
- No fallback when an assistant's configured model is unavailable

A **global default model** provides:
1. Single source of truth for organization's primary model
2. Simplified assistant creation (can use org default)
3. Easier organization-wide model changes
4. Clear fallback hierarchy

### Global Small-Fast Model

Many plugins and processors need to make auxiliary LLM calls for tasks such as:
- Query rewriting/expansion in RAG processors
- Content classification and analysis
- Intent detection
- Data extraction and transformation
- Rubric scoring pre-processing
- Prompt validation

These tasks don't require the most powerful models and can benefit from faster, cheaper alternatives. A **dedicated small-fast-model** configuration allows:
1. Cost optimization (can be 98% cheaper)
2. Faster response times for auxiliary operations
3. Clear separation between main completion models and utility models
4. Plugin flexibility in choosing when to use the fast model

### Combined Benefits

Having both global configurations provides:
- **Clarity**: Clear distinction between primary work model and utility model
- **Flexibility**: Can mix providers (e.g., OpenAI for main, Ollama for fast)
- **Simplicity**: One place to configure organization-wide model preferences
- **Efficiency**: Optimize cost and performance per use case

---

## Architecture Overview

### Current State

Organizations currently configure models per-provider:

```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "providers": {
        "openai": {
          "enabled": true,
          "api_key": "sk-...",
          "base_url": "https://api.openai.com/v1",
          "default_model": "gpt-4o",
          "models": ["gpt-4o", "gpt-4o-mini"]
        },
        "ollama": {
          "enabled": true,
          "base_url": "http://localhost:11434",
          "default_model": "llama3.1:latest",
          "models": ["llama3.1:latest", "llama3.2:latest"]
        }
      }
    }
  }
}
```

### Proposed State

Add **two global configurations** at the setup level:

```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "global_default_model": {
        "provider": "openai",
        "model": "gpt-4o"
      },
      "small_fast_model": {
        "provider": "openai",
        "model": "gpt-4o-mini"
      },
      "providers": {
        "openai": {
          "enabled": true,
          "api_key": "sk-...",
          "base_url": "https://api.openai.com/v1",
          "default_model": "gpt-4o",  // Per-provider default (kept for backward compatibility)
          "models": ["gpt-4o", "gpt-4o-mini"]
        },
        "ollama": {
          "enabled": true,
          "base_url": "http://localhost:11434",
          "default_model": "llama3.1:latest",  // Per-provider default (kept for backward compatibility)
          "models": ["llama3.1:latest", "llama3.2:latest"]
        }
      }
    }
  }
}
```

**Key Design Decisions:**
- **Global scope**: Both configurations are global per setup (not per provider)
- **Provider specification**: Explicitly specify which provider to use for each
- **Model specification**: Explicitly specify which model from that provider
- **Flexibility**: Can use different providers for each (e.g., OpenAI for default, Ollama for fast)
- **Per-provider defaults preserved**: Keep existing per-provider `default_model` for backward compatibility and fallback

### Model Resolution Hierarchy

When a completion is requested, the system will resolve the model in this order:

1. **Explicit model specified** in assistant configuration → use that
2. **Global default model** configured → use that
3. **Per-provider default model** → use that (backward compatibility)
4. **First available model** from provider → use that
5. **Error** if none available

For auxiliary plugin operations using small-fast-model:

1. **Global small-fast-model** configured → use that
2. **Global default model** → fallback
3. **Per-provider default** → fallback
4. **Skip operation** or error (plugin-dependent)

---

## Detailed Implementation Plan

### Phase 1: Backend Infrastructure

#### 1.1 Database Schema (JSON Config)

**File:** Organization config JSON structure (stored in `organizations.config` column)

**Changes:**
- Add `global_default_model` object at the setup level
- Add `small_fast_model` object at the setup level
- Both have structure: `{ "provider": string, "model": string }`

**Example:**
```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "name": "Default Setup",
      "global_default_model": {
        "provider": "openai",
        "model": "gpt-4o"
      },
      "small_fast_model": {
        "provider": "openai",
        "model": "gpt-4o-mini"
      },
      "providers": { ... }
    }
  }
}
```

#### 1.2 Environment Variables

**File:** `.env` and documentation

**New Variables:**
```bash
# Global default model for the organization
GLOBAL_DEFAULT_MODEL_PROVIDER=openai    # or ollama, anthropic, etc.
GLOBAL_DEFAULT_MODEL_NAME=gpt-4o        # model name from the provider

# Small fast model for auxiliary plugin operations
SMALL_FAST_MODEL_PROVIDER=openai        # or ollama, anthropic, etc.
SMALL_FAST_MODEL_NAME=gpt-4o-mini       # model name from the provider
```

These will be used to initialize the system organization's global model configurations.

#### 1.3 Database Manager Updates

**File:** `backend/lamb/database_manager.py`

**Method: `_get_default_org_config()`**
```python
def _get_default_org_config(self) -> Dict[str, Any]:
    """Get default configuration for new organizations"""
    return {
        "version": "1.0",
        "setups": {
            "default": {
                "name": "Default Setup",
                "is_default": True,
                "global_default_model": {
                    "provider": "",
                    "model": ""
                },
                "small_fast_model": {
                    "provider": "",
                    "model": ""
                },
                "providers": {},
                "knowledge_base": {}
            }
        },
        # ... rest of config
    }
```

**Method: `sync_system_org_with_env()`**

Add logic to sync both global models from environment variables:

```python
def sync_system_org_with_env(self, org_id: int):
    # ... existing code ...
    
    # Sync global default model from environment
    global_default_provider = os.getenv('GLOBAL_DEFAULT_MODEL_PROVIDER', '').strip()
    global_default_model = os.getenv('GLOBAL_DEFAULT_MODEL_NAME', '').strip()
    
    if global_default_provider and global_default_model:
        if 'default' not in config['setups']:
            config['setups']['default'] = {}
        
        config['setups']['default']['global_default_model'] = {
            "provider": global_default_provider,
            "model": global_default_model
        }
        logger.info(f"Synced global-default-model: {global_default_provider}/{global_default_model}")
    
    # Sync small fast model from environment
    small_fast_provider = os.getenv('SMALL_FAST_MODEL_PROVIDER', '').strip()
    small_fast_model = os.getenv('SMALL_FAST_MODEL_NAME', '').strip()
    
    if small_fast_provider and small_fast_model:
        if 'default' not in config['setups']:
            config['setups']['default'] = {}
        
        config['setups']['default']['small_fast_model'] = {
            "provider": small_fast_provider,
            "model": small_fast_model
        }
        logger.info(f"Synced small-fast-model: {small_fast_provider}/{small_fast_model}")
    
    self.update_organization_config(org_id, config)
```

**Method: `create_organization()`**

Ensure new organizations inherit both global models from system baseline:

```python
def create_organization(self, slug: str, name: str, is_system: bool = False, 
                      config: Dict[str, Any] = None, status: str = "active") -> Optional[int]:
    # ... existing code ...
    
    # Inherit from system organization baseline (includes both global models)
    if config is None:
        config = self.get_system_org_config_as_baseline()
    else:
        # Ensure both global models exist if not provided
        if 'setups' in config and 'default' in config['setups']:
            system_cfg = self.get_system_org_config_as_baseline()
            if 'setups' in system_cfg and 'default' in system_cfg['setups']:
                # Inherit global_default_model
                if 'global_default_model' not in config['setups']['default']:
                    config['setups']['default']['global_default_model'] = system_cfg['setups']['default'].get(
                        'global_default_model', {"provider": "", "model": ""}
                    )
                # Inherit small_fast_model
                if 'small_fast_model' not in config['setups']['default']:
                    config['setups']['default']['small_fast_model'] = system_cfg['setups']['default'].get(
                        'small_fast_model', {"provider": "", "model": ""}
                    )
    
    # ... rest of method
```

#### 1.4 Organization Config Resolver

**File:** `backend/lamb/completions/org_config_resolver.py`

**Add new methods:**

```python
def get_global_default_model_config(self) -> Dict[str, str]:
    """
    Get the global-default-model configuration for this organization
    
    Returns:
        Dict with keys 'provider' and 'model'
        Returns empty dict if not configured
    """
    org_config = self.organization.get('config', {})
    setups = org_config.get('setups', {})
    setup = setups.get(self.setup_name, {})
    global_default_config = setup.get('global_default_model', {})
    
    provider = global_default_config.get('provider', '')
    model = global_default_config.get('model', '')
    
    # If not configured and this is system org, try env vars
    if (not provider or not model) and self.organization.get('is_system', False):
        provider = os.getenv('GLOBAL_DEFAULT_MODEL_PROVIDER', '').strip()
        model = os.getenv('GLOBAL_DEFAULT_MODEL_NAME', '').strip()
    
    return {
        "provider": provider,
        "model": model
    }

def get_small_fast_model_config(self) -> Dict[str, str]:
    """
    Get the small-fast-model configuration for this organization
    
    Returns:
        Dict with keys 'provider' and 'model'
        Returns empty dict if not configured
    """
    org_config = self.organization.get('config', {})
    setups = org_config.get('setups', {})
    setup = setups.get(self.setup_name, {})
    small_fast_config = setup.get('small_fast_model', {})
    
    provider = small_fast_config.get('provider', '')
    model = small_fast_config.get('model', '')
    
    # If not configured and this is system org, try env vars
    if (not provider or not model) and self.organization.get('is_system', False):
        provider = os.getenv('SMALL_FAST_MODEL_PROVIDER', '').strip()
        model = os.getenv('SMALL_FAST_MODEL_NAME', '').strip()
    
    return {
        "provider": provider,
        "model": model
    }

def resolve_model_for_completion(self, requested_model: Optional[str] = None, 
                                 requested_provider: Optional[str] = None) -> Dict[str, str]:
    """
    Resolve which model to use for a completion using the hierarchy:
    1. Explicitly requested model/provider
    2. Global default model
    3. Per-provider default model
    4. First available model from provider
    
    Args:
        requested_model: Explicitly requested model name (optional)
        requested_provider: Explicitly requested provider (optional)
    
    Returns:
        Dict with 'provider' and 'model' keys
    
    Raises:
        ValueError: If no model can be resolved
    """
    # 1. If explicit model and provider requested, use that
    if requested_model and requested_provider:
        # Validate it exists in provider config
        provider_config = self.get_provider_config(requested_provider)
        if provider_config and requested_model in provider_config.get('models', []):
            return {"provider": requested_provider, "model": requested_model}
        else:
            logger.warning(f"Requested model {requested_provider}/{requested_model} not available, falling back")
    
    # 2. Try global default model
    global_default = self.get_global_default_model_config()
    if global_default.get('provider') and global_default.get('model'):
        provider = global_default['provider']
        model = global_default['model']
        provider_config = self.get_provider_config(provider)
        if provider_config and model in provider_config.get('models', []):
            logger.info(f"Using global default model: {provider}/{model}")
            return {"provider": provider, "model": model}
        else:
            logger.warning(f"Global default model {provider}/{model} not available, falling back")
    
    # 3. Try per-provider default (if provider is known)
    if requested_provider:
        provider_config = self.get_provider_config(requested_provider)
        if provider_config:
            default_model = provider_config.get('default_model')
            models = provider_config.get('models', [])
            if default_model and default_model in models:
                logger.info(f"Using provider default model: {requested_provider}/{default_model}")
                return {"provider": requested_provider, "model": default_model}
            elif models:
                model = models[0]
                logger.info(f"Using first available model from provider: {requested_provider}/{model}")
                return {"provider": requested_provider, "model": model}
    
    # 4. Try first available provider and model
    org_config = self.organization.get('config', {})
    setups = org_config.get('setups', {})
    setup = setups.get(self.setup_name, {})
    providers = setup.get('providers', {})
    
    for provider_name, provider_config in providers.items():
        if provider_config.get('enabled', True) and provider_config.get('models'):
            model = provider_config['models'][0]
            logger.info(f"Using first available provider: {provider_name}/{model}")
            return {"provider": provider_name, "model": model}
    
    raise ValueError("No models configured for this organization")
```

#### 1.5 Connector Updates

**Files:** 
- `backend/lamb/completions/connectors/openai.py`
- `backend/lamb/completions/connectors/ollama.py`
- `backend/lamb/completions/connectors/anthropic.py` (if exists)
- `backend/lamb/completions/connectors/google.py` (if exists)

**Changes:** Add optional parameter `use_small_fast_model: bool = False`

**Example for `openai.py`:**

```python
async def llm_connect(
    messages: list, 
    stream: bool = False, 
    body: Dict[str, Any] = None, 
    llm: str = None, 
    assistant_owner: Optional[str] = None,
    use_small_fast_model: bool = False  # NEW PARAMETER
):
    """
    Connect to OpenAI API (organization-aware)
    
    Args:
        messages: List of conversation messages
        stream: Whether to stream the response
        body: Request body with additional parameters
        llm: Specific model to use (overrides defaults)
        assistant_owner: Email of assistant owner for org config
        use_small_fast_model: If True, use organization's small-fast-model instead of default
    """
    
    # ... existing code to get config ...
    
    # NEW: Handle small-fast-model logic
    if use_small_fast_model and assistant_owner:
        try:
            config_resolver = OrganizationConfigResolver(assistant_owner)
            small_fast_config = config_resolver.get_small_fast_model_config()
            
            if small_fast_config.get('provider') == 'openai' and small_fast_config.get('model'):
                llm = small_fast_config['model']
                logger.info(f"Using small-fast-model: {llm}")
                multimodal_logger.info(f"🚀 Using small-fast-model: {llm}")
            else:
                logger.warning("Small-fast-model requested but not configured for OpenAI, using default")
        except Exception as e:
            logger.error(f"Error getting small-fast-model config: {e}")
    
    # ... rest of existing implementation ...
```

**Note:** Similar changes for `ollama.py` and other connectors, checking that the provider matches.

#### 1.6 Helper Utility for Plugins

**File:** `backend/lamb/completions/small_fast_model_helper.py` (NEW)

Create a convenience function for plugins to easily invoke the small-fast-model:

```python
"""
Helper utilities for plugins to invoke the small-fast-model
"""

import logging
from typing import List, Dict, Any, Optional
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = logging.getLogger(__name__)


async def invoke_small_fast_model(
    messages: List[Dict[str, Any]],
    assistant_owner: str,
    stream: bool = False,
    body: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Convenience function for plugins to invoke the organization's small-fast-model
    
    Args:
        messages: List of conversation messages
        assistant_owner: Email of assistant owner (for org resolution)
        stream: Whether to stream the response
        body: Optional request body parameters
    
    Returns:
        LLM response (format depends on connector)
    
    Raises:
        ValueError: If small-fast-model is not configured
        Exception: If the connector fails
    
    Example:
        ```python
        # In a RAG processor
        response = await invoke_small_fast_model(
            messages=[{"role": "user", "content": "Rewrite this query: ..."}],
            assistant_owner=assistant.owner
        )
        ```
    """
    try:
        # Get small-fast-model configuration
        config_resolver = OrganizationConfigResolver(assistant_owner)
        small_fast_config = config_resolver.get_small_fast_model_config()
        
        provider = small_fast_config.get('provider')
        model = small_fast_config.get('model')
        
        if not provider or not model:
            raise ValueError(
                "Small-fast-model is not configured for this organization. "
                "Please configure it in the organization settings."
            )
        
        logger.info(f"Invoking small-fast-model: {provider}/{model}")
        
        # Import and call the appropriate connector
        if provider == 'openai':
            from lamb.completions.connectors import openai
            return await openai.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,  # Explicitly use the small-fast-model
                assistant_owner=assistant_owner,
                use_small_fast_model=False  # Don't trigger the flag since we're explicitly setting llm
            )
        
        elif provider == 'ollama':
            from lamb.completions.connectors import ollama
            return await ollama.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,
                assistant_owner=assistant_owner,
                use_small_fast_model=False
            )
        
        elif provider == 'anthropic':
            from lamb.completions.connectors import anthropic
            return await anthropic.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,
                assistant_owner=assistant_owner,
                use_small_fast_model=False
            )
        
        elif provider == 'google':
            from lamb.completions.connectors import google
            return await google.llm_connect(
                messages=messages,
                stream=stream,
                body=body,
                llm=model,
                assistant_owner=assistant_owner,
                use_small_fast_model=False
            )
        
        else:
            raise ValueError(f"Unsupported provider for small-fast-model: {provider}")
    
    except Exception as e:
        logger.error(f"Error invoking small-fast-model: {e}")
        raise


def get_small_fast_model_info(assistant_owner: str) -> Dict[str, str]:
    """
    Get information about the configured small-fast-model
    
    Args:
        assistant_owner: Email of assistant owner
    
    Returns:
        Dict with 'provider' and 'model' keys
    """
    config_resolver = OrganizationConfigResolver(assistant_owner)
    return config_resolver.get_small_fast_model_config()


def is_small_fast_model_configured(assistant_owner: str) -> bool:
    """
    Check if small-fast-model is configured for the organization
    
    Args:
        assistant_owner: Email of assistant owner
    
    Returns:
        True if configured, False otherwise
    """
    config = get_small_fast_model_info(assistant_owner)
    return bool(config.get('provider') and config.get('model'))
```

---

### Phase 2: API Endpoints

#### 2.1 Organization Router Updates

**File:** `backend/creator_interface/organization_router.py`

**Update Pydantic Model:**

```python
class OrgAdminApiSettings(BaseModel):
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    ollama_base_url: Optional[str] = None
    available_models: Optional[Dict[str, List[str]]] = None
    model_limits: Optional[Dict[str, Dict[str, int]]] = None
    selected_models: Optional[Dict[str, List[str]]] = None
    default_models: Optional[Dict[str, str]] = None  # Per-provider defaults (backward compatibility)
    global_default_model: Optional[Dict[str, str]] = None  # NEW: {"provider": "openai", "model": "gpt-4o"}
    small_fast_model: Optional[Dict[str, str]] = None  # NEW: {"provider": "openai", "model": "gpt-4o-mini"}
```

**Update `get_api_settings()` endpoint:**

Around line 2500, add:

```python
# Get global model configurations
global_default_model = {}
small_fast_model = {}
if 'default' in config.get('setups', {}):
    global_default_model = config['setups']['default'].get('global_default_model', {})
    small_fast_model = config['setups']['default'].get('small_fast_model', {})

return {
    "openai_api_key_set": bool(providers.get('openai', {}).get('api_key')),
    "openai_base_url": providers.get('openai', {}).get('base_url') or config.OPENAI_BASE_URL,
    "ollama_base_url": providers.get('ollama', {}).get('base_url') or config.OLLAMA_BASE_URL,
    "available_models": available_models,
    "selected_models": selected_models,
    "default_models": default_models,  # Per-provider (backward compatibility)
    "global_default_model": global_default_model,  # NEW
    "small_fast_model": small_fast_model,  # NEW
    "api_status": api_status
}
```

**Update `update_api_settings()` endpoint:**

Around line 2600, add:

```python
# Update global-default-model configuration (AFTER per-provider default models section)
if settings.global_default_model is not None:
    provider = settings.global_default_model.get('provider', '')
    model = settings.global_default_model.get('model', '')
    
    # Validate that the provider exists and is enabled
    if provider and model:
        if provider not in providers:
            logger.warning(f"Global-default-model provider '{provider}' not configured, ignoring")
        else:
            # Validate that the model is in the enabled models list
            enabled_models = providers.get(provider, {}).get('models', [])
            if model not in enabled_models:
                logger.warning(f"Global-default-model '{model}' not in enabled models for {provider}, auto-correcting")
                if enabled_models:
                    # Auto-select first enabled model
                    model = enabled_models[0]
                    settings.global_default_model['model'] = model
                    logger.info(f"Auto-corrected global-default-model to '{model}'")
                else:
                    # No models enabled, clear the configuration
                    settings.global_default_model = {"provider": "", "model": ""}
                    logger.warning(f"No models enabled for {provider}, clearing global-default-model")
            
            # Save to config
            if 'default' not in config['setups']:
                config['setups']['default'] = {}
            
            config['setups']['default']['global_default_model'] = {
                "provider": settings.global_default_model.get('provider', ''),
                "model": settings.global_default_model.get('model', '')
            }
            logger.info(f"Updated global-default-model: {settings.global_default_model}")
    else:
        # Clear global-default-model if empty
        if 'default' in config['setups']:
            config['setups']['default']['global_default_model'] = {"provider": "", "model": ""}
        logger.info("Cleared global-default-model configuration")

# Update small-fast-model configuration
if settings.small_fast_model is not None:
    provider = settings.small_fast_model.get('provider', '')
    model = settings.small_fast_model.get('model', '')
    
    # Validate that the provider exists and is enabled
    if provider and model:
        if provider not in providers:
            logger.warning(f"Small-fast-model provider '{provider}' not configured, ignoring")
        else:
            # Validate that the model is in the enabled models list
            enabled_models = providers.get(provider, {}).get('models', [])
            if model not in enabled_models:
                logger.warning(f"Small-fast-model '{model}' not in enabled models for {provider}, auto-correcting")
                if enabled_models:
                    # Auto-select first enabled model
                    model = enabled_models[0]
                    settings.small_fast_model['model'] = model
                    logger.info(f"Auto-corrected small-fast-model to '{model}'")
                else:
                    # No models enabled, clear the configuration
                    settings.small_fast_model = {"provider": "", "model": ""}
                    logger.warning(f"No models enabled for {provider}, clearing small-fast-model")
            
            # Save to config
            if 'default' not in config['setups']:
                config['setups']['default'] = {}
            
            config['setups']['default']['small_fast_model'] = {
                "provider": settings.small_fast_model.get('provider', ''),
                "model": settings.small_fast_model.get('model', '')
            }
            logger.info(f"Updated small-fast-model: {settings.small_fast_model}")
    else:
        # Clear small-fast-model if empty
        if 'default' in config['setups']:
            config['setups']['default']['small_fast_model'] = {"provider": "", "model": ""}
        logger.info("Cleared small-fast-model configuration")

# Save updated configuration
db_manager.update_organization_config(org_id, config)
```

---

### Phase 3: Frontend Implementation

#### 3.1 Organization Admin Page

**File:** `frontend/svelte-app/src/routes/org-admin/+page.svelte`

**Update State (around line 165):**

```javascript
let newApiSettings = $state({
    openai_api_key: '',
    openai_base_url: '',
    ollama_base_url: '',
    available_models: [],
    model_limits: {},
    selected_models: {},
    default_models: {},  // Per-provider defaults (backward compatibility)
    global_default_model: {provider: '', model: ''},  // NEW
    small_fast_model: {provider: '', model: ''}  // NEW
});
```

**Update `fetchApiSettings()` function:**

```javascript
async function fetchApiSettings() {
    // ... existing code ...
    
    const data = await response.json();
    
    newApiSettings = {
        openai_api_key: '',
        openai_base_url: data.openai_base_url || '',
        ollama_base_url: data.ollama_base_url || '',
        available_models: data.available_models || {},
        selected_models: data.selected_models || {},
        default_models: data.default_models || {},  // Per-provider
        global_default_model: data.global_default_model || {provider: '', model: ''},  // NEW
        small_fast_model: data.small_fast_model || {provider: '', model: ''}  // NEW
    };
    
    // ... rest of code ...
}
```

**Update `saveApiSettings()` function:**

```javascript
async function saveApiSettings() {
    // ... existing validation ...
    
    const payload = {
        openai_api_key: newApiSettings.openai_api_key || undefined,
        openai_base_url: newApiSettings.openai_base_url || undefined,
        ollama_base_url: newApiSettings.ollama_base_url || undefined,
        selected_models: newApiSettings.selected_models,
        default_models: newApiSettings.default_models,  // Per-provider
        global_default_model: newApiSettings.global_default_model,  // NEW
        small_fast_model: newApiSettings.small_fast_model  // NEW
    };
    
    // ... rest of save logic ...
}
```

**Add UI Component (after per-provider default models section, around line 2890):**

```svelte
<!-- Global Model Configurations -->
<div class="mt-8 space-y-6">
    <h3 class="text-lg font-semibold text-gray-900 border-b pb-2">
        Global Model Configuration
    </h3>
    <p class="text-sm text-gray-600">
        Configure organization-wide default models that apply across all assistants and operations.
    </p>

    <!-- Global Default Model Configuration -->
    <div class="p-4 bg-indigo-50 border border-indigo-200 rounded-md">
        <h4 class="text-md font-semibold text-indigo-900 mb-3">
            Global Default Model
        </h4>
        <p class="text-sm text-indigo-700 mb-4">
            The primary model for this organization. Used for assistants and completions when 
            no specific model is configured. This overrides per-provider defaults.
        </p>
        
        <div class="grid grid-cols-2 gap-4">
            <!-- Provider Selection -->
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Provider
                </label>
                <select
                    bind:value={newApiSettings.global_default_model.provider}
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    onchange={() => {
                        // Reset model when provider changes
                        newApiSettings.global_default_model.model = '';
                        addPendingChange('Global default model provider changed');
                    }}
                >
                    <option value="">-- None --</option>
                    {#each Object.keys(newApiSettings.selected_models || {}) as providerName}
                        {#if newApiSettings.selected_models[providerName]?.length > 0}
                            <option value={providerName}>{providerName}</option>
                        {/if}
                    {/each}
                </select>
            </div>
            
            <!-- Model Selection -->
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Model
                </label>
                <select
                    bind:value={newApiSettings.global_default_model.model}
                    class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    disabled={!newApiSettings.global_default_model.provider}
                    onchange={() => addPendingChange('Global default model changed')}
                >
                    <option value="">-- Select Model --</option>
                    {#if newApiSettings.global_default_model.provider && newApiSettings.selected_models[newApiSettings.global_default_model.provider]}
                        {#each newApiSettings.selected_models[newApiSettings.global_default_model.provider] as model}
                            <option value={model}>{model}</option>
                        {/each}
                    {/if}
                </select>
            </div>
        </div>
        
        {#if newApiSettings.global_default_model.provider && newApiSettings.global_default_model.model}
            <div class="mt-3 p-2 bg-indigo-100 border border-indigo-300 rounded text-sm text-indigo-900">
                ✓ Global default model configured: 
                <strong>{newApiSettings.global_default_model.provider}/{newApiSettings.global_default_model.model}</strong>
            </div>
        {:else}
            <div class="mt-3 p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">
                ℹ️ No global default model configured. Per-provider defaults will be used.
            </div>
        {/if}
    </div>

    <!-- Small Fast Model Configuration -->
<div class="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
    <h4 class="text-md font-semibold text-blue-900 mb-3">
        Small Fast Model (Optional)
    </h4>
    <p class="text-sm text-blue-700 mb-4">
        Configure a lightweight model for auxiliary plugin operations like query rewriting, 
        classification, and data extraction. This can reduce costs and improve performance 
        for internal processing tasks.
    </p>
    
    <div class="grid grid-cols-2 gap-4">
        <!-- Provider Selection -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
                Provider
            </label>
            <select
                bind:value={newApiSettings.small_fast_model.provider}
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                onchange={() => {
                    // Reset model when provider changes
                    newApiSettings.small_fast_model.model = '';
                    addPendingChange('Small fast model provider changed');
                }}
            >
                <option value="">-- None --</option>
                {#each Object.keys(newApiSettings.selected_models || {}) as providerName}
                    {#if newApiSettings.selected_models[providerName]?.length > 0}
                        <option value={providerName}>{providerName}</option>
                    {/if}
                {/each}
            </select>
        </div>
        
        <!-- Model Selection -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
                Model
            </label>
            <select
                bind:value={newApiSettings.small_fast_model.model}
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={!newApiSettings.small_fast_model.provider}
                onchange={() => addPendingChange('Small fast model changed')}
            >
                <option value="">-- Select Model --</option>
                {#if newApiSettings.small_fast_model.provider && newApiSettings.selected_models[newApiSettings.small_fast_model.provider]}
                    {#each newApiSettings.selected_models[newApiSettings.small_fast_model.provider] as model}
                        <option value={model}>{model}</option>
                    {/each}
                {/if}
            </select>
        </div>
    </div>
    
    {#if newApiSettings.small_fast_model.provider && newApiSettings.small_fast_model.model}
        <div class="mt-3 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-800">
            ✓ Small fast model configured: 
            <strong>{newApiSettings.small_fast_model.provider}/{newApiSettings.small_fast_model.model}</strong>
        </div>
    {:else}
        <div class="mt-3 p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-600">
            ℹ️ No small fast model configured. Plugins will use default models for auxiliary operations.
        </div>
    {/if}
</div>

</div> <!-- End of Global Model Configurations -->
```

---

### Phase 4: Plugin Integration Examples

Each plugin decides when and how to use the small-fast-model. Here are examples:

#### 4.1 RAG Processor Example

**File:** `backend/lamb/completions/rag/simple_rag.py`

**Use Case:** Query rewriting/expansion before KB retrieval

```python
import logging
from typing import Dict, Any, List
from lamb.lamb_classes import Assistant
from lamb.completions.small_fast_model_helper import invoke_small_fast_model, is_small_fast_model_configured

logger = logging.getLogger(__name__)

async def rag_processor(messages: List[Dict[str, Any]], assistant: Assistant = None) -> Dict[str, Any]:
    """
    RAG processor with optional query enhancement using small-fast-model
    """
    logger.info("Using simple_rag processor")
    
    # Extract last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_message = msg.get("content", "")
            break
    
    query = last_user_message
    
    # Optional: Use small-fast-model for query enhancement
    if assistant and is_small_fast_model_configured(assistant.owner):
        try:
            logger.info("Enhancing query with small-fast-model")
            
            enhancement_messages = [{
                "role": "system",
                "content": "You are a query enhancement assistant. Rewrite the user's query to be more specific and search-friendly. Return only the enhanced query, nothing else."
            }, {
                "role": "user",
                "content": f"Original query: {last_user_message}"
            }]
            
            response = await invoke_small_fast_model(
                messages=enhancement_messages,
                assistant_owner=assistant.owner,
                stream=False
            )
            
            # Extract enhanced query from response
            if isinstance(response, dict) and 'choices' in response:
                enhanced_query = response['choices'][0]['message']['content'].strip()
                logger.info(f"Enhanced query: {enhanced_query}")
                query = enhanced_query
        
        except Exception as e:
            logger.warning(f"Failed to enhance query with small-fast-model: {e}, using original")
    
    # Continue with KB retrieval using 'query'
    # ... existing KB retrieval logic ...
```

#### 4.2 Prompt Processor Example

**File:** `backend/lamb/completions/pps/simple_augment.py`

**Use Case:** Content classification before processing

```python
from lamb.completions.small_fast_model_helper import invoke_small_fast_model, is_small_fast_model_configured

def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Prompt processor with optional content analysis using small-fast-model
    """
    
    messages = request.get('messages', [])
    
    # Optional: Use small-fast-model to detect if image generation is requested
    if assistant and is_small_fast_model_configured(assistant.owner):
        last_user_msg = next((m for m in reversed(messages) if m.get('role') == 'user'), None)
        
        if last_user_msg:
            try:
                classification_messages = [{
                    "role": "system",
                    "content": "Analyze if this message requests image generation. Answer only 'yes' or 'no'."
                }, {
                    "role": "user",
                    "content": last_user_msg.get('content', '')
                }]
                
                response = await invoke_small_fast_model(
                    messages=classification_messages,
                    assistant_owner=assistant.owner,
                    stream=False
                )
                
                # Process response to determine if image generation
                # ... use result to modify processing logic ...
            
            except Exception as e:
                logger.warning(f"Classification with small-fast-model failed: {e}")
    
    # Continue with normal processing
    # ... existing augmentation logic ...
```

#### 4.3 Evaluator Example

**File:** `backend/lamb/evaluaitor/rubrics.py`

**Use Case:** Pre-scoring analysis

```python
async def generate_rubric_with_ai(prompt: str, organization_id: int, user_email: str) -> Dict[str, Any]:
    """
    Generate rubric structure using small-fast-model if available
    """
    from lamb.completions.small_fast_model_helper import invoke_small_fast_model, is_small_fast_model_configured
    
    # Check if we should use small-fast-model
    if is_small_fast_model_configured(user_email):
        logger.info("Using small-fast-model for rubric generation")
        
        messages = [{
            "role": "system",
            "content": "You are a rubric generation assistant. Create a structured rubric based on the prompt."
        }, {
            "role": "user",
            "content": prompt
        }]
        
        response = await invoke_small_fast_model(
            messages=messages,
            assistant_owner=user_email,
            stream=False
        )
        
        # Process response into rubric structure
        # ...
    else:
        # Fall back to default model or other logic
        # ...
```

---

## Migration and Backward Compatibility

### Existing Organizations

**No breaking changes:**
- Organizations without `small_fast_model` configured will continue to work
- Plugins check if small-fast-model is configured before using it
- Default behavior: use existing default_model logic

### System Organization

**Initial Setup:**
1. Set environment variables:
   ```bash
   # Global default model
   GLOBAL_DEFAULT_MODEL_PROVIDER=openai
   GLOBAL_DEFAULT_MODEL_NAME=gpt-4o
   
   # Small fast model
   SMALL_FAST_MODEL_PROVIDER=openai
   SMALL_FAST_MODEL_NAME=gpt-4o-mini
   ```

2. Run system org sync:
   ```bash
   curl -X POST 'http://localhost:8000/lamb/v1/organizations/system/sync' \
     -H 'Authorization: Bearer <system_admin_token>'
   ```

### New Organizations

**Automatic inheritance:**
- New organizations created via admin panel will inherit both global models from system org
- Can be customized per-organization in org-admin settings
- If not customized, will continue to use system org values

---

## Validation Rules

### Backend Validation

**For both global_default_model and small_fast_model:**

1. **Provider must exist**: The specified provider must be configured in the organization
2. **Provider must be enabled**: The provider must have `enabled: true`
3. **Model must be in enabled list**: The model must be in the provider's `models` array
4. **Auto-correction**: If validation fails, auto-correct to first available model or clear config
5. **Independence**: global_default_model and small_fast_model are independent (can use different providers)

### Frontend Validation

1. **Provider dropdown**: Only show providers that have enabled models
2. **Model dropdown**: Only show models from the selected provider's enabled list
3. **Disabled state**: Disable model dropdown if no provider selected
4. **Visual feedback**: Show green checkmark when configured, gray info when not configured

---

## Testing Strategy

### Backend Tests

**Unit Tests:**
```python
# test_org_config_resolver.py
def test_get_global_default_model_config():
    # Test with configured global-default-model
    # Test with empty configuration
    # Test with system org fallback to env vars
    pass

def test_get_small_fast_model_config():
    # Test with configured small-fast-model
    # Test with empty configuration
    # Test with system org fallback to env vars
    pass

def test_resolve_model_for_completion():
    # Test hierarchy: explicit > global default > provider default > first available
    # Test with various configurations
    pass

def test_global_model_validation():
    # Test that model must be in enabled list
    # Test auto-correction behavior
    # Test independence of global_default and small_fast models
    pass
```

**Integration Tests:**
```python
# test_small_fast_model_integration.py
async def test_invoke_small_fast_model():
    # Test successful invocation
    # Test with different providers
    # Test error handling
    pass

async def test_plugin_uses_small_fast_model():
    # Test RAG processor with small-fast-model
    # Test fallback when not configured
    pass
```

### Frontend Tests

**Playwright Tests:**
```javascript
// test_org_admin_global_models.js
test('configure global default model', async ({ page }) => {
  // Navigate to org admin
  // Select provider
  // Select model
  // Save settings
  // Verify saved correctly
});

test('configure small fast model', async ({ page }) => {
  // Navigate to org admin
  // Select provider (can be different from global default)
  // Select model
  // Save settings
  // Verify saved correctly
});

test('global models validation', async ({ page }) => {
  // Test model dropdown disabled without provider
  // Test only enabled models shown
  // Test both models can use different providers
});

test('global models independence', async ({ page }) => {
  // Configure global default with OpenAI
  // Configure small fast with Ollama
  // Verify both saved correctly
});
```

### Manual Testing Checklist

- [ ] System org sync populates both global models from env vars
- [ ] New organization inherits both global models from system org
- [ ] Org admin UI displays both model configurations
- [ ] Can configure global-default-model and small-fast-model independently
- [ ] Can use different providers for each global model
- [ ] Validation prevents selecting disabled models
- [ ] Backend API endpoint saves and returns both configurations correctly
- [ ] Completion uses global-default-model when no explicit model specified
- [ ] Completion falls back correctly through the hierarchy
- [ ] Plugin can successfully invoke small-fast-model
- [ ] Plugin gracefully handles missing small-fast-model config
- [ ] Different providers (OpenAI, Ollama, mixed) work correctly
- [ ] Error messages are clear and helpful

---

## Documentation Requirements

### For Administrators

**Location:** `Documentation/admin_guide.md` (or similar)

**Content:**
- What are global-default-model and small-fast-model
- When to use each
- How to configure them in org-admin settings
- Recommended models for different scenarios
- Cost implications
- How model resolution works (hierarchy)

### For Plugin Developers

**Location:** `Documentation/plugin_development_guide.md` (or similar)

**Content:**
- When to use small-fast-model vs global-default-model
- How to check if models are configured
- How to invoke small-fast-model using helper function
- How to use global-default-model in completions
- Example code snippets
- Error handling best practices
- Performance considerations
- Model resolution hierarchy

### API Documentation

**Location:** API endpoint documentation (Swagger/OpenAPI)

**Content:**
- Document `global_default_model` and `small_fast_model` fields in API settings endpoints
- Request/response examples
- Validation rules
- Model resolution logic

---

## Performance and Cost Considerations

### Performance Benefits

- **Faster auxiliary operations**: Small models typically have lower latency
- **Reduced main model load**: Offload simple tasks to fast model
- **Better throughput**: More requests can be processed in parallel

### Cost Optimization

**Example Cost Comparison:**
- GPT-4: $10/1M input tokens, $30/1M output tokens
- GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens
- **Savings**: ~98% for auxiliary operations

**Calculation Example:**
- 1000 queries/day with query rewriting (avg 100 tokens input, 50 tokens output)
- Using GPT-4: (100 * $10 + 50 * $30) / 1M * 1000 = $2.50/day
- Using GPT-4o-mini: (100 * $0.15 + 50 * $0.60) / 1M * 1000 = $0.045/day
- **Monthly savings**: ~$73

### Monitoring

Consider adding metrics:
- Count of small-fast-model invocations
- Average latency comparison
- Cost tracking per model type
- Error rates

---

## Security Considerations

### API Key Security

- Small-fast-model uses same provider credentials as main model
- No additional security concerns beyond existing provider configuration
- Credentials stored in organization config (already encrypted/secured)

### Model Capability Restrictions

- Small models may have different capabilities (no vision, limited context)
- Plugins should handle capability mismatches gracefully
- Consider adding capability checking before invocation

### Rate Limiting

- Small-fast-model shares rate limits with provider
- Monitor usage to avoid hitting limits
- Consider separate rate limit tracking for fast model

---

## Future Enhancements

### Phase 5: Advanced Features (Future)

1. **Multiple Fast Models**:
   - Different fast models for different tasks (classification, extraction, rewriting)
   - Task-specific model selection

2. **Automatic Model Selection**:
   - AI-driven model selection based on task complexity
   - Cost/performance optimization engine

3. **Usage Analytics**:
   - Dashboard showing small-fast-model vs default model usage
   - Cost savings calculator
   - Performance metrics

4. **Model Fallback Chain**:
   - Primary model → small-fast-model → default model
   - Intelligent fallback based on error types

5. **Per-Assistant Override**:
   - Allow individual assistants to override organization's small-fast-model
   - Use case: specific assistants need different fast models

---

## Implementation Timeline

### Week 1: Backend Foundation
- [ ] Update database manager with both global model structures
- [ ] Add environment variable support for both models
- [ ] Implement org config resolver methods (get_global_default, get_small_fast, resolve_model)
- [ ] Update connector signatures and model resolution logic

### Week 2: Backend Integration
- [ ] Create small-fast-model helper utility
- [ ] Update API endpoints (get/update settings) for both models
- [ ] Add validation logic for both models
- [ ] Implement model resolution hierarchy in completions
- [ ] Write unit tests

### Week 3: Frontend Implementation
- [ ] Update org-admin page with UI components for both models
- [ ] Implement state management for both configurations
- [ ] Add validation and error handling
- [ ] Add visual distinction between the two model types
- [ ] Manual UI testing

### Week 4: Plugin Integration & Testing
- [ ] Update completion pipeline to use global-default-model
- [ ] Update 1-2 example plugins to use small-fast-model
- [ ] Integration testing (test model resolution hierarchy)
- [ ] Performance testing
- [ ] Documentation writing

### Week 5: Polish & Deploy
- [ ] Bug fixes
- [ ] Additional documentation (admin guide, developer guide)
- [ ] Deployment preparation
- [ ] Migration guide for existing organizations

---

## Success Criteria

### Functional Requirements
✅ Organization admins can configure both global models via UI  
✅ Both configurations are independent (can use different providers)  
✅ Configuration is validated and saved correctly  
✅ Completions use global-default-model when no explicit model specified  
✅ Model resolution hierarchy works correctly  
✅ Plugins can invoke small-fast-model using helper function  
✅ Graceful fallback when not configured  
✅ System org syncs both models from environment variables  

### Non-Functional Requirements
✅ No breaking changes to existing functionality  
✅ Clear error messages and logging  
✅ Performance improvement for auxiliary operations  
✅ Cost reduction measurable  
✅ Comprehensive documentation  

---

## Questions and Answers

### Q: What's the difference between global-default-model and per-provider default_model?
**A:** The global-default-model is organization-wide and takes precedence over per-provider defaults. It's the "primary model" for the organization. Per-provider defaults are kept for backward compatibility and as fallbacks.

### Q: Can I use different providers for global-default-model and small-fast-model?
**A:** Yes! For example, you could use OpenAI's GPT-4o as your global default and Ollama's Llama 3.2 as your small-fast-model. They are completely independent.

### Q: What happens if small-fast-model provider is different from the assistant's connector?
**A:** No problem. The small-fast-model is invoked independently for auxiliary tasks. The assistant uses its configured model for main completions, and plugins call the small-fast-model separately for internal operations.

### Q: When would a completion use the global-default-model?
**A:** When:
1. An assistant doesn't have a specific model configured in its metadata
2. An assistant's configured model is not available
3. A new assistant is created without specifying a model
4. An API call doesn't specify a model

### Q: What if a plugin tries to use small-fast-model but it's not configured?
**A:** The plugin should check with `is_small_fast_model_configured()` first. If not configured, the plugin should gracefully fall back to its default behavior, skip the auxiliary operation, or use the global-default-model.

### Q: Can different assistants have different global models?
**A:** In Phase 1, no. All assistants in an organization share the same global models. However, individual assistants can still specify their own models in their metadata, which takes precedence. Per-assistant overrides could be added in a future enhancement.

### Q: How do I know which model will be used for a completion?
**A:** Follow the hierarchy:
1. Explicit model in assistant metadata → that model
2. Global default model configured → that model
3. Per-provider default model → that model
4. First available model from provider → that model

Logging at INFO level will show which model is selected and why.

### Q: Will this work with custom/local models?
**A:** Yes! As long as the provider (Ollama, etc.) is configured and the model is in the enabled list, it will work for both global models.

---

## Appendix A: Configuration Schema

### Complete Setup Configuration with Small-Fast-Model

```json
{
  "version": "1.0",
  "setups": {
    "default": {
      "name": "Default Setup",
      "is_default": true,
      "global_default_model": {
        "provider": "openai",
        "model": "gpt-4o"
      },
      "small_fast_model": {
        "provider": "openai",
        "model": "gpt-4o-mini"
      },
      "providers": {
        "openai": {
          "enabled": true,
          "api_key": "sk-...",
          "base_url": "https://api.openai.com/v1",
          "default_model": "gpt-4o",
          "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
        },
        "ollama": {
          "enabled": true,
          "base_url": "http://localhost:11434",
          "default_model": "llama3.1:latest",
          "models": ["llama3.1:latest", "llama3.2:latest", "mistral:latest"]
        },
        "anthropic": {
          "enabled": false,
          "api_key": "",
          "default_model": "claude-3-5-sonnet-20241022",
          "models": []
        }
      },
      "knowledge_base": {
        "server_url": "http://localhost:9090",
        "api_token": "kb-api-key"
      }
    }
  },
  "assistant_defaults": {
    "prompt_template": "User: {user_message}\nAssistant:",
    "system_prompt": "You are a helpful educational assistant.",
    "connector": "openai",
    "llm": "gpt-4o"
  },
  "features": {
    "rag_enabled": true,
    "mcp_enabled": true,
    "lti_publishing": true,
    "signup_enabled": false,
    "sharing_enabled": true
  },
  "limits": {
    "usage": {
      "tokens_per_month": 1000000,
      "max_assistants": 100,
      "max_assistants_per_user": 10,
      "storage_gb": 10
    }
  }
}
```

---

## Appendix B: Environment Variables

### Complete List of Environment Variables

```bash
# Existing variables
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
OPENAI_MODELS=gpt-4o,gpt-4o-mini,gpt-3.5-turbo

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:latest

# NEW: Global Default Model Configuration
GLOBAL_DEFAULT_MODEL_PROVIDER=openai
GLOBAL_DEFAULT_MODEL_NAME=gpt-4o

# NEW: Small Fast Model Configuration
SMALL_FAST_MODEL_PROVIDER=openai
SMALL_FAST_MODEL_NAME=gpt-4o-mini

# Alternative example - mixing providers
# GLOBAL_DEFAULT_MODEL_PROVIDER=openai
# GLOBAL_DEFAULT_MODEL_NAME=gpt-4o
# SMALL_FAST_MODEL_PROVIDER=ollama
# SMALL_FAST_MODEL_NAME=llama3.2:latest
```

---

## Appendix C: Example Plugin Usage Patterns

### Pattern 1: Optional Enhancement

```python
# Use small-fast-model if available, otherwise continue normally
if is_small_fast_model_configured(assistant.owner):
    try:
        enhanced_data = await invoke_small_fast_model(...)
        # Use enhanced data
    except Exception as e:
        logger.warning(f"Enhancement failed: {e}, continuing with original")
        # Use original data
else:
    # Use original data
```

### Pattern 2: Required Enhancement

```python
# Small-fast-model is required for this operation
if not is_small_fast_model_configured(assistant.owner):
    raise ValueError("This plugin requires small-fast-model to be configured")

result = await invoke_small_fast_model(...)
```

### Pattern 3: Fallback to Default Model

```python
# Try small-fast-model, fall back to default model
try:
    result = await invoke_small_fast_model(...)
except Exception as e:
    logger.warning(f"Small-fast-model failed: {e}, using default model")
    # Use regular connector with default model
    result = await connector.llm_connect(...)
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-16 | System | Initial implementation plan (small-fast-model only) |
| 2.0 | 2025-12-16 | System | Added global-default-model configuration |

---

**End of Document**

