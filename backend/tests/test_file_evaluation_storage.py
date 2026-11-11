"""Submissions live under LAMB_DB_PATH and are stored by relative path (#559)."""
import os

import pytest

import config
from lamb.modules.file_evaluation.storage_service import FileStorageService, uploads_root


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LAMB_DB_PATH", str(tmp_path))
    return tmp_path


def _save(**overrides):
    args = dict(activity_id=7, submission_id="abc", file_name="my essay.pdf", file_bytes=b"content")
    args.update(overrides)
    return FileStorageService.save_submission_file(**args)


def test_file_is_saved_under_the_data_directory_with_a_relative_path(data_dir):
    stored = _save()

    assert not os.path.isabs(stored)
    assert stored.startswith("7/abc_") and stored.endswith("_my_essay.pdf")
    resolved = FileStorageService.resolve_path(stored)
    assert resolved == str(data_dir / "uploads" / "file-eval" / stored)
    with open(resolved, "rb") as fh:
        assert fh.read() == b"content"


def test_stored_path_survives_a_move_of_the_data_directory(data_dir, tmp_path_factory, monkeypatch):
    stored = _save()
    new_home = tmp_path_factory.mktemp("moved") / "lamb"
    os.rename(data_dir, new_home)
    monkeypatch.setattr(config, "LAMB_DB_PATH", str(new_home))

    assert os.path.isfile(FileStorageService.resolve_path(stored))


def test_legacy_absolute_path_maps_onto_the_current_root(data_dir):
    legacy = "/app/backend/uploads/file-eval/7/abc_20260101_000000_essay.pdf"

    assert FileStorageService.resolve_path(legacy) == os.path.join(
        uploads_root(), "7", "abc_20260101_000000_essay.pdf"
    )


@pytest.mark.parametrize("stored", [
    "", None, "../../lamb_v4.db", "7/../../../etc/passwd", "/etc/passwd",
    "/app/backend/uploads/file-eval/../../../etc/passwd", ".",
])
def test_paths_outside_the_uploads_root_do_not_resolve(data_dir, stored):
    assert FileStorageService.resolve_path(stored) is None


def test_reupload_removes_the_previous_file(data_dir):
    first = _save()
    second = _save(file_name="final.pdf", previous_file_path=first)

    assert not os.path.exists(FileStorageService.resolve_path(first))
    assert os.path.isfile(FileStorageService.resolve_path(second))


def test_delete_ignores_paths_outside_the_uploads_root(data_dir):
    outside = data_dir / "lamb_v4.db"
    outside.write_bytes(b"db")

    FileStorageService.delete_path(str(outside))
    FileStorageService.delete_path("../../lamb_v4.db")

    assert outside.exists()
