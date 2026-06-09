"""Regression test for route ordering in the creator-interface library router.

The specific image-file route must be registered before the wildcard capability
route so that FastAPI matches it first. See library_router.py for the fix.

Run with:
    pytest backend/tests/test_library_route_ordering.py -v
"""


def test_image_file_route_registered_before_capability_route():
    """Verify route ordering prevents wildcard from catching image file requests.

    The specific route /content/images/file/{filename} must be registered before
    the wildcard route /content/{capability}, otherwise FastAPI will match the
    wildcard route first and return JSON instead of the image file.
    """
    from creator_interface.library_router import router

    image_file_idx = None
    capability_idx = None

    for idx, route in enumerate(router.routes):
        if not hasattr(route, "path"):
            continue
        if route.path.endswith("/content/images/file/{filename}"):
            image_file_idx = idx
        elif route.path.endswith("/content/{capability}"):
            capability_idx = idx

    assert image_file_idx is not None, "Image file route not found"
    assert capability_idx is not None, "Capability route not found"
    assert image_file_idx < capability_idx, (
        f"Image file route (index {image_file_idx}) must be registered before "
        f"capability route (index {capability_idx}) to prevent route matching conflicts"
    )
