"""Public KB roots support both root and reverse-proxy deployments."""
import importlib.util
from pathlib import Path
import unittest

class StaticURL(unittest.TestCase):
    def test_root_and_subpath_with_or_without_trailing_slash(self):
        path = Path(__file__).resolve().parents[2] / 'lamb-kb-server-stable/backend/static_urls.py'
        spec = importlib.util.spec_from_file_location('kb_static_urls_test', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        for base in ['http://localhost:19090', 'https://example.test/kb']:
            for suffix in ['', '/', '///']:
                self.assertEqual(module.static_url_prefix(base + suffix), base + '/static')
