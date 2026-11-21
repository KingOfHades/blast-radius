# Blast Radius entry

Selects, for each sqlglot patch, only the tests that can execute the changed code.

## How it works
- `map.json` is built once from the pinned sqlglot commit (`eb11aec`) by running its whole test suite with
  per-test line coverage (`tools/covplugin.py`, `tools/build_map.py`). It records, per source line, which tests execute it,
  plus per-function ranges, which tests use which dialect classes, which fixtures each test opens, and an import map.
  It contains no patch-to-test table: it only describes the pinned commit.
- `src.zip` holds the pinned commit's `sqlglot/` sources so the selector can read the old file at run time (no network).
- `selector.py` parses each patch, finds the old-file lines/functions it touches and unions the tests covering them.
  Comment-only edits select nothing. Changes it cannot reason about (syntax errors, import-time edits in core modules,
  config files, deleted/renamed files) fall back to running every test, so they can never be missed.
- Tests are packed onto at most 8 workers, choosing the worker count that minimises `max load + 2 s * workers`.

Rebuild the map: clone sqlglot at the pinned commit, `pip install -r requirements.lock coverage`, run
`SKIP_INTEGRATION=0 pytest tests -p covplugin -n 2` with `tools/` on `PYTHONPATH`, then `python tools/build_map.py`.
