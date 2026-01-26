# GitHub Installation & Release Summary

## ✅ Current Setup

Your loco project is now set up for easy installation and versioning from GitHub!

### For Users: Installing from GitHub

**Install latest from main:**
```bash
pipx install git+https://github.com/showdownlabs/loco.git
```

**Install specific version:**
```bash
pipx install git+https://github.com/showdownlabs/loco.git@v0.1.0
```

**Upgrade existing installation:**
```bash
pipx upgrade loco
```

### For Maintainers: Creating Releases

When you merge a PR to main and want to release:

1. **Update version numbers:**
   - `pyproject.toml` → `version = "0.2.0"`
   - `src/loco/__init__.py` → `__version__ = "0.2.0"`

2. **Commit and push:**
   ```bash
   git commit -m "chore: bump version to 0.2.0"
   git push
   ```

3. **Create and push tag:**
   ```bash
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin v0.2.0
   ```

4. **GitHub Actions automatically:**
   - Builds the package
   - Creates GitHub Release
   - Attaches built wheels/sdist
   - Generates release notes

### Workflow Files Created

- `.github/workflows/release.yml` - Triggers on version tags (v*)
- `docs/installation.md` - User installation guide  
- `docs/releasing.md` - Maintainer release process

### Version Strategy

Following Semantic Versioning:
- **0.1.x** - Patch: Bug fixes
- **0.x.0** - Minor: New features
- **x.0.0** - Major: Breaking changes

### Next Steps (Optional)

**Publish to PyPI** for easier installation:
1. Create PyPI account
2. Add `PYPI_API_TOKEN` to GitHub Secrets
3. Uncomment PyPI section in `release.yml`
4. Users can then: `pipx install loco`

## Testing

You can test building locally:
```bash
pip install build
python -m build
ls dist/  # Should see .whl and .tar.gz files
```

## Documentation

- Installation: `docs/installation.md`
- Release Process: `docs/releasing.md`
- Updated: `README.md` with pipx install instructions
