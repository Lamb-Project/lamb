import importlib
import json
import logging
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger(__name__)

REQUIRED_PLUGIN_METADATA_KEYS = (
    "prompt_processor",
    "connector",
    "llm",
    "rag_processor",
)


def _get_compatible_rag(pps_name: str) -> Optional[List[str]]:
    """Load COMPATIBLE_RAG from the prompt processor module, if declared."""
    try:
        pps_module = importlib.import_module(f"lamb.completions.pps.{pps_name}")
    except ModuleNotFoundError:
        return None
    return getattr(pps_module, "COMPATIBLE_RAG", None)


def _validate_compatible_rag(metadata_dict: Dict[str, Any]) -> Optional[str]:
    """Ensure rag_processor and document_rag are compatible with prompt_processor."""
    pps_name = metadata_dict.get("prompt_processor", "")
    if not pps_name:
        return None

    compatible_rag = _get_compatible_rag(pps_name)
    if compatible_rag is None:
        return None

    rag_processor = metadata_dict.get("rag_processor", "")
    if rag_processor and rag_processor not in compatible_rag:
        return (
            f"rag_processor '{rag_processor}' not compatible with "
            f"prompt_processor '{pps_name}'. Compatible: {compatible_rag}"
        )

    document_rag = metadata_dict.get("document_rag", "")
    if document_rag and document_rag not in compatible_rag:
        return (
            f"document_rag '{document_rag}' not compatible with "
            f"prompt_processor '{pps_name}'. Compatible: {compatible_rag}"
        )

    return None


def validate_update_plugin_metadata(
    original_body: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate assistant plugin metadata for updates.

    Updates must provide complete plugin metadata so the backend never replaces a
    valid stored configuration with partial or blank data.

    Returns:
        Tuple[Optional[str], Optional[str]]: (normalized_metadata_json, error_message)
    """
    raw_metadata = original_body.get("metadata", original_body.get("api_callback"))

    if raw_metadata is None:
        return None, (
            "Assistant updates must include metadata with prompt_processor, "
            "connector, llm, and rag_processor."
        )

    if isinstance(raw_metadata, dict):
        metadata_dict = raw_metadata
    elif isinstance(raw_metadata, str):
        if not raw_metadata.strip():
            return None, "Assistant metadata cannot be empty on update."
        try:
            parsed = json.loads(raw_metadata)
        except json.JSONDecodeError as e:
            return None, f"Assistant metadata must be valid JSON: {str(e)}"
        if not isinstance(parsed, dict):
            return None, "Assistant metadata must be a JSON object."
        metadata_dict = parsed
    else:
        return None, "Assistant metadata must be a JSON string or object."

    missing_keys = [
        key for key in REQUIRED_PLUGIN_METADATA_KEYS
        if not isinstance(metadata_dict.get(key), str) or not metadata_dict.get(key).strip()
    ]
    if missing_keys:
        return None, (
            "Assistant metadata is incomplete. Missing required plugin fields: "
            + ", ".join(missing_keys)
        )

    # single_file_rag specific validation
    if metadata_dict.get("rag_processor") == "single_file_rag":
        has_library_ref = (
            metadata_dict.get("library_id") and metadata_dict.get("item_id")
        )
        has_file_ref = bool(metadata_dict.get("file_path"))
        if not has_library_ref and not has_file_ref:
            return None, (
                "single_file_rag requires either library_id + item_id "
                "or file_path in metadata"
            )
        if metadata_dict.get("library_id") and not metadata_dict.get("item_id"):
            return None, "single_file_rag: library_id requires item_id"
        if metadata_dict.get("item_id") and not metadata_dict.get("library_id"):
            return None, "single_file_rag: item_id requires library_id"

    # document_rag specific validation
    if metadata_dict.get("document_rag") == "library_file_rag":
        has_library_ref = (
            metadata_dict.get("library_id") and metadata_dict.get("item_id")
        )
        if not has_library_ref:
            return None, (
                "document_rag=library_file_rag requires library_id + item_id in metadata"
            )
        if metadata_dict.get("library_id") and not metadata_dict.get("item_id"):
            return None, "document_rag: library_id requires item_id"
        if metadata_dict.get("item_id") and not metadata_dict.get("library_id"):
            return None, "document_rag: item_id requires library_id"

    compatible_error = _validate_compatible_rag(metadata_dict)
    if compatible_error:
        return None, compatible_error

    normalized_metadata = json.dumps(metadata_dict)
    return normalized_metadata, None
