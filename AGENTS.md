# Agentic Data Pipeline - AI Agent Instructions

## Project Overview
This repository contains a timeseries data ingestion and cleaning pipeline designed for use by other projects. The project is explicitly developed using agentic AI to accelerate development and maintain code quality.

### Core Purpose
- **Ingest** timeseries data from various sources
- **Clean** and normalize data for downstream consumption
- **Reusable**: Used as a dependency by other projects in the ML_Monitor ecosystem

### Architecture Philosophy
This is an agentic-first project - use automated refactoring, testing, and documentation generation wherever applicable. The pipeline should be modular, well-tested, and maintainable.

## Development Conventions

### Project Structure (Expected)
When building out the pipeline, follow this structure:
```
agentic-data-pipeline/
├── src/
│   ├── pipeline/          # Core pipeline orchestration
│   ├── ingestion/         # Data source connectors
│   ├── cleaning/          # Data cleaning and normalization
│   └── utils/             # Shared utilities
├── tests/                 # Unit and integration tests
├── docs/                  # Project documentation
├── config/                # Configuration files
├── requirements.txt       # Python dependencies
└── setup.py              # Package setup
```

### Tech Stack Expectations
- **Language**: Python (likely; confirm if changed)
- **Data Format**: Timeseries data (likely pandas/polars-based)
- **Testing**: pytest (standard for Python projects)
- **Documentation**: Markdown in `docs/` directory
- **Environment Management**: `uv` for fast dependency management and virtual environments
- **Config**: Use `.env` for local secrets/config (see `.gitignore`)

## Common Development Tasks

### 1. Adding a New Data Source Ingestion
When adding a new ingestion connector:
- Create a new module in `src/ingestion/`
- Implement interface consistent with existing ingestion modules
- Include comprehensive docstrings with examples
- Add unit tests with sample data
- Update documentation with usage example

### 2. Adding a Data Cleaning Operation
- Create cleaning module in `src/cleaning/`
- Write with pandas/polars operations (if applicable)
- Include inline comments explaining transformations
- Add integration tests with realistic timeseries patterns
- Document expected input/output schema

### 3. Testing & Quality
- Run tests before committing: `pytest tests/`
- Aim for at least 85% line coverage and 85% branch coverage on future commits,
  measured separately across the package by the non-integration unit suite.
- Add meaningful tests for new or changed behavior, including branch outcomes.
  These are development targets while the baseline is below them, not CI gates.
  See README.md for coverage reports and interpretation.
- Use meaningful test names describing what is tested
- Mock external data sources in unit tests
- Use fixtures for common test data patterns

### 4. Configuration Management
- Use `.env` files for local development (not committed)
- Store defaults in code or `config/` directory
- Document all configuration options in README or docs
- Use type hints for config objects

## Guidelines for AI Agents

### When Implementing Features
1. **Create focused modules**: Keep modules single-responsibility
2. **Type hints**: Add type annotations for all function signatures
3. **Docstrings**: Include module, class, and function docstrings with examples
4. **Error handling**: Raise informative exceptions with context
5. **Logging**: Use Python logging module for debugging info

### When Writing Tests
1. Use descriptive test function names (`test_<feature>_<scenario>`)
2. Arrange-Act-Assert pattern for test structure
3. Test both happy paths and error conditions
4. Mock external dependencies
5. Use pytest fixtures for setup

### When Creating Documentation
1. Link to existing docs rather than duplicating
2. Include code examples for complex features
3. Document configuration options upfront
4. Explain design decisions for non-obvious choices
5. Keep README updated with current project status

### Agentic Best Practices
- Use automated refactoring tools to maintain consistency
- Generate type stubs if exposing library APIs
- Suggest test generation for improved coverage
- Recommend documentation generation from docstrings
- Apply workspace-wide cleanup (unused imports, formatting) regularly

## Key Files & References
- [README.md](README.md) - Project overview and quick start
- [LICENSE](LICENSE) - Project licensing

## Environment Setup
```bash
# Install uv if not already installed
# curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run tests
uv run pytest tests/

# Run pipeline
uv run python -m src.pipeline
```

## Before Starting Work
- Ensure `uv` is installed (see Environment Setup section)
- Run `uv sync` to set up the virtual environment and dependencies
- Review existing tests to understand patterns
- Check for existing issues or TODOs in comments
- Read relevant docs in `docs/` if available
- Confirm dependencies and versions in `pyproject.toml` align with project goals

## When Stuck
1. Check if similar functionality exists elsewhere in codebase
2. Look for TODO/FIXME comments pointing to known issues
3. Review test patterns to understand expected behavior
4. Consult project documentation for design decisions
5. Default to clarity and explicitness over clever code

## Future Enhancement Areas
- [To be populated as development progresses]
- Consider adding ML model integration if needed
- Performance optimization for large-scale ingestion
- Multi-source coordination and merging


## Learned Development Practices

These practices reflect lessons from hardening the current repository and take precedence over older generic guidance above where they conflict.

### Repository Reality
- The installable package lives under `src/agentic_data_pipeline/`; do not invent or assume a different package layout.
- Dependencies and tool configuration are managed in `pyproject.toml` with `uv`.
- Prefer the existing storage, ingestion, dashboard, and test abstractions over introducing parallel implementations.
- Treat the package as a reusable library: preserve public contracts and backwards compatibility deliberately.

### Local Verification Before Push
Do not use GitHub Actions as the primary edit/test loop. Before pushing a code change, run the same inexpensive checks locally and fix failures first:

```bash
uv sync --dev
uv run ruff check --fix src tests
uv run ruff format src tests
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright
uv run pytest
```

Where a test requires credentials or a true external integration, run the local/unit suite first and leave only the environment-specific integration verification to CI.

Batch related, locally verified edits into sensible commits. Avoid pushing a sequence of speculative fixes that each triggers a full CI run.

### Pre-commit and Automatic Fixes
- Install the repository hooks once with `uv run pre-commit install`.
- Ruff safe fixes and Ruff formatting are appropriate pre-commit automation.
- Keep the Ruff pre-commit revision aligned with the Ruff version used by the project/CI.
- Do not enable `--unsafe-fixes` automatically. Changes that may alter semantics require review.
- Do not treat Pyright findings as mechanically auto-fixable. Resolve them by understanding and narrowing the actual runtime types.
- CI should verify committed code rather than modify or auto-commit it.

### Quality Gates
The intended order is:

1. Ruff lint.
2. Ruff format check.
3. Pyright.
4. pytest/unit tests.
5. Credentialed integration tests where applicable.

Keep these checks enabled. Fix code and tests rather than weakening rules, adding broad suppressions, or excluding troublesome files merely to make CI green. A green pipeline is only meaningful if the checks remain substantive.

### Type Checking
- Prefer explicit type narrowing at pandas, NumPy, statsmodels, and external-library boundaries.
- Use public APIs rather than implementation details where possible.
- Add maintained type stubs when they improve checking (for example, pandas stubs) rather than suppressing broad classes of errors.
- A targeted `cast` is acceptable when a third-party library has an imprecise overloaded return type and the runtime contract is known; keep it local and document non-obvious cases.
- Storage unions should only include backends that actually implement every method used by the function.
- Type-checking changes must still pass runtime tests; a change made solely to satisfy Pyright can introduce real regressions.

### Dependency Management
- Avoid unconstrained major-version upgrades for core runtime/checking dependencies when a new major release could silently change APIs or typing behavior.
- Pin development checker versions where reproducible CI/pre-commit behavior matters.
- Keep local, pre-commit, and CI checker versions consistent.

### Data and Storage Semantics
- Canonical market data uses a timezone-aware datetime index and explicit metadata such as symbol and interval.
- Persisted market observations distinguish `event_timestamp` (when the market event occurred) from `available_timestamp` (when that observation became available to the pipeline).
- Preserve the original `available_timestamp` of unchanged historical observations during incremental updates. Only new/revised observations should receive a new availability time.
- When persistence intentionally adds metadata columns, update tests to verify that contract rather than deleting useful provenance merely to preserve an outdated equality assertion.
- Be careful with pandas `attrs`: concatenation/transformation can lose metadata, so preserve and restore it deliberately where required.
- Prefer staged/atomic persistence for file-backed datasets so interrupted writes do not replace valid data with partial output.

### Tests and Regression Handling
- A static-analysis fix is not complete until unit tests also pass.
- When a checker-driven refactor causes a runtime failure, fix the runtime regression rather than changing the test unless the intended public contract genuinely changed.
- When the contract intentionally changes, update tests to assert both the existing canonical data and the new behavior/provenance.
- External providers should be mocked in unit tests; keep credentialed/live-provider behavior in explicit integration tests.
- Continue working toward at least 85% line and branch coverage without adding low-value tests purely to inflate the number.

### CI Iteration Discipline
When CI fails after local verification:
1. Inspect the exact failed job and step.
2. Read the failure log rather than guessing.
3. Fix all related failures that can be understood from that run.
4. Re-run the complete local quality sequence.
5. Push one coherent fix.
6. Confirm the newest commit's workflow, not an older queued/intermediate run.

Do not claim the pipeline is green until the workflow for the current branch head has completed successfully.

### Branch Discipline
- Do experimental production-hardening work on a dedicated branch such as `production-checks`.
- Keep `main` stable where practical.
- Merge hardened changes back through a reviewed pull request once the branch passes its complete CI pipeline.
- Avoid force-pushing protected branches as part of ordinary development.
