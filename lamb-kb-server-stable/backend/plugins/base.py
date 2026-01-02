"""
Base plugin interface for ingestion strategies.

This module defines the base plugin interface and registry for document ingestion strategies.
"""

import abc
import importlib
import inspect
import os
import pkgutil
from enum import Enum, auto
from typing import Dict, List, Type, Any, Optional, Set, Tuple, Union, Callable


class ChunkUnit(str, Enum):
    """Enum for text chunking units."""
    CHAR = "char"
    WORD = "word"
    LINE = "line"


# Type alias for progress callback function
# callback(current: int, total: int, message: str) -> None
ProgressCallback = Callable[[int, int, str], None]


class IngestPlugin(abc.ABC):
    """Base class for ingestion plugins.
    
    Plugins can optionally support progress reporting by checking for a
    'progress_callback' in kwargs and calling it periodically.
    
    Progress callback signature:
        progress_callback(current: int, total: int, message: str) -> None
        
    Example usage in plugin:
        def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
            progress_callback = kwargs.get('progress_callback')
            
            # Report start
            if progress_callback:
                progress_callback(0, 100, "Starting conversion...")
            
            # ... do work ...
            
            # Report progress
            if progress_callback:
                progress_callback(50, 100, "Processing chunks...")
            
            # ... finish work ...
            
            return chunks
    """
    
    # Plugin metadata
    name: str = "base"
    kind: str = "base"
    description: str = "Base plugin interface"
    supported_file_types: Set[str] = set()
    
    # Whether this plugin supports progress reporting
    # Plugins that process multiple items (URLs, videos) should set this to True
    supports_progress: bool = False
    
    @abc.abstractmethod
    def ingest(self, file_path: str, **kwargs) -> List[Dict[str, Any]]:
        """Ingest a file and return a list of chunks with metadata.
        
        Args:
            file_path: Path to the file to ingest
            **kwargs: Additional plugin-specific parameters
                      May include 'progress_callback' for progress reporting
            
        Returns:
            A list of dictionaries, each containing:
                - text: The chunk text
                - metadata: A dictionary of metadata for the chunk
        """
        pass
    
    @abc.abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get the parameters accepted by this plugin.
        
        Returns:
            A dictionary mapping parameter names to their specifications
        """
        pass
    
    def report_progress(self, kwargs: Dict[str, Any], current: int, total: int, message: str) -> None:
        """Helper method to report progress if callback is available.
        
        Args:
            kwargs: The kwargs dict passed to ingest()
            current: Current progress value
            total: Total expected value
            message: Human-readable status message
        """
        callback = kwargs.get('progress_callback')
        if callback and callable(callback):
            try:
                callback(current, total, message)
            except Exception:
                pass  # Don't let progress reporting break ingestion


class PluginRegistry:
    """Registry for plugins."""
    
    _ingest_plugins: Dict[str, Type[IngestPlugin]] = {}
    _query_plugins: Dict[str, Type['QueryPlugin']] = {}
    
    @classmethod
    def register(cls, plugin_class: Type[Union[IngestPlugin, 'QueryPlugin']]) -> Type[Union[IngestPlugin, 'QueryPlugin']]:
        """Register a plugin class.
        
        Args:
            plugin_class: The plugin class to register
            
        Returns:
            The registered plugin class (for decorator use)
        """

        env_var_name = f"PLUGIN_{plugin_class.name.upper()}"
        env_var_value = os.getenv(env_var_name, "ENABLE").upper()
        print(f"DEBUG: Checking {env_var_name}={env_var_value}")
        if env_var_value == "DISABLE":
            print(f"INFO: Plugin {plugin_class.name} is disabled via {env_var_name}=DISABLE")
            return plugin_class 

        if issubclass(plugin_class, IngestPlugin):
            plugin_name = plugin_class.name
            cls._ingest_plugins[plugin_name] = plugin_class
        elif issubclass(plugin_class, QueryPlugin):
            plugin_name = plugin_class.name
            cls._query_plugins[plugin_name] = plugin_class
        else:
            raise TypeError(f"{plugin_class.__name__} is not a supported plugin type")
        
        return plugin_class
    
    @classmethod
    def get_plugin(cls, name: str) -> Optional[Type[IngestPlugin]]:
        """Get an ingestion plugin by name (backward compatibility).
        
        Args:
            name: Name of the plugin to get
            
        Returns:
            The plugin class if found, None otherwise
        """
        return cls._ingest_plugins.get(name)
    
    @classmethod
    def get_ingest_plugin(cls, name: str) -> Optional[Type[IngestPlugin]]:
        """Get an ingestion plugin by name.
        
        Args:
            name: Name of the plugin to get
            
        Returns:
            The plugin class if found, None otherwise
        """
        return cls._ingest_plugins.get(name)
    
    @classmethod
    def get_query_plugin(cls, name: str) -> Optional[Type['QueryPlugin']]:
        """Get a query plugin by name.
        
        Args:
            name: Name of the plugin to get
            
        Returns:
            The plugin class if found, None otherwise
        """
        return cls._query_plugins.get(name)
    
    @classmethod
    def list_plugins(cls) -> List[Dict[str, Any]]:
        """List all registered ingestion plugins (backward compatibility).
        
        Returns:
            List of plugin metadata
        """
        return cls.list_ingest_plugins()
    
    @classmethod
    def list_ingest_plugins(cls) -> List[Dict[str, Any]]:
        """List all registered ingestion plugins.
        
        Returns:
            List of plugin metadata
        """
        return [
            {
                "name": plugin_class.name,
                "description": plugin_class.description,
                "kind": plugin_class.kind,
                "supported_file_types": list(plugin_class.supported_file_types),
                "parameters": plugin_class().get_parameters()
            }
            for plugin_class in cls._ingest_plugins.values()
        ]
    
    @classmethod
    def list_query_plugins(cls) -> List[Dict[str, Any]]:
        """List all registered query plugins.
        
        Returns:
            List of plugin metadata
        """
        return [
            {
                "name": plugin_class.name,
                "description": plugin_class.description,
                "parameters": plugin_class().get_parameters()
            }
            for plugin_class in cls._query_plugins.values()
        ]
    
    @classmethod
    def get_plugin_for_file_type(cls, file_extension: str) -> List[Type[IngestPlugin]]:
        """Get plugins that support a given file extension.
        
        Args:
            file_extension: File extension (without the dot)
            
        Returns:
            List of plugin classes that support the file extension
        """
        return [
            plugin_class for plugin_class in cls._ingest_plugins.values()
            if file_extension.lower() in plugin_class.supported_file_types
        ]


class QueryPlugin(abc.ABC):
    """Base class for query plugins."""
    
    # Plugin metadata
    name: str = "base_query"
    description: str = "Base query plugin interface"
    
    @abc.abstractmethod
    def query(self, collection_id: int, query_text: str, **kwargs) -> List[Dict[str, Any]]:
        """Query a collection and return results.
        
        Args:
            collection_id: ID of the collection to query
            query_text: The query text
            **kwargs: Additional plugin-specific parameters
            
        Returns:
            A list of dictionaries, each containing:
                - similarity: Similarity score
                - data: The text content
                - metadata: A dictionary of metadata for the chunk
        """
        pass
    
    @abc.abstractmethod
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Get the parameters accepted by this plugin.
        
        Returns:
            A dictionary mapping parameter names to their specifications
        """
        pass


def discover_plugins(package_name: str = "plugins") -> None:
    """Discover and load plugins from a package.
    
    Args:
        package_name: Name of the package to search for plugins
    """
    package = importlib.import_module(package_name)
    
    for _, name, is_pkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        if not is_pkg:
            importlib.import_module(name)
        else:
            discover_plugins(name)
