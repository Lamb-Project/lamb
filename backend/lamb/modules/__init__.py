"""LAMB modules package — pluggable LTI activity types.

This package follows the contract of the #277 ActivityModule framework so
modules can be migrated into `discover_modules()` once that lands on main.
"""


def discover_modules():
    """Scan for modules that export a `module` object.

    For now only `workshop` is registered here (route-A independent module).
    When #277 lands, this is replaced by the framework's directory scanner.
    """
    modules = {}
    try:
        from lamb.modules.workshop import module as workshop_module
        modules[workshop_module.name] = workshop_module
    except Exception:
        pass
    return modules


def get_module(name: str):
    """Return a registered module by name, or None."""
    return discover_modules().get(name)
