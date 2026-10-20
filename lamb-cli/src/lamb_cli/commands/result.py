"""Read private, immutable AAC results without local filesystem access."""
import uuid
import typer
from lamb_cli.client import get_client
from lamb_cli.output import print_json

app = typer.Typer(no_args_is_help=True)

@app.command('read')
def read_result(result_id: str, path: str = typer.Option('', '--path'),
                offset: int = typer.Option(0, '--offset', min=0)):
    """Read a bounded result page. Follow next_command; paths use JSON pointers."""
    try: identity = str(uuid.UUID(result_id))
    except ValueError: raise typer.BadParameter('Use a result UUID') from None
    with get_client() as client:
        result = client.get(f'/creator/aac/results/{identity}', params={'path':path,'offset':offset})
    print_json(result)
