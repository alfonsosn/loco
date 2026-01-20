# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Claude Desktop Compatibility**: Support for `.claude/` directories alongside `.loco/`
  - Skills can now be placed in `.claude/skills/` or `.loco/skills/`
  - Agents can now be placed in `.claude/agents/` or `.loco/agents/`
  - Precedence order: global config → `.claude/` → `.loco/` (highest)
  - Enables seamless sharing of configurations between Loco and Claude Desktop
  - See `examples/claude-desktop-compat/` for usage examples

### Changed
- Updated documentation to reflect `.claude/` directory support
- Enhanced discovery logic to check both `.claude/` and `.loco/` directories

## [Previous Releases]

See commit history for changes prior to this changelog.
