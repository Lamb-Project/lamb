"""Duplicating an already-decoded rubric must preserve the source and nested data."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from lamb.evaluaitor.rubric_database import RubricDatabaseManager

class DuplicateRubric(unittest.TestCase):
    def test_decoded_source_copied_without_mutation(self):
        source={'rubric_data':{'rubricId':'old','title':'Original','criteria':[{'id':'c1','weight':100,'levels':[{'id':'l1','score':1}]}]}}
        before=copy.deepcopy(source)
        db=RubricDatabaseManager.__new__(RubricDatabaseManager)
        db.db_manager=SimpleNamespace(get_user_organization_by_email=Mock(return_value={'id':9}))
        db._get_rubric_by_id_unchecked=Mock(return_value=source)
        db.create_rubric=Mock(side_effect=lambda **kwargs:kwargs)
        result=db.duplicate_rubric('old','new@example.test')
        self.assertEqual(source,before)
        self.assertEqual(result['rubric_data']['title'],'Original (Copy)')
        self.assertNotEqual(result['rubric_data']['rubricId'],'old')
        self.assertEqual(result['organization_id'],9);self.assertFalse(result['is_public'])
        self.assertEqual(result['rubric_data']['criteria'],source['rubric_data']['criteria'])
        result['rubric_data']['criteria'][0]['weight']=50
        self.assertEqual(source,before)
