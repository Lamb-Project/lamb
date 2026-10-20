"""Compatibility for the pinned CLI's incorrect subwikiid request parameter.

Moodle 4.5 mod/wiki/classes/external.php::get_subwiki_pages_parameters
requires wikiid. This adapter preserves the library HTTP/read-only boundary.
"""
from moodle_cli.services.base import BaseService


class WikiPagesService(BaseService):
    def pages(self, wiki_id):
        data = self.call('mod_wiki_get_subwiki_pages', wikiid=wiki_id)
        return data.get('pages', [])
