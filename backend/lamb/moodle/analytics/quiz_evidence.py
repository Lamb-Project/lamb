"""Presentation semantics for new and already-saved quiz evidence.

Apply only after authorization. Never rewrite the immutable stored snapshot.
"""
from copy import deepcopy

SCORE_BASES = {
    'first_finished': 'Raw marks from each student’s first finished attempt; not final gradebook grades.',
    'latest_finished': 'Raw marks from each student’s latest finished attempt; not final gradebook grades.',
    'best_scored_finished': 'Best observed raw mark per student among scored finished attempts; not final gradebook grades.',
    'all_finished': 'Raw marks from ALL selected finished attempts, including multiple attempts per student; NOT last-attempt marks or final gradebook grades.',
}
BEST_WARNINGS = (
    'Best observed scores can change when missing marks arrive.',
    'La mejor puntuación observada puede cambiar al llegar notas ausentes.',
    'La millor puntuació observada pot canviar quan arribin notes absents.',
    'Behatutako puntuaziorik onena alda daiteke falta diren notak iristean.',
)
BEST_LIMITATION = 'Best-scored selection uses observed marks only; an ungraded attempt may change the best result.'


def with_quiz_semantics(snapshot):
    recipe = snapshot.get('recipe')
    if not isinstance(recipe, dict) or recipe.get('id') != 'quiz-overview':
        return snapshot
    policy = snapshot.get('metrics', {}).get('attempt_policy')
    if policy not in SCORE_BASES:
        return snapshot  # Do not guess a policy for unsupported legacy evidence.
    result = deepcopy(snapshot)
    result['attempt_policy'] = policy
    result['score_basis'] = SCORE_BASES[policy]
    result['preview_basis'] = 'Excluded previews are practice/teacher previews, not student exemptions.'
    result['retry_basis'] = ('Actual finished attempts 1 and 2 with both marks. Score change is in percentage points, '
                             'not raw points or relative percent change; the between-attempt gap is in seconds, '
                             'not study time. Aggregate deltas do not provide individual endpoint scores.')
    if policy != 'best_scored_finished':
        for warning in BEST_WARNINGS:
            if isinstance(result.get('caption'), str):
                result['caption'] = result['caption'].replace(warning + ' ', '').replace(warning, '')
        for container in (result, result['metrics']):
            if isinstance(container.get('limitations'), list):
                container['limitations'] = [item for item in container['limitations'] if item != BEST_LIMITATION]
    return result
