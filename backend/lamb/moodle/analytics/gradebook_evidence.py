"""Read-time interpretation labels; never alter immutable grade evidence."""
from copy import deepcopy


def with_gradebook_semantics(snapshot):
    recipe = snapshot.get('recipe')
    if not isinstance(recipe, dict) or recipe.get('id') != 'assessment-comparison':
        return snapshot
    result = deepcopy(snapshot)
    result['grade_count_basis'] = (
        'graded_n counts nonexcluded, nonnull stored final grades, NOT submissions. '
        'valid_n counts scores usable for comparison. Stale items have valid_n=0 '
        'even when graded_n>0; do not subtract excluded/null counts from graded_n again.')
    result['grade_score_basis'] = (
        'Stored final grades, not raw marks. A pass threshold classifies passing; '
        'it does not generate final grades. Q1/median/Q3 are normalized percentages; '
        'IQR is percentage points, not a percent change. Missing grades are not missing submissions.')
    return result
