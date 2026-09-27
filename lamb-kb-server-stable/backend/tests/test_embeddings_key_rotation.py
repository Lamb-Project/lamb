"""Rotating the global embeddings key reaches existing collections (#195)."""
import os
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from database.connection import effective_apikey, get_db
from routers.collections import router
from services.collections import CollectionsService


class EffectiveKey(unittest.TestCase):
    def test_default_or_empty_uses_the_current_global_key(self):
        for stored in ('', None, 'default'):
            with self.subTest(stored=stored), patch('config.get_embeddings_config', return_value={'apikey': 'sk-rotated'}):
                self.assertEqual(effective_apikey(stored), 'sk-rotated')

    def test_explicit_collection_key_is_kept(self):
        with patch('config.get_embeddings_config', return_value={'apikey': 'sk-rotated'}):
            self.assertEqual(effective_apikey('sk-explicit'), 'sk-explicit')


class CreateStoresNoDefaultKey(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(app)
        p = patch('dependencies.API_KEY', 'test-token'); p.start(); self.addCleanup(p.stop)
        e = patch.dict(os.environ, {'EMBEDDINGS_VENDOR': 'openai', 'EMBEDDINGS_MODEL': 'text-embedding-3-small',
                                    'EMBEDDINGS_APIKEY': 'sk-at-creation', 'EMBEDDINGS_ENDPOINT': 'https://api.example/v1'})
        e.start(); self.addCleanup(e.stop)

    def _create(self, apikey):
        captured = {}
        def create(collection, db):
            captured['apikey'] = collection.embeddings_model.apikey
            return {'id': 1, 'name': collection.name, 'owner': '7', 'visibility': 'private', 'description': '',
                    'creation_date': '2026-09-27T00:00:00', 'embeddings_model': {'vendor': 'openai', 'model': 'm'}}
        with patch.object(CollectionsService, 'create_collection', side_effect=create):
            self.client.post('/collections', headers={'Authorization': 'Bearer test-token'}, json={
                'name': 'rotation_probe', 'owner': '7', 'visibility': 'private',
                'embeddings_model': {'model': 'default', 'vendor': 'default', 'api_endpoint': 'default', 'apikey': apikey}})
        return captured.get('apikey')

    def test_default_key_is_not_frozen_into_the_collection(self):
        self.assertEqual(self._create('default'), '')

    def test_explicit_key_is_stored_as_given(self):
        self.assertEqual(self._create('sk-explicit'), 'sk-explicit')


class ResetScript(unittest.TestCase):
    def test_clears_only_keys_equal_to_the_retired_key(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.models import Base, Collection
        import reset_embedding_keys
        engine = create_engine('sqlite://'); Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        with Session() as s:
            s.add_all([Collection(name='old', owner='7', embeddings_model={'vendor': 'openai', 'model': 'm', 'apikey': 'sk-old'}),
                       Collection(name='own', owner='7', embeddings_model={'vendor': 'openai', 'model': 'm', 'apikey': 'sk-explicit'}),
                       Collection(name='local', owner='7', embeddings_model={'vendor': 'ollama', 'model': 'm', 'apikey': ''})])
            s.commit()
        with patch.object(reset_embedding_keys, 'SessionLocal', Session), patch.dict(os.environ, {'OLD_EMBEDDINGS_APIKEY': 'sk-old'}):
            reset_embedding_keys.main([])            # dry run changes nothing
            with Session() as s:
                self.assertEqual(s.query(Collection).filter_by(name='old').one().embeddings_model['apikey'], 'sk-old')
            reset_embedding_keys.main(['--apply'])
        with Session() as s:
            keys = {c.name: c.embeddings_model['apikey'] for c in s.query(Collection).all()}
        self.assertEqual(keys, {'old': '', 'own': 'sk-explicit', 'local': ''})
