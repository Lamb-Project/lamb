"""Every static mount that can reach backend/static must be the guarded class.

Regression for the /lamb/static hole: the lamb sub-application mounted a plain
StaticFiles on the same tree the guarded /static mount protects, so learning
scenarios, owned documents and the Moodle course cache were served anonymously
through /lamb/static/... . This walks every mount, sub-applications included.
"""
import os
from pathlib import Path

from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from lamb.document_static import DocumentAwareStaticFiles


def _static_mounts(app, prefix=''):
    for route in getattr(app, 'routes', []):
        if not isinstance(route, Mount):
            continue
        path = prefix + route.path
        if isinstance(route.app, StaticFiles):
            yield path, route.app
        else:
            yield from _static_mounts(route.app, path)


def test_backend_static_tree_is_only_served_through_the_guarded_class(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    import main as backend_main
    protected = (Path.cwd() / 'static').resolve()
    found = list(_static_mounts(backend_main.app))
    assert found, 'no static mounts discovered'
    offenders = []
    for path, static in found:
        directories = [Path(d).resolve() for d in static.all_directories]
        if any(d == protected or protected in d.parents for d in directories):
            if not isinstance(static, DocumentAwareStaticFiles):
                offenders.append(path)
    assert offenders == [], f'unguarded mounts over backend/static: {offenders}'


def test_lamb_sub_application_has_no_static_mount():
    from lamb.main import app as lamb_app
    assert not list(_static_mounts(lamb_app))
