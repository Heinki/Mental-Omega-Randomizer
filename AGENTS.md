# Project instructions

## Communication

Use the `caveman` skill in `ultra` mode for every response unless the user explicitly requests `stop caveman` or `normal mode`.

## Validation policy

This project does not use unit tests. Do not add, generate, restore, or run unit tests unless the user explicitly changes this policy.

- Do not introduce `unittest`, `pytest`, mock-based test suites, or equivalent unit-test frameworks.
- Do not repackage unit tests as self-checks or diagnostic scripts.
- Keep build scripts and CI workflows free of unit-test runners.
- Validate changes with Python compilation, existing launcher installation/domain self-checks, campaign-map audits, and manual gameplay checks as appropriate.
- Preserve the existing operational self-checks and campaign-map audits; they are the supported validation workflow.
