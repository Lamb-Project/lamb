#!/usr/bin/env python3
"""Let existing collections follow the global embeddings key after a rotation (#195).

Collections created before #195 stored the global key they were created with. This
clears that stored key (so the collection uses the current global key at query time),
but only where it equals the old global key you supply; explicit per-collection keys
are left alone. Dry run by default.

    OLD_EMBEDDINGS_APIKEY=sk-old... python reset_embedding_keys.py           # report
    OLD_EMBEDDINGS_APIKEY=sk-old... python reset_embedding_keys.py --apply   # write
"""
import argparse
import json
import os
import sys

from database.connection import SessionLocal
from database.models import Collection


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='write the change (default: report only)')
    args = parser.parse_args(argv)
    old = os.environ.get('OLD_EMBEDDINGS_APIKEY', '')
    if not old:
        sys.exit('Set OLD_EMBEDDINGS_APIKEY to the key being retired.')
    db = SessionLocal()
    try:
        matched = 0
        for collection in db.query(Collection).all():
            config = collection.embeddings_model
            config = json.loads(config) if isinstance(config, str) else dict(config or {})
            if config.get('apikey') != old:
                continue
            matched += 1
            print(f'collection {collection.id} ({collection.name}): stored key equals the retired key')
            if args.apply:
                config['apikey'] = ''
                collection.embeddings_model = json.dumps(config) if isinstance(collection.embeddings_model, str) else config
        if args.apply:
            db.commit()
        print(f"{matched} collection(s) {'updated' if args.apply else 'would be updated (dry run)'}")
    finally:
        db.close()


if __name__ == '__main__':
    main()
