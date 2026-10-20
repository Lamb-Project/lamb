"""Production wiring: LAMB's database, organization settings, proxy clients and the usage ledger.
Shared by the web routes (lti.py) and the worker."""
import os

from .ledger import UsageLedger
from .proxy_client import ProxyClient
from .service import TokenDealerService
from .settings import from_org_config
from .store import TokenDealerStore

_db = None


def db():
    global _db
    if _db is None:
        from lamb.database_manager import LambDatabaseManager
        _db = LambDatabaseManager()
    return _db


def settings_for(org_id):
    org = db().get_organization_by_id(org_id) or {}
    return from_org_config(org.get('config') or {})


def client_for(org_id):
    s = settings_for(org_id)
    return ProxyClient(s.proxy_url, s.proxy_admin_key)


def store():
    return TokenDealerStore(db())


def service():
    return TokenDealerService(store(), settings_for, client_for)


def ledger_path():
    import config
    return os.environ.get('TOKEN_DEALER_LEDGER_PATH') or os.path.join(config.LAMB_DB_PATH, 'token_dealer_usage.db')


def ledger():
    return UsageLedger(ledger_path())
