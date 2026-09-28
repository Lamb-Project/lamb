"""One approved batch of documents chosen across a course (#524)."""
from unittest.mock import patch

import pytest

from lamb.aac.pack_loader import load_pack
from lamb.moodle import course_batch as cb
from lamb.moodle.document_contract import IMPORT_KEYS, parse_document


def mod(i, name, modname, files=(), visible=1, instance=None):
    return {'id': i, 'name': name, 'modname': modname, 'instance': instance or i + 100, 'visible': visible,
            'contents': [{'type': 'file', 'filename': f, 'fileurl': f'https://m.example/pluginfile.php/{i}/{f}',
                          'filesize': size, 'timemodified': 1} for f, size in files]}


COURSE = [mod(1, 'Lecture 1 notes', 'resource', [('l1.pdf', 1000)]),
          mod(2, 'Slides', 'resource', [('s.pptx', 2000), ('s.key', 10)]),
          mod(3, 'Exercise 1', 'resource', [('ex1.pdf', 500)]),
          mod(4, 'Huge', 'resource', [('big.pdf', 11 * 1024 * 1024)]),
          mod(5, 'Forum', 'forum'), mod(6, 'Hidden notes', 'resource', [('h.pdf', 10)], visible=0),
          mod(7, 'Reading page', 'page'), mod(8, 'Readings', 'folder')]


def sources(ids):
    with patch.object(cb, 'MoodleScope') as scope, patch.object(cb, 'modules', lambda client, course: COURSE), \
            patch.object(cb, 'folder_files', lambda *a: (None, [{'kind': 'folder_file', 'source_path': '/r/a.docx',
                                                                  'size_bytes': 5, 'file': {'filename': 'a.docx'}}])), \
            patch.object(cb, 'activity_sources', lambda client, kind, course, owner, base, selected: [({'kind': kind, 'item_id': selected}, None)]):
        scope.return_value.require_teacher.return_value = 50
        return cb.course_sources(None, 'https://m.example', 9, 50, ids)


def test_chosen_modules_become_exact_documents_with_skip_reasons():
    course, found, skipped = sources([1, 2, 4, 5, 6, 7, 8, 99, 1])
    assert course == 50
    assert [s.get('source_path') for s in found] == ['Lecture 1 notes/l1.pdf', 'Slides/s.pptx', 'Reading page', '/r/a.docx']
    assert found[0]['kind'] == 'course_file' and found[0]['metadata_hash']
    reasons = {(s.get('module_id'), s.get('path'), s['reason']) for s in skipped}
    assert (2, 'Slides/s.key', 'unsupported_format') in reasons and (4, 'Huge/big.pdf', 'over_10_MiB') in reasons
    assert (5, None, 'not_a_document') in reasons and (6, None, 'hidden') in reasons and (99, None, 'not_in_course') in reasons
    assert 3 not in {s.get('module_id') for s in skipped}  # not chosen, not mentioned


def test_command_parses_like_the_folder_batch():
    assert 'import.course' in IMPORT_KEYS
    spec, params = parse_document(['moodle', 'import', 'course', '50', '--module', '1', '--module', '7', '--new-kb', 'Apuntes', '--chunk-size', '3000'])
    assert spec.policy == 'ask' and params['module'] == (1, 7) and params['new_kb'] == 'Apuntes'
    spec, params = parse_document(['moodle', 'import', 'course', '50', '--module', '1', '--to', 'kb', '4'])
    assert params['kb_id'] == 4
    with pytest.raises(ValueError):
        parse_document(['moodle', 'import', 'course', '50', '--module', '1'])


def test_pack_routes_and_teaches_the_course_batch():
    pack = load_pack()
    assert pack.data('routing.yaml')['DEFAULT_SKILL']['moodle.import.course'] == 'moodle-course-documents'
    assert 'moodle import course COURSE_ID --module MODULE_ID' in pack.text('skills/moodle_course_documents.md')


def test_approval_details_list_every_document_and_skip():
    from lamb.moodle.import_review import render_review
    review = {'kind': 'course', 'source': {'kind': 'course', 'course_id': 50, 'modules': [1, 5]},
              'destination': {'single_file': False, 'kb_id': None, 'new_kb': 'apuntes', 'description': ''},
              'file_count': 1, 'bytes': 1000,
              'files': [{'path': 'Lecture 1 notes/l1.pdf', 'bytes': 1000, 'conversion_losses': {},
                         'ingestion': {'chunk_size': 3000, 'chunk_overlap': 200, 'units': 'characters', 'splitter_type': 'x'}}],
              'skipped': [{'module_id': 5, 'name': 'Forum', 'reason': 'not_a_document'}]}
    text = render_review(review, 'es')
    assert 'Lecture 1 notes/l1.pdf' in text and 'Forum: no es un documento' in text
    assert 'apuntes' in text and 'Tamaño de fragmento: 3000' in text and 'Una aprobación cubre exactamente' in text
