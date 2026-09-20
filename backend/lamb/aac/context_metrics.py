"""Content-free context observations. Byte sizes are not token estimates or budgets."""
from __future__ import annotations

import json
import re
from typing import Any


def json_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def command_name(call: dict) -> str:
    """Only a validated command key, never arguments, IDs, URLs or source text."""
    from lamb.aac.liteshell.shell import prepare_command
    try:
        function = call['function']
        if function['name'] != 'execute_command':
            return 'unknown'
        command = json.loads(function['arguments'])['command']
        return prepare_command(command)[0]
    except (KeyError, ValueError, TypeError, AttributeError):
        return 'unknown'


def request_sizes(kwargs: dict) -> dict:
    messages = kwargs['messages']
    tools = kwargs.get('tools', [])
    names = {}
    results = []
    for index, message in enumerate(messages):
        for call in message.get('tool_calls', []) or []:
            names[call.get('id')] = command_name(call)
        if message.get('role') == 'tool':
            content = message.get('content', '')
            results.append({'message_index': index, 'command': names.get(message.get('tool_call_id'), 'unknown'),
                            'content_bytes': len(content.encode('utf-8')) if isinstance(content, str) else json_bytes(content)})
    return {
        'measurement_version': 1,
        'message_count': len(messages),
        'request_json_bytes': json_bytes(kwargs),
        'messages_json_bytes': json_bytes(messages),
        'system_prompt_bytes': len(messages[0].get('content', '').encode('utf-8')) if messages and messages[0].get('role') == 'system' else 0,
        'system_messages_json_bytes': sum(json_bytes(m) for m in messages if m.get('role') in ('system', 'developer')),
        'tool_schema_json_bytes': json_bytes(tools) if tools else 0,
        'tool_results': results,
        'tool_result_content_bytes': sum(r['content_bytes'] for r in results),
    }


def usage_counts(usage: Any) -> dict | None:
    if hasattr(usage, 'model_dump'):
        usage = usage.model_dump()
    if not isinstance(usage, dict):
        return None
    def count(value):
        return value if type(value) is int and value >= 0 else None
    result = {key: count(usage.get(key)) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    for group, key in [('prompt_tokens_details', 'cached_tokens'), ('completion_tokens_details', 'reasoning_tokens')]:
        details = usage.get(group)
        result[key] = count(details.get(key)) if isinstance(details, dict) else None
    return result if any(v is not None for v in result.values()) else None


def is_context_rejection(error: Exception) -> bool:
    # Do not relabel authentication, rate limits or arbitrary application errors.
    if getattr(error, 'status_code', None) not in (400, 413, 422):
        return False
    body = getattr(error, 'body', None)
    if isinstance(body, dict) and isinstance(body.get('error'), dict):
        body = body['error']
    code = body.get('code') if isinstance(body, dict) else getattr(error, 'code', None)
    if code in ('context_length_exceeded', 'context_window_exceeded', 'input_too_long'):
        return True
    message = body.get('message', '') if isinstance(body, dict) else (body if isinstance(body, str) else '')
    # Compatible local servers often provide only a message, without an error code.
    return bool(re.search(r'(maximum context length|context (?:length|window|size).{0,80}(?:exceed|too (?:large|long))|'
                          r'(?:exceed|too (?:large|long)).{0,80}context (?:length|window|size)|'
                          r'(?:input|prompt) (?:is )?too long|exceeds the available context size)', str(message), re.I))


class ContextSizeError(Exception):
    """Known provider context rejection with a safe, actionable user message."""
    code = 'context_length_exceeded'

    def __init__(self, state: dict | None = None):
        state = state or {}
        language = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language', 'en'))
        messages = {
            'en': 'This conversation is too large for the selected model. Open New conversation and provide a shorter request or fewer resources. Earlier actions may already have completed; check their status before repeating them. This history remains available.',
            'es': 'Esta conversación es demasiado grande para el modelo seleccionado. Abre Nueva conversación y utiliza una petición más corta o menos recursos. Puede que las acciones anteriores ya se hayan completado; comprueba su estado antes de repetirlas. Este historial sigue disponible.',
            'ca': 'Aquesta conversa és massa gran per al model seleccionat. Obre Nova conversa i fes una petició més curta o amb menys recursos. Pot ser que les accions anteriors ja s’hagin completat; comprova’n l’estat abans de repetir-les. Aquest historial continua disponible.',
            'eu': 'Elkarrizketa hau handiegia da hautatutako modeloarentzat. Ireki elkarrizketa berri bat eta erabili eskaera laburrago bat edo baliabide gutxiago. Aurreko ekintzak amaituta egon daitezke; egiaztatu haien egoera errepikatu aurretik. Historia hau erabilgarri dago oraindik.',
        }
        super().__init__(messages.get(language, messages['en']))
