"""Consistent browser display for Markdown knowledge-base documents."""
from pathlib import Path
from starlette.staticfiles import StaticFiles


class KnowledgeBaseStaticFiles(StaticFiles):
    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        # Python's MIME database varies by OS/container. Unknown Markdown becomes
        # application/octet-stream, so a normal document link starts a download.
        # Display source text without interpreting embedded HTML or scripts.
        if Path(full_path).suffix.lower() in {'.md', '.markdown'}:
            response.headers['content-type'] = 'text/plain; charset=utf-8'
            response.headers['x-content-type-options'] = 'nosniff'
        return response
