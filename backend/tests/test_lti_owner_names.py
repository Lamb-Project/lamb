"""lamb-0.8: teacher-facing LTI screens name an assistant's owner, not the account email.

LTI Creator accounts carry a synthetic email (lti_creator_<org>_<id>@lamb-lti.local); the
setup page and the chat dashboard show the owner's name instead. Same-named organizations
are told apart in the setup chooser by their slug.
"""
import sqlite3
from types import SimpleNamespace

from lamb.database_manager import LambDatabaseManager

SYNTH = 'lti_creator_uni_7@lamb-lti.local'


def _db(tmp_path):
    path = tmp_path / 'lamb.db'
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE Creator_users (id INTEGER PRIMARY KEY, user_email TEXT UNIQUE, user_name TEXT);
        CREATE TABLE assistants (id INTEGER PRIMARY KEY, name TEXT, description TEXT, owner TEXT,
                                 organization_id INTEGER, api_callback TEXT);
        CREATE TABLE assistant_publish (assistant_id INTEGER, oauth_consumer_name TEXT, group_id TEXT, group_name TEXT);
        CREATE TABLE assistant_shares (assistant_id INTEGER, shared_with_user_id INTEGER);
        CREATE TABLE lti_activity_assistants (activity_id INTEGER, assistant_id INTEGER, added_at INTEGER);
    """)
    c.execute("INSERT INTO Creator_users VALUES (7, ?, 'Dr. Alice Smith')", (SYNTH,))
    c.execute("INSERT INTO Creator_users VALUES (8, 'bob@x.edu', 'Bob Johnson')")
    c.execute("INSERT INTO assistants VALUES (30, 'tutor', '', ?, 1, NULL)", (SYNTH,))
    c.execute("INSERT INTO assistants VALUES (31, 'grader', '', 'gone@x.edu', 1, NULL)")
    c.executemany("INSERT INTO assistant_publish VALUES (?, 'c', 'g', 'g')", [(30,), (31,)])
    c.execute("INSERT INTO assistant_shares VALUES (31, 7)")
    c.executemany("INSERT INTO lti_activity_assistants VALUES (9, ?, 0)", [(30,), (31,)])
    c.commit(); c.close()
    return SimpleNamespace(table_prefix='', get_connection=lambda: sqlite3.connect(path),
                           assistant_has_rubric_for_eval=LambDatabaseManager.assistant_has_rubric_for_eval)


def test_setup_list_carries_owner_names(tmp_path):
    rows = LambDatabaseManager.get_published_assistants_for_org_user(_db(tmp_path), 1, 7, SYNTH)
    assert {r['name']: r['owner_name'] for r in rows} == {'tutor': 'Dr. Alice Smith', 'grader': None}


def test_activity_assistants_carry_owner_names(tmp_path):
    rows = LambDatabaseManager.get_activity_assistants(_db(tmp_path), 9)
    assert {r['name']: (r['owner'], r['owner_name']) for r in rows} == {
        'tutor': (SYNTH, 'Dr. Alice Smith'), 'grader': ('gone@x.edu', None)}
