import importlib
from pathlib import Path

# Registry for LTI Activity Modules
_registry = {}

def register_module(module):
    _registry[module.name] = module

def get_module(name: str):
    return _registry.get(name)

def get_all_modules() -> list:
    return list(_registry.values())

def discover_modules():
    """Auto-discover modules on startup by importing their __init__.py files."""
    modules_dir = Path(__file__).parent
    for module_dir in modules_dir.iterdir():
        if module_dir.is_dir() and (module_dir / "__init__.py").exists():
            mod = importlib.import_module(f"lamb.modules.{module_dir.name}")
            if hasattr(mod, 'module'):
                register_module(mod.module)
