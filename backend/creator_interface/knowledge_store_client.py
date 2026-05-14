"""HTTP client for the new KB Server microservice (Knowledge Stores).

Targets the redesigned server on port 9092 — distinct from the stable
``kb_server_manager.py`` (port 9090). Resolves org-specific config via
``OrganizationConfigResolver.get_knowledge_store_config`` and uses async
httpx with per-call client lifecycle (matches ``LibraryManagerClient``).

The KB Server is intentionally ignorant of users, organizations, and
libraries; LAMB owns ACL, multi-tenancy, and content delivery (ADR-1 / ADR-6
of issue #334). Embedding API keys are sent per-request and held in memory
only by the KB Server (ADR-4) — they are never persisted there.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = logging.getLogger(__name__)

LAMB_KB_SERVER_V2 = os.getenv("LAMB_KB_SERVER_V2", "")
LAMB_KB_SERVER_V2_TOKEN = os.getenv("LAMB_KB_SERVER_V2_TOKEN", "")

# Fallback plugin data used when the KB Server is unreachable or not yet
# configured.  Mirrors the built-in plugins registered in lamb-kb-server so
# the creation wizard always has sensible defaults regardless of server state.
_BUILTIN_BACKENDS: List[Dict[str, Any]] = [
    {"name": "chromadb"},
    {"name": "qdrant"},
]

_BUILTIN_STRATEGIES: List[Dict[str, Any]] = [
    {
        "name": "simple",
        "description": "Recursive character text splitting",
        "parameters": [
            {"name": "chunk_size", "type": "int", "description": "Maximum characters per chunk", "default": 1000, "min_value": 50, "max_value": 8000},
            {"name": "chunk_overlap", "type": "int", "description": "Characters of overlap between adjacent chunks", "default": 200, "min_value": 0, "max_value": 2000},
        ],
    },
    {
        "name": "hierarchical",
        "description": "Parent-child header-based chunking",
        "parameters": [
            {"name": "parent_chunk_size", "type": "int", "description": "Max characters in a parent section before secondary splitting", "default": 2000, "min_value": 200, "max_value": 16000},
            {"name": "child_chunk_size", "type": "int", "description": "Max characters in each child chunk (used for embedding)", "default": 400, "min_value": 50, "max_value": 4000},
        ],
    },
    {"name": "by_page", "description": "One chunk per document page", "parameters": []},
    {"name": "by_section", "description": "Chunk by document section headers", "parameters": []},
]

_BUILTIN_VENDORS: List[Dict[str, Any]] = [
    {
        "name": "openai",
        "description": "OpenAI embeddings",
        "parameters": [
            {"name": "model", "type": "string", "description": "Embedding model name", "default": "text-embedding-3-small"},
            {"name": "api_endpoint", "type": "string", "description": "Custom OpenAI-compatible base URL (leave empty for api.openai.com)", "default": ""},
        ],
    },
    {
        "name": "ollama",
        "description": "Ollama local embeddings",
        "parameters": [
            {"name": "model", "type": "string", "description": "Model name", "default": "nomic-embed-text"},
            {"name": "api_endpoint", "type": "string", "description": "Ollama API endpoint", "default": "http://host.docker.internal:11435/api/embeddings"},
        ],
    },
    {
        "name": "local",
        "description": "Local sentence-transformers embeddings (no API key needed)",
        "parameters": [
            {"name": "model", "type": "string", "description": "Sentence-Transformers model name or local path", "default": "all-MiniLM-L6-v2"},
        ],
    },
]


class KnowledgeStoreClient:
    """Async HTTP client for the new KB Server (port 9092)."""

    def __init__(self):
        self.global_server_url = LAMB_KB_SERVER_V2
        self.global_token = LAMB_KB_SERVER_V2_TOKEN

    def _get_ks_config(self, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve KB Server URL, token, and org allow-lists for the user.

        Args:
            creator_user: LAMB creator user dict with at least ``email``.

        Returns:
            Dict with ``url``, ``token``, ``allowed_vector_db_backends``,
            ``allowed_chunking_strategies``, ``allowed_embedding_vendors``,
            ``allowed_embedding_models``.

        Raises:
            ValueError: If no KB Server is configured.
        """
        user_email = creator_user.get("email") if creator_user else None
        if user_email:
            try:
                resolver = OrganizationConfigResolver(user_email)
                ks_config = resolver.get_knowledge_store_config()
                if ks_config and ks_config.get("server_url"):
                    return {
                        "url": ks_config["server_url"],
                        "token": ks_config.get("api_token") or self.global_token,
                        "allowed_vector_db_backends": ks_config.get(
                            "allowed_vector_db_backends", []
                        ),
                        "allowed_chunking_strategies": ks_config.get(
                            "allowed_chunking_strategies", []
                        ),
                        "allowed_embedding_vendors": ks_config.get(
                            "allowed_embedding_vendors", []
                        ),
                        "allowed_embedding_models": ks_config.get(
                            "allowed_embedding_models", {}
                        ),
                    }
            except Exception as e:
                logger.warning(f"Error resolving KS config for {user_email}: {e}")

        if not self.global_server_url:
            raise ValueError(
                "Knowledge Store server not configured (set LAMB_KB_SERVER_V2)"
            )
        return {
            "url": self.global_server_url,
            "token": self.global_token,
            "allowed_vector_db_backends": [],
            "allowed_chunking_strategies": [],
            "allowed_embedding_vendors": [],
            "allowed_embedding_models": {},
        }

    def resolve_embedding_api_key(self, creator_user: Dict[str, Any],
                                  vendor: str) -> str:
        """Get the org-level API key for a given embedding vendor.

        Reuses the existing ``providers[vendor].api_key`` slot used by chat
        completions and RAG (ADR-KS-4). Returns an empty string if not set,
        which is acceptable for vendors that don't need a key (e.g. local).

        Args:
            creator_user: LAMB creator user dict with at least ``email``.
            vendor: Embedding vendor name.

        Returns:
            API key string (possibly empty).
        """
        user_email = creator_user.get("email") if creator_user else None
        if not user_email:
            return ""
        try:
            resolver = OrganizationConfigResolver(user_email)
            return resolver.get_provider_api_key(vendor) or ""
        except Exception as e:
            logger.warning(
                f"Error resolving embedding key for {user_email}/{vendor}: {e}"
            )
            return ""

    def _headers(self, token: str) -> Dict[str, str]:
        if not token:
            raise ValueError(
                "Knowledge Store token is not configured. "
                "Set LAMB_KB_SERVER_V2_TOKEN in backend/.env"
            )
        return {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, config: Dict[str, Any],
                       expect_204: bool = False, **kwargs) -> Any:
        """Make an HTTP request to the KB Server.

        Args:
            method: HTTP method.
            path: URL path appended to the server URL.
            config: Resolved config dict from ``_get_ks_config``.
            expect_204: When True, accept an empty 204 No Content response
                and return ``{}`` rather than parsing JSON.
            **kwargs: Passed through to ``httpx.AsyncClient.request``.

        Returns:
            Parsed JSON response, or ``{}`` for 204.

        Raises:
            HTTPException: On non-2xx responses or connection errors.
        """
        url = f"{config['url'].rstrip('/')}{path}"
        headers = self._headers(config["token"])
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
                if response.is_success:
                    if expect_204 or not response.content:
                        return {}
                    return response.json()
                detail = "Unknown error"
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text or f"HTTP {response.status_code}"
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Knowledge Store server error: {detail}",
                )
        except httpx.RequestError as exc:
            logger.error(f"Knowledge Store connection error: {exc}")
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to Knowledge Store server",
            )

    # ------------------------------------------------------------------
    # System / discovery
    # ------------------------------------------------------------------

    async def get_backends(self, creator_user: Dict[str, Any] = None) -> Dict:
        """List vector DB backends registered on the KB Server."""
        config = self._get_ks_config(creator_user)
        return await self._request("GET", "/backends", config)

    async def get_chunking_strategies(self, creator_user: Dict[str, Any] = None) -> Dict:
        """List chunking strategies registered on the KB Server."""
        config = self._get_ks_config(creator_user)
        return await self._request("GET", "/chunking-strategies", config)

    async def get_embedding_vendors(self, creator_user: Dict[str, Any] = None) -> Dict:
        """List embedding vendors registered on the KB Server."""
        config = self._get_ks_config(creator_user)
        return await self._request("GET", "/embedding-vendors", config)

    # ------------------------------------------------------------------
    # Collection CRUD
    # ------------------------------------------------------------------

    async def create_collection(
        self,
        knowledge_store_id: str,
        organization_id: int,
        name: str,
        chunking_strategy: str,
        embedding_vendor: str,
        embedding_model: str,
        vector_db_backend: str,
        description: str = "",
        chunking_params: Dict[str, Any] = None,
        embedding_endpoint: str = "",
        creator_user: Dict[str, Any] = None,
    ) -> Dict:
        """Create a collection on the KB Server.

        Mirrors LAMB's ``knowledge_stores.id`` to the server's collection ID
        so the two records stay in lockstep.
        """
        config = self._get_ks_config(creator_user)
        payload = {
            "id": knowledge_store_id,
            "organization_id": str(organization_id),
            "name": name,
            "description": description,
            "chunking_strategy": chunking_strategy,
            "chunking_params": chunking_params or {},
            "embedding": {
                "vendor": embedding_vendor,
                "model": embedding_model,
                "api_endpoint": embedding_endpoint or "",
            },
            "vector_db_backend": vector_db_backend,
        }
        return await self._request("POST", "/collections", config, json=payload)

    async def get_collection(self, knowledge_store_id: str,
                             creator_user: Dict[str, Any] = None) -> Dict:
        """Get a collection by ID."""
        config = self._get_ks_config(creator_user)
        return await self._request(
            "GET", f"/collections/{knowledge_store_id}", config,
        )

    async def update_collection(self, knowledge_store_id: str,
                                name: str = None, description: str = None,
                                chunking_params: Optional[Dict[str, Any]] = None,
                                creator_user: Dict[str, Any] = None) -> Dict:
        """Update mutable fields of a collection (name, description, chunking_params).

        ``chunking_params`` updates apply only to content ingested AFTER the
        change — existing chunks keep their original parameters.
        """
        config = self._get_ks_config(creator_user)
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if chunking_params is not None:
            body["chunking_params"] = chunking_params
        return await self._request(
            "PUT", f"/collections/{knowledge_store_id}", config, json=body,
        )

    async def delete_collection(self, knowledge_store_id: str,
                                creator_user: Dict[str, Any] = None) -> Dict:
        """Delete a collection. Server returns 204 No Content."""
        config = self._get_ks_config(creator_user)
        return await self._request(
            "DELETE", f"/collections/{knowledge_store_id}", config,
            expect_204=True,
        )

    # ------------------------------------------------------------------
    # Content ingestion / deletion
    # ------------------------------------------------------------------

    async def add_content(
        self,
        knowledge_store_id: str,
        documents: List[Dict[str, Any]],
        embedding_api_key: str,
        embedding_api_endpoint: str = "",
        creator_user: Dict[str, Any] = None,
    ) -> Dict:
        """Queue documents for asynchronous ingestion (returns 202 + job_id).

        Args:
            knowledge_store_id: Target collection UUID.
            documents: List of document payloads (each: source_item_id, title,
                text, permalinks, pages, extra_metadata).
            embedding_api_key: Vendor API key (sent per request, never stored).
            embedding_api_endpoint: Optional endpoint override.
            creator_user: LAMB user dict for org config resolution.

        Returns:
            Dict with ``job_id``, ``status``, ``documents_total``.
        """
        config = self._get_ks_config(creator_user)
        payload = {
            "documents": documents,
            "embedding_credentials": {
                "api_key": embedding_api_key or "",
                "api_endpoint": embedding_api_endpoint or "",
            },
        }
        return await self._request(
            "POST", f"/collections/{knowledge_store_id}/add-content",
            config, json=payload,
        )

    async def delete_content_by_source(
        self, knowledge_store_id: str, source_item_id: str,
        creator_user: Dict[str, Any] = None,
    ) -> Dict:
        """Delete all vectors for a given source item."""
        config = self._get_ks_config(creator_user)
        return await self._request(
            "DELETE",
            f"/collections/{knowledge_store_id}/content/{source_item_id}",
            config,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        knowledge_store_id: str,
        query_text: str,
        embedding_api_key: str,
        embedding_api_endpoint: str = "",
        top_k: int = 5,
        creator_user: Dict[str, Any] = None,
    ) -> Dict:
        """Run a similarity search over a collection.

        Returns chunks with permalink-bearing metadata so the caller can
        render citations.
        """
        config = self._get_ks_config(creator_user)
        payload = {
            "query_text": query_text,
            "top_k": top_k,
            "embedding_credentials": {
                "api_key": embedding_api_key or "",
                "api_endpoint": embedding_api_endpoint or "",
            },
        }
        return await self._request(
            "POST", f"/collections/{knowledge_store_id}/query",
            config, json=payload,
        )

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    async def get_job_status(self, job_id: str,
                             creator_user: Dict[str, Any] = None) -> Dict:
        """Poll an ingestion job's status."""
        config = self._get_ks_config(creator_user)
        return await self._request("GET", f"/jobs/{job_id}", config)

    # ------------------------------------------------------------------
    # Org-level discovery (for the UI options endpoint)
    # ------------------------------------------------------------------

    async def get_org_options(self, creator_user: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate the org's allow-lists with the server's registered plugins.

        The result tells the frontend which chunking strategies, embedding
        vendors / models, and vector DB backends the user is allowed to pick
        when creating a Knowledge Store. The server's full registries are
        intersected with the org's allow-lists; an empty allow-list means
        "everything the server offers".

        Returns:
            Dict with ``vector_db_backends``, ``chunking_strategies``,
            ``embedding_vendors``, ``embedding_models``.
        """
        try:
            config = self._get_ks_config(creator_user)
        except Exception:
            config = {
                "allowed_vector_db_backends": [],
                "allowed_chunking_strategies": [],
                "allowed_embedding_vendors": [],
                "allowed_embedding_models": {},
            }
        try:
            backends = (await self.get_backends(creator_user)).get("backends", [])
        except Exception:
            backends = []
        try:
            strategies = (await self.get_chunking_strategies(creator_user)).get(
                "strategies", []
            )
        except Exception:
            strategies = []
        try:
            vendors = (await self.get_embedding_vendors(creator_user)).get(
                "vendors", []
            )
        except Exception:
            vendors = []

        # Fall back to built-in plugin data when the KB Server is unreachable
        # or not configured — this ensures the creation wizard always renders.
        if not backends:
            backends = _BUILTIN_BACKENDS
        if not strategies:
            strategies = _BUILTIN_STRATEGIES
        if not vendors:
            vendors = _BUILTIN_VENDORS

        allowed_backends = config["allowed_vector_db_backends"]
        allowed_strategies = config["allowed_chunking_strategies"]
        allowed_vendors = config["allowed_embedding_vendors"]
        allowed_models_map: Dict[str, List[str]] = config["allowed_embedding_models"] or {}

        def _filter_names(plugins: List[Dict[str, Any]],
                          allowed: List[str]) -> List[Dict[str, Any]]:
            if not allowed:
                return plugins
            return [p for p in plugins if p.get("name") in allowed]

        filtered_vendors = _filter_names(vendors, allowed_vendors)

        # Override the static plugin-level ``api_endpoint`` default with the
        # org-level ``setups[default].providers[<vendor>].endpoint`` value so
        # the UI's "create Knowledge Store" form pre-fills with an endpoint
        # that is reachable from the kb-server-v2 container (e.g. the docker
        # bridge address) instead of ``localhost``. The static default in the
        # plugin (#D1 fix) remains the code-level fallback when the org has no
        # provider config set.
        user_email = creator_user.get("email") if creator_user else None
        if user_email:
            try:
                resolver = OrganizationConfigResolver(user_email)
                for vendor in filtered_vendors:
                    vendor_name = vendor.get("name")
                    if not vendor_name:
                        continue
                    # Tag the vendor with whether the org has it configured.
                    # "Configured" means the org has a non-empty entry under
                    # setups.default.providers.<vendor> — the entry need not
                    # contain an api_key (e.g. ollama uses base_url, no key).
                    # ``local`` plugins are configuration-free and always
                    # available.
                    try:
                        provider_cfg = resolver.get_provider_config(vendor_name) or {}
                    except Exception:
                        provider_cfg = {}
                    # ollama needs no API key (just a reachable base URL), so
                    # treat it like "local" — always selectable.
                    vendor["api_key_configured"] = (
                        bool(provider_cfg) or vendor_name in ("local", "ollama")
                    )
                    try:
                        org_endpoint = resolver.get_provider_endpoint(vendor_name) or ""
                    except ValueError:
                        org_endpoint = ""
                    if not org_endpoint:
                        continue
                    for param in vendor.get("parameters", []) or []:
                        if param.get("name") == "api_endpoint":
                            param["default"] = org_endpoint
            except Exception as e:
                logger.warning(
                    f"Could not resolve embedding-vendor availability from org "
                    f"config for {user_email}: {e}"
                )
        else:
            # No user context — leave the field unset; frontend treats absent
            # as "unknown / show all" so the wizard still works for tests.
            for vendor in filtered_vendors:
                vendor.setdefault("api_key_configured", True)

        # Per-vendor model list: if the org's allow-list specifies models for
        # a vendor, use it. Otherwise fall back to the vendor plugin's own
        # default (its ``model`` parameter's ``default`` value) so the UI has
        # at least one model to pre-select. Without this fallback, an org that
        # configures ``allowed_embedding_vendors`` but skips
        # ``allowed_embedding_models`` ships an empty model dropdown and the
        # wizard's "Next" stays disabled with no way forward.
        resolved_models_map: Dict[str, List[str]] = {}
        for vendor in filtered_vendors:
            vendor_name = vendor.get("name")
            if not vendor_name:
                continue
            org_allowed = allowed_models_map.get(vendor_name) or []
            if org_allowed:
                resolved_models_map[vendor_name] = org_allowed
                continue
            plugin_default = ""
            for param in vendor.get("parameters", []) or []:
                if param.get("name") == "model":
                    plugin_default = (param.get("default") or "").strip()
                    break
            if plugin_default:
                resolved_models_map[vendor_name] = [plugin_default]

        return {
            "vector_db_backends": _filter_names(backends, allowed_backends),
            "chunking_strategies": _filter_names(strategies, allowed_strategies),
            "embedding_vendors": filtered_vendors,
            "embedding_models": resolved_models_map,
        }

    def validate_against_allow_list(
        self,
        creator_user: Dict[str, Any],
        chunking_strategy: str,
        embedding_vendor: str,
        embedding_model: str,
        vector_db_backend: str,
    ) -> Optional[str]:
        """Validate user-supplied locked-setup choices against org allow-lists.

        Returns:
            ``None`` if valid; otherwise an error message string suitable for
            an HTTP 400 detail.
        """
        config = self._get_ks_config(creator_user)

        allowed_strategies = config["allowed_chunking_strategies"]
        if allowed_strategies and chunking_strategy not in allowed_strategies:
            return (
                f"Chunking strategy '{chunking_strategy}' is not allowed for this "
                f"organization. Allowed: {', '.join(allowed_strategies)}."
            )

        allowed_vendors = config["allowed_embedding_vendors"]
        if allowed_vendors and embedding_vendor not in allowed_vendors:
            return (
                f"Embedding vendor '{embedding_vendor}' is not allowed for this "
                f"organization. Allowed: {', '.join(allowed_vendors)}."
            )

        allowed_models_map: Dict[str, List[str]] = config["allowed_embedding_models"] or {}
        allowed_models = allowed_models_map.get(embedding_vendor) or []
        if allowed_models and embedding_model not in allowed_models:
            return (
                f"Embedding model '{embedding_model}' is not allowed for vendor "
                f"'{embedding_vendor}'. Allowed: {', '.join(allowed_models)}."
            )

        allowed_backends = config["allowed_vector_db_backends"]
        if allowed_backends and vector_db_backend not in allowed_backends:
            return (
                f"Vector DB backend '{vector_db_backend}' is not allowed for this "
                f"organization. Allowed: {', '.join(allowed_backends)}."
            )

        return None
