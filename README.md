# self-healing-docs

Flags documentation sections that no longer match the code, and suggests a fix.

```
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add keys
pytest                 # offline
pytest -m live         # real API calls
```

Status: Phase 1 (chunkers + fixtures). See CLAUDE.md for conventions.
