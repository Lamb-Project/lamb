"""Assistants created with minimal metadata can be edited partially (#335)."""
import json
from unittest.mock import patch

from creator_interface import assistant_router as ar


class Resolver:
    def __init__(self, owner):
        self.owner = owner

    def resolve_model_for_completion(self, model=None, provider=None):
        return {'provider': provider or 'openai', 'model': model or 'gpt-4.1-mini'}


def required(meta):
    return all(isinstance(meta.get(k), str) and meta[k].strip() for k in ar.REQUIRED_PLUGIN_METADATA_KEYS)


def test_minimal_create_gets_complete_metadata_from_the_organization():
    with patch.object(ar, 'OrganizationConfigResolver', Resolver):
        for raw in ('', None, 'not json', '[]', '{}'):
            meta = json.loads(ar._ensure_metadata_defaults(raw, 'owner@example.test'))
            assert required(meta) and meta == {'prompt_processor': 'simple_augment', 'rag_processor': 'no_rag',
                                                'connector': 'openai', 'llm': 'gpt-4.1-mini'}
        kept = ar._ensure_metadata_defaults({'rag_processor': 'simple_rag', 'connector': 'ollama', 'llm': 'qwen'}, 'o@x')
        assert kept['rag_processor'] == 'simple_rag' and kept['connector'] == 'ollama' and kept['llm'] == 'qwen'


def test_unresolvable_organization_still_gets_the_connector_default():
    class Broken(Resolver):
        def resolve_model_for_completion(self, *a):
            raise ValueError('no model')
    with patch.object(ar, 'OrganizationConfigResolver', Broken):
        meta = json.loads(ar._ensure_metadata_defaults('', 'owner@example.test'))
    assert meta['connector'] == 'openai' and meta['rag_processor'] == 'no_rag' and 'llm' not in meta


def test_partial_metadata_merges_over_stored_and_complete_metadata_replaces():
    stored = json.dumps({'prompt_processor': 'simple_augment', 'connector': 'openai', 'llm': 'gpt-4.1-mini',
                         'rag_processor': 'simple_rag', 'capabilities': {'vision': False}})
    merged = json.loads(ar._merge_partial_metadata(stored, json.dumps({'llm': 'gpt-4.1'})))
    assert merged['llm'] == 'gpt-4.1' and merged['rag_processor'] == 'simple_rag' and merged['capabilities'] == {'vision': False}
    full = json.dumps({'prompt_processor': 'simple_augment', 'connector': 'openai', 'llm': 'gpt-4.1', 'rag_processor': 'no_rag'})
    assert ar._merge_partial_metadata(stored, full) == full
    assert ar._merge_partial_metadata(stored, {'llm': 'x'})['connector'] == 'openai'
    assert ar._merge_partial_metadata(stored, 'not json') == 'not json'
