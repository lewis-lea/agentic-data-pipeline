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
- Keep test coverage above 80% for critical paths
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
