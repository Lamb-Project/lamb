"""Every reply ends with numbered options, except next to a prepared approval (pack 1.11.9)."""
from lamb.aac.pack_loader import load_pack


def test_options_rule_is_unconditional_from_1_11_9():
    persona = load_pack().text('persona.md')
    assert 'End every reply with numbered options' in persona and 'add no menu before or alongside it' in persona
    assert 'When a useful next choice is needed' in load_pack(version='1.11.8').text('persona.md')  # frozen
