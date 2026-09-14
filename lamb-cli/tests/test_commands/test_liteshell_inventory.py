"""Gate every CLI command/parameter against the explicitly reviewed AAC parity inventory.

A reviewed gap is not supported behavior. This test detects drift, not feature completeness.
"""
import json,re
from pathlib import Path
from typer.main import get_command
from lamb_cli.main import app

def test_complete_cli_surface_matches_reviewed_parity_inventory():
    repo=Path(__file__).resolve().parents[3]
    manifest=json.loads((repo/'backend/tests/fixtures/cli_liteshell_parity.json').read_text())
    rows={}
    def walk(command,path=()):
        if hasattr(command,'commands'):
            for name,sub in command.commands.items():walk(sub,path+(name,))
        else:
            rows['.'.join(path)]={'params':[{'name':p.name,'kind':type(p).__name__,'opts':p.opts,'secondary_opts':getattr(p,'secondary_opts',[]),'required':p.required,'default':str(p.default),'type':re.sub(r' at 0x[0-9a-f]+', '', str(p.type)),'nargs':p.nargs,'is_flag':getattr(p,'is_flag',False)} for p in command.params]}
    walk(get_command(app))
    assert rows==manifest['cli'], 'CLI changed: review AAC parity and update the classified inventory, not just the count'
    assert set(rows)==set(manifest['dispositions'])
