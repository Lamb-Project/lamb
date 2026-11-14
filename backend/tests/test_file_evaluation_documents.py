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


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.mark.parametrize("filename,content", [
    ("essay.doc", b"legacy document"), ("essay.DOC", b"legacy document"), ("essay.docx", None), ("notes.txt", b"plain text"),
    ("notes.md", b"# heading"), ("essay", PDF_BYTES), ("essay.pdf.docx", PDF_BYTES),
    ("renamed.pdf", b"plain text with a pdf name"), ("word-renamed.pdf", None), ("empty.pdf", b""),
])
def test_upload_accepts_pdf_only_and_refuses_everything_else_before_saving(filename, content):
    # Submissions are PDF only (Marc, 10 and 14 November 2026): by name and by content.
    from lamb.modules.file_evaluation import router as routes

    app = FastAPI()
    app.include_router(routes.router)
    service = Mock()
    payload = {"lti_type": "file_eval", "lti_activity_id": 7, "lti_user_email": "student@example.test"}
    with patch.object(routes, "_decode_jwt", return_value=payload), patch.object(routes, "_service", service):
        with TestClient(app) as client:
            response = client.post("/activities/7/submissions", files={"file": (filename, docx_bytes() if content is None else content)})
    assert response.status_code == 400
    assert response.json()["detail"] == routes.PDF_ONLY and "PDF" in routes.PDF_ONLY
    service.create_submission.assert_not_called()


@pytest.mark.parametrize("filename", ["essay.pdf", "ESSAY.PDF"])
def test_upload_passes_a_real_pdf_on_to_storage(filename):
    from lamb.modules.file_evaluation import router as routes

    app = FastAPI()
    app.include_router(routes.router)
    service = Mock()
    service.create_submission.return_value = {"id": 1, "file_name": filename}
    payload = {"lti_type": "file_eval", "lti_activity_id": 7, "lti_user_email": "student@example.test"}
    with patch.object(routes, "_decode_jwt", return_value=payload), patch.object(routes, "_service", service):
        with TestClient(app) as client:
            client.post("/activities/7/submissions", files={"file": (filename, PDF_BYTES, "application/pdf")})
    service.create_submission.assert_called_once()
    assert service.create_submission.call_args.kwargs["file_bytes"] == PDF_BYTES
