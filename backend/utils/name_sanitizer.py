"""
Name Sanitization Utility for LAMB

Provides functions to sanitize and validate names for Assistants and Knowledge Bases.
Ensures names conform to the naming rules:
- Only ASCII letters, numbers, and underscores
- Spaces are converted to underscores
- Converted to lowercase
- Max 50 characters
- Handles duplicates by appending _2, _3, etc.
"""

import re
from typing import Tuple, Optional, Callable
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="MAIN")


def sanitize_name(
    name: str, 
    max_length: int = 50,
    to_lowercase: bool = True
) -> Tuple[str, bool]:
    """
    Sanitize a name for use in Assistant or KB creation.
    
    Rules:
    - Only ASCII letters (a-z, A-Z), numbers (0-9), spaces, and underscores (_)
    - Spaces are converted to underscores
    - Optionally convert to lowercase (default: True)
    - Remove special characters
    - Collapse multiple underscores
    - Remove leading/trailing underscores
    - Enforce maximum length
    - Return "untitled" if result is empty
    
    Args:
        name: Original name from user
        max_length: Maximum length for sanitized name (default: 50)
        to_lowercase: Whether to convert to lowercase (default: True)
    
    Returns:
        Tuple of (sanitized_name, was_modified)
    
    Examples:
        >>> sanitize_name("My Assistant")
        ('my_assistant', True)
        
        >>> sanitize_name("Test@Name!")
        ('testname', True)
        
        >>> sanitize_name("My  Multiple   Spaces")
        ('my_multiple_spaces', True)
        
        >>> sanitize_name("test_123")
        ('test_123', False)
    """
    if not name:
        return "untitled", True
    
    original_name = name
    
    # 1. Trim whitespace
    name = name.strip()
    
    # 2. Convert to lowercase if requested
    if to_lowercase:
        name = name.lower()
    
    # 3. Replace spaces with underscores
    name = re.sub(r'\s+', '_', name)
    
    # 4. Remove all characters except ASCII letters, numbers, and underscores
    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
    
    # 5. Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    
    # 6. Remove leading/trailing underscores
    name = name.strip('_')
    
    # 7. Enforce maximum length
    if len(name) > max_length:
        name = name[:max_length]
        # Remove trailing underscore if truncation created one
        name = name.rstrip('_')
    
    # 8. Fallback if empty after sanitization
    if not name:
        name = "untitled"
    
    was_modified = (name != original_name)
    return name, was_modified


def sanitize_with_duplicate_check(
    name: str,
    check_exists_fn: Callable[[str], bool],
    max_length: int = 50,
    to_lowercase: bool = True
) -> Tuple[str, bool]:
    """
    Sanitize a name and ensure it's unique by appending _2, _3, etc. if duplicates exist.
    
    Args:
        name: Original name from user
        check_exists_fn: Function that takes a name and returns True if it exists
        max_length: Maximum length for sanitized name (default: 50)
        to_lowercase: Whether to convert to lowercase (default: True)
    
    Returns:
        Tuple of (unique_sanitized_name, was_modified)
    
    Examples:
        >>> def check_fn(n): return n in ['test_assistant', 'test_assistant_2']
        >>> sanitize_with_duplicate_check("Test Assistant", check_fn)
        ('test_assistant_3', True)
    """
    # First, sanitize the name
    sanitized_name, was_modified = sanitize_name(name, max_length, to_lowercase)
    
    # Check if it exists
    if not check_exists_fn(sanitized_name):
        # Name is unique, return as-is
        return sanitized_name, was_modified
    
    # Name exists, need to append counter
    base_name = sanitized_name
    counter = 2
    
    # Reserve space for counter suffix (e.g., "_999" = 4 chars)
    # Max counter we support is 999, so reserve 4 chars
    max_base_length = max_length - 4
    if len(base_name) > max_base_length:
        base_name = base_name[:max_base_length].rstrip('_')
    
    # Try incrementing counter until we find a unique name
    while counter < 1000:  # Safety limit
        candidate_name = f"{base_name}_{counter}"
        
        if not check_exists_fn(candidate_name):
            logger.info(f"Name '{sanitized_name}' exists, using '{candidate_name}' instead")
            return candidate_name, True  # Always modified when counter is added
        
        counter += 1
    
    # If we somehow exhaust 1000 attempts, add timestamp
    import time
    timestamp_suffix = str(int(time.time()) % 10000)  # Last 4 digits of timestamp
    final_name = f"{base_name}_{timestamp_suffix}"
    logger.warning(f"Exhausted counter attempts, using timestamp: {final_name}")
    return final_name, True


def validate_sanitized_name(name: str) -> bool:
    """
    Validate that a name is already in sanitized format.
    
    Args:
        name: Name to validate
    
    Returns:
        True if name is valid (already sanitized), False otherwise
    
    Examples:
        >>> validate_sanitized_name("my_assistant")
        True
        
        >>> validate_sanitized_name("My Assistant")
        False
        
        >>> validate_sanitized_name("test@name")
        False
    """
    if not name:
        return False
    
    # Check pattern: only lowercase letters, numbers, and underscores
    if not re.match(r'^[a-z0-9_]+$', name):
        return False
    
    # Check for multiple consecutive underscores
    if '__' in name:
        return False
    
    # Check for leading/trailing underscores
    if name.startswith('_') or name.endswith('_'):
        return False
    
    # Check length
    if len(name) > 50:
        return False
    
    return True


def sanitize_assistant_name_with_prefix(
    user_name: str,
    user_id: int,
    check_exists_fn: Callable[[str], bool],
    max_length: int = 50
) -> Tuple[str, str, bool]:
    """
    Sanitize an assistant name and add user ID prefix.
    
    The final format is: {user_id}_{sanitized_name}
    If duplicate exists, appends counter: {user_id}_{sanitized_name}_2
    
    Args:
        user_name: Original name from user
        user_id: User ID to prefix
        check_exists_fn: Function that checks if prefixed name exists
        max_length: Maximum length for sanitized name (default: 50)
    
    Returns:
        Tuple of (prefixed_name, sanitized_base_name, was_modified)
    
    Examples:
        >>> def check_fn(n): return n == '1_my_assistant'
        >>> sanitize_assistant_name_with_prefix("My Assistant", 1, check_fn)
        ('1_my_assistant_2', 'my_assistant', True)
    """
    # Sanitize the base name first
    sanitized_base, was_modified = sanitize_name(user_name, max_length, to_lowercase=True)
    
    # Calculate max length for base name considering prefix
    # Format: {user_id}_{base_name}
    # Reserve space for user_id + underscore + potential counter (_999)
    prefix_length = len(str(user_id)) + 1  # "123_"
    counter_reserve = 4  # "_999"
    max_base_length = max_length - prefix_length - counter_reserve
    
    # Truncate base name if needed
    if len(sanitized_base) > max_base_length:
        sanitized_base = sanitized_base[:max_base_length].rstrip('_')
        was_modified = True
    
    # Create prefixed name
    prefixed_name = f"{user_id}_{sanitized_base}"
    
    # Check for duplicates and add counter if needed
    if check_exists_fn(prefixed_name):
        counter = 2
        while counter < 1000:
            candidate = f"{user_id}_{sanitized_base}_{counter}"
            if not check_exists_fn(candidate):
                logger.info(f"Assistant name '{prefixed_name}' exists, using '{candidate}'")
                return candidate, sanitized_base, True
            counter += 1
        
        # Fallback to timestamp if counter exhausted
        import time
        timestamp_suffix = str(int(time.time()) % 10000)
        final_name = f"{user_id}_{sanitized_base}_{timestamp_suffix}"
        logger.warning(f"Exhausted counter for assistant, using timestamp: {final_name}")
        return final_name, sanitized_base, True
    
    return prefixed_name, sanitized_base, was_modified


def sanitize_kb_name_with_duplicate_check(
    name: str,
    user_id: int,
    org_id: int,
    check_exists_fn: Callable[[str, int, int], bool],
    max_length: int = 50
) -> Tuple[str, bool]:
    """
    Sanitize a Knowledge Base name and ensure uniqueness per user+org.
    
    Args:
        name: Original name from user
        user_id: Owner user ID
        org_id: Organization ID
        check_exists_fn: Function(name, user_id, org_id) that checks existence
        max_length: Maximum length for sanitized name
    
    Returns:
        Tuple of (unique_sanitized_name, was_modified)
    """
    # Sanitize the base name
    sanitized_name, was_modified = sanitize_name(name, max_length, to_lowercase=True)
    
    # Check if it exists for this user+org
    if not check_exists_fn(sanitized_name, user_id, org_id):
        return sanitized_name, was_modified
    
    # Name exists, append counter
    base_name = sanitized_name
    max_base_length = max_length - 4  # Reserve for _999
    if len(base_name) > max_base_length:
        base_name = base_name[:max_base_length].rstrip('_')
    
    counter = 2
    while counter < 1000:
        candidate = f"{base_name}_{counter}"
        if not check_exists_fn(candidate, user_id, org_id):
            logger.info(f"KB name '{sanitized_name}' exists, using '{candidate}'")
            return candidate, True
        counter += 1
    
    # Fallback to timestamp
    import time
    timestamp_suffix = str(int(time.time()) % 10000)
    final_name = f"{base_name}_{timestamp_suffix}"
    logger.warning(f"Exhausted KB counter, using timestamp: {final_name}")
    return final_name, True

