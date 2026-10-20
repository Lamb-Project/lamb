import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from lamb.completions.rag.single_file_rag import rag_processor
from lamb.completions.pps.simple_augment import prompt_processor

@pytest.mark.parametrize('vision', [False, True])
def test_owned_file_context_has_real_title_without_fake_link_or_similarity(tmp_path, vision):
    document = tmp_path / 'grounding.txt'
    document.write_text('Exact document text')
    assistant = SimpleNamespace(id=1, owner='teacher@example.invalid',
        metadata=json.dumps({'file_path':'7/grounding.txt','capabilities':{'vision':vision}}),
        system_prompt='', prompt_template='{context}\nQuestion: {user_input}')
    with patch('lamb.uploaded_files.document_for_owner', return_value=document):
        context = rag_processor([], assistant)
    content = [{'type':'text','text':'Quote the document'}] if vision else 'Quote the document'
    result = prompt_processor({'messages':[{'role':'user','content':content}]}, assistant, context)
    rendered = result[-1]['content'][0]['text'] if vision else result[-1]['content']
    assert context['context'] == 'Exact document text'
    assert '1. grounding.txt' in rendered
    assert 'Unknown' not in rendered and ']()' not in rendered and 'similarity:' not in rendered


def test_kb_sources_keep_their_actual_link_and_similarity():
    from lamb.completions.pps.simple_augment import _format_sources
    assert '[Chapter](https://example.invalid/chapter) (similarity: 0.812)' in _format_sources([
        {'title':'Chapter','url':'https://example.invalid/chapter','similarity':0.812}])
