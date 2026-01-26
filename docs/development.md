# Development Guide

## Setting Up Development Environment

### Prerequisites

- Python 3.11 or higher
- Git
- pipx (recommended) or pip

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/alfonsosn/loco.git
cd loco

# Install in editable mode (changes take effect immediately)
pipx install -e .

# Or with pip
pip install -e .
```

With editable mode (`-e`), any changes you make to the source code are immediately available when you run `loco` - no reinstalling needed!

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

This installs additional tools like pytest for testing.

## Making Changes

### 1. Create a Feature Branch

```bash
git checkout -b feat/your-feature-name
```

### 2. Make Your Changes

Edit files in `src/loco/` as needed.

### 3. Test Your Changes

```bash
# Run loco (your changes are live with editable install)
loco

# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_something.py -v
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: description of your feature"
```

We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks
- `ci:` - CI/CD changes

## Pulling Latest Changes

### If Working on a Branch

```bash
# Pull latest from your branch
git pull origin feat/your-feature-name

# Changes are immediately available (with editable install)
loco
```

### After PR is Merged

```bash
# Switch to main and pull
git checkout main
git pull origin main

# Changes are immediately available (with editable install)
loco
```

### Reinstalling (If Not Using Editable Mode)

If you installed without `-e`, you'll need to reinstall after pulling:

```bash
git pull origin main
pipx reinstall loco --force
```

## Testing Installation from GitHub

To test how users will install your changes:

```bash
# Uninstall local version
pipx uninstall loco

# Install from your branch
pipx install git+https://github.com/alfonsosn/loco.git@feat/your-feature-name

# Test it works
loco --version
loco --help
```

## Creating a Pull Request

### 1. Push Your Branch

```bash
git push origin feat/your-feature-name
```

### 2. Create PR

```bash
# Using GitHub CLI
gh pr create --title "feat: your feature title" --body "Description of changes"

# Or visit GitHub and create PR through web interface
```

### 3. CI Will Run Automatically

- GitHub Actions will run tests
- Build the package
- Check for issues

### 4. Address Review Comments

```bash
# Make changes
git add .
git commit -m "fix: address review comments"
git push origin feat/your-feature-name
```

PR will automatically update and CI will re-run.

## Project Structure

```
loco/
├── src/loco/           # Main source code
│   ├── __init__.py     # Package version
│   ├── cli.py          # CLI entry point and main loop
│   ├── chat.py         # Conversation and LLM interaction
│   ├── config.py       # Configuration management
│   ├── tools.py        # Built-in tools (read, write, bash, etc.)
│   ├── commands.py     # Custom command system
│   ├── agents.py       # Agent/subagent system
│   ├── ui/             # User interface components
│   └── mcp/            # Model Context Protocol
├── tests/              # Test files
├── docs/               # Documentation
├── .loco/              # Local commands (for loco itself)
├── .github/            # GitHub Actions workflows
└── pyproject.toml      # Project configuration
```

## Common Development Tasks

### Adding a New Tool

1. Add tool class to `src/loco/tools.py`
2. Register it in tool_registry
3. Update documentation
4. Add tests in `tests/`

### Adding a New Slash Command

1. Add command logic to `handle_slash_command()` in `src/loco/cli.py`
2. Update `/help` text
3. Document in `docs/`

### Adding a Custom Command

1. Create directory: `.loco/commands/mycommand/`
2. Add `COMMAND.md` with instructions
3. Command is auto-discovered on startup

### Debugging

```bash
# Run with Python directly for debugging
python -m loco.cli

# Add print statements or use debugger
python -m pdb -m loco.cli
```

## Code Style

- Follow PEP 8
- Use type hints where possible
- Keep functions focused and small
- Write docstrings for public APIs
- Use meaningful variable names

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage

```bash
pip install pytest-cov
pytest tests/ --cov=src/loco --cov-report=html
open htmlcov/index.html
```

### Write Tests

Add test files to `tests/` directory:

```python
# tests/test_feature.py
def test_my_feature():
    # Arrange
    input_data = "test"
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result == expected_output
```

## Building Package Locally

```bash
# Install build tools
pip install build

# Build package
python -m build

# Check dist/ directory
ls dist/
# Should see .whl and .tar.gz files

# Install built package
pip install dist/loco-0.1.0-py3-none-any.whl
```

## Troubleshooting

### Command Not Found After Install

```bash
# Ensure pipx bin directory is in PATH
pipx ensurepath

# Or reinstall
pipx reinstall loco
```

### Changes Not Taking Effect

```bash
# Make sure you installed in editable mode
pipx install -e . --force

# Or reinstall
pipx reinstall loco --force
```

### Import Errors

```bash
# Make sure you're in the project root
cd /path/to/loco

# Reinstall
pipx install -e . --force
```

## Getting Help

- Check existing issues: https://github.com/alfonsosn/loco/issues
- Create new issue: https://github.com/alfonsosn/loco/issues/new
- Read documentation: `docs/`

## Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Python Packaging Guide](https://packaging.python.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [LiteLLM Documentation](https://docs.litellm.ai/)
