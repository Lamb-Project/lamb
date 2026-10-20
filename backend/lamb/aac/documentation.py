"""Language-neutral documentation anchors with explicit English fallback."""
import hashlib
import json
import re
from lamb.aac.pack_loader import docs_root

FALLBACK = '<!-- fallback: en -->'


def manifest():
    return json.loads((docs_root() / 'manifest.json').read_text())


def sections(text):
    matches = list(re.finditer(r'^<a id="([a-z0-9-]+)"></a>\s*$', text, re.M))
    return {m.group(1): text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
            for i,m in enumerate(matches)}


def coverage(language):
    return manifest()['coverage'][language]


def content_metadata(root, metadata):
    """Derive coverage and revision hashes from the delivered documentation."""
    coverage = {}
    hashes = {}
    for language in metadata['coverage']:
        translated = total = 0
        for topic, definition in metadata['topics'].items():
            path = root/language/(topic+'.md')
            text = path.read_text()
            actual = sections(text)
            if list(actual) != definition['anchors']:
                raise ValueError(f'Documentation anchor mismatch: {language}/{topic}')
            if language == 'en' and any(not body or FALLBACK in body for body in actual.values()):
                raise ValueError(f'Canonical English section is missing: {topic}')
            total += len(actual)
            translated += sum(bool(body) and FALLBACK not in body for body in actual.values())
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        coverage[language] = {'translated_sections': translated, 'total_sections': total}
    revision = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {'coverage': coverage, 'document_hashes': hashes, 'revision': revision}


def read_topic(topic, language='en', section=None):
    metadata = manifest()
    if topic not in metadata['topics'] or language not in metadata['coverage']:
        raise ValueError('Unknown documentation topic or language')
    canonical = sections((docs_root() / 'en' / (topic+'.md')).read_text())
    local = sections((docs_root() / language / (topic+'.md')).read_text())
    if section and section not in canonical:
        raise ValueError(f'Unknown anchor {section}; available: {", ".join(canonical)}')
    anchors = [section] if section else list(canonical)
    fallback = [anchor for anchor in anchors if not local.get(anchor) or FALLBACK in local[anchor]]
    text = '\n\n'.join(f'<a id="{anchor}"></a>\n'+(canonical[anchor] if anchor in fallback else local[anchor]) for anchor in anchors)
    return {'topic':topic, 'language':language, 'content':text, 'anchors':anchors,
            'fallback_language':'en' if fallback else None, 'fallback_sections':fallback,
            'notice':('Some requested sections are available only in English. Tell the user explicitly; '
                      'do not present English text or images as a localized guide.') if fallback else None,
            'version':metadata['version']}


def validate_docs(root=None):
    root = root or docs_root()
    metadata = json.loads((root/'manifest.json').read_text())
    calculated = content_metadata(root, metadata)
    for key, value in calculated.items():
        if metadata.get(key) != value:
            raise ValueError(f'Documentation {key} is stale; rebuild the documentation manifest')
    for topic, definition in metadata['topics'].items():
        expected = definition['anchors']
        for language in metadata['coverage']:
            path = root/language/(topic+'.md')
            if list(sections(path.read_text())) != expected:
                raise ValueError(f'Documentation anchor mismatch: {language}/{topic}')
    for image in metadata['images']:
        p = root/image['path']
        if not p.resolve().is_relative_to(root.resolve()) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=image['sha256']:
            raise ValueError('Invalid documentation image: '+image['path'])
    return True
