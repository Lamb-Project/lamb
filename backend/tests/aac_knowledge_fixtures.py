"""Deterministic dependencies for request lifecycle tests; no provider/network calls."""
from contextlib import contextmanager
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

CAPABILITIES={'rag_processors':[{'id':'no_rag','description':'No external context'}],
              'prompt_processors':[], 'connectors':[], 'ingestion_plugins':{'status':'available','items':[]}, 'lti':{'available':True}}
CONFIG={'setups':{'default':{'providers':{'ollama':{'enabled':True,'models':['fixture'],'base_url':'http://fixture'}},
                           'global_default_model':{'provider':'ollama','model':'fixture'}}}}

@contextmanager
def knowledge_dependencies():
    resolver=N(organization={'id':1,'config':CONFIG},get_global_default_model_config=lambda:{'provider':'ollama','model':'fixture'})
    with patch('lamb.aac.brief.capability_map', AsyncMock(return_value=CAPABILITIES)), patch('lamb.aac.router.OrganizationConfigResolver',return_value=resolver):
        yield
