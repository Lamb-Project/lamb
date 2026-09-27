"""Course inventory read and budget fallback (#521)."""
import unittest

from lamb.aac.pack_loader import load_pack
from lamb.moodle.contract import command_specs, prepare_moodle
from lamb.moodle.course_structure import inventory
from tests.test_aac_legacy import agent, message, tool, turn
from tests.test_result_previews_and_subsections import course


def test_inventory_lists_every_module_with_sections_parents_and_files():
    inv = inventory(course())
    assert inv['total_modules'] == 12 and inv['matched'] == 12 and inv['sections'] == 5
    rows = {r['name']: r for r in inv['modules']}
    assert rows['Week 2 Lesson 2 lecture notes']['files'][0]['filename'] == 'lecture-notes-v2.pdf'
    assert rows['Week 2 Lesson 2 lecture notes']['section_name'] == 'Week 2 : RAG'
    assert rows['Week 2 Lesson 2 lecture notes']['parent_section_id'] is None
    assert rows['notes 914']['section_id'] == 914 and rows['notes 914']['parent_section_name'] == 'Week 2 : RAG'
    assert rows['Lesson 2.2']['subsection_section_id'] == 914


def test_inventory_filters_keep_totals_honest():
    pdf = inventory(course(), mimetype='application/pdf')
    assert pdf['total_modules'] == 12 and pdf['matched'] == 7
    assert all(r['files'] for r in pdf['modules'])
    assigns = inventory(course(), modname='assign')
    assert [r['name'] for r in assigns['modules']] == ['Exercise 2-1 Delivery']
    assert inventory('not a list')['modules'] == []


def test_inventory_is_a_parsed_read_command():
    assert command_specs()['course.inventory'].policy == 'auto'
    spec, params = prepare_moodle('moodle course inventory 50 --mimetype application/pdf')
    assert spec.key == 'course.inventory' and params['course_id'] == 50 and params['mimetype'] == 'application/pdf'


def test_pack_routes_inventory_and_teaches_it():
    pack = load_pack()
    assert pack.data('routing.yaml')['DEFAULT_SKILL']['moodle.course.inventory'] == 'moodle-triage'
    assert 'moodle course inventory' in pack.text('skills/moodle_course_documents.md')
    assert 'moodle.course.inventory' not in load_pack(version='1.11.7').data('routing.yaml')['DEFAULT_SKILL']


class BudgetFallback(unittest.IsolatedAsyncioTestCase):
    async def test_empty_answer_after_budget_states_reads_and_how_to_continue(self):
        a, p, s = agent([message('', [tool('lamb assistant get 42')]), message('')])
        a.max_tool_rounds = 1
        a.required_skill = lambda *args: None
        answer = await turn(a, False, 'Inspect assistant 42')
        assert 'continue' in answer and 'Reads completed' in answer
        assert a.conversation[-1]['content'].endswith(answer.split('\n\n')[-1])
