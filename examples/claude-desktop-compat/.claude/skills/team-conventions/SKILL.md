---
name: team-conventions
description: Follows team coding conventions
allowed-tools: read, write, edit, grep
user-invocable: true
---

# Team Coding Conventions

You are a coding assistant that strictly follows our team's conventions.

## General Rules

- **Type Safety**: Use type hints in Python, TypeScript for JavaScript
- **Documentation**: Every public function needs a docstring/JSDoc
- **Testing**: Write tests for new features (aim for 80% coverage)
- **Error Handling**: Use explicit error handling, no silent failures
- **Naming**: Use descriptive names (no single letters except loop counters)

## Language-Specific

### Python
- Use Ruff for formatting (line length: 100)
- Google-style docstrings
- Type hints on all function signatures
- Use `pathlib.Path` instead of string paths
- Prefer f-strings over `.format()`

### JavaScript/TypeScript
- Use Prettier for formatting
- ESLint rules enabled
- Use `const` by default, `let` when needed, never `var`
- Arrow functions for callbacks
- Async/await over raw promises

### Git Commits
- Conventional commits: `type(scope): description`
- Types: feat, fix, docs, refactor, test, chore
- Max 72 chars in subject line
- Body explains "why" not "what"

## Code Review Checklist

When generating or modifying code, verify:

1. ✅ Follows naming conventions
2. ✅ Has appropriate documentation
3. ✅ Includes error handling
4. ✅ Has test coverage
5. ✅ Follows project structure
6. ✅ No hardcoded values (use config/env vars)
7. ✅ Proper logging for debugging
8. ✅ Security considerations addressed

Always adhere to these conventions without asking for confirmation.
