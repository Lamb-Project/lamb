"""RAG_collections resolves to accessible KB IDs or fails loudly (#517)."""
import pytest

from lamb.services.rag_collections import RagCollectionsError, resolve_for_user, resolve_rag_collections

KBS = [
    {'kb_id': '1', 'kb_name': 'a1_syllabus_and_plans'},
    {'kb_id': '9', 'kb_name': 'jap_kb_w01_28cdfa'},
    {'kb_id': '12', 'kb_name': 'shared_notes'},
    {'kb_id': '13', 'kb_name': 'shared_notes'},
]


def test_ids_pass_through_in_order_without_duplicates():
    assert resolve_rag_collections('9, 1,9', KBS) == '9,1'


def test_exact_name_resolves_to_its_id():
    assert resolve_rag_collections('jap_kb_w01_28cdfa', KBS) == '9'
    assert resolve_rag_collections('1,jap_kb_w01_28cdfa', KBS) == '1,9'


def test_empty_value_stays_empty():
    assert resolve_rag_collections('', KBS) == ''
    assert resolve_rag_collections(' , ', KBS) == ''
    assert resolve_for_user('', 8, 2, lookup=lambda u, o: pytest.fail('no lookup for empty value')) == ''


@pytest.mark.parametrize('raw', ['99', 'unknown_kb', 'JAP_KB_W01_28CDFA', '1,missing'])
def test_unresolvable_entry_is_rejected_by_name(raw):
    with pytest.raises(RagCollectionsError) as exc:
        resolve_rag_collections(raw, KBS)
    assert "lamb kb list" in str(exc.value)


def test_ambiguous_name_is_rejected_with_candidate_ids():
    with pytest.raises(RagCollectionsError) as exc:
        resolve_rag_collections('shared_notes', KBS)
    assert '12, 13' in str(exc.value)


def test_resolution_uses_the_given_owner_and_organization():
    seen = []

    def lookup(user_id, org_id):
        seen.append((user_id, org_id))
        return [{'kb_id': '5', 'kb_name': 'b1_week_1_exercises_3_to_5'}]

    assert resolve_for_user('b1_week_1_exercises_3_to_5', 10, 3, lookup=lookup) == '5'
    assert seen == [(10, 3)]
    with pytest.raises(RagCollectionsError):
        resolve_for_user('1', 10, 3, lookup=lookup)  # another owner's private KB
