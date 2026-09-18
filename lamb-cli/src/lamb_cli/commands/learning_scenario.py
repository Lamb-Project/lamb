"""Personal learning scenarios shared with AAC conversations."""
import typer
from lamb_cli.client import get_client
from lamb_cli.output import print_json

app = typer.Typer(help='Manage persistent learning scenarios for AAC.')
BASE = '/creator/aac/learning-scenarios'

@app.command('list')
def list_scenarios(output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    with get_client() as c: print_json(c.get(BASE))

@app.command('get')
def get(key: str, output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    with get_client() as c: print_json(c.get(BASE+'/'+key))

@app.command('create')
def create(title: str, content: str = typer.Option('', '--content'), moodle_course_id: int = typer.Option(None, '--moodle-course-id', min=1), output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    with get_client() as c: print_json(c.post(BASE, json={'title':title, 'content':content, **({'links':{'moodle_course_id':moodle_course_id}} if moodle_course_id is not None else {})}))

@app.command('update')
def update(key: str, revision: int = typer.Option(..., '--revision'), title: str = typer.Option(None, '--title'), content: str = typer.Option(None, '--content'), moodle_course_id: str = typer.Option(None, '--moodle-course-id', help='Positive course ID, or none to clear the link.'), output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    body = {'revision':revision}
    if title is not None: body['title'] = title
    if content is not None: body['content'] = content
    if moodle_course_id is not None:
        if moodle_course_id != 'none' and (not moodle_course_id.isdigit() or int(moodle_course_id) < 1):
            raise typer.BadParameter('Use a positive Moodle course ID or none')
        body['links'] = {} if moodle_course_id == 'none' else {'moodle_course_id':int(moodle_course_id)}
    if len(body)==1: raise typer.BadParameter('Provide --title, --content or --moodle-course-id')
    with get_client() as c: print_json(c.put(BASE+'/'+key, json=body))

@app.command('remove')
def remove(key: str, revision: int = typer.Option(..., '--revision'), output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    with get_client() as c: print_json(c.delete(BASE+'/'+key, params={'revision':revision}))

@app.command('duplicate')
def duplicate(key: str, title: str = typer.Option(..., '--title'), output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    with get_client() as c: print_json(c.post(BASE+'/'+key+'/duplicate', json={'title':title}))

@app.command('default')
def default(key: str, output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    """Set ID as the default; use none to clear it."""
    with get_client() as c: print_json(c.put(BASE+'/default', json={'scenario_id':None if key=='none' else key}))

@app.command('selected')
def selected(session: str, output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    with get_client() as c: print_json(c.get('/creator/aac/sessions/'+session+'/learning-scenario'))

@app.command('select')
def select(session: str, key: str, output: str = typer.Option("json", "-o", "--output", help="Structured JSON output.")):
    """Select ID, default or none for an idle conversation."""
    with get_client() as c: print_json(c.put('/creator/aac/sessions/'+session+'/learning-scenario', json={'scenario_id':None if key=='none' else key}))
