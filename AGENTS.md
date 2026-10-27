# Project instructions

## Communication

Use the `caveman` skill in `ultra` mode for every response unless the user explicitly requests `stop caveman` or `normal mode`.

## Validation policy

This project does not use unit tests. Do not add, generate, restore, or run unit tests unless the user explicitly changes this policy.

- Do not introduce `unittest`, `pytest`, mock-based test suites, or equivalent unit-test frameworks.
- Do not repackage unit tests as self-checks or diagnostic scripts.
- Keep build scripts and CI workflows free of unit-test runners.
- Validate changes with Python compilation, builds, operational installation/configuration/catalogue reports, audits of actual installed campaign maps, and manual gameplay checks as appropriate.
- Preserve runtime input validation, game-data integrity checks, operational installation reports, and audits of actual installed campaign maps. Synthetic domain scenarios and fake-repository harnesses are tests and must not be restored as self-checks.
