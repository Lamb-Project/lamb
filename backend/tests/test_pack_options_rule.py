"""Next-step suggestions follow fulfillment; old immutable packs keep their historical rules."""
from lamb.aac.pack_loader import load_pack


def test_options_rule_with_its_two_exceptions():
    persona = load_pack().text('persona.md')
    assert 'Fulfill the user\'s request before offering further possibilities' in persona
    assert 'no compulsory menu' in persona
    assert 'End every reply with numbered options' not in persona
    assert 'give the likely answers as options' in load_pack(version='1.11.9').text('persona.md')  # frozen
    assert 'When a useful next choice is needed' in load_pack(version='1.11.8').text('persona.md')  # frozen


def test_persona_names_lamb_legatus_acting_for_the_teacher():
    persona = load_pack().text('persona.md')
    assert persona.startswith('You are LAMB LEGATUS') and 'the teacher has the agency' in persona and 'never an agent' in persona
