"""A reply that announces a step without taking it gets one follow-up to act or say what blocks it."""
import unittest

from lamb.aac.language import announces_unfinished_work
from lamb.moodle.course_structure import inventory
from tests.test_aac_legacy import agent, message, tool, turn
from tests.test_result_previews_and_subsections import course


def test_detects_announced_work_in_four_languages():
    for text in ('Para preparar la importación necesito las referencias. Voy a continuar con esa comprobación.',
                 'Ahora solo tengo los recursos. Obtendré las referencias de cada PDF.',
                 "I only have the resource ids. I'll now fetch the file references.",
                 'Ara continuaré amb la comprovació.', 'Erreferentziak lortuko dut.'):
        assert announces_unfinished_work(text), text


def test_questions_options_and_finished_replies_are_not_nudged():
    for text in ('¿Voy a continuar con la importación?', 'He creado la base de conocimiento prueba.',
                 'Voy a continuar cuando me digas el nombre. ¿Qué nombre quieres darle?',
                 'Puedo seguir así:\n1. Continuar con la importación\n2. Otra cosa: dime', ''):
        assert not announces_unfinished_work(text), text


def test_inventory_rows_carry_the_context_for_file_listing():
    rows = {r['name']: r for r in inventory(course())['modules']}
    assert rows['Week 2 Lesson 2 lecture notes']['contextid'] == 3410 + 5000


class Followup(unittest.IsolatedAsyncioTestCase):
    async def test_announced_step_is_taken_after_one_followup(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                a, p, s = agent([message('Voy a continuar con esa comprobación.'),
                                 message('', [tool('lamb assistant get 42')]), message('Listo: el asistente 42 existe.')])
                a.required_skill = lambda *args: None
                answer = await turn(a, streaming, 'comprueba el asistente 42')
                assert s.execute.await_count == 1 and 'Listo' in answer
                # What the user saw first stays in the conversation; streaming also shows it inline.
                assert any(m.get('content') == 'Voy a continuar con esa comprobación.' for m in a.conversation)
                assert streaming is False or 'Voy a continuar' in answer

    async def test_no_followup_after_a_question_and_at_most_one_per_turn(self):
        a, p, s = agent([message('¿Qué nombre quieres darle?')])
        a.required_skill = lambda *args: None
        assert (await turn(a, False, 'crea una base')) == '¿Qué nombre quieres darle?'
        a, p, s = agent([message('Voy a continuar.'), message('Voy a continuar con eso.')])
        a.required_skill = lambda *args: None
        answer = await turn(a, False, 'sigue')
        assert s.execute.await_count == 0 and 'Voy a continuar con eso.' in answer
        assert sum('Voy a continuar' in (m.get('content') or '') for m in a.conversation if m['role'] == 'assistant') == 2
