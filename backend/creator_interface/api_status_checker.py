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
        Check OpenAI API connectivity and fetch available models
        
        Args:
            config: OpenAI configuration
            
        Returns:
            Status information for OpenAI
        """
        api_key = config.get("api_key")
        import config as app_config
        base_url = config.get("base_url") or app_config.OPENAI_BASE_URL
        
        if not api_key:
            return {
                "provider": "openai",
                "status": "not_configured",
                "error": "No API key configured",
                "models": []
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                # First, get the list of available models
                models = []
                try:
                    async with session.get(
                        f"{base_url}/models",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as models_response:
                        if models_response.status == 200:
                            data = await models_response.json()
                            models = [model["id"] for model in data.get("data", [])]
                except Exception as e:
                    logger.warning(f"Failed to fetch models list: {e}")
                
                # Now test streaming capability with a simple request
                headers["Accept"] = "text/event-stream"
                test_payload = {
                    "model": config.get("default_model", "gpt-3.5-turbo"),
                    "messages": [
                        {
                            "role": "user",
                            "content": "Hi"
                        }
                    ],
                    "stream": True
                }
                
                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=test_payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        # Successfully initiated stream
                        return {
                            "provider": "openai",
                            "status": "working",
                            "models": models,
                            "model_count": len(models),
                            "api_base": base_url,
                            "streaming": "enabled"
                        }
                    else:
                        error_text = await response.text()
                        try:
                            error_json = await response.json()
                            error_code = error_json.get("error", {}).get("code")
                            error_message = error_json.get("error", {}).get("message", error_text)
                            
                            # Check for the specific streaming verification error
                            if error_code == "unsupported_value" and "stream" in error_json.get("error", {}).get("param", ""):
                                return {
                                    "provider": "openai",
                                    "status": "error",
                                    "error": "Organization not verified for streaming",
                                    "error_details": error_message,
                                    "models": models,
                                    "model_count": len(models),
                                    "api_base": base_url,
                                    "streaming": "disabled"
                                }
                        except:
                            pass
                        
                        return {
                            "provider": "openai",
                            "status": "error",
                            "error": f"HTTP {response.status}: {error_text}",
                            "models": models,
                            "model_count": len(models),
                            "api_base": base_url
                        }
                        
        except asyncio.TimeoutError:
            return {
                "provider": "openai",
                "status": "error",
                "error": "Connection timeout",
                "models": [],
                "api_base": base_url
            }
        except Exception as e:
            return {
                "provider": "openai",
                "status": "error",
                "error": str(e),
                "models": [],
                "api_base": base_url
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