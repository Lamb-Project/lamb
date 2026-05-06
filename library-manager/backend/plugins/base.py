"""Plugin base class and registry for Library Manager import plugins.

Each plugin converts a source (file, URL, YouTube) into the common Library
Item format: markdown text + optional per-page breakdown + optional images.
Plugins do NOT chunk — that is the KB Server's responsibility.

Usage::

    @PluginRegistry.register
    class MyPlugin(LibraryImportPlugin):
        name = "my_plugin"
        ...
"""

import abc
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes returned by plugins
# ---------------------------------------------------------------------------


@dataclass
class PageContent:
    """A single page extracted from a multi-page document."""

    page_number: int
    text: str  # Markdown text for this page


@dataclass
class ExtractedImage:
    """An image extracted during document import."""

    filename: str  # e.g. "img_001.png"
    data: bytes  # Raw image bytes
    page_number: int | None = None
    description: str | None = None  # LLM-generated or basic description


@dataclass
class ImportResult:
    """The structured output every import plugin must produce.

    This is the common format that all plugins converge to, regardless of
    source type (file, URL, YouTube).
    """

    full_text: str  # Full document as markdown
    pages: list[PageContent] = field(default_factory=list)
    images: list[ExtractedImage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_ref: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Plugin parameter descriptor
# ---------------------------------------------------------------------------


@dataclass
class PluginParameter:
    """Describes one configurable parameter of an import plugin."""

    name: str
    type: str  # "string", "int", "float", "bool", "enum"
    description: str = ""
    default: Any = None
    required: bool = False
    choices: list[str] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    # If True, this param is hidden in SIMPLIFIED mode.
    advanced: bool = False


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class LibraryImportPlugin(abc.ABC):
    """Abstract base for all Library Manager import plugins.

    Subclasses must set the class-level attributes ``name``,
    ``description``, ``supported_source_types``, and
    ``supported_file_types``, and implement ``import_content`` and
    ``get_parameters``.
    """

    name: str = "base"
    description: str = "Base plugin interface"
    supported_source_types: set[str] = set()  # {'file', 'url', 'youtube'}
    supported_file_types: set[str] = set()  # {'.pdf', '.docx', ...}
    required_keys: list[str] = []  # ['openai_vision'] if needed

    @abc.abstractmethod
    def import_content(
        self,
        source_path: str,
        *,
        api_keys: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> ImportResult:
        """Import a document from the given source and return structured content.

        This method must NOT perform chunking. It returns the full extracted
        text, optional per-page breakdown, and optional extracted images.

        Args:
            source_path: Path to the uploaded file, or URL string for
                remote sources.
            api_keys: Org API keys needed by this plugin (e.g.
                ``{"openai_vision": "sk-..."}``) — held in memory only.
            **kwargs: Additional plugin-specific parameters.

        Returns:
            An ``ImportResult`` containing the structured content.

        Raises:
            ImportError: If a required dependency is not installed.
            ValueError: If the source is invalid or unsupported.
            RuntimeError: If the import fails for any other reason.
        """

    @abc.abstractmethod
    def get_parameters(self) -> list[PluginParameter]:
        """Return the parameter schema for this plugin.

        Returns:
            A list of ``PluginParameter`` descriptors.
        """

    def report_progress(
        self,
        kwargs: dict[str, Any],
        current: int,
        total: int,
        message: str,
    ) -> None:
        """Call the progress callback if one was provided.

        Args:
            kwargs: The keyword arguments passed to ``import_content``.
            current: Current step number.
            total: Total number of steps.
            message: Human-readable progress message.
        """
        callback = kwargs.get("progress_callback")
        if callable(callback):
            callback(current, total, message)


# ---------------------------------------------------------------------------
# Plugin registry
# ---------------------------------------------------------------------------


class PluginRegistry:
    """Singleton registry that collects and manages import plugins.

    Plugins self-register via the ``@PluginRegistry.register`` decorator.
    The registry respects ``PLUGIN_<NAME>=DISABLE|SIMPLIFIED|ADVANCED``
    environment variables.
    """

    _plugins: dict[str, type[LibraryImportPlugin]] = {}

    @classmethod
    def register(cls, plugin_class: type[LibraryImportPlugin]) -> type[LibraryImportPlugin]:
        """Class decorator that registers an import plugin.

        Args:
            plugin_class: The plugin class to register.

        Returns:
            The unmodified plugin class (allows stacking decorators).
        """
        mode = cls.get_plugin_mode(plugin_class.name)
        if mode == "DISABLE":
            logger.info("Plugin '%s' is disabled via environment", plugin_class.name)
            return plugin_class

        cls._plugins[plugin_class.name] = plugin_class
        logger.debug("Registered import plugin: %s", plugin_class.name)
        return plugin_class

    @classmethod
    def get_plugin(cls, name: str) -> LibraryImportPlugin | None:
        """Instantiate and return a plugin by name.

        Args:
            name: The plugin's ``name`` attribute.

        Returns:
            A fresh plugin instance, or ``None`` if not found/disabled.
        """
        plugin_class = cls._plugins.get(name)
        if plugin_class is None:
            return None
        return plugin_class()

    @classmethod
    def list_plugins(cls) -> list[dict[str, Any]]:
        """Return metadata for all registered (non-disabled) plugins.

        Returns:
            A list of dicts with keys: ``name``, ``description``,
            ``supported_source_types``, ``supported_file_types``,
            ``required_keys``, ``mode``, ``parameters``.
        """
        result = []
        for name, plugin_class in cls._plugins.items():
            instance = plugin_class()
            mode = cls.get_plugin_mode(name)
            params = instance.get_parameters()

            if mode == "SIMPLIFIED":
                params = [p for p in params if not p.advanced]

            result.append({
                "name": name,
                "description": plugin_class.description,
                "supported_source_types": sorted(plugin_class.supported_source_types),
                "supported_file_types": sorted(plugin_class.supported_file_types),
                "required_keys": plugin_class.required_keys,
                "mode": mode,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "default": p.default,
                        "required": p.required,
                        "choices": p.choices,
                    }
                    for p in params
                ],
            })
        return result

    @classmethod
    def get_plugin_for_file_type(cls, extension: str) -> LibraryImportPlugin | None:
        """Find the first plugin that supports a given file extension.

        Args:
            extension: File extension without dot (e.g. ``"pdf"``).

        Returns:
            A plugin instance, or ``None`` if no plugin supports this type.
        """
        ext = extension.lower().lstrip(".")
        for plugin_class in cls._plugins.values():
            if ext in plugin_class.supported_file_types:
                return plugin_class()
        return None

    @classmethod
    def get_plugin_mode(cls, name: str) -> str:
        """Read the governance mode for a plugin from environment.

        Checks ``PLUGIN_<UPPER_NAME>`` env var.

        Args:
            name: Plugin name (e.g. ``"simple_import"``).

        Returns:
            One of ``"DISABLE"``, ``"SIMPLIFIED"``, or ``"ADVANCED"``
            (default).
        """
        env_key = f"PLUGIN_{name.upper()}"
        value = os.getenv(env_key, "ADVANCED").upper()
        if value in ("DISABLE", "SIMPLIFIED", "ADVANCED"):
            return value
        return "ADVANCED"

    @classmethod
    def sanitize_params(
        cls, plugin_name: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Filter plugin parameters based on governance mode.

        In ``SIMPLIFIED`` mode, only non-advanced parameters are kept.
        Unknown parameters are always stripped.

        Args:
            plugin_name: Name of the plugin.
            params: Raw parameters from the request.

        Returns:
            A sanitized copy of the parameters.
        """
        plugin = cls.get_plugin(plugin_name)
        if plugin is None:
            return {}

        mode = cls.get_plugin_mode(plugin_name)
        allowed = plugin.get_parameters()
        allowed_names = {
            p.name
            for p in allowed
            if mode == "ADVANCED" or not p.advanced
        }

        return {k: v for k, v in params.items() if k in allowed_names}
