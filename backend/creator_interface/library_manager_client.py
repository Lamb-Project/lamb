"""HTTP client for the Library Manager microservice.

Follows the same pattern as ``kb_server_manager.py``: resolves org-specific
config, uses async httpx, and maps Library Manager responses to LAMB's
enriched format.
"""

import json
import logging
import os
from typing import Any, Dict

import httpx
from fastapi import HTTPException, UploadFile

from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = logging.getLogger(__name__)

LAMB_LIBRARY_SERVER = os.getenv("LAMB_LIBRARY_SERVER", "")
LAMB_LIBRARY_TOKEN = os.getenv("LAMB_LIBRARY_TOKEN", "")


class LibraryManagerClient:
    """Async HTTP client for Library Manager service calls."""

    def __init__(self):
        self.global_server_url = LAMB_LIBRARY_SERVER
        self.global_token = LAMB_LIBRARY_TOKEN

    def _get_library_config(self, creator_user: Dict[str, Any]) -> Dict[str, str]:
        """Resolve Library Manager URL and token for the user's organization.

        Args:
            creator_user: LAMB creator user dict with at least ``email``.

        Returns:
            Dict with ``url``, ``token``, ``allowed_plugins``,
            and ``external_keys`` keys.

        Raises:
            ValueError: If no Library Manager is configured.
        """
        user_email = creator_user.get("email")
        if user_email:
            try:
                resolver = OrganizationConfigResolver(user_email)
                lib_config = resolver.get_library_config()
                if lib_config and lib_config.get("server_url"):
                    return {
                        "url": lib_config["server_url"],
                        "token": lib_config.get("api_token") or self.global_token,
                        "allowed_plugins": lib_config.get("allowed_import_plugins", []),
                        "external_keys": lib_config.get("external_service_keys", {}),
                    }
            except Exception as e:
                logger.warning(f"Error resolving library config for {user_email}: {e}")

        if not self.global_server_url:
            raise ValueError("Library Manager not configured (set LAMB_LIBRARY_SERVER)")
        return {
            "url": self.global_server_url,
            "token": self.global_token,
            "allowed_plugins": [],
            "external_keys": {},
        }

    def _headers(self, token: str) -> Dict[str, str]:
        """Return authorization headers for Library Manager requests."""
        return {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, config: Dict[str, str],
                       **kwargs) -> Any:
        """Make an HTTP request to the Library Manager.

        Args:
            method: HTTP method.
            path: URL path (appended to server URL).
            config: Resolved config dict with ``url`` and ``token``.
            **kwargs: Passed to httpx request.

        Returns:
            Parsed JSON response.

        Raises:
            HTTPException: On non-2xx responses or connection errors.
        """
        url = f"{config['url'].rstrip('/')}{path}"
        headers = self._headers(config["token"])
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
                if response.is_success:
                    if not response.content:
                        return {}
                    return response.json()
                detail = "Unknown error"
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text or f"HTTP {response.status_code}"
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Library Manager error: {detail}",
                )
        except httpx.RequestError as exc:
            logger.error(f"Library Manager connection error: {exc}")
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to Library Manager",
            )

    async def _fetch_bytes(self, method: str, path: str,
                           config: Dict[str, str], **kwargs) -> httpx.Response:
        """Make a request and return the full response with body read.

        Used for export/proxy where we need the raw bytes. The httpx client
        is properly closed via context manager after reading.

        Args:
            method: HTTP method.
            path: URL path.
            config: Resolved config dict.
            **kwargs: Passed to httpx request.

        Returns:
            httpx.Response with body already read.

        Raises:
            HTTPException: On non-2xx or connection error.
        """
        url = f"{config['url'].rstrip('/')}{path}"
        headers = self._headers(config["token"])
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
                if not response.is_success:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail="Library Manager request failed",
                    )
                return response
        except httpx.RequestError as exc:
            logger.error(f"Library Manager connection error: {exc}")
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to Library Manager",
            )

    # ------------------------------------------------------------------
    # Library CRUD
    # ------------------------------------------------------------------

    async def create_library(self, library_id: str, organization_id: int,
                             name: str, import_config: Dict = None,
                             creator_user: Dict[str, Any] = None) -> Dict:
        """Create a library on the Library Manager."""
        config = self._get_library_config(creator_user)
        return await self._request("POST", "/libraries", config, json={
            "id": library_id,
            "organization_id": str(organization_id),
            "name": name,
            "import_config": import_config,
        })

    async def get_library(self, library_id: str,
                          creator_user: Dict[str, Any] = None) -> Dict:
        """Get library details from the Library Manager."""
        config = self._get_library_config(creator_user)
        return await self._request("GET", f"/libraries/{library_id}", config)

    async def delete_library(self, library_id: str,
                             creator_user: Dict[str, Any] = None) -> Dict:
        """Delete a library from the Library Manager."""
        config = self._get_library_config(creator_user)
        return await self._request("DELETE", f"/libraries/{library_id}", config)

    # ------------------------------------------------------------------
    # Content importing
    # ------------------------------------------------------------------

    async def import_file(self, library_id: str, file: UploadFile,
                          plugin_name: str, title: str,
                          plugin_params: Dict = None,
                          api_keys: Dict[str, str] = None,
                          creator_user: Dict[str, Any] = None) -> Dict:
        """Upload a file for import into a library."""
        config = self._get_library_config(creator_user)
        file_content = await file.read()
        await file.seek(0)
        files = {"file": (file.filename, file_content, file.content_type)}
        data = {
            "plugin_name": plugin_name,
            "title": title,
            "plugin_params": json.dumps(plugin_params or {}),
            "api_keys": json.dumps(api_keys or {}),
        }
        return await self._request("POST", f"/libraries/{library_id}/import/file",
                                   config, files=files, data=data)

    async def import_url(self, library_id: str, url: str, plugin_name: str,
                         title: str, plugin_params: Dict = None,
                         api_keys: Dict[str, str] = None,
                         creator_user: Dict[str, Any] = None) -> Dict:
        """Import content from a URL into a library."""
        config = self._get_library_config(creator_user)
        return await self._request("POST", f"/libraries/{library_id}/import/url", config, json={
            "url": url,
            "plugin_name": plugin_name,
            "title": title,
            "plugin_params": plugin_params,
            "api_keys": api_keys,
        })

    async def import_youtube(self, library_id: str, video_url: str,
                             plugin_name: str, title: str,
                             language: str = "en",
                             plugin_params: Dict = None,
                             api_keys: Dict[str, str] = None,
                             creator_user: Dict[str, Any] = None) -> Dict:
        """Import a YouTube video transcript into a library."""
        config = self._get_library_config(creator_user)
        params = plugin_params or {}
        params["language"] = language
        return await self._request("POST", f"/libraries/{library_id}/import/youtube", config, json={
            "video_url": video_url,
            "plugin_name": plugin_name,
            "title": title,
            "plugin_params": params,
            "api_keys": api_keys,
            "language": language,
        })

    # ------------------------------------------------------------------
    # Content retrieval
    # ------------------------------------------------------------------

    async def get_items(self, library_id: str, creator_user: Dict[str, Any] = None,
                        **params) -> Dict:
        """List items in a library with optional filters."""
        config = self._get_library_config(creator_user)
        return await self._request("GET", f"/libraries/{library_id}/items",
                                   config, params=params)

    async def get_item(self, library_id: str, item_id: str,
                       creator_user: Dict[str, Any] = None) -> Dict:
        """Get details of a single library item."""
        config = self._get_library_config(creator_user)
        return await self._request("GET", f"/libraries/{library_id}/items/{item_id}", config)

    async def get_item_status(self, library_id: str, item_id: str,
                              creator_user: Dict[str, Any] = None) -> Dict:
        """Get the import status for an item."""
        config = self._get_library_config(creator_user)
        return await self._request("GET", f"/libraries/{library_id}/items/{item_id}/status", config)

    async def delete_item(self, library_id: str, item_id: str,
                          creator_user: Dict[str, Any] = None) -> Dict:
        """Delete an item from a library."""
        config = self._get_library_config(creator_user)
        return await self._request("DELETE", f"/libraries/{library_id}/items/{item_id}", config)

    # ------------------------------------------------------------------
    # Plugins & config
    # ------------------------------------------------------------------

    async def get_plugins(self, creator_user: Dict[str, Any] = None) -> Dict:
        """List available import plugins, filtered by org config."""
        config = self._get_library_config(creator_user)
        result = await self._request("GET", "/plugins", config)
        allowed = config.get("allowed_plugins", [])
        if allowed:
            result["plugins"] = [p for p in result.get("plugins", [])
                                 if p["name"] in allowed]
        return result

    async def get_import_config(self, library_id: str,
                                creator_user: Dict[str, Any] = None) -> Dict:
        """Get a library's import configuration."""
        config = self._get_library_config(creator_user)
        return await self._request("GET", f"/libraries/{library_id}/import-config", config)

    async def update_import_config(self, library_id: str, import_config: Dict,
                                   creator_user: Dict[str, Any] = None) -> Dict:
        """Update a library's import configuration."""
        config = self._get_library_config(creator_user)
        return await self._request("PUT", f"/libraries/{library_id}/import-config",
                                   config, json=import_config)

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    async def export_library(self, library_id: str,
                             creator_user: Dict[str, Any] = None) -> httpx.Response:
        """Export a library as a ZIP archive."""
        config = self._get_library_config(creator_user)
        return await self._fetch_bytes("GET", f"/libraries/{library_id}/export", config)

    async def import_library_zip(self, organization_id: int, zip_data: bytes,
                                 creator_user: Dict[str, Any] = None) -> Dict:
        """Import a library from a ZIP archive."""
        config = self._get_library_config(creator_user)
        files = {"file": ("library.zip", zip_data, "application/zip")}
        return await self._request(
            "POST", "/libraries/import",
            config, files=files,
            params={"organization_id": str(organization_id)},
        )

    # ------------------------------------------------------------------
    # Permalink proxy
    # ------------------------------------------------------------------

    async def proxy_content(self, library_id: str, item_id: str, subpath: str,
                            creator_user: Dict[str, Any] = None) -> httpx.Response:
        """Proxy a permalink content request to the Library Manager.

        Args:
            library_id: Library UUID.
            item_id: Content item UUID.
            subpath: Remaining path after the item ID (e.g. ``content/full.md``).
            creator_user: LAMB user dict.

        Returns:
            httpx.Response with body already read.

        Raises:
            HTTPException: If subpath contains path traversal sequences.
        """
        if ".." in subpath or subpath.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid content path")
        config = self._get_library_config(creator_user)
        path = f"/libraries/{library_id}/items/{item_id}/{subpath}"
        return await self._fetch_bytes("GET", path, config)
