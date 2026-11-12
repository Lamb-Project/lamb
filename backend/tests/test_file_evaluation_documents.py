"""File evaluation reads real DOCX paragraphs/tables and rejects legacy DOC (#561)."""
from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lamb.modules.file_evaluation.document_extractor import DocumentExtractor


def docx_bytes():
    document = Document()
    document.add_paragraph("Respuesta: energía y evaluación — 日本語.")
    document.add_paragraph("")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Criterio"
    table.cell(0, 1).text = "Resultado: 42"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.mark.parametrize("filename", ["essay.docx", "essay.DOCX"])
def test_extracts_real_docx_paragraphs_and_tables(tmp_path, filename):
    path = tmp_path / filename
    path.write_bytes(docx_bytes())
    assert DocumentExtractor.extract_text_from_file(str(path)) == (
        "Respuesta: energía y evaluación — 日本語.\nCriterio\nResultado: 42"
    )


def test_empty_docx_has_no_text(tmp_path):
    path = tmp_path / "empty.docx"
    Document().save(path)
    assert DocumentExtractor.extract_text_from_file(str(path)) is None


def test_corrupt_docx_does_not_return_text(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a Word document")
    assert DocumentExtractor.extract_text_from_file(str(path)) is None


def test_legacy_doc_is_not_sent_to_docx_parser(tmp_path):
    path = tmp_path / "old.doc"
    path.write_bytes(docx_bytes())
    with patch.object(DocumentExtractor, "_extract_from_docx") as parse:
        assert DocumentExtractor.extract_text_from_file(str(path)) is None
    parse.assert_not_called()


@pytest.mark.parametrize("filename", ["essay.doc", "essay.DOC"])
def test_upload_rejects_legacy_doc_before_saving(filename):
    from lamb.modules.file_evaluation import router as routes

    app = FastAPI()
    app.include_router(routes.router)
    service = Mock()
    payload = {"lti_type": "file_eval", "lti_activity_id": 7, "lti_user_email": "student@example.test"}
    with patch.object(routes, "_decode_jwt", return_value=payload), patch.object(routes, "_service", service):
        with TestClient(app) as client:
            response = client.post("/activities/7/submissions", files={"file": (filename, b"legacy document")})
    assert response.status_code == 400
    assert "Save the document as .docx" in response.json()["detail"]
    service.create_submission.assert_not_called()
