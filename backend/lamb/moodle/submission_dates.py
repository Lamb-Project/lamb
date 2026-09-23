"""Correct provenance for dates returned by mod_assign_get_assignments.

This source applies the connected Moodle user's effective access. A presentation
correction on read must not rewrite old immutable snapshots or their numbers.
"""
TEXT = {
    'en': ('Connected account deadline','Connected account deadline passed',
        'Dates apply to the connected Moodle account and may include its overrides. They are not verified course defaults or individual student deadlines.'),
    'es': ('Fecha límite de la cuenta conectada','Plazo de la cuenta conectada vencido',
        'Las fechas corresponden a la cuenta de Moodle conectada y pueden incluir sus excepciones. No son fechas base del curso verificadas ni plazos individuales del alumnado.'),
    'ca': ('Data límit del compte connectat','Termini del compte connectat vençut',
        'Les dates corresponen al compte de Moodle connectat i poden incloure les seves excepcions. No són dates base del curs verificades ni terminis individuals de l’alumnat.'),
    'eu': ('Konektatutako kontuaren epemuga','Konektatutako kontuaren epemuga amaituta',
        'Datak konektatutako Moodle kontuari dagozkio eta haren salbuespenak izan ditzakete. Ez dira egiaztatutako ikastaroaren oinarrizko datak edo ikasleen banakako epemugak.'),
}


def with_date_provenance(snapshot):
    if snapshot.get('recipe') != 'assignment-submissions-v1':
        return snapshot
    title,passed,caption=TEXT.get(snapshot.get('language'),TEXT['en'])
    labels=list(snapshot['labels'])
    labels[4]=title;labels[7]=passed
    return {**snapshot,'labels':labels,'deadline_basis':'connected_account_effective',
        'deadline_provenance_caption':caption,
        'deadline_provenance_corrected_on_read':'deadline_basis' not in snapshot}
