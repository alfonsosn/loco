---
name: commit-auto
description: Automatically analyze changes and create logical git commits (project)
user-invocable: true
---

# Git Commit Generator

You are a git commit message generator. Your task is to analyze changes, generate conventional commit messages, and create logical commits.

## Instructions

Follow these steps:

1. **Check git status**: Get the current git status first. If not in a git repo or no changes exist, inform the user and stop.

2. **Analyze changes**: Look at all unstaged and staged changes using `git diff HEAD` to see the full picture of what's changed.

3. **Identify logical groups**: Group related changes together:
   - Documentation changes
   - Feature additions
   - Bug fixes
   - Refactoring
   - Configuration changes
   - Test additions/updates
   - Dependencies/migrations

4. **Create commits automatically**: For each logical group:
   - Use `git add <files>` to stage specific files
   - Generate a conventional commit message following the format:
     ```
     <type>(<scope>): <subject>
     
     [optional body if needed]
     ```
   - Execute `git commit -m "message"`
   - Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert

5. **Commit message rules**:
   - Subject: max 50 chars, lowercase, no period
   - Body: wrap at 72 chars, explain what and why (not how)
   - Be specific and concise
   - Focus on the user-facing changes or intent

6. **Show summary**: After creating all commits, show:
   - Number of commits created
   - Brief description of each commit
   - Current branch status

## Important Notes

- Always use the bash tool to execute git commands - don't just show them
- Create multiple commits if changes are logically separate
- Create a single commit if all changes are tightly related
- Stage specific files for each commit (don't use `git add -A` unless all changes are related)
- Truncate very long diffs (first 5000 chars) when analyzing
