"""
Moodle Augment Prompt Processor

This prompt processor extends simple_augment to automatically inject Moodle user context
into prompts. It adds support for the {moodle_info_for_user} template variable.

Usage:
1. Set an assistant's prompt_processor to "moodle_augment" in metadata
2. Use {moodle_info_for_user} in the prompt template to inject course information
3. Optionally include user_id in the request metadata for user identification

Example prompt template:
    You are a helpful academic assistant.
    
    The student is enrolled in the following courses:
    {moodle_info_for_user}
    
    Based on this context, help the student with their question:
    {user_input}
    
    Additional context from knowledge base:
    {context}

User ID Extraction Priority:
1. request.metadata.user_id - Explicitly provided user ID
2. request.metadata.lti_user_id - LTI launch user ID
3. request.metadata.lis_person_sourcedid - LTI person source ID
4. request.metadata.email - User email
5. "default" - Fallback if no user identification is available
"""

from typing import Dict, Any, List, Optional
from lamb.lamb_classes import Assistant
import json
import asyncio
import logging
from utils.timelog import Timelog

logger = logging.getLogger(__name__)


def _has_vision_capability(assistant: Assistant) -> bool:
    """
    Check if the assistant has vision capabilities enabled.

    Args:
        assistant: Assistant object with metadata

    Returns:
        bool: True if vision is enabled, False otherwise
    """
    if not assistant:
        return False

    metadata_str = getattr(assistant, 'metadata', None) or getattr(assistant, 'api_callback', None)
    if not metadata_str:
        return False

    try:
        metadata = json.loads(metadata_str)
        capabilities = metadata.get('capabilities', {})
        return capabilities.get('vision', False)
    except (json.JSONDecodeError, AttributeError):
        return False


def _extract_user_id(request: Dict[str, Any]) -> str:
    """
    Extract user ID from request metadata.
    
    Attempts to find user identification in the following order:
    1. request.metadata.user_id - Explicitly provided
    2. request.metadata.lti_user_id - From LTI launch
    3. request.metadata.lis_person_sourcedid - LTI person ID
    4. request.metadata.email - User email
    5. Falls back to "default"
    
    Args:
        request: The incoming request dictionary
        
    Returns:
        str: User ID or "default" if not found
    """
    metadata = request.get('metadata', {})
    
    # Try various user identification fields
    user_id = (
        metadata.get('user_id') or
        metadata.get('lti_user_id') or
        metadata.get('lis_person_sourcedid') or
        metadata.get('email') or
        metadata.get('user') or
        None
    )
    
    if user_id:
        logger.info(f"Extracted user ID from request metadata: {user_id}")
        return str(user_id)
    
    logger.info("No user ID found in request metadata, using 'default'")
    return "default"


def _get_moodle_courses_sync(user_id: str) -> str:
    """
    Synchronously get Moodle courses for a user.
    
    This is a wrapper that calls the async Moodle tool synchronously.
    
    Args:
        user_id: The user identifier
        
    Returns:
        JSON string with course information
    """
    try:
        from lamb.completions.tools.moodle import get_moodle_courses
        
        # Run the async function in an event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(get_moodle_courses(user_id))
        finally:
            loop.close()
        
        return result
    except Exception as e:
        logger.error(f"Error getting Moodle courses for user {user_id}: {e}")
        return json.dumps({
            "user_id": user_id,
            "courses": [],
            "error": str(e),
            "success": False
        })


def _format_moodle_context(moodle_json: str) -> str:
    """
    Format Moodle course data into a human-readable string for the LLM.
    
    Args:
        moodle_json: JSON string from the Moodle tool
        
    Returns:
        Formatted string describing the user's courses
    """
    try:
        data = json.loads(moodle_json)
        
        if not data.get('success', False):
            error = data.get('error', 'Unknown error')
            return f"(Unable to retrieve course information: {error})"
        
        courses = data.get('courses', [])
        
        if not courses:
            return "(No enrolled courses found)"
        
        # Format course list
        course_lines = []
        for course in courses:
            name = course.get('name', 'Unknown Course')
            shortname = course.get('shortname', '')
            category = course.get('category', '')
            role = course.get('role', 'student')
            
            line = f"- {name}"
            if shortname:
                line += f" ({shortname})"
            if category:
                line += f" - {category}"
            if role and role != 'student':
                line += f" [Role: {role}]"
            
            course_lines.append(line)
        
        course_count = len(courses)
        header = f"Enrolled in {course_count} course{'s' if course_count != 1 else ''}:"
        
        return header + "\n" + "\n".join(course_lines)
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Moodle JSON: {e}")
        return "(Error parsing course information)"


def prompt_processor(
    request: Dict[str, Any],
    assistant: Optional[Assistant] = None,
    rag_context: Optional[Dict[str, Any]] = None
) -> List[Dict[str, str]]:
    """
    Moodle-aware prompt processor that extends simple_augment.
    
    Supports all placeholders from simple_augment plus:
    - {moodle_info_for_user}: Injects the user's Moodle course information
    
    The user is identified from request metadata (user_id, lti_user_id, email, etc.)
    
    Args:
        request: The incoming request dictionary with messages and optional metadata
        assistant: The assistant configuration object
        rag_context: Optional RAG context dictionary
        
    Returns:
        List of processed message dictionaries
    """
    Timelog("moodle_augment: Starting prompt processing", 2)
    
    messages = request.get('messages', [])
    if not messages:
        return messages

    # Get the last user message
    last_message = messages[-1]['content']

    # Create new messages list
    processed_messages = []

    if assistant:
        # Add system message from assistant if available
        if assistant.system_prompt:
            processed_messages.append({
                "role": "system",
                "content": assistant.system_prompt
            })
        
        # Add previous messages except the last one
        processed_messages.extend(messages[:-1])
        
        # Process the last message using the prompt template
        if assistant.prompt_template:
            # Check if template uses Moodle placeholder
            uses_moodle = "{moodle_info_for_user}" in assistant.prompt_template
            
            # Get Moodle context if needed
            moodle_context = ""
            if uses_moodle:
                user_id = _extract_user_id(request)
                Timelog(f"moodle_augment: Fetching Moodle courses for user: {user_id}", 2)
                moodle_json = _get_moodle_courses_sync(user_id)
                moodle_context = _format_moodle_context(moodle_json)
                Timelog(f"moodle_augment: Moodle context generated", 2)
            
            # Check if assistant has vision capabilities
            has_vision = _has_vision_capability(assistant)

            if isinstance(last_message, list) and has_vision:
                # Multimodal content with vision-enabled assistant
                augmented_content = []

                # Extract text parts for {user_input} substitution
                text_parts = []
                for item in last_message:
                    if item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))

                user_input_text = ' '.join(text_parts)

                # Create augmented text content with template
                Timelog(f"User message: {user_input_text}", 2)
                augmented_text = assistant.prompt_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")

                # Add Moodle context if template uses it
                if uses_moodle:
                    augmented_text = augmented_text.replace("{moodle_info_for_user}", moodle_context)

                # Add RAG context if available
                if rag_context:
                    context = json.dumps(rag_context)
                    augmented_text = augmented_text.replace("{context}", "\n\n" + context + "\n\n")
                else:
                    augmented_text = augmented_text.replace("{context}", "")

                # Add the augmented text as first element
                augmented_content.append({
                    "type": "text",
                    "text": augmented_text
                })

                # Preserve all non-text elements (images, etc.)
                for item in last_message:
                    if item.get('type') != 'text':
                        augmented_content.append(item)

                # Add processed multimodal message
                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": augmented_content
                })

            else:
                # Text-only processing (legacy format or vision-disabled assistant)
                if isinstance(last_message, list):
                    # Extract text parts only (strips images for security)
                    text_parts = []
                    for item in last_message:
                        if item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                    user_input_text = ' '.join(text_parts)
                else:
                    # Legacy string format
                    user_input_text = str(last_message)

                # Replace placeholders in template
                Timelog(f"User message: {user_input_text}", 2)
                prompt = assistant.prompt_template.replace("{user_input}", "\n\n" + user_input_text + "\n\n")

                # Add Moodle context if template uses it
                if uses_moodle:
                    prompt = prompt.replace("{moodle_info_for_user}", moodle_context)

                # Add RAG context if available
                if rag_context:
                    context = json.dumps(rag_context)
                    prompt = prompt.replace("{context}", "\n\n" + context + "\n\n")
                else:
                    prompt = prompt.replace("{context}", "")

                # Add processed text message
                processed_messages.append({
                    "role": messages[-1]['role'],
                    "content": prompt
                })
        else:
            # If no template, use original message
            processed_messages.append(messages[-1])
        
        Timelog("moodle_augment: Prompt processing complete", 2)
        return processed_messages
    
    # If no assistant provided, return original messages
    return messages
