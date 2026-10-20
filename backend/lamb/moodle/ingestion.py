"""Explicit KB chunking, pinned in import reviews and reused on refresh."""
import click

SPLITTERS = ('RecursiveCharacterTextSplitter', 'CharacterTextSplitter', 'TokenTextSplitter')
DEFAULTS = {'chunk_size': 1000, 'chunk_overlap': 100, 'splitter_type': SPLITTERS[0]}


def options():
    return [click.Option(['--chunk-size'], type=click.IntRange(min=1), help='Chunk size; characters unless using TokenTextSplitter.'),
            click.Option(['--chunk-overlap'], type=click.IntRange(min=0), help='Overlap in the same units; must be smaller than chunk size.'),
            click.Option(['--splitter-type'], type=click.Choice(SPLITTERS), help='KB text splitter. Defaults to recursive character splitting.')]


def configuration(params, *, single_file=False, previous=None):
    overrides = {k: params[k] for k in DEFAULTS if params.get(k) is not None}
    if single_file:
        if overrides:
            raise ValueError('Chunking options apply only to KB imports; single-file grounding keeps the full document')
        return None
    result = {**DEFAULTS, **{k: v for k, v in (previous or {}).items() if k in DEFAULTS}, **overrides}
    if (type(result['chunk_size']) is not int or result['chunk_size'] < 1 or
            type(result['chunk_overlap']) is not int or not 0 <= result['chunk_overlap'] < result['chunk_size']):
        raise ValueError('Use a positive --chunk-size and 0 <= --chunk-overlap < chunk size')
    if result['splitter_type'] not in SPLITTERS:
        raise ValueError('Unsupported --splitter-type')
    return dict(result, units='tokens' if result['splitter_type'] == 'TokenTextSplitter' else 'characters')
