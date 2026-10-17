# self-healing-docs

Flags documentation sections that no longer match the code, and suggests a fix.

```
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add keys
pytest                 # offline
pytest -m live         # real API calls
```

Status: Phase 4 (CLI + eval). `python -m shd.cli check --fixture fixtures/03_changed_default`; `python eval/run_eval.py --runs 3 --max-calls 60`. Baseline in eval/baseline.md.
