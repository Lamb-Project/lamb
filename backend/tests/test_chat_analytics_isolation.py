"""Exercise analytics SQL against a real SQLite database with colliding model IDs."""
import json
import sqlite3
import unittest
from unittest.mock import Mock
from lamb.services.chat_analytics_service import ChatAnalyticsService


class AnalyticsIsolation(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE chat(id TEXT,user_id TEXT,title TEXT,created_at INTEGER,updated_at INTEGER,chat TEXT); CREATE TABLE user(id TEXT,name TEXT,email TEXT);')
        for chat_id, models in [('own', ['lamb_assistant.25']), ('foreign', ['lamb_assistant.250']), ('suffix', ['other_lamb_assistant.25']), ('multi', ['another-model','lamb_assistant.25'])]:
            data = {'models': models, 'history': {'messages': {'q': {'role':'user','content':'Hi'}, 'a': {'role':'assistant','content':'Hello'}}}}
            self.db.execute('INSERT INTO chat VALUES (?,?,?,?,?,?)',(chat_id,'student',chat_id,1789200000,1789200000,json.dumps(data)))
        self.service = ChatAnalyticsService.__new__(ChatAnalyticsService)
        self.service._get_lamb_internal_chats = Mock(return_value=[])
        self.service._get_lamb_chat_detail = Mock(return_value=None)
        def query(sql, params=(), fetch_one=False):
            cursor = self.db.execute(sql, params)
            return cursor.fetchone() if fetch_one else cursor.fetchall()
        self.service._execute_query = query

    def test_list_exact_membership(self):
        result = self.service.get_chats_for_assistant(25)
        self.assertNotIn('error', result)
        self.assertEqual({c['id'] for c in result['chats']}, {'own','multi'})

    def test_foreign_detail_denied(self):
        self.assertIsNone(self.service.get_chat_detail('foreign',25))
        self.assertIsNotNone(self.service.get_chat_detail('own',25))

    def test_counts_exact_membership(self):
        result = self.service.get_assistant_stats(25)
        self.assertNotIn('error', result)
        self.assertEqual(result['stats']['total_chats'],2)
        self.assertEqual(result['stats']['total_messages'],4)

    def test_timeline_exact_membership(self):
        for period in ['day','week','month']:
            with self.subTest(period=period):
                result = self.service.get_assistant_timeline(25,period=period)
                self.assertNotIn('error',result)
                self.assertEqual(sum(p['chat_count'] for p in result['data']),2)
