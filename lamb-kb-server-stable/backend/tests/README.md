# Lamb KB Server Tests

This directory contains tests and tools for the lamb-kb-server.

## Structure

```
tests/
├── e2e/              # End-to-end API tests (pytest)
│   ├── conftest.py   # Pytest fixtures and client
│   ├── test_*.py     # Test modules
│   └── README.md     # E2E test documentation
├── tools/            # Maintenance/debug utilities
│   ├── README.md     # Tool documentation
│   └── *.py          # Utility scripts
├── pytest.ini        # Pytest configuration
└── README.md         # This file
```

## Running E2E Tests

```bash
cd /path/to/lamb-kb-server-stable/backend/tests
pytest            # Run all tests
pytest -v         # Verbose output
pytest -k "query" # Run tests matching pattern
```

## Requirements

- KB Server running on `http://localhost:9090`
- Ollama running with `OLLAMA_HOST=0.0.0.0`
- Python packages: `pytest`, `requests`
