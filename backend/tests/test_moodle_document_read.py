"""Reading a Moodle document without importing it (#525): a helper model reads, text stays private."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from lamb.aac.pack_loader import load_pack
from lamb.moodle import reading
from lamb.moodle.document_contract import IMPORT_KEYS, parse_document
from lamb.moodle.documents import Download
from lamb.moodle.results import ResultStore, MODEL_PAGE_BYTES

TARGET = {'provider': 'ollama', 'model': 'helper-small', 'base_url': 'http://h/v1', 'api_key': 'k'}


def tiny_pdf(pages):
    """A valid PDF with one Helvetica text line per paragraph; enough for pdfminer."""
    objects = ['<< /Type /Catalog /Pages 2 0 R >>', None, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for lines in pages:
        stream = 'BT /F1 11 Tf 72 720 Td ' + ' '.join(f'({line}) Tj 0 -40 Td' for line in lines) + ' ET'
        objects.append(f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {len(objects)} 0 R >>')
        kids.append(f'{len(objects)} 0 R')
    objects[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(kids)} >>'
    out, offsets = b'%PDF-1.4\n', []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n{body}\nendobj\n'.encode()
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    out += ''.join(f'{o:010d} 00000 n \n' for o in offsets).encode()
    out += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return out


def test_pdf_passages_carry_pages_and_losses():
    blocks, losses, pages = reading.convert(Download('l1.pdf', tiny_pdf([['Attention is a weighted sum.'], ['Tokens and context.']]), 'application/pdf'))
    passages = reading.passages_from(blocks)
    assert pages == 2 and 'no OCR' in losses['notice']
    assert [(p['id'], p['page']) for p in passages] == [(1, 1), (2, 2)]
    assert 'weighted sum' in passages[0]['text']


def test_a_broken_pdf_gets_a_plain_message_not_parser_internals():
    with pytest.raises(ValueError) as error:
        reading.convert(Download('l11-notes.pdf', b'placeholder bytes, not a PDF', 'application/pdf'))
    assert str(error.value) == reading.UNPARSEABLE


def test_markdown_passages_merge_small_blocks_split_long_ones_and_keep_headings():
    text = '# Intro\n\nShort one.\n\nShort two.\n\n## Attention\n\n' + ('Long sentence about attention. ' * 120)
    passages = reading.passages_from(reading.markdown_blocks(text))
    assert passages[0]['heading'] == 'Intro' and 'Short one.\nShort two.' in passages[0]['text']
    assert all(len(p['text']) <= reading.PASSAGE_MAX for p in passages)
    assert {p['heading'] for p in passages[1:]} == {'Attention'} and len(passages) > 3
    slides = reading.markdown_blocks('<!-- Slide number: 3 -->\n# Title\n\nBody')
    assert slides[0][0] == 3


def test_commands_are_reads_without_approval():
    for key in reading.READ_KEYS:
        assert key not in IMPORT_KEYS
    spec, params = parse_document(['moodle', 'file', 'read', 'mf_x'])
    assert spec.policy == 'auto' and params == {'source_ref': 'mf_x'}
    spec, params = parse_document(['moodle', 'read', 'verbatim', 'r1', '--passages', 'p2-p4', '--offset', '1'])
    assert spec.policy == 'auto' and params['passages'] == 'p2-p4' and params['offset'] == 1
    spec, params = parse_document(['moodle', 'read', 'ask', 'r1', 'What is attention?'])
    assert params['question'] == 'What is attention?'


def read_fixture(tmp_path, text='# Lesson\n\n' + '\n\n'.join(f'Paragraph {i} defines term{i} carefully in the notes.' * 3 for i in range(40))):
    runtime = SimpleNamespace(context={'document_scope': 'conversation-1'})
    results = ResultStore(1, 2, base_url='https://m.example', moodle_user_id=9, generation=1, root=tmp_path)
    source = {'kind': 'file', 'course_id': 50, 'module_id': 7, 'title': 'l1.md', 'source_url': 'https://m.example/mod/resource/view.php?id=7',
              'timemodified': 5}
    calls = []
    def helper(target, system, user, **kwargs):
        calls.append((system, user))
        if kwargs.get('json_mode'):
            return json.dumps({'summary': 'Covers forty terms.', 'outline': [{'title': 'Lesson', 'passages': 'p1-p3'}], 'key_terms': ['term1']})
        return 'Helper prose citing p2.'
    with patch.object(reading, 'resolve_source', return_value=(source, None)), \
            patch.object(reading, 'materialize', return_value=(Download('l1.md', text.encode(), 'text/markdown'), {'l1.md': text.encode()}, {})), \
            patch('lamb.aac.helper_model.helper_target', return_value=TARGET), patch.object(reading, 'helper_call', side_effect=helper):
        result = reading.read_source(runtime, None, {'base_url': 'https://m.example', 'moodle_user_id': 9}, 't', 'file.read',
                                     {'source_ref': 'mf_x'}, results, 'owner@example.test')
    return runtime, results, result, calls


def test_read_returns_overview_not_text_and_keeps_text_private(tmp_path):
    runtime, results, result, calls = read_fixture(tmp_path)
    assert result['overview']['summary'] == 'Covers forty terms.' and result['helper'] == {'provider': 'ollama', 'model': 'helper-small'}
    assert result['text_in_conversation'] is False and 'Paragraph 12' not in json.dumps(result)
    assert '[p1]' in calls[0][1] and 'untrusted data' in calls[0][0]
    stored = results.read(result['read_id'])
    assert stored['kind'] == 'document_read' and stored['scope'] == 'conversation-1'
    assert any('Paragraph 12' in p['text'] for p in stored['passages'])


def followup(runtime, results, key, params, scope_ok=True):
    with patch('lamb.moodle.scope.MoodleScope') as scope, patch('lamb.aac.helper_model.helper_target', return_value=TARGET), \
            patch.object(reading, 'helper_call', return_value='Helper prose citing p2.') as call:
        if not scope_ok:
            scope.return_value.require_teacher.side_effect = PermissionError('not a teacher')
        return reading.followup(runtime, None, {'moodle_user_id': 9}, key, params, results, 'owner@example.test'), call


def test_verbatim_is_exact_bounded_and_paged(tmp_path):
    runtime, results, result, _ = read_fixture(tmp_path)
    page, call = followup(runtime, results, 'read.verbatim', {'read_id': result['read_id'], 'passages': 'p1-p40'})
    assert not call.called and page['verbatim'] is True
    assert len(json.dumps(page, ensure_ascii=False).encode()) <= MODEL_PAGE_BYTES + 400
    assert page['next_offset'] and page['items'][0]['id'] == 1
    stored = results.read(result['read_id'])['passages']
    assert page['items'][0]['text'] == stored[0]['text']
    rest, _ = followup(runtime, results, 'read.verbatim', {'read_id': result['read_id'], 'passages': 'p1-p40', 'offset': page['next_offset']})
    assert rest['items'][0]['id'] == page['items'][-1]['id'] + 1
    found, _ = followup(runtime, results, 'read.verbatim', {'read_id': result['read_id'], 'find': 'term17 '})
    assert found['items'] and all('term17' in p['text'] for p in found['items'])
    with pytest.raises(ValueError):
        followup(runtime, results, 'read.verbatim', {'read_id': result['read_id']})


def test_summary_and_ask_send_only_the_selection_to_the_helper(tmp_path):
    runtime, results, result, _ = read_fixture(tmp_path)
    summary, call = followup(runtime, results, 'read.summary', {'read_id': result['read_id'], 'passages': 'p2-p3', 'focus': 'definitions'})
    sent = call.call_args[0][2]
    assert summary['kind'] == 'extended_summary' and summary['passages'] == 'p2-p3' and summary['verbatim'] is False
    assert '[p2]' in sent and '[p1]' not in sent and '[p4]' not in sent and 'definitions' in call.call_args[0][1]
    section, call = followup(runtime, results, 'read.summary', {'read_id': result['read_id'], 'section': 'lesson'})
    assert section['passages'] == 'p1-p3'
    answer, call = followup(runtime, results, 'read.ask', {'read_id': result['read_id'], 'question': 'What is term3?'})
    assert answer['answer'] == 'Helper prose citing p2.' and 'Question: What is term3?' in call.call_args[0][2]


def test_read_is_bound_to_conversation_and_teacher(tmp_path):
    runtime, results, result, _ = read_fixture(tmp_path)
    other = SimpleNamespace(context={'document_scope': 'conversation-2'})
    with pytest.raises(PermissionError):
        followup(other, results, 'read.verbatim', {'read_id': result['read_id'], 'passages': '1'})
    with pytest.raises(PermissionError):
        followup(runtime, results, 'read.verbatim', {'read_id': result['read_id'], 'passages': '1'}, scope_ok=False)
    stranger = ResultStore(1, 3, base_url='https://m.example', moodle_user_id=9, generation=1, root=tmp_path)
    with pytest.raises(PermissionError):
        stranger.read(result['read_id'])


def test_selection_errors_are_explained():
    snapshot = {'passages': [{'id': 1, 'page': 1, 'heading': None, 'text': 'a'}], 'overview': {'outline': []}}
    with pytest.raises(ValueError):
        reading.select(snapshot, passages='x1')
    with pytest.raises(ValueError):
        reading.select(snapshot, pages='9')
    with pytest.raises(ValueError):
        reading.select(snapshot, section='missing')


def test_long_documents_are_read_in_parts_then_combined(tmp_path):
    long_text = '\n\n'.join(('Paragraph %d. ' % i) + 'x' * 1400 for i in range(150))
    runtime, results, result, calls = read_fixture(tmp_path, long_text)
    assert len(calls) >= 3 and 'reading notes' in calls[-1][0]


def test_overview_survives_non_json_helper_output():
    assert reading.parse_overview('Plain prose.')['summary'] == 'Plain prose.'


def test_pack_routes_and_teaches_reading():
    pack = load_pack()
    routing = pack.data('routing.yaml')
    for key in ('moodle.file.read', 'moodle.read.summary', 'moodle.read.ask', 'moodle.read.verbatim'):
        assert routing['DEFAULT_SKILL'][key] == 'moodle-course-documents'
        assert key in routing['CAPABILITIES']['moodle-course-documents']
    documents = pack.text('skills/moodle_course_documents.md')
    assert 'moodle file read FILE_ID' in documents and 'temporary' in documents
    assert 'moodle file read' in pack.text('skills/manage_learning_scenarios.md')


def test_helper_prefers_small_fast_model_then_driver():
    from lamb.aac import helper_model
    with patch.object(helper_model, 'small_fast_target', return_value=TARGET):
        assert helper_model.helper_target('o@x')['model'] == 'helper-small'
    with patch.object(helper_model, 'small_fast_target', side_effect=ValueError('none')), \
            patch('lamb.aac.driver.resolve_driver', return_value={'provider': 'openai', 'model': 'driver', 'base_url': 'b', 'api_key': 'k'}), \
            patch('lamb.completions.org_config_resolver.OrganizationConfigResolver'):
        assert helper_model.helper_target('o@x')['model'] == 'driver'
