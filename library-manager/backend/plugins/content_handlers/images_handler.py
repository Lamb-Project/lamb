"""Images capability handler: returns an image gallery JSON listing."""

from __future__ import annotations

from pathlib import Path

from plugins.content_handlers.capability import (
    Capability,
    CapabilityPayload,
    CapabilityRegistry,
    ContentHandler,
    HandlerUnavailable,
)

# Recognised image extensions. Kept here (not in a global registry) because
# the handler decides what counts as an image for *its* output.
_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif",
    ".svg", ".jpx", ".jp2", ".jxr", ".jb2", ".pnm",
}

_MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".svg": "image/svg+xml",
    ".jpx": "image/jpx",
    ".jp2": "image/jp2",
    ".jxr": "image/jxr",
    ".jb2": "image/jb2",
    ".pnm": "image/pnm",
}


@CapabilityRegistry.register
class ImagesHandler(ContentHandler):
    """Return an inventory of extracted images for a library item.

    The handler does NOT inline image bytes (which would blow up JSON
    payloads). Instead it lists each file plus its API URL — the actual
    bytes are served by a dedicated raw-file route registered in the
    capabilities router.
    """

    capability = Capability.IMAGES
    description = "Extracted image files (filename, URL and MIME type)."

    def get(self, item_path: Path) -> CapabilityPayload:
        """List ``content/images/*`` files.

        Args:
            item_path: Path to the item directory. The handler reads the
                organisation, library and item IDs from the item path
                segments to build the public URL.

        Returns:
            CapabilityPayload with ``mime="application/json"`` and ``body``
            shaped ``[{"filename": str, "url": str, "mime": str}, ...]``.

        Raises:
            HandlerUnavailable: If the ``content/images`` directory is
                missing or empty.
        """
        images_dir = item_path / "content" / "images"
        if not images_dir.is_dir():
            raise HandlerUnavailable(
                f"Item at {item_path} has no content/images directory"
            )

        image_files = sorted(
            f for f in images_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
        )
        if not image_files:
            raise HandlerUnavailable(
                f"Item at {item_path} has no image files"
            )

        # Item path: CONTENT_DIR/{org}/{library}/{item}
        item_id = item_path.name
        library_id = item_path.parent.name

        gallery = [
            {
                "filename": f.name,
                "url": (
                    f"/libraries/{library_id}/items/{item_id}"
                    f"/content/images/file/{f.name}"
                ),
                "mime": _MIME_MAP.get(f.suffix.lower(), "application/octet-stream"),
            }
            for f in image_files
        ]

        return CapabilityPayload(mime="application/json", body=gallery)
