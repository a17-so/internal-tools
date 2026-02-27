# Agent Rules: Outreach Tool Automation

Use this file as the project-local implementation guide for AI coding agents.

## Mission

Build a reliable local automation system from `outreach-automation-plan.md` with production-grade safety and maintainability.

## Non-Negotiables

1. No secrets in source control.
2. Strong typing for all new Python modules.
3. Small modules with single responsibility.
4. Explicit error handling with actionable logs.
5. Deterministic tests for core business logic.

## Code Quality Bar

- Follow `black`, `ruff`, and `mypy` rules in `pyproject.toml`.
- Keep functions focused; extract helpers instead of long procedural blocks.
- Prefer dataclasses/typed models over untyped dictionaries.
- Use retries only for transient errors, never for validation errors.

## Project Conventions

- Source package: `src/outreach_automation/`
- Tests mirror source paths in `tests/`
- All external integrations are behind client interfaces/adapters.
- Place platform selectors in one module so UI changes are isolated.

## Security

- Never log credentials, OAuth tokens, cookies, or raw session blobs.
- Redact PII in error logs where possible.
- Keep `.env` local only; update `.env.example` when adding variables.

## Delivery Workflow

1. Add or update tests.
2. Implement code.
3. Run `make check` and `make test`.
4. Update `README.md` for any behavior/config changes.
