"""Regression: real SQLite sources must produce one complete, stable page sequence."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from lamb.database_manager import LambDatabaseManager
from lamb.services.chat_analytics_service import ChatAnalyticsService


class ActivityPagination(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'chats.db'
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.db.executescript('''
            CREATE TABLE chat(id TEXT,user_id TEXT,title TEXT,created_at INTEGER,updated_at INTEGER,chat TEXT);
            CREATE TABLE user(id TEXT,name TEXT,email TEXT);
            CREATE TABLE lamb_chats(id TEXT,user_id INTEGER,assistant_id INTEGER,title TEXT,created_at INTEGER,updated_at INTEGER,chat TEXT,archived INTEGER);
            CREATE TABLE Creator_users(id INTEGER,user_name TEXT,user_email TEXT);
        ''')
        self.service = ChatAnalyticsService.__new__(ChatAnalyticsService)
        self.service.lamb_db = LambDatabaseManager.__new__(LambDatabaseManager)
        self.service.lamb_db.table_prefix = ''
        self.service.lamb_db.get_connection = lambda: sqlite3.connect(self.path)
        def query(sql, params=(), fetch_one=False):
            cursor = self.db.execute(sql, params)
            return cursor.fetchone() if fetch_one else cursor.fetchall()
        self.service._execute_query = query

    def seed(self, external, internal):
        self.expected = []
        for source, count in [('owi', external), ('lamb', internal)]:
            for i in range(count):
                cid = f'{source}-{i:03}'
                stamp = 1790000000 + i // 3  # Ties and interleaving are intentional.
                data = json.dumps({'models': ['lamb_assistant.25'], 'history': {'messages': {'q': {'content': 'needle' if i % 2 else 'plain'}}}})
                if source == 'owi':
                    self.db.execute('INSERT INTO chat VALUES(?,?,?,?,?,?)', (cid, 'student', cid, stamp, stamp, data))
                else:
                    self.db.execute('INSERT INTO lamb_chats VALUES(?,?,?,?,?,?,?,?)', (cid, 1, 25, cid, stamp, stamp, data, 0))
                self.expected.append((stamp, cid, i))
        self.db.commit()
        self.expected.sort(reverse=True)

    def assert_pages(self, size, expected=None, **filters):
        expected = [r[1] for r in self.expected] if expected is None else expected
        seen = []
        pages = (len(expected) + size - 1) // size
        for page in range(1, pages + 2):
            result = self.service.get_chats_for_assistant(25, page=page, per_page=size, **filters)
            self.assertNotIn('error', result)
            self.assertEqual(result['total'], len(expected))
            self.assertEqual(result['total_pages'], pages)
            ids = [c['id'] for c in result['chats']]
            self.assertEqual(ids, expected[(page-1)*size:page*size])
            seen.extend(ids)
        self.assertEqual(seen, expected)

    def test_reported_thirty_student_chats(self):
        self.seed(30, 0)
        for size in (10, 20, 50, 100):
            with self.subTest(size=size): self.assert_pages(size)

    def test_mixed_sources_ties_and_filters(self):
        self.seed(31, 17)
        for size in (1, 10, 20, 50):
            with self.subTest(size=size): self.assert_pages(size)
        self.assert_pages(7, [r[1] for r in self.expected if r[2] % 2], search_content='needle')
        threshold = 1790000005
        self.assert_pages(7, [r[1] for r in self.expected if r[0] >= threshold], start_date=datetime.fromtimestamp(threshold))

    def test_internal_chats_beyond_one_hundred(self):
        self.seed(0, 151)
        for size in (20, 50, 100):
            with self.subTest(size=size): self.assert_pages(size)

    def test_empty(self):
        self.seed(0, 0)
        self.assert_pages(20)
