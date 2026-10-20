"""Controlled vocabulary annotations for the model copy, never persisted user text."""
import re

# Protect quoted text and code before matching words. Apostrophes inside words are
# not quote delimiters (l'assistent must still be recognized in Catalan).
PROTECTED = re.compile(
    r'(?P<fence>`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:^(?P=fence)[ \t]*$|\Z)'
    r'|(?P<ticks>`+)(?!`)[^\n]*?(?:(?P=ticks)(?!`)|$)'
    r'|"(?:\\.|[^"\\])*(?:"|\Z)'
    r'|“[^”]*(?:”|\Z)|«[^»]*(?:»|\Z)'
    r"|(?<!\w)'(?:\\.|[^'\\\n])*(?:'(?!\w)|$)"
    r'|^[ \t]*>[^\n]*(?:\n[ \t]*>[^\n]*)*', re.M)


def vocabulary(glossary):
    """Expand only authored stem/suffix pairs, never arbitrary lexical guesses."""
    forms = {}
    for entry in glossary.get('terms', []):
        variants = list(entry.get('forms', []))
        for stem in entry.get('stems', []):
            variants.extend(stem['stem'] + suffix for suffix in stem['suffixes'])
        for form in variants:
            key = form.casefold()
            if key in forms and forms[key] != entry['english']:
                raise ValueError(f'Ambiguous glossary form: {form}')
            forms[key] = entry['english']
    return forms


def lookup(glossary, term):
    folded = term.casefold().strip()
    english = vocabulary(glossary).get(folded, folded)
    return [entry for entry in glossary.get('terms', [])
            if english.casefold() == entry['english'].casefold()]


def annotate(text, glossary):
    forms = vocabulary(glossary)
    negatives = {word.casefold() for word in glossary.get('negative_forms', [])}
    if not forms:
        return text
    pattern = re.compile(r'(?<!\w)('+ '|'.join(re.escape(form) for form in sorted(forms,key=len,reverse=True)) + r')(?!\w)', re.I)
    def replace(match):
        word = match.group(0)
        english = forms[word.casefold()]
        return word if word.casefold() in negatives or word.casefold()==english.casefold() else f'{word} (en:{english})'
    pieces=[];last=0
    for match in PROTECTED.finditer(text):
        pieces.extend([pattern.sub(replace,text[last:match.start()]),match.group(0)])
        last=match.end()
    pieces.append(pattern.sub(replace,text[last:]))
    return ''.join(pieces)


def model_messages(messages, glossary):
    result=[]
    for message in messages:
        copied=dict(message)
        content=copied.get('content')
        if copied.get('role')=='user' and isinstance(content,str) and not content.startswith(('[System:','[Application ')):
            copied['content']=annotate(content,glossary)
        result.append(copied)
    return result
