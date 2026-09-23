"""Narrow response checks for observed analytics failures, not semantic proof.

Only activated by successful analytics evidence in the current turn. Never
rewrites a factual claim silently. The agent may repair once without tools.
"""
import re
import unicodedata

RECIPES = {'forum-network', 'forum-participation', 'forum-discussions', 'quiz-overview', 'deadlines', 'grade-distribution', 'grading-queue', 'course-access', 'resource-reach', 'activity-completion', 'view-trends', 'view-heatmap', 'view-distribution', 'active-day-distribution'}


def contract(result):
    data = result.get('data')
    if not result.get('success') or not isinstance(data, dict):
        return None
    recipe = data.get('recipe')
    if not isinstance(recipe, dict) or recipe.get('id') not in RECIPES:
        return None
    return {'recipe':recipe['id'],
            'publication_unknown':recipe['id']=='grade-distribution' and data.get('grade_released') is None}


def violations(text, evidence):
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    normalized = normalized.replace('*','').replace('`','')
    errors = []
    if not text.strip():
        errors.append('Provide a nonempty explanation of the saved evidence and its limits.')
    if '<<<canvas' in normalized or '<<<end_canvas' in normalized:
        errors.append('Use the saved Moodle chart; do not emit canvas markup.')
    if re.search(r'(?m)^\s*(?:next\??|what next\??|¿?que hacemos ahora\??|que fem ara\??|zer egin orain\??)\s*:?[ \t]*$', normalized):
        errors.append('Remove the unrequested next-action menu; keep the requested explanation.')
    if evidence.get('publication_unknown'):
        patterns = [r'\b(?:unpublished|not (?:yet )?(?:released|published))\b',
                    r'\bno (?:son|estan) [^.\n]{0,65}\bpublicad[ao]s?\b',
                    r'\bno (?:son|estan) [^.\n]{0,65}\bpublicades?\b',
                    r'\bargitaratu gabe\b']
        if any(re.search(pattern,normalized) for pattern in patterns):
            errors.append('Publication was not collected. Do not assert published or unpublished; explicitly say it is unknown.')
    return errors


def repair_instruction(errors):
    return ('[Application analytics response check] Revise the draft answer once, without tools or new evidence. '
            'Preserve the requested explanation and exact evidence. Do not discuss this internal check. '
            + ' '.join(errors))


def evidence_instruction(evidence, state):
    """Trusted tail guidance, never inferred from chart labels or persisted.

Source locale describes saved evidence, not the requested response language.
This is guidance rather than a claim that language or arithmetic is validated.
"""
    from lamb.aac.language import LANGUAGES
    state = state or {}
    language = state.get('response_language_policy', {}).get('effective_language', state.get('ui_language'))
    parts = ['[Application analytics evidence guidance] Explain the saved evidence without an unrequested next-action or refresh menu.']
    if language in LANGUAGES:
        parts.append(f'Reply in {LANGUAGES[language]}. Saved chart labels and captions may use another language; '
                     'they do not change the response language. Keep resource names and commands unchanged.')
    if evidence.get('recipe') == 'quiz-overview':
        parts.append('Preserve the saved attempt_policy exactly: all_finished includes all selected finished attempts, '
                     'not just the latest one. Missing marks are not zero; excluded previews are not exemptions. '
                     'Retry score_change_percentage_points is a difference in PERCENTAGE POINTS, not raw points '
                     'or relative percent improvement. between_attempt_seconds is seconds, not study time. '
                     'Do not infer individual starting or ending scores from an aggregate mean delta.')
    if evidence.get('recipe') in {'forum-participation','forum-discussions'}:
        parts.append('Forum learner IDs are not names; do not invent identity mappings. '
                     'outside_population_window_posts means posts INSIDE the window by authors OUTSIDE the current student population, '
                     'not posts outside the date window. Reply counts are counts, not last-activity timestamps. '
                     'Use window_start_local and window_end_local verbatim for dates; do not reinterpret UTC as local dates. '
                     'Participation counts use public post creation in [since, until), with an exclusive end. '
                     'For forum-participation rows, replies includes ONLY current students replies INSIDE that window. '
                     'For forum-discussions rows, observed_public_replies_as_of includes all visible authors and self-replies '
                     'through the snapshot, not only students or the window. Never apply that broader rule to learner rows. '
                     'Age is seconds at the snapshot, not now. '
                     'No observed public replies does not establish unanswered or unresolved questions. '
                     'Resolution, contribution quality and learning are not established; private/deleted posts are excluded.')
    if evidence.get('recipe')=='forum-network':
        parts.append('Forum network IDs are Moodle student identifiers, not verified names. '
                     'Edges point from reply author to immediate parent author, both current students. '
                     'Only reply creation must be inside the requested window; parents may predate it. '
                     'Self-replies and nonstudent endpoints are excluded; unavailable parents are not reconstructed. '
                     'Degrees count distinct incoming/outgoing peers; unique_peers unions both directions, '
                     'not their sum. Edge weights count replies, not unique peers. '
                     'Graph positions follow student IDs around a circle, not importance. '
                     'Do not confuse node position with arrow direction or self-replies with self-criticism. '
                     'Above 50 students the saved view is an exact degree table, not a truncated graph. '
                     'Unknown no-peer flags reflect incomplete evidence. Even complete zero-edge evidence '
                     'does not prove social isolation, disengagement, quality, learning or social value. '
                     'Use window_start_local and window_end_local verbatim, with exclusive end. '
                     'Evidence is saved at the snapshot, not current Moodle data.')
    return ' '.join(parts)


def failure_notice(language):
    return {
        'en':'I could not validate the explanation against the saved chart. The chart remains available in Moodle > Charts; no additional data was collected during the explanation check.',
        'es':'No he podido validar la explicación con el gráfico guardado. El gráfico sigue disponible en Moodle > Charts; no se han consultado datos adicionales durante la comprobación de la explicación.',
        'ca':'No he pogut validar l’explicació amb el gràfic desat. El gràfic continua disponible a Moodle > Charts; no s’han consultat dades addicionals durant la comprovació de l’explicació.',
        'eu':'Ezin izan dut azalpena gordetako grafikoarekin baliozkotu. Grafikoa Moodle > Charts atalean dago; azalpena egiaztatzean ez da datu gehigarririk bildu.',
    }.get(language, 'I could not validate the explanation against the saved chart. No additional data was collected during the explanation check.')
