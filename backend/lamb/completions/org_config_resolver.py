"""
Organization Configuration Resolver for LAMB

This module provides organization-aware configuration resolution for LLM providers.
It handles the hierarchy of configuration sources and provides fallback to environment
variables for backward compatibility with the system organization.
"""

import os
import logging
from typing import Dict, Any, Optional
from lamb.database_manager import LambDatabaseManager
import config

logger = logging.getLogger(__name__)


class OrganizationConfigResolver:
    """Resolves configuration for providers based on organization context"""
    
    def __init__(self, assistant_owner: str, setup_name: str = "default"):
        """
        Initialize the configuration resolver
        
        Args:
            assistant_owner: The email of the assistant owner to get organization from
            setup_name: The setup name to use (default: "default")
        """
        self.assistant_owner = assistant_owner
        self.setup_name = setup_name
        self.db_manager = LambDatabaseManager()
        self._org = None
        self._config_cache = {}
        
    @property
    def organization(self):
        """Lazy load organization data from assistant owner"""
        if self._org is None:
            # Get user by email to find their organization
            user = self.db_manager.get_creator_user_by_email(self.assistant_owner)
            if not user:
                logger.error(f"User {self.assistant_owner} not found")
                raise ValueError(f"User {self.assistant_owner} not found")
            
            # Get organization from user (user is a dict, not an object)
            org_id = user.get('organization_id') if isinstance(user, dict) else getattr(user, 'organization_id', None)
            if not org_id:
                logger.error(f"No organization_id for user {self.assistant_owner}")
                raise ValueError(f"No organization found for user {self.assistant_owner}")
            
            self._org = self.db_manager.get_organization_by_id(org_id)
            if not self._org:
                logger.error(f"Organization {org_id} not found for user {self.assistant_owner}")
                raise ValueError(f"Organization {org_id} not found for user {self.assistant_owner}")
        return self._org
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get provider configuration with fallback hierarchy
        
        Args:
            provider: Provider name (e.g., "openai", "ollama")
            
        Returns:
            Dict containing provider configuration
        """
        cache_key = f"{provider}_{self.setup_name}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
            
        # Try to get from organization config (organization is a dict)
        org_config = self.organization.get('config', {})
        setups = org_config.get('setups', {})
        setup = setups.get(self.setup_name, {})
        providers = setup.get('providers', {})
        config = providers.get(provider, {})
        
        # If not found and this is the system organization, fallback to env vars
        if not config and self.organization.get('is_system', False):
            logger.info(f"Falling back to environment variables for {provider}")
            config = self._load_from_env(provider)
            
        # Cache the result
        if config:
            self._config_cache[cache_key] = config
            
        return config or {}
    
    def get_knowledge_base_config(self) -> Dict[str, Any]:
        """Get knowledge base configuration"""
        org_config = self.organization.get('config', {})
        setups = org_config.get('setups', {})
        setup = setups.get(self.setup_name, {})
        kb_config = setup.get("knowledge_base", {})
        
        # Fallback to env vars for system org
        if not kb_config and self.organization.get('is_system', False):
            kb_config = {
                "server_url": os.getenv('LAMB_KB_SERVER') or (config.OWI_BASE_URL.replace(':8080', ':9090') if hasattr(config, 'OWI_BASE_URL') else None),
                "api_token": os.getenv('LAMB_KB_SERVER_TOKEN') or config.LAMB_BEARER_TOKEN
            }
            
        return kb_config
    
    def get_feature_flag(self, feature: str) -> bool:
        """Get feature flag value"""
        org_config = self.organization.get('config', {})
        features = org_config.get("features", {})
        return features.get(feature, False)
    
    def _load_from_env(self, provider: str) -> Dict[str, Any]:
        """Load provider configuration from environment variables"""
        if provider == "openai":
            return self._load_openai_from_env()
        elif provider == "ollama":
            return self._load_ollama_from_env()
        elif provider == "google":
            return self._load_google_from_env()
        elif provider == "llm":
            return self._load_llm_from_env()
        else:
            return {}
    
    def _load_openai_from_env(self) -> Dict[str, Any]:
        """Load OpenAI configuration from environment variables"""
        provider_config = {}
        
        if os.getenv("OPENAI_API_KEY"):
            provider_config["api_key"] = os.getenv("OPENAI_API_KEY")
            provider_config["base_url"] = os.getenv("OPENAI_BASE_URL") or config.OPENAI_BASE_URL
            
            # Handle models
            models_str = os.getenv("OPENAI_MODELS", "")
            if models_str:
                provider_config["models"] = [m.strip() for m in models_str.split(",") if m.strip()]
            else:
                provider_config["models"] = [os.getenv("OPENAI_MODEL") or config.OPENAI_MODEL]
                
            provider_config["default_model"] = os.getenv("OPENAI_MODEL") or config.OPENAI_MODEL
            provider_config["enabled"] = os.getenv("OPENAI_ENABLED", "true").lower() == "true"
            
        return provider_config
    
    def _load_ollama_from_env(self) -> Dict[str, Any]:
        """Load Ollama configuration from environment variables"""
        config = {}
        
        if os.getenv("OLLAMA_BASE_URL"):
            config["base_url"] = os.getenv("OLLAMA_BASE_URL")
            config["models"] = [os.getenv("OLLAMA_MODEL", "llama3.1")]
            config["enabled"] = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
            
        return config
    
    def _load_llm_from_env(self) -> Dict[str, Any]:
        """Load LLM CLI configuration from environment variables"""
        config = {}

        config["default_model"] = os.getenv("LLM_DEFAULT_MODEL", "o1-mini")
        config["enabled"] = os.getenv("LLM_ENABLED", "false").lower() == "true"

        return config

    def _load_google_from_env(self) -> Dict[str, Any]:
        """Load Google Gen AI / Vertex AI configuration from environment variables"""
        config = {}

        # First try Google Gen AI API key (simpler, for Gemini/Imagen)
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if api_key:
            config["api_key"] = api_key
            config["models"] = ["imagen-3.0-generate-001", "imagen-3.0-fast-generate-001"]
            config["default_model"] = "imagen-3.0-generate-001"
            config["enabled"] = True
            return config

        # Fallback to Vertex AI (uses project_id and location instead of API key)
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT_ID")
        location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION", "us-central1")

        if project_id:
            config["project_id"] = project_id
            config["location"] = location
            config["models"] = ["imagen-3.0-generate-001", "imagen-3.0-fast-generate-001"]
            config["default_model"] = "imagen-3.0-generate-001"
            config["enabled"] = os.getenv("VERTEX_ENABLED", "true").lower() == "true"

        return config


class OrganizationContext:
    """Container for organization context passed through request flow"""
    
    def __init__(self, assistant_owner: str, setup: str = "default"):
        self.assistant_owner = assistant_owner
        self.setup = setup
        
    def get_config_resolver(self) -> OrganizationConfigResolver:
        """Get a configuration resolver for this context"""
        return OrganizationConfigResolver(self.assistant_owner, self.setup)