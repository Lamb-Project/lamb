"""
Prompt Template Loader for AI Rubric Generation

Loads multilingual prompt templates from markdown files with language fallback support.
"""

import os
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache for loaded templates to avoid repeated file I/O
_template_cache: Dict[str, str] = {}

# Supported languages
SUPPORTED_LANGUAGES = ['en', 'es', 'eu', 'ca']
DEFAULT_LANGUAGE = 'en'

# Prompt templates directory
PROMPTS_DIR = Path(__file__).parent / 'prompts'


def load_prompt_template(template_name: str, language: str = 'en') -> Optional[str]:
    """
    Load a prompt template from markdown file with language fallback.
    
    Args:
        template_name: Template name (e.g., 'rubric_generation')
        language: Language code (en, es, eu, ca)
        
    Returns:
        Template content as string, or None if not found
        
    Examples:
        >>> template = load_prompt_template('rubric_generation', 'es')
        >>> # Tries: rubric_generation_es.md -> rubric_generation_en.md
    """
    # Normalize language code
    language = language.lower() if language else DEFAULT_LANGUAGE
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language '{language}', falling back to English")
        language = DEFAULT_LANGUAGE
    
    # Try to load from cache first
    cache_key = f"{template_name}_{language}"
    if cache_key in _template_cache:
        logger.debug(f"Template loaded from cache: {cache_key}")
        return _template_cache[cache_key]
    
    # Try language-specific template first
    template_path = PROMPTS_DIR / f"{template_name}_{language}.md"
    
    if template_path.exists():
        try:
            content = template_path.read_text(encoding='utf-8')
            _template_cache[cache_key] = content
            logger.info(f"Loaded template: {template_path.name}")
            return content
        except Exception as e:
            logger.error(f"Error reading template {template_path}: {e}")
    
    # Fallback to English if language-specific template not found
    if language != DEFAULT_LANGUAGE:
        logger.info(f"Template not found for language '{language}', falling back to English")
        fallback_path = PROMPTS_DIR / f"{template_name}_{DEFAULT_LANGUAGE}.md"
        
        if fallback_path.exists():
            try:
                content = fallback_path.read_text(encoding='utf-8')
                # Cache under both keys for efficiency
                _template_cache[cache_key] = content
                _template_cache[f"{template_name}_{DEFAULT_LANGUAGE}"] = content
                logger.info(f"Loaded fallback template: {fallback_path.name}")
                return content
            except Exception as e:
                logger.error(f"Error reading fallback template {fallback_path}: {e}")
    
    logger.error(f"Template not found: {template_name} (tried {language}, then {DEFAULT_LANGUAGE})")
    return None


def render_template(template: str, variables: Dict[str, str]) -> str:
    """
    Replace template variables with actual values.
    
    Args:
        template: Template content with placeholders like {user_prompt}
        variables: Dictionary of variable names to values
        
    Returns:
        Rendered template with variables replaced
        
    Example:
        >>> template = "User asked: {user_prompt}"
        >>> rendered = render_template(template, {'user_prompt': 'Create a rubric'})
        >>> # Returns: "User asked: Create a rubric"
    """
    rendered = template
    
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        rendered = rendered.replace(placeholder, str(value))
    
    return rendered


def get_rubric_generation_prompt(user_prompt: str, language: str = 'en') -> Optional[str]:
    """
    Get the complete rubric generation prompt for a given language.
    
    Args:
        user_prompt: User's natural language request for rubric creation
        language: Language code (en, es, eu, ca)
        
    Returns:
        Rendered prompt ready to send to LLM, or None if template not found
    """
    template = load_prompt_template('rubric_generation', language)
    
    if not template:
        logger.error(f"Could not load rubric generation template for language '{language}'")
        return None
    
    # Render template with user's prompt
    variables = {
        'user_prompt': user_prompt,
        'language': language
    }
    
    rendered_prompt = render_template(template, variables)
    
    logger.debug(f"Rendered prompt for language '{language}' (length: {len(rendered_prompt)} chars)")
    
    return rendered_prompt


def clear_template_cache():
    """
    Clear the template cache. Useful for development/testing.
    """
    global _template_cache
    _template_cache.clear()
    logger.info("Template cache cleared")


def list_available_templates() -> Dict[str, list]:
    """
    List all available prompt templates organized by name and language.
    
    Returns:
        Dictionary of template names to list of available languages
        
    Example:
        >>> templates = list_available_templates()
        >>> # Returns: {'rubric_generation': ['en', 'es', 'eu', 'ca']}
    """
    if not PROMPTS_DIR.exists():
        return {}
    
    templates = {}
    
    for file_path in PROMPTS_DIR.glob('*.md'):
        # Extract template name and language
        # Format: template_name_lang.md (e.g., rubric_generation_en.md)
        name_parts = file_path.stem.rsplit('_', 1)
        if len(name_parts) == 2:
            template_name, lang = name_parts
            if lang in SUPPORTED_LANGUAGES:
                if template_name not in templates:
                    templates[template_name] = []
                templates[template_name].append(lang)
    
    return templates


# Validate templates exist on module load
def _validate_templates():
    """
    Validate that required templates exist. Log warnings for missing templates.
    """
    required_templates = ['rubric_generation']
    
    available = list_available_templates()
    
    for template_name in required_templates:
        if template_name not in available:
            logger.warning(f"Required template '{template_name}' not found in {PROMPTS_DIR}")
        elif DEFAULT_LANGUAGE not in available[template_name]:
            logger.warning(f"Default language '{DEFAULT_LANGUAGE}' not available for template '{template_name}'")
        else:
            logger.info(f"Template '{template_name}' available in languages: {available[template_name]}")


# Run validation when module is imported
try:
    _validate_templates()
except Exception as e:
    logger.error(f"Error validating templates: {e}")

