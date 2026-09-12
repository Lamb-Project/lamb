"""New RAG assistants must deliver retrieved context without a hand-written template."""
import json,unittest
from types import SimpleNamespace as N
from creator_interface.assistant_router import prepare_assistant_body
from lamb.completions.pps.simple_augment import prompt_processor

class CreationContext(unittest.TestCase):
    def prepare(self,mode,**extra):
        body,error=prepare_assistant_body({'name':'test','metadata':json.dumps({'rag_processor':mode,'prompt_processor':'simple_augment'}),**extra},{'id':7,'email':'test@example.test'})
        self.assertIsNone(error)
        return body
    def test_default_rag_template_delivers_context_and_question(self):
        for mode in ['simple_rag','single_file_rag','context_aware_rag','hierarchical_rag','rubric_rag']:
            with self.subTest(mode=mode):
                body=self.prepare(mode)
                out=prompt_processor({'messages':[{'role':'user','content':'QUESTION_MARKER'}]},N(**body),{'context':'CONTEXT_MARKER'})
                self.assertIn('CONTEXT_MARKER',out[-1]['content'])
                self.assertIn('QUESTION_MARKER',out[-1]['content'])
    def test_explicit_template_is_preserved(self):
        for template in ['', 'Custom {user_input}', '{context} / {user_input}']:
            self.assertEqual(self.prepare('rubric_rag',prompt_template=template)['prompt_template'],template)
    def test_no_rag_still_passes_original_message(self):
        body=self.prepare('no_rag')
        self.assertEqual(body['prompt_template'],'')
        self.assertEqual(prompt_processor({'messages':[{'role':'user','content':'Original'}]},N(**body))[-1]['content'],'Original')
    def test_custom_processor_does_not_receive_assumed_template(self):
        body=self.prepare('simple_rag',metadata={'rag_processor':'simple_rag','prompt_processor':'custom'})
        self.assertEqual(body['prompt_template'],'')

if __name__=='__main__':unittest.main()
