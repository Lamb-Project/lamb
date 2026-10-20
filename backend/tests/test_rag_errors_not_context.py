"""RAG failures never reach the model as retrieved content."""
import asyncio
import json
from types import SimpleNamespace as N

from lamb.completions.pps.simple_augment import prompt_processor
from lamb.completions.rag import context_aware_rag, hierarchical_rag, simple_rag, single_file_rag

MESSAGES = [{'role': 'user', 'content': 'QUESTION_MARKER'}]


def assistant(**x):
    base = dict(id=1, name='a', owner='o@example.test', RAG_collections='', api_callback='{}', metadata='{}',
                system_prompt='', prompt_template='Context: {context}\n\nUser: {user_input}', RAG_Top_k=3)
    base.update(x)
    return N(**base)


def run(fn, a):
    result = fn(messages=MESSAGES, assistant=a, request={})
    return asyncio.run(result) if asyncio.iscoroutine(result) else result


def test_knowledge_base_rags_without_collections_return_an_error_not_context():
    for module in (simple_rag, context_aware_rag, hierarchical_rag):
        result = run(module.rag_processor, assistant())
        assert result['context'] == '' and 'No RAG collections' in result['error'], module.__name__
        prompt = prompt_processor({'messages': MESSAGES}, assistant(), result)[-1]['content']
        assert 'No RAG collections' not in prompt and 'QUESTION_MARKER' in prompt


def test_single_file_rag_failure_is_an_error_not_context():
    meta = json.dumps({'file_path': 'nobody/missing-file.md'})
    result = run(single_file_rag.rag_processor, assistant(api_callback=meta, metadata=meta))
    assert result['context'] == '' and result.get('error')
