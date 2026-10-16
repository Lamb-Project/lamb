"""LAMB modules package — pluggable LTI activity types.

A minimal registry used until the #277 Activity Module System is available on
this line (upstream it lives on `lamb-1.0-alpha`, not on main/dev). See
Documentation/workshop-design.md §3.
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
