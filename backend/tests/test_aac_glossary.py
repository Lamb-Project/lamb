"""Controlled annotation changes only the provider copy of user prose."""
import copy
import unittest
from lamb.aac.glossary import annotate, lookup, model_messages, vocabulary
from lamb.aac.pack_loader import load_pack
from tests.test_aac_legacy import agent, message, turn


class GlossaryTests(unittest.IsolatedAsyncioTestCase):
    def glossary(self, locale='ca'):
        return load_pack().data(f'glossary/{locale}.yaml')

    async def test_controlled_stems_and_negatives(self):
        glossary = self.glossary()
        self.assertEqual(annotate("L'assistent i els assistents", glossary), "L'assistent (en:assistant) i els assistents (en:assistant)")
        for text in ['assistència', 'asistencia', 'publication_date', 'assistant_id', 'preassistent', 'assistentíssim']:
            self.assertEqual(annotate(text, glossary), text)
        basque = self.glossary('eu')
        self.assertEqual(annotate('laguntzailearen', basque), 'laguntzailearen (en:assistant)')
        self.assertEqual(lookup(basque, 'laguntzailearen')[0]['english'], 'assistant')
        self.assertEqual(lookup(glossary, 'ASSISTENTS')[0]['english'], 'assistant')
        with self.assertRaises(ValueError): vocabulary({'terms': [{'english': 'a', 'forms': ['x']}, {'english': 'b', 'forms': ['x']}]})

    async def test_quotes_code_and_unclosed_blocks_are_never_annotated(self):
        glossary = self.glossary()
        samples = ['"assistent"', '“assistent”', '«assistent»', "'assistent'", '`assistent`',
                   '``assistent ` text``', '```python\nassistent\n```', '~~~text\nassistent\n~~~',
                   '```text\nassistent', '`assistent', '"assistent', '> assistent\n> assistents',
                   '"assistent \\" assistents"', '"assistent\nassistents"']
        for text in samples:
            with self.subTest(text=text): self.assertEqual(annotate(text, glossary), text)
        self.assertEqual(annotate('"assistent" assistents', glossary), '"assistent" assistents (en:assistant)')

    async def test_non_user_messages_and_original_objects_remain_unchanged(self):
        history = [{'role': 'user', 'content': 'assistent'}, {'role': 'assistant', 'content': 'assistent'},
                   {'role': 'tool', 'content': 'assistent'}, {'role': 'user', 'content': '[System: workflow] assistent'}]
        saved = copy.deepcopy(history)
        mapped = model_messages(history, self.glossary())
        self.assertEqual(history, saved)
        self.assertEqual(mapped[0]['content'], 'assistent (en:assistant)')
        self.assertEqual(mapped[1:], saved[1:])

    async def test_both_transports_send_annotation_but_store_original_and_never_translate(self):
        pack = load_pack()
        for streaming in (False, True):
            state = {'brief': {'glossary': self.glossary()}, 'ui_language': 'ca'}
            a, provider, shell = agent([message('Resposta')], pack=pack, skill_state=state)
            self.assertEqual(await turn(a, streaming, 'Explica els assistents'), 'Resposta')
            self.assertTrue(any(m.get('content') == 'Explica els assistents (en:assistant)' for m in provider.calls[0]['messages']))
            self.assertTrue(any(m.get('content') == 'Explica els assistents' for m in a.conversation))
            self.assertFalse(any('(en:assistant)' in m.get('content', '') for m in a.conversation))
            shell.execute.assert_not_awaited()
