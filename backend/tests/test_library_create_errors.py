"""Library create: a name conflict is 409, any other database failure is 500 (#466)."""
import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from creator_interface import library_router
from lamb.database_manager import LambDatabaseManager, LibraryStoreError


def manager(path, with_table=True):
    db = object.__new__(LambDatabaseManager)
    db.table_prefix = 'T_'
    db.get_connection = lambda: sqlite3.connect(path)
    if with_table:
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE T_libraries (id TEXT PRIMARY KEY, organization_id INTEGER, name TEXT, description TEXT,'
                      ' owner_user_id INTEGER, is_shared INTEGER, import_config TEXT, status TEXT, created_at INTEGER,'
                      ' updated_at INTEGER, UNIQUE(organization_id, name))')
    return db


def test_conflict_returns_none_and_missing_table_raises(tmp_path):
    db = manager(tmp_path / 'a.db')
    assert db.create_library('a', 'Readings', 1, 7) == 'a'
    assert db.create_library('b', 'Readings', 1, 7) is None
    assert db.create_library('c', 'Readings', 1, 8) == 'c'
    with pytest.raises(LibraryStoreError):
        manager(tmp_path / 'b.db', with_table=False).create_library('d', 'Readings', 1, 7)


def create(monkeypatch, db):
    monkeypatch.setattr(library_router, '_db', db)
    auth = SimpleNamespace(organization={'id': 7}, user={'id': 1})
    return asyncio.run(library_router.create_library(library_router.LibraryCreate(name='Readings'), auth))


def test_router_maps_conflict_to_409_and_database_error_to_500(monkeypatch, tmp_path):
    db = manager(tmp_path / 'a.db')
    db.create_library('a', 'Readings', 1, 7)
    with pytest.raises(HTTPException) as e:
        create(monkeypatch, db)
    assert e.value.status_code == 409
    with pytest.raises(HTTPException) as e:
        create(monkeypatch, manager(tmp_path / 'b.db', with_table=False))
    assert e.value.status_code == 500 and 'already taken' not in e.value.detail


class Auth:
    user = {'id': 1}
    organization = {'id': 7}

    def require_library_access(self, *a, **k):
        return None


class Client:
    def __init__(self, error):
        self.error = error

    async def get_library(self, *a, **k):
        raise self.error


def test_library_detail_is_503_when_the_library_manager_is_down_and_null_count_otherwise(monkeypatch, tmp_path):
    db = manager(tmp_path / 'e.db')
    db.create_library('a', 'Readings', 1, 7)
    db.get_library = lambda lid: {'id': lid, 'owner_user_id': 1}
    monkeypatch.setattr(library_router, '_db', db)
    monkeypatch.setattr(library_router, '_client', Client(HTTPException(status_code=503, detail='Unable to connect to Library Manager')))
    with pytest.raises(HTTPException) as e:
        asyncio.run(library_router.get_library('a', Auth()))
    assert e.value.status_code == 503 and e.value.headers == {'Retry-After': '30'}
    monkeypatch.setattr(library_router, '_client', Client(HTTPException(status_code=500, detail='one library failed')))
    assert asyncio.run(library_router.get_library('a', Auth()))['item_count'] is None
