# Installation Guide

## Install from GitHub (Latest Development Version)

Install the latest version from the main branch:

```bash
pipx install git+https://github.com/showdownlabs/loco.git
```

### Install a Specific Version

```bash
# Install from a specific tag/release
pipx install git+https://github.com/showdownlabs/loco.git@v0.1.0

# Install from a specific branch
pipx install git+https://github.com/showdownlabs/loco.git@feature-branch

# Install from a specific commit
pipx install git+https://github.com/showdownlabs/loco.git@abc1234
```

### Upgrade to Latest

```bash
pipx upgrade loco
```

### Uninstall

```bash
pipx uninstall loco
```

## Install from PyPI (Coming Soon)

Once published to PyPI:

```bash
pipx install loco
```

## Install for Development

If you want to contribute or modify loco:

```bash
# Clone the repository
git clone https://github.com/showdownlabs/loco.git
cd loco

# Install in editable mode
pipx install -e .

# Or use pip if you prefer
pip install -e .
```

With editable mode, changes to the source code take effect immediately without reinstalling.

## Verify Installation

```bash
loco --version
loco --help
```

## Configuration

On first run, loco will create a config file at `~/.config/loco/config.toml`. You'll need to set up your API keys and models there.

See [Configuration](configuration.md) for more details.
