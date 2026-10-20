"""Each RAG configuration states what it needs (#335)."""
import json

from lamb.services.assistant_config_rules import config_errors, rule_inputs

FULL = 'Context: {context}\n\nUser: {user_input}'


def meta(rag, **extra):
    return json.dumps({'prompt_processor': 'simple_augment', 'connector': 'openai', 'llm': 'm', 'rag_processor': rag, **extra})


def test_no_rag_needs_user_input_or_an_empty_template_and_never_context():
    assert config_errors(meta('no_rag'), '', '') == []
    assert config_errors(meta('no_rag'), 'Answer briefly: {user_input}', '') == []
    assert config_errors(meta('no_rag'), FULL, '') == []
    assert '{user_input}' in config_errors(meta('no_rag'), 'Be kind.', '')[0]


def test_knowledge_base_rags_need_both_placeholders_and_a_knowledge_base():
    for rag in ('simple_rag', 'context_aware_rag', 'hierarchical_rag'):
        assert config_errors(meta(rag), FULL, '3,4') == []
        errors = config_errors(meta(rag), '', '')
        assert len(errors) == 3 and any('{context}' in e for e in errors) and any('knowledge base' in e for e in errors)
        assert [e for e in config_errors(meta(rag), 'User: {user_input}', '3') if '{context}' in e]


def test_single_file_and_rubric_rags_need_their_source():
    assert config_errors(meta('single_file_rag', file_path='u/1/notes.md'), FULL, '') == []
    assert config_errors(meta('single_file_rag'), FULL, '') == ['Single file RAG needs a file.']
    assert config_errors(meta('rubric_rag', rubric_id='7'), FULL, '') == []
    assert config_errors(meta('rubric_rag'), FULL, '') == ['Rubric RAG needs a rubric.']


def test_custom_prompt_processors_and_unknown_rags_are_not_checked():
    assert config_errors(json.dumps({'prompt_processor': 'custom', 'rag_processor': 'simple_rag'}), '', '') == []
    assert config_errors(meta('future_rag'), '', '') == []


def test_legacy_metadata_defaults_do_not_count_as_a_configuration_change():
    legacy = json.dumps({'rag_processor': 'simple_rag'})
    filled = meta('simple_rag')
    assert rule_inputs(legacy, '', '') == rule_inputs(filled, '', '')
    assert rule_inputs(filled, '', '') != rule_inputs(filled, 'User: {user_input}', '')
