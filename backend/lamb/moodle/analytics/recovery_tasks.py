"""Route bounded analytics recovery without weakening namespace permissions."""
from . import completion_tasks, quiz_tasks, forum_tasks, gradebook_tasks
from .gradebook_run import GradebookCheckpoints
from .forum_checkpoints import ForumCheckpoints
from .checkpoints import CompletionCheckpoints
from .quiz_run import QuizCheckpoints


def execute(runtime, results, client, owner, key, params):
    handlers = ((CompletionCheckpoints, completion_tasks), (QuizCheckpoints, quiz_tasks), (ForumCheckpoints, forum_tasks),
                (GradebookCheckpoints,gradebook_tasks))
    if key == 'analytics.start':
        if params['recipe']=='assessment-comparison':
            return gradebook_tasks.execute(runtime,results,client,owner,key,params)
        if params['recipe'] in {'forum-participation','forum-discussions','forum-network'}:
            return forum_tasks.execute(runtime,results,client,owner,key,params)
        if params['recipe'] not in {'quiz-overview', 'activity-completion'}:
            raise ValueError('Unsupported recoverable recipe')
        handler = quiz_tasks if params['recipe'] == 'quiz-overview' else completion_tasks
        return handler.execute(runtime, results, client, owner, key, params)
    if key == 'analytics.runs':
        items = []
        for _, handler in handlers:
            items.extend(handler.execute(runtime, results, client, owner, key, params)['items'])
        client.checkpoint()
        return {'items': sorted(items, key=lambda item: item['started_at'], reverse=True),
                'meaning': 'Authorized completion, quiz, forum and assessment recovery handles for this connection.'}
    if key != 'analytics.continue':
        raise ValueError('Unknown analytics recovery operation')
    selected = []
    for factory, handler in handlers:
        store = factory(results)
        path = store._path(params['run_id'])
        if path.exists() or path.is_symlink():
            selected.append(handler)
    if len(selected) != 1:
        raise PermissionError('Analytics run is unavailable')
    return selected[0].execute(runtime, results, client, owner, key, params)
