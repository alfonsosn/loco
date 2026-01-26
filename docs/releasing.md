# Release Process

## Creating a New Release

### 1. Update Version Number

Update the version in two places:

**pyproject.toml:**
```toml
[project]
version = "0.2.0"  # Update this
```

**src/loco/__init__.py:**
```python
__version__ = "0.2.0"  # Update this
```

### 2. Update CHANGELOG.md

Add a new section for the release:

```markdown
## [0.2.0] - 2024-01-XX

### Added
- Feature 1
- Feature 2

### Fixed
- Bug fix 1

### Changed
- Breaking change 1
```

### 3. Commit Changes

```bash
git add pyproject.toml src/loco/__init__.py CHANGELOG.md
git commit -m "chore: bump version to 0.2.0"
git push
```

### 4. Create and Push Git Tag

```bash
# Create annotated tag
git tag -a v0.2.0 -m "Release v0.2.0"

# Push tag to GitHub
git push origin v0.2.0
```

### 5. GitHub Actions Will Automatically:

- Build the package
- Create a GitHub Release with the built wheels
- Generate release notes from commits

### 6. Users Can Install

```bash
# Install the new version
pipx install git+https://github.com/showdownlabs/loco.git@v0.2.0

# Or upgrade existing installation
pipx upgrade loco
```

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.2.0): New features, backward compatible
- **PATCH** (0.1.1): Bug fixes, backward compatible

### When to Bump

- **Patch (0.1.x)**: Bug fixes, documentation, small improvements
- **Minor (0.x.0)**: New features, new commands, new tools
- **Major (x.0.0)**: Breaking API changes, major refactors

## Publishing to PyPI (Future)

Once ready for wider distribution:

1. Create a PyPI account
2. Generate API token
3. Add token to GitHub Secrets as `PYPI_API_TOKEN`
4. Uncomment the PyPI publish step in `.github/workflows/release.yml`
5. Push a new tag

Users will then be able to:
```bash
pipx install loco
```

## Hotfix Process

For urgent bug fixes:

1. Create a hotfix branch from the tag
2. Fix the bug
3. Bump patch version
4. Create new tag
5. Cherry-pick to main if needed

```bash
git checkout -b hotfix/0.1.1 v0.1.0
# make fixes
git commit -m "fix: critical bug"
# bump version to 0.1.1
git tag -a v0.1.1 -m "Hotfix v0.1.1"
git push origin v0.1.1
git checkout main
git cherry-pick <commit-hash>
```
