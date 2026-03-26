"""
API Status Checker for Organization Dashboard

This module provides functionality to test API connectivity and fetch available models
for different providers (OpenAI, Ollama) to show detailed configuration status.
"""

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = logging.getLogger(__name__)


class APIStatusChecker:
    """Check API connectivity and fetch available models for different providers"""
    
    def __init__(self, organization_config: Dict[str, Any]):
        """
        Initialize with organization configuration
        
        Args:
            organization_config: Organization configuration dictionary
        """
        self.config = organization_config
        
    async def check_all_apis(self) -> Dict[str, Any]:
        """
        Check all configured APIs and return detailed status
        
        Returns:
            Dict with status for each provider
        """
        results = {
            "overall_status": "unknown",
            "providers": {},
            "summary": {
                "configured_count": 0,
                "working_count": 0,
                "total_models": 0
            }
        }
        
        # Get provider configurations
        setups = self.config.get("setups", {})
        default_setup = setups.get("default", {})
        providers = default_setup.get("providers", {})
        
        # Check each provider
        check_tasks = []
        
        if "openai" in providers:
            results["summary"]["configured_count"] += 1
            check_tasks.append(self._check_openai(providers["openai"]))
        
        if "ollama" in providers:
            results["summary"]["configured_count"] += 1
            check_tasks.append(self._check_ollama(providers["ollama"]))
        
        # Run all checks concurrently
        if check_tasks:
            provider_results = await asyncio.gather(*check_tasks, return_exceptions=True)
            
            for result in provider_results:
                if isinstance(result, Exception):
                    logger.error(f"API check failed with exception: {result}")
                    continue
                    
                if result:
                    provider_name = result["provider"]
                    results["providers"][provider_name] = result
                    
                    if result["status"] == "working":
                        results["summary"]["working_count"] += 1
                        results["summary"]["total_models"] += len(result.get("models", []))
        
        # Determine overall status
        if results["summary"]["configured_count"] == 0:
            results["overall_status"] = "not_configured"
        elif results["summary"]["working_count"] == 0:
            results["overall_status"] = "error"
        elif results["summary"]["working_count"] == results["summary"]["configured_count"]:
            results["overall_status"] = "working"
        else:
            results["overall_status"] = "partial"
            
        return results
    
    async def _check_openai(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check OpenAI-compatible API connectivity and fetch available models.
        
        Works with OpenAI, OpenRouter, and other OpenAI-compatible providers.
        
        Flow:
        1. Fetch models list from /models endpoint
        2. Check if configured default_model exists in available models
        3. Test completion with default model
        4. Return detailed status with actionable error messages
        
        Args:
            config: OpenAI provider configuration
            
        Returns:
            Status information for the provider
        """
        api_key = config.get("api_key")
        import config as app_config
        base_url = config.get("base_url") or app_config.OPENAI_BASE_URL
        default_model = config.get("default_model")
        
        if not api_key:
            return {
                "provider": "openai",
                "status": "not_configured",
                "error": "No API key configured",
                "models": [],
                "default_model_valid": False,
                "needs_model_selection": False
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                # Step 1: Fetch available models from /models endpoint
                models = []
                models_fetch_error = None
                try:
                    async with session.get(
                        f"{base_url}/models",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as models_response:
                        if models_response.status == 200:
                            data = await models_response.json()
                            models = [model["id"] for model in data.get("data", [])]
                        elif models_response.status == 401:
                            # API key is invalid
                            return {
                                "provider": "openai",
                                "status": "error",
                                "error": "Invalid API key. Please check your API key and try again.",
                                "error_code": "invalid_api_key",
                                "models": [],
                                "api_base": base_url,
                                "default_model_valid": False,
                                "needs_model_selection": False
                            }
                        elif models_response.status == 403:
                            # API key doesn't have permission
                            return {
                                "provider": "openai",
                                "status": "error",
                                "error": "API key does not have permission to access models. Check your API key permissions.",
                                "error_code": "forbidden",
                                "models": [],
                                "api_base": base_url,
                                "default_model_valid": False,
                                "needs_model_selection": False
                            }
                        else:
                            error_text = await models_response.text()
                            models_fetch_error = f"HTTP {models_response.status}: {error_text[:200]}"
                except asyncio.TimeoutError:
                    return {
                        "provider": "openai",
                        "status": "error",
                        "error": f"Connection timeout while fetching models. Service at {base_url} may be down or unreachable.",
                        "error_code": "timeout",
                        "models": [],
                        "api_base": base_url,
                        "default_model_valid": False,
                        "needs_model_selection": False
                    }
                except aiohttp.ClientError as e:
                    return {
                        "provider": "openai",
                        "status": "error",
                        "error": f"Connection error: {str(e)}. Service at {base_url} may be down or unreachable.",
                        "error_code": "connection_error",
                        "models": [],
                        "api_base": base_url,
                        "default_model_valid": False,
                        "needs_model_selection": False
                    }
                
                # If models fetch failed but didn't return early, report the error
                if models_fetch_error and not models:
                    return {
                        "provider": "openai",
                        "status": "error",
                        "error": f"Failed to fetch models list: {models_fetch_error}",
                        "error_code": "models_fetch_failed",
                        "models": [],
                        "api_base": base_url,
                        "default_model_valid": False,
                        "needs_model_selection": False
                    }
                
                # Step 2: Check if default model is in the available models list
                default_model_valid = default_model and default_model in models
                needs_model_selection = bool(models) and default_model and default_model not in models
                
                # If no default model configured but we have models, that's okay
                if not default_model and models:
                    return {
                        "provider": "openai",
                        "status": "working",
                        "models": models,
                        "model_count": len(models),
                        "api_base": base_url,
                        "default_model_valid": False,
                        "needs_model_selection": True,
                        "warning": "No default model configured. Please select a default model from the available models."
                    }
                
                # If default model is not in the list, report it but still show as partially working
                if needs_model_selection:
                    return {
                        "provider": "openai",
                        "status": "working",
                        "models": models,
                        "model_count": len(models),
                        "api_base": base_url,
                        "default_model_valid": False,
                        "needs_model_selection": True,
                        "warning": f"Default model '{default_model}' is not available. Please select a different default model.",
                        "configured_default_model": default_model
                    }
                
                # Step 3: Test with the default model
                if default_model:
                    headers["Accept"] = "text/event-stream"
                    test_payload = {
                        "model": default_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": "Hi"
                            }
                        ],
                        "stream": True
                    }
                    
                    try:
                        async with session.post(
                            f"{base_url}/chat/completions",
                            headers=headers,
                            json=test_payload,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as response:
                            
                            if response.status == 200:
                                # Successfully initiated stream - everything is working
                                return {
                                    "provider": "openai",
                                    "status": "working",
                                    "models": models,
                                    "model_count": len(models),
                                    "api_base": base_url,
                                    "streaming": "enabled",
                                    "default_model_valid": True,
                                    "needs_model_selection": False,
                                    "tested_model": default_model
                                }
                            else:
                                error_text = await response.text()
                                error_message = error_text
                                error_code = None
                                
                                try:
                                    error_json = await response.json()
                                    error_code = error_json.get("error", {}).get("code")
                                    error_message = error_json.get("error", {}).get("message", error_text)
                                except:
                                    pass
                                
                                # Model is in the list but test failed - something else is wrong
                                if default_model_valid:
                                    # Check for specific error types
                                    if error_code == "unsupported_value" and "stream" in str(error_message).lower():
                                        return {
                                            "provider": "openai",
                                            "status": "working",
                                            "models": models,
                                            "model_count": len(models),
                                            "api_base": base_url,
                                            "streaming": "disabled",
                                            "default_model_valid": True,
                                            "needs_model_selection": False,
                                            "warning": "Streaming is not available. Non-streaming requests will work."
                                        }
                                    elif response.status == 429:
                                        return {
                                            "provider": "openai",
                                            "status": "working",
                                            "models": models,
                                            "model_count": len(models),
                                            "api_base": base_url,
                                            "default_model_valid": True,
                                            "needs_model_selection": False,
                                            "warning": "Rate limited. The API is accessible but you've hit usage limits."
                                        }
                                    elif response.status == 402:
                                        return {
                                            "provider": "openai",
                                            "status": "error",
                                            "error": "Payment required. Please check your billing status with the provider.",
                                            "error_code": "payment_required",
                                            "models": models,
                                            "model_count": len(models),
                                            "api_base": base_url,
                                            "default_model_valid": True,
                                            "needs_model_selection": False
                                        }
                                    else:
                                        return {
                                            "provider": "openai",
                                            "status": "error",
                                            "error": f"Model test failed: {error_message[:200]}",
                                            "error_code": error_code or "test_failed",
                                            "models": models,
                                            "model_count": len(models),
                                            "api_base": base_url,
                                            "default_model_valid": True,
                                            "needs_model_selection": False,
                                            "tested_model": default_model
                                        }
                                else:
                                    # Model not in list and test failed - user needs to select a valid model
                                    return {
                                        "provider": "openai",
                                        "status": "working",
                                        "models": models,
                                        "model_count": len(models),
                                        "api_base": base_url,
                                        "default_model_valid": False,
                                        "needs_model_selection": True,
                                        "warning": f"Default model '{default_model}' is not available or invalid. Please select a different default model.",
                                        "configured_default_model": default_model
                                    }
                    except asyncio.TimeoutError:
                        # Test timed out, but models list worked - partial functionality
                        return {
                            "provider": "openai",
                            "status": "working",
                            "models": models,
                            "model_count": len(models),
                            "api_base": base_url,
                            "default_model_valid": default_model_valid,
                            "needs_model_selection": not default_model_valid,
                            "warning": "Completion test timed out, but models list is available."
                        }
                
                # No default model to test, but we have models - provider is accessible
                return {
                    "provider": "openai",
                    "status": "working",
                    "models": models,
                    "model_count": len(models),
                    "api_base": base_url,
                    "default_model_valid": False,
                    "needs_model_selection": True,
                    "warning": "No default model configured. Please select a default model."
                }
                        
        except asyncio.TimeoutError:
            return {
                "provider": "openai",
                "status": "error",
                "error": f"Connection timeout. Service at {base_url} may be down or unreachable.",
                "error_code": "timeout",
                "models": [],
                "api_base": base_url,
                "default_model_valid": False,
                "needs_model_selection": False
            }
        except Exception as e:
            return {
                "provider": "openai",
                "status": "error",
                "error": f"Connection error: {str(e)}",
                "error_code": "connection_error",
                "models": [],
                "api_base": base_url,
                "default_model_valid": False,
                "needs_model_selection": False
            }
    
    async def _check_ollama(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check Ollama API connectivity and fetch available models
        
        Args:
            config: Ollama configuration
            
        Returns:
            Status information for Ollama
        """
        base_url = config.get("base_url")
        
        if not base_url:
            return {
                "provider": "ollama",
                "status": "not_configured",
                "error": "No base URL configured",
                "models": []
            }
        
        try:
            # Test API connectivity by listing models
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        models = [model["name"] for model in data.get("models", [])]
                        
                        return {
                            "provider": "ollama",
                            "status": "working",
                            "models": models,
                            "model_count": len(models),
                            "api_base": base_url
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "provider": "ollama",
                            "status": "error",
                            "error": f"HTTP {response.status}: {error_text}",
                            "models": [],
                            "api_base": base_url
                        }
                        
        except asyncio.TimeoutError:
            return {
                "provider": "ollama",
                "status": "error",
                "error": "Connection timeout",
                "models": [],
                "api_base": base_url
            }
        except Exception as e:
            return {
                "provider": "ollama",
                "status": "error",
                "error": str(e),
                "models": [],
                "api_base": base_url
            }


async def check_organization_api_status(organization_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to check API status for an organization
    
    Args:
        organization_config: Organization configuration dictionary
        
    Returns:
        API status results
    """
    checker = APIStatusChecker(organization_config)
    return await checker.check_all_apis()