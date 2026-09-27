"""What each RAG configuration needs before an assistant can work (#335).

Applies to the standard simple_augment prompt processor, which inserts the retrieved text only
where {context} appears and the student's message only where {user_input} appears. An empty
template is valid without RAG: the message then passes unchanged. Custom prompt processors
define their own template rules and are not checked here.
"""
import json

KB_RAG = frozenset({'simple_rag', 'context_aware_rag', 'hierarchical_rag'})
CONTEXT_RAG = KB_RAG | {'single_file_rag', 'rubric_rag'}
NAMES = {'simple_rag': 'Simple RAG', 'context_aware_rag': 'Context-aware RAG', 'hierarchical_rag': 'Hierarchical RAG',
         'single_file_rag': 'Single file RAG', 'rubric_rag': 'Rubric RAG'}


def _metadata(raw):
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def rule_inputs(metadata, prompt_template, rag_collections):
    """The values the rules depend on; an update is checked only when these change."""
    meta = _metadata(metadata)
    return (meta.get('prompt_processor') or 'simple_augment', meta.get('rag_processor') or 'no_rag', prompt_template or '',
            (rag_collections or '').strip(), meta.get('file_path') or '', str(meta.get('rubric_id') or ''))


def config_errors(metadata, prompt_template, rag_collections):
    """Human-readable problems with this configuration; empty when it can work."""
    processor, rag, template, collections, file_path, rubric = rule_inputs(metadata, prompt_template, rag_collections)
    if processor != 'simple_augment':
        return []
    errors = []
    if rag == 'no_rag':
        if template.strip() and '{user_input}' not in template:
            errors.append("The prompt template needs {user_input}, where the student's message goes "
                          "(or leave the template empty).")
        return errors
    if rag not in CONTEXT_RAG:
        return errors
    name = NAMES[rag]
    if '{user_input}' not in template:
        errors.append(f"{name} needs {{user_input}} in the prompt template, where the student's message goes.")
    if '{context}' not in template:
        errors.append(f"{name} needs {{context}} in the prompt template, where the retrieved content goes.")
    if rag in KB_RAG and not collections:
        errors.append(f"{name} needs at least one knowledge base.")
    if rag == 'single_file_rag' and not file_path:
        errors.append("Single file RAG needs a file.")
    if rag == 'rubric_rag' and not rubric:
        errors.append("Rubric RAG needs a rubric.")
    return errors
