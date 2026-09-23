"""Narrow response checks for observed analytics failures, not semantic proof.

Only activated by successful analytics evidence in the current turn. Never
rewrites a factual claim silently. The agent may repair once without tools.
"""
import re
import unicodedata

RECIPES = {'quiz-overview', 'deadlines', 'grade-distribution', 'grading-queue', 'course-access', 'resource-reach', 'activity-completion', 'view-trends', 'view-heatmap', 'view-distribution', 'active-day-distribution'}


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


def failure_notice(language):
    return {
        'en':'I could not validate the explanation against the saved chart. The chart remains available in Moodle > Charts; no additional data was collected during the explanation check.',
        'es':'No he podido validar la explicación con el gráfico guardado. El gráfico sigue disponible en Moodle > Charts; no se han consultado datos adicionales durante la comprobación de la explicación.',
        'ca':'No he pogut validar l’explicació amb el gràfic desat. El gràfic continua disponible a Moodle > Charts; no s’han consultat dades addicionals durant la comprovació de l’explicació.',
        'eu':'Ezin izan dut azalpena gordetako grafikoarekin baliozkotu. Grafikoa Moodle > Charts atalean dago; azalpena egiaztatzean ez da datu gehigarririk bildu.',
    }.get(language, 'I could not validate the explanation against the saved chart. No additional data was collected during the explanation check.')
