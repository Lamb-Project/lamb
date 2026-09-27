"""Previews never pass for complete data; course subsections stay linked (#521)."""
import json
import time
import uuid

from lamb.aac import result_store as rs
from lamb.aac.pack_loader import load_pack
from lamb.moodle.course_structure import with_subsection_links


def module(i, name, modname='resource', filename=None, sectionid=None):
    m = {'id': i, 'name': name, 'modname': modname, 'url': f'https://moodle.example/mod/{modname}/view.php?id={i}',
         'instance': i + 1000, 'contextid': i + 5000, 'visible': 1, 'uservisible': True, 'visibleoncoursepage': 1,
         'modicon': 'https://moodle.example/theme/image.php/boost/core/1/f/pdf', 'purpose': 'content',
         'afterlink': '<div>' + 'x' * 300 + '</div>', 'description': 'd' * 200}
    if filename: m['contents'] = [{'type': 'file', 'filename': filename, 'mimetype': 'application/pdf', 'filesize': 1000,
                                   'fileurl': f'https://moodle.example/pluginfile.php/{i}/{filename}'}]
    if sectionid: m['customdata'] = json.dumps({'sectionid': str(sectionid)})
    return m


def course():
    week = {'id': 789, 'name': 'Week 2 : RAG', 'summary': '', 'modules': [
        module(3310, 'Lecture 2.1', 'subsection', sectionid=896), module(3373, 'Lesson 2.2', 'subsection', sectionid=914),
        module(3375, 'Exercise 2-1', filename='w2-ex1.pdf'), module(3376, 'Exercise 2-1 Delivery', 'assign'),
        module(3409, 'Markitdown , and markitdown OCR', filename='markitdown.pdf'),
        module(3410, 'Week 2 Lesson 2 lecture notes', filename='lecture-notes-v2.pdf'),
        module(3439, 'Lesson 2.3', 'subsection', sectionid=929), module(3551, 'Lesson 2.4', 'subsection', sectionid=940)]}
    subs = [{'id': sid, 'name': f'Lesson {sid}', 'summary': '', 'modules': [module(sid * 10, f'notes {sid}', filename=f'n{sid}.pdf')]}
            for sid in (896, 914, 929, 940)]
    return [week, *subs]


def envelope(payload):
    return {'id': uuid.uuid4().hex, 'payload': payload, 'created_at': time.time(), 'expires_at': time.time() + 60,
            'sha256': 'fixture'}


def modules_of(item):
    mods = item['value']['modules']
    return mods['items'] if isinstance(mods, dict) else mods


def test_page_preview_shows_every_module_of_a_large_section_with_files():
    page = rs.page(envelope({'data': with_subsection_links(course())}), '/data', 0)
    week = page['items'][0]
    assert week['complete'] is False and week['read_command']
    names = [m['name'] for m in modules_of(week)]
    assert 'Markitdown , and markitdown OCR' in names and 'Week 2 Lesson 2 lecture notes' in names and len(names) == 8
    files = {m['name']: m.get('contents', {}).get('filenames') for m in modules_of(week)}
    assert files['Week 2 Lesson 2 lecture notes'] == ['lecture-notes-v2.pdf']
    assert len(rs.encode({'success': True, 'data': page})) <= rs.RESULT_BYTES


def test_list_previews_state_what_they_omit():
    rows = [{'id': i, 'name': f'student {i}', 'body': 'y' * 400} for i in range(500)]
    preview = rs.preview({'rows': rows})['rows']
    assert preview['total'] == 500 and preview['omitted'] == 500 - preview['shown'] > 0 and preview['compacted'] is True
    assert [r['id'] for r in preview['items']] == list(range(preview['shown']))
    small = rs.preview({'rows': rows[:2]})['rows']
    assert isinstance(small, list) and len(small) == 2


def test_object_previews_count_omitted_keys():
    value = {f'k{i}': i for i in range(20)}
    assert rs.preview(value)['_omitted_keys'] == 8


def test_subsection_links_both_ways():
    sections = with_subsection_links(course())
    week = sections[0]
    link = {m['name']: m.get('subsection_section_id') for m in week['modules']}
    assert link['Lesson 2.2'] == 914 and link['Exercise 2-1'] is None
    lesson = next(s for s in sections if s['id'] == 914)
    assert lesson['subsection_of'] == {'section_id': 789, 'section_name': 'Week 2 : RAG', 'module_id': 3373}


def test_subsection_links_tolerate_missing_or_malformed_customdata():
    sections = [{'id': 1, 'name': 'w', 'modules': [{'id': 5, 'modname': 'subsection', 'customdata': 'not json'},
                                                    {'id': 6, 'modname': 'subsection', 'customdata': {'sectionid': '999'}}]}]
    assert with_subsection_links(sections)[0]['modules'][0].get('subsection_section_id') is None
    assert with_subsection_links('not a list') == 'not a list'


def test_pack_teaches_previews_and_subsections():
    pack = load_pack()
    assert 'complete: false is a preview' in pack.text('persona.md')
    assert 'subsection_of' in pack.text('skills/moodle_course_documents.md')
    assert 'complete: false is a preview' not in load_pack(version='1.11.6').text('persona.md')
