"""Create an approved batch's KB once, retaining uncertain outcomes for inspection."""
from .import_delivery import definite_refusal


async def create_destination(storage, identity, http, runtime):
    # The same owner lock used by individual uploads protects this one request
    # across workers and restarts. No retry after an uncertain create outcome.
    with storage.lock():
        ticket = storage.get('reviews', identity)
        if not ticket.get('approved') or runtime.result_binding() != ticket['binding']:
            raise PermissionError('Folder approval or Moodle connection changed')
        previous = ticket.get('kb_creation')
        if previous:
            return previous['status'] == 'completed'
        destination = ticket['review']['destination']
        ticket['kb_creation'] = {'status': 'outcome_unknown', 'name': destination['new_kb'],
            'note': 'Creation may have completed. Inspect your knowledge bases before starting another batch. This batch will not create again.'}
        storage.put('reviews', identity, ticket)
        try:
            result = await http.post('/creator/knowledgebases', json={
                'name': destination['new_kb'], 'description': destination.get('description', '')})
            if result.get('kb_server_available') is False:
                ticket['kb_creation'].update(status='failed', note='Knowledge base server unavailable; no files were imported.')
                storage.put('reviews', identity, ticket)
                return False
            kid = result.get('kb_id')
            if isinstance(kid, bool) or not str(kid).isdigit() or int(kid) < 1:
                raise ValueError('Creation returned no valid knowledge base id')
            ticket['kb_creation'] = {'status': 'completed', 'name': destination['new_kb'], 'kb_id': int(kid)}
            storage.put('reviews', identity, ticket)
            return True
        except BaseException as exc:
            if definite_refusal(exc):
                ticket['kb_creation'].update(status='failed', note='Knowledge base creation was refused. No files were imported.')
                storage.put('reviews', identity, ticket)
            raise
