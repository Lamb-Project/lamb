"""
Organization Configuration Resolver for LAMB

This module provides organization-aware configuration resolution for LLM providers.
Startup seeds deployment defaults. Runtime requests read the saved organization
configuration, including explicit disables and cleared values.
"""

import logging
from typing import Dict, Any, Optional
from lamb.database_manager import LambDatabaseManager

logger = logging.getLogger(__name__)


class OrganizationConfigResolver:
    """Resolves configuration for providers based on organization context"""
    
    def __init__(self, assistant_owner: Optional[str] = None, setup_name: str = "default"):
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
        if self._org is None and self.assistant_owner is None:
            self._org = self.db_manager.get_organization_by_slug("lamb")
            if not self._org:
                raise ValueError("System organization not found")
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
        Get saved provider configuration
        
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
        
        # Cache the result
        if config:
            self._config_cache[cache_key] = config
            
        return config or {}
    
    def get_knowledge_base_config(self) -> Dict[str, Any]:
        """Get knowledge base configuration"""
        org_config = self.organization.get('config', {})
        setups = org_config.get('setups', {})
        setup = setups.get(self.setup_name, {})
        legacy = setup.get("knowledge_base", {})
        current = org_config.get("kb_server", {})
        def first(mapping, names):
            return next((mapping[key] for key in names if key in mapping), None)
        # Normalize aliases before merging, so legacy server_url cannot beat a
        # saved current url and explicit empty credentials never trigger fallback.
        result = {
            "server_url": first(legacy, ("server_url", "url")),
            "api_token": first(legacy, ("api_token", "api_key", "token")),
        }
        for field, names in (("server_url", ("url", "server_url")),
                              ("api_token", ("api_key", "api_token", "token"))):
            if any(name in current for name in names):
                result[field] = first(current, names)
        for field in ("embedding_model", "collection_defaults"):
            if field in current or field in legacy:
                result[field] = current.get(field, legacy.get(field))
        return result if legacy or current else {}

    def get_library_config(self) -> Dict[str, Any]:
        """Get Library Manager configuration for this organization.

        Resolves from ``setups[setup_name].library`` in org config.
        Startup seeds missing system-organization connection settings.

        Returns:
            Dict with ``server_url``, ``api_token``, ``allowed_import_plugins``,
            and ``external_service_keys``.
        """
        org_config = self.organization.get('config', {})
        setups = org_config.get('setups', {})
        setup = setups.get(self.setup_name, {})
        lib_config = setup.get("library", {})

        if lib_config:
            return {
                "server_url": lib_config.get("server_url", lib_config.get("url")),
                "api_token": lib_config.get("api_token", lib_config.get("token")),
                "allowed_import_plugins": lib_config.get("allowed_import_plugins", []),
                "external_service_keys": lib_config.get("external_service_keys", {}),
            }

        return {}

    def get_feature_flag(self, feature: str) -> bool:
        """Get feature flag value"""
        org_config = self.organization.get('config', {})
        features = org_config.get("features", {})
        return features.get(feature, False)
    
    def get_global_default_model_config(self) -> Dict[str, str]:
        """
        Get the global-default-model configuration for this organization
        
        Returns:
            Dict with keys 'provider' and 'model'
            Returns empty strings if not configured
        """
        org_config = self.organization.get('config', {})
        setups = org_config.get('setups', {})
        setup = setups.get(self.setup_name, {})
        global_default_config = setup.get('global_default_model', {})
        
        provider = global_default_config.get('provider', '')
        model = global_default_config.get('model', '')
        
        return {
            "provider": provider,
            "model": model
        }

    def get_small_fast_model_config(self) -> Dict[str, str]:
        """
        Get the small-fast-model configuration for this organization
        
        Returns:
            Dict with keys 'provider' and 'model'
            Returns empty strings if not configured
        """
        org_config = self.organization.get('config', {})
        setups = org_config.get('setups', {})
        setup = setups.get(self.setup_name, {})
        small_fast_config = setup.get('small_fast_model', {})
        
        provider = small_fast_config.get('provider', '')
        model = small_fast_config.get('model', '')
        
        return {
            "provider": provider,
            "model": model
        }

    def resolve_model_for_completion(self, requested_model=None, requested_provider=None,
                                     available_providers=None):
        """Resolve preferences against enabled org configuration, never a live model probe.

        Installed/enabled connectors supplied by the caller bound the fallback set.
        Empty or omitted catalogs are unknown, not an explicit disable. A nonempty
        catalog remains an allowlist. Stored assistant preferences are untouched.
        """
        def config_for(provider):
            if not provider or (available_providers is not None and provider not in available_providers):
                return {}
            config = self.get_provider_config(provider)
            return config if config and config.get('enabled', True) else {}

        def allowed(provider, model):
            config = config_for(provider)
            catalog = config.get('models')
            return bool(config and model and (not catalog or model in catalog))

        def select(provider, model):
            if (provider, model) != (requested_provider, requested_model):
                logger.warning('Using organization model fallback: %s/%s', provider, model)
            return {'provider': provider, 'model': model}

        if allowed(requested_provider, requested_model):
            return select(requested_provider, requested_model)
        default = self.get_global_default_model_config()
        if allowed(default.get('provider'), default.get('model')):
            return select(default['provider'], default['model'])
        providers = self.organization.get('config', {}).get('setups', {}).get(self.setup_name, {}).get('providers', {})
        for provider in dict.fromkeys([requested_provider, *providers]):
            config = config_for(provider)
            catalog = config.get('models') or []
            model = config.get('default_model')
            if allowed(provider, model):
                return select(provider, model)
            if catalog:
                return select(provider, catalog[0])
        raise ValueError('No enabled model and connector configured for this organization')



class OrganizationContext:
    """Container for organization context passed through request flow"""
    
    def __init__(self, assistant_owner: str, setup: str = "default"):
        self.assistant_owner = assistant_owner
        self.setup = setup
        
    def get_config_resolver(self) -> OrganizationConfigResolver:
        """Get a configuration resolver for this context"""
        return OrganizationConfigResolver(self.assistant_owner, self.setup)