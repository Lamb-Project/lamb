"""In-memory fakes standing in for the neo4j driver/session/result.

``graph_store.GraphStore`` only ever touches Neo4j through three shapes:

* ``driver.session()`` used as a context manager,
* ``session.run(query, **params)`` returning a result that exposes
  ``.data()`` / ``.single()`` / iteration,
* ``session.execute_write(fn, *args, **kwargs)`` running a unit-of-work
  callback with a transaction object that itself exposes ``.run(...)``.

These fakes reproduce exactly that surface so the store can be exercised
without a live Neo4j. Responses are programmed as an ordered queue; each
``run`` call pops the next one. A response may be a :class:`FakeResult`, a
list of row dicts (wrapped automatically), or a callable
``(query, params) -> FakeResult`` for query-dependent behaviour.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

Response = Union["FakeResult", List[Dict[str, Any]], Callable[[str, dict], Any], None]


class FakeResult:
    def __init__(self, rows: Optional[List[Dict[str, Any]]] = None, single=...):
        self._rows = rows or []
        # `single` sentinel: default to first row (or None) when not provided.
        if single is ...:
            self._single = self._rows[0] if self._rows else None
        else:
            self._single = single

    def data(self) -> List[Dict[str, Any]]:
        return list(self._rows)

    def single(self):
        return self._single

    def __iter__(self):
        return iter(self._rows)


def _coerce(resp: Response, query: str, params: dict) -> FakeResult:
    if callable(resp) and not isinstance(resp, FakeResult):
        resp = resp(query, params)
    if resp is None:
        return FakeResult()
    if isinstance(resp, FakeResult):
        return resp
    if isinstance(resp, list):
        return FakeResult(rows=resp)
    raise TypeError(f"Unsupported fake response: {resp!r}")


class FakeSession:
    """Context-manager session that records runs and replays a response queue.

    Also serves as its own transaction object for ``execute_write`` — the
    unit-of-work callback receives this session and calls ``.run`` on it,
    drawing from the same queue.
    """

    def __init__(self, responses: Optional[List[Response]] = None):
        self.responses: List[Response] = list(responses or [])
        self.runs: List[Dict[str, Any]] = []

    # context-manager protocol (``with driver.session() as session:``)
    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def run(self, query: str, **params) -> FakeResult:
        self.runs.append({"query": query, "params": params})
        resp = self.responses.pop(0) if self.responses else None
        return _coerce(resp, query, params)

    def execute_write(self, fn: Callable, *args, **kwargs):
        return fn(self, *args, **kwargs)

    def execute_read(self, fn: Callable, *args, **kwargs):
        return fn(self, *args, **kwargs)


class FakeDriver:
    def __init__(
        self,
        session: Optional[FakeSession] = None,
        *,
        connectivity_error: Optional[Exception] = None,
    ):
        self._session = session or FakeSession()
        self.connectivity_error = connectivity_error
        self.closed = False

    def session(self) -> FakeSession:
        return self._session

    def verify_connectivity(self) -> None:
        if self.connectivity_error is not None:
            raise self.connectivity_error

    def close(self) -> None:
        self.closed = True


def make_store(
    *,
    responses: Optional[List[Response]] = None,
    session: Optional[FakeSession] = None,
    driver: Optional[FakeDriver] = None,
    schema_ready: bool = True,
    config: Optional[Dict[str, Any]] = None,
):
    """Build a ``GraphStore`` wired to a fake driver, bypassing real Neo4j.

    Returns ``(store, session)`` so tests can assert on ``session.runs``.
    """
    from services.graph_store import GraphStore

    sess = session or FakeSession(responses)
    drv = driver or FakeDriver(sess)
    cfg = {
        "enabled": False,  # keep __init__ from creating a real driver
        "neo4j_uri": "",
        "neo4j_user": "neo4j",
        "neo4j_password": "",
    }
    if config:
        cfg.update(config)
    store = GraphStore(kg_config=cfg)
    store.driver = drv
    store.enabled = True
    # Populate connection fields so ``is_configured()`` is True without ever
    # having created a real driver in __init__.
    store.uri = "bolt://fake:7687"
    store.user = "neo4j"
    store.password = "fake-password"
    store._schema_ready = schema_ready
    return store, sess
