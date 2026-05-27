"""Content capability handlers for the Library Manager.

Each module in this package registers a :class:`ContentHandler` subclass via
``@CapabilityRegistry.register``. Handlers extract a specific capability
(text, pages, images, audio, transcript, ...) from a stored library item.

Auto-discovery: Files in this subpackage are picked up by the recursive
plugin discovery scan at startup. Dropping in a new ``my_handler.py`` is
sufficient to expose a new capability on items that have it.
"""
