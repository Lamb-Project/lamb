"""Per-user integrations (Moodle, future: Canvas, etc.) for the AAC liteshell.

Integrations hold credentials for external systems on behalf of individual
LAMB users. Credentials are encrypted at rest and only exist in plaintext
inside the Python process during subprocess env injection.

Not exposed to the assistants runtime — AAC agent tooling only.
"""
