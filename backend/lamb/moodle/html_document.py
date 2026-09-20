"""Small, offline HTML-to-Markdown conversion for Moodle authored documents.

No rendering, scripts, remote media, MathJax or LLM calls. Losses are explicit.
"""
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode


def safe_link(value, base):
    target = urlsplit(urljoin(base, value))
    if target.scheme not in {'http', 'https'} or target.username or target.password:
        return ''
    query = [(k, v) for k, v in parse_qsl(target.query) if k.lower() not in
             {'token', 'wstoken', 'access_token', 'sesskey', 'password', 'secret'}]
    return urlunsplit((target.scheme, target.netloc, target.path, urlencode(query), target.fragment))


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ['root', {}, []]
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = [tag, dict(attrs), []]
        self.stack[-1][2].append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            if len(self.stack) > 100:
                raise ValueError('HTML nesting exceeds the conversion limit')
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1][2].append(data)


def convert_html(html, base_url):
    parser = Tree()
    parser.feed(html)
    losses = {'images': 0, 'media': 0, 'complex_tables': 0, 'active_content': 0}
    has_text = False

    def render(node):
        nonlocal has_text
        if isinstance(node, str):
            has_text = has_text or bool(node.strip())
            return re.sub(r'\s+', ' ', node)
        tag, attrs, children = node
        if tag in {'script', 'style', 'head', 'form', 'template'}:
            losses['active_content'] += 1
            return ''
        if tag == 'img':
            losses['images'] += 1
            return '[Image omitted]'
        if tag in {'iframe', 'object', 'embed', 'video', 'audio', 'canvas', 'svg', 'math'}:
            losses['media'] += 1
            return '[Media or formula omitted]'
        if tag == 'table':
            rows = []
            def collect(item):
                if isinstance(item, str): return
                if item[0] == 'tr': rows.append(item)
                else:
                    for child in item[2]: collect(child)
            collect(node)
            cells = [[c for c in row[2] if not isinstance(c, str) and c[0] in {'th', 'td'}] for row in rows]
            complex_table = any(c[1].get('colspan', '1') != '1' or c[1].get('rowspan', '1') != '1' for row in cells for c in row)
            values = [[''.join(render(ch) for ch in c[2]).strip().replace('|', '\\|').replace('\n', ' ') for c in row] for row in cells]
            if not values: return ''
            if complex_table or len({len(r) for r in values}) > 1:
                losses['complex_tables'] += 1
                return '\n\n[Complex table flattened]\n' + '\n'.join(' | '.join(r) for r in values) + '\n\n'
            lines = ['| ' + ' | '.join(r) + ' |' for r in values]
            lines.insert(1, '| ' + ' | '.join('---' for _ in values[0]) + ' |')
            return '\n\n' + '\n'.join(lines) + '\n\n'
        text = ''.join(render(child) for child in children)
        if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            return '\n\n' + '#' * int(tag[1]) + ' ' + text.strip() + '\n\n'
        if tag in {'p', 'div', 'section', 'article', 'ul', 'ol', 'blockquote'}:
            return '\n\n' + text.strip() + '\n\n'
        if tag == 'li': return '\n- ' + text.strip() + '\n'
        if tag == 'br': return '\n'
        if tag == 'hr': return '\n\n---\n\n'
        if tag in {'strong', 'b'}: return '**' + text + '**'
        if tag in {'em', 'i'}: return '*' + text + '*'
        if tag == 'a':
            url = safe_link(attrs.get('href', ''), base_url)
            return '[' + text.strip() + '](' + url.replace(')', '%29') + ')' if url else text
        return text

    markdown = re.sub(r'\n[ \t]+', '\n', render(parser.root))
    markdown = re.sub(r'\n{3,}', '\n\n', markdown).strip() + '\n'
    if not has_text or not markdown.strip(): raise ValueError('Document has no importable text; images and media are not converted')
    return markdown, losses


LOSS_NOTICE = ('Text conversion preserves headings, lists, links and simple tables. '
               'Images, media and image-based formulae are omitted; complex tables may be flattened. '
               'No OCR or rendering is performed. Review the imported document before using it.')
